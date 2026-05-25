"""
qa/hyde.py — HyDE (Hypothetical Document Embeddings)

원 쿼리를 LLM에 넣어 "영상 내용을 모르는 상태에서 상상한 가상 답변"을 생성한다.
이 가상 답변을 임베딩해서 vector 검색에 사용하면, 원 쿼리와 정답 청크 간
어휘 격차가 줄어 recall이 개선된다.

최종 답변 생성에는 여전히 실제 청크만 쓰이므로 답안 유출 없음.
BM25는 원 쿼리를 그대로 써야 희귀 토큰 매칭이 살아남는다 (HyDE가 희석함).
"""

import time
from typing import List, Optional

import requests
from langsmith import traceable

from ..config import QACfg, RetrievalCfg, get_stage_config
from ..prompts import get_hyde_prompt


@traceable(name="qa.0_hyde", run_type="llm")
def generate_hypothetical_answer(
    query: str,
    speakers: Optional[List[str]] = None,
    retrieval_cfg: Optional[RetrievalCfg] = None,
    qa_cfg: Optional[QACfg] = None,
) -> str:
    """쿼리에 대한 가상 답변을 생성한다. LLM 실패 시 원 쿼리를 반환 (fallback).

    speakers는 화자 인지 템플릿(v2-speaker 등)에 메타데이터로 주입된다.
    템플릿이 speakers를 쓰지 않으면 무시된다.
    """
    stage = get_stage_config()
    retrieval_cfg = retrieval_cfg or stage.retrieval
    qa_cfg = qa_cfg or stage.qa

    prompt = get_hyde_prompt(
        query, speakers=speakers, version=retrieval_cfg.hyde_prompt_version
    )
    messages = [{"role": "user", "content": prompt}]
    print(f"[hyde] query={query!r} prompt_version={retrieval_cfg.hyde_prompt_version}")

    try:
        answer = _call_chat(messages, qa_cfg)
    except Exception as e:
        print(f"[hyde] 호출 실패 — 원 쿼리 fallback. error={e}")
        return query

    answer = (answer or "").strip()
    if not answer:
        print("[hyde] 빈 응답 — 원 쿼리 fallback")
        return query

    print(f"[hyde] hypothetical={answer!r}")
    return answer


def _call_chat(messages, cfg: QACfg) -> str:
    """QACfg 기반 chat completion 최소 호출 헬퍼 (openai/ollama 분기)."""
    if cfg.provider == "openai":
        from openai import OpenAI, RateLimitError

        client = OpenAI(api_key=cfg.openai_api_key)
        for attempt in range(5):
            try:
                resp = client.chat.completions.create(
                    model=cfg.openai_chat_model,
                    messages=messages,
                )
                return resp.choices[0].message.content
            except RateLimitError:
                wait = min(2**attempt, 10)
                print(f"[hyde] rate limit, retry in {wait}s ({attempt + 1}/5)")
                time.sleep(wait)
        raise RuntimeError("OpenAI chat rate limit: 5회 재시도 후에도 실패")

    resp = requests.post(
        f"{cfg.ollama_base}/api/chat",
        json={
            "model": cfg.ollama_chat_model,
            "messages": messages,
            "stream": False,
        },
    )
    return resp.json()["message"]["content"]
