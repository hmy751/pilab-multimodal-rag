"""
qa/llm_rerank.py — LLM 기반 listwise rerank

Cohere cross-encoder가 해결 못하는 "영상 내부 alias" (쿼리의 고유명사가 청크엔
지시어로만 등장하는 경우)를 LLM의 문맥 추론으로 돌파한다.

listwise 방식: 후보 청크 전체를 한 번의 프롬프트에 담아 상위 N개 chunk_index를
JSON으로 받는다. pointwise 대비 호출 수가 1회로 고정돼 비용·latency 우위.

실패 경로:
- LLM 호출 실패 → 입력 순서 유지하며 top-K 반환 (fallback)
- JSON 파싱 실패 → 정규식으로 숫자 배열 추출 시도 → 그래도 실패면 fallback
"""

import json
import re
import time
from typing import Any, Dict, List, Optional

import requests
from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree

from ..config import QACfg, RetrievalCfg, get_stage_config
from ..prompts import get_llm_rerank_prompt


# 각 청크를 프롬프트에 넣을 때 텍스트 앞부분만 잘라 토큰 절약.
# 너무 짧으면 맥락 증발, 너무 길면 비용 증가. 200자가 경험적 균형점.
_CHUNK_TEXT_LIMIT = 200


def _format_candidates(segments: List[Dict[str, Any]]) -> str:
    """LLM 프롬프트에 넣을 후보 리스트 문자열을 만든다.

    speaker_id가 enrich돼 있으면 "(speaker=..., start=Xs)" 형태로 포함한다.
    v2-speaker 프롬프트가 이 형식을 전제로 질문-화자 매칭을 수행한다.
    """
    lines = []
    for seg in segments:
        idx = seg.get("chunk_index")
        start = seg.get("start_time", 0.0)
        text = (seg.get("text") or "").strip().replace("\n", " ")
        if len(text) > _CHUNK_TEXT_LIMIT:
            text = text[:_CHUNK_TEXT_LIMIT] + "…"
        speaker = seg.get("speaker_id")
        meta = (
            f"speaker={speaker}, start={start:.0f}s"
            if speaker
            else f"start={start:.0f}s"
        )
        lines.append(f"[{idx}] ({meta}) {text}")
    return "\n".join(lines)


def _parse_ranked_indices(raw: str) -> Optional[List[int]]:
    """LLM 출력에서 ranked_indices 숫자 배열을 추출한다. 실패 시 None."""
    if not raw:
        return None
    try:
        obj = json.loads(raw)
        arr = obj.get("ranked_indices")
        if isinstance(arr, list) and all(isinstance(x, int) for x in arr):
            return arr
    except Exception:
        pass

    m = re.search(r'"ranked_indices"\s*:\s*\[([^\]]*)\]', raw)
    if m:
        try:
            nums = [int(x.strip()) for x in m.group(1).split(",") if x.strip()]
            return nums or None
        except Exception:
            return None
    return None


@traceable(name="qa.3.1_llm_rerank", run_type="llm")
def llm_rerank_segments(
    query: str,
    segments: List[Dict[str, Any]],
    speakers: Optional[List[str]] = None,
    cfg: Optional[RetrievalCfg] = None,
    qa_cfg: Optional[QACfg] = None,
) -> List[Dict[str, Any]]:
    """segments를 listwise LLM rerank로 재정렬해 상위 rerank_top_k개를 반환.

    speakers는 화자 인지 템플릿(v2-speaker)에 메타데이터로 주입된다.
    템플릿이 speakers를 쓰지 않으면 무시된다.

    실패 시 입력 순서 그대로 top_k를 반환한다 (fallback).
    """
    stage = get_stage_config()
    cfg = cfg or stage.retrieval
    qa_cfg = qa_cfg or stage.qa
    top_k = cfg.rerank_top_k
    run = get_current_run_tree()

    if not segments:
        return segments

    candidates_text = _format_candidates(segments)
    prompt = get_llm_rerank_prompt(
        query=query,
        candidates=candidates_text,
        top_k=top_k,
        speakers=speakers,
        version=cfg.llm_rerank_prompt_version,
    )
    print(
        f"[llm_rerank] candidates={len(segments)} top_k={top_k} "
        f"prompt_version={cfg.llm_rerank_prompt_version}"
    )

    try:
        raw = _call_chat_json(prompt, qa_cfg)
    except Exception as e:
        print(f"[llm_rerank] 호출 실패, fallback 사용 — {e}")
        if run is not None:
            run.add_metadata({"skipped": "api_error", "error": str(e)})
        return _fallback(segments, top_k)

    print(f"[llm_rerank] raw response={raw!r}")
    ranked = _parse_ranked_indices(raw)
    if not ranked:
        print("[llm_rerank] 파싱 실패, fallback 사용")
        if run is not None:
            run.add_metadata({"skipped": "parse_error"})
        return _fallback(segments, top_k)

    # ranked_indices → segments 매핑
    by_idx = {s.get("chunk_index"): s for s in segments}
    reranked = []
    for rank, ci in enumerate(ranked[:top_k]):
        seg = by_idx.get(ci)
        if seg is None:
            continue
        out = seg.copy()
        # LLM은 절대 점수를 안 주므로 순위 역순 기반 점수를 기록 (디버깅/관측용)
        out["rerank_score"] = 1.0 - rank / max(top_k, 1)
        out["accepted"] = True
        reranked.append(out)

    if not reranked:
        print("[llm_rerank] 매핑 결과 비어있음, fallback 사용")
        if run is not None:
            run.add_metadata({"skipped": "empty_mapping"})
        return _fallback(segments, top_k)

    preview = [s.get("chunk_index") for s in reranked]
    print(f"[llm_rerank] 최종 {len(reranked)}개: {preview}")
    return reranked


def _fallback(segments: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
    """입력 순서 그대로 top_k를 반환하는 fallback (RRF 순서가 앞에 오도록 사전 정렬된 상태 가정)."""
    out = []
    for i, seg in enumerate(segments[:top_k]):
        s = seg.copy()
        s["accepted"] = True
        s["rerank_score"] = 1.0 - i / max(top_k, 1)
        out.append(s)
    return out


def _call_chat_json(prompt: str, cfg: QACfg) -> str:
    """QACfg 기반 chat 호출. OpenAI는 JSON mode 사용."""
    messages = [{"role": "user", "content": prompt}]

    if cfg.provider == "openai":
        from openai import OpenAI, RateLimitError

        client = OpenAI(api_key=cfg.openai_api_key)
        for attempt in range(5):
            try:
                resp = client.chat.completions.create(
                    model=cfg.openai_chat_model,
                    messages=messages,
                    response_format={"type": "json_object"},
                )
                return resp.choices[0].message.content or ""
            except RateLimitError:
                wait = min(2**attempt, 10)
                print(f"[llm_rerank] rate limit, retry in {wait}s ({attempt + 1}/5)")
                time.sleep(wait)
        raise RuntimeError("OpenAI chat rate limit: 5회 재시도 후에도 실패")

    resp = requests.post(
        f"{cfg.ollama_base}/api/chat",
        json={
            "model": cfg.ollama_chat_model,
            "messages": messages,
            "stream": False,
            "format": "json",
        },
    )
    return resp.json()["message"]["content"]
