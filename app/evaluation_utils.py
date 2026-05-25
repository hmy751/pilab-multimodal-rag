from typing import List, Dict, Any, Optional, Tuple
import requests
import re
from jiwer import wer, cer

from app.qa.chat import get_answer_by_chat_model
from app.qa.retrieval import retrieve_segments

from app.config import JudgeCfg, get_stage_config
from app.prompts import (
    get_eval_answer_relevance_prompt,
    get_eval_groundedness_prompt,
    get_eval_retrieval_precision_prompt,
    get_eval_visual_text_alignment_prompt,
)


def _llm_chat(prompt: str, cfg: JudgeCfg | None = None) -> str:
    """평가용 LLM 호출 헬퍼 — provider에 따라 분기."""
    cfg = cfg or get_stage_config().judge
    if cfg.provider == "openai":
        from openai import OpenAI

        client = OpenAI(api_key=cfg.openai_api_key)
        resp = client.chat.completions.create(
            model=cfg.openai_chat_model,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content.strip()
    else:
        resp = requests.post(
            f"{cfg.ollama_base}/api/chat",
            json={
                "model": cfg.ollama_chat_model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            },
        )
        return resp.json()["message"]["content"].strip()


# ────────────────────────────────────────
# WER + CER 계산
# ────────────────────────────────────────
def calculate_wer_cer(reference: str, hypothesis: str) -> Tuple[float, float]:
    """
    Word Error Rate(단어 오류율)과 Character Error Rate(문자 오류율)을 함께 계산합니다.

    WER = (S + D + I) / N  (단어 단위)
    CER = (S + D + I) / N  (문자 단위)

    한국어에서는 띄어쓰기·조사 차이로 WER이 과대평가되는 경향이 있어
    CER을 함께 보면 체감 품질에 더 가까운 판단이 가능합니다.

    Args:
        reference (str): 정답 전사 텍스트 (직접 받아쓰기)
        hypothesis (str): faster-whisper 또는 Whisper API 전사 결과

    Returns:
        Tuple[float, float]: (WER, CER) — 0.0 = 완벽, 1.0 = 전혀 다름
    """
    return wer(reference, hypothesis), cer(reference, hypothesis)


def calculate_answer_relevance(question: str, answer: str) -> float:
    prompt = get_eval_answer_relevance_prompt().format(question=question, answer=answer)
    raw = _llm_chat(prompt)
    match = re.search(r"\d+\.?\d*", raw)
    return float(match.group()) if match else 0.0


def calculate_groundedness(answer: str, context: str) -> float:
    prompt = get_eval_groundedness_prompt().format(context=context, answer=answer)
    raw = _llm_chat(prompt)
    match = re.search(r"\d+\.?\d*", raw)
    return float(match.group()) if match else 0.0


def calculate_retrieval_precision(
    retrieved_segments: List[Dict], question: str
) -> float:
    if not retrieved_segments:
        return 0.0

    relevant_count = 0
    for seg in retrieved_segments:
        prompt = get_eval_retrieval_precision_prompt().format(
            question=question, text=seg.get("text", "")
        )
        raw = _llm_chat(prompt)
        match = re.search(r"\d+\.?\d*", raw)
        score = float(match.group()) if match else 0.0

        relevant_count += 1 if score >= 0.5 else 0

    return relevant_count / len(retrieved_segments)


def run_full_evaluation(
    media_id: str,
    test_questions: List[str],
    reference_transcript: Optional[str] = None,
) -> Dict[str, Any]:
    import time

    from .embedding import embed_query
    from .supabase_utils import (
        get_media_segments,
        get_media_by_id,
    )

    relevance_scores: List[float] = []
    groundedness_scores: List[float] = []
    precision_scores: List[float] = []
    qa_results: List[Dict[str, Any]] = []

    for question_index, question in enumerate(test_questions, start=1):
        question_start = time.perf_counter()

        # 1. 임베딩 + 검색 + 선별 (rerank/threshold)
        query_embedding = embed_query(question)
        all_segments, accepted_segments = retrieve_segments(
            question, query_embedding, media_id
        )

        # 2. 답변 생성
        answer, context_text = get_answer_by_chat_model(question, accepted_segments)

        # 3. 메트릭 계산
        relevance = calculate_answer_relevance(question, answer)
        groundedness = calculate_groundedness(answer, context_text)
        precision = calculate_retrieval_precision(accepted_segments, question)

        relevance_scores.append(relevance)
        groundedness_scores.append(groundedness)
        precision_scores.append(precision)

        question_latency = round((time.perf_counter() - question_start) * 1000)

        qa_results.append(
            {
                "test_id": f"Q{question_index}",
                "query": question,
                "answer": answer,
                "context_text": context_text,
                "sources": [
                    {
                        "chunk_index": seg.get("chunk_index"),
                        "similarity": seg.get("similarity"),
                        "accepted": seg.get("accepted", True),
                        "text": seg.get("text", "")[:200],
                    }
                    for seg in all_segments
                ],
                "metrics": {
                    "answer_relevance": relevance,
                    "groundedness": groundedness,
                    "retrieval_precision": precision,
                },
                "latency_ms": question_latency,
            }
        )

    def _avg(lst: List[float]) -> float:
        return sum(lst) / len(lst) if lst else 0.0

    wer_score = None
    cer_score = None
    if reference_transcript:
        media = get_media_by_id(media_id)
        full_transcript = media.get("full_transcript") if media else None
        if not full_transcript:
            # fallback: full_transcript 컬럼이 없는 기존 데이터
            segments = get_media_segments(media_id)
            full_transcript = " ".join([seg.get("text", "") for seg in segments])
        wer_score, cer_score = calculate_wer_cer(reference_transcript, full_transcript)

    # [선택 과제] Visual-Text Alignment
    alignment_scores: List[float] = []
    all_segments = get_media_segments(media_id)
    for seg in all_segments:
        desc = seg.get("frame_description")
        text = seg.get("text", "")
        if desc and text:
            alignment_scores.append(calculate_visual_text_alignment(desc, text))

    return {
        "metrics": {
            "wer": wer_score,
            "cer": cer_score,
            "answer_relevance": _avg(relevance_scores),
            "groundedness": _avg(groundedness_scores),
            "retrieval_precision": _avg(precision_scores),
            "visual_text_alignment": (
                _avg(alignment_scores) if alignment_scores else None
            ),
        },
        "qa_results": qa_results,
        "question_count": len(test_questions),
    }


# ────────────────────────────────────────
# [선택 과제] Visual-Text Alignment
# ────────────────────────────────────────
def calculate_visual_text_alignment(
    frame_description: str, transcript_text: str
) -> float:
    """
    [선택 과제] 비전 모델이 생성한 프레임 설명과 전사 텍스트의 일치도를 평가합니다.

    목표치: > 0.65

    이 함수는 필수 과제가 아닙니다. 아래 가이드를 따라 선택적으로 구현하세요.

    구현 아이디어:
    1. LLM-as-Judge: "아래 영상 설명과 음성 전사가 같은 장면을 묘사합니까? 0.0~1.0으로 점수를 주세요."
    2. 임베딩 코사인 유사도: embed_query(frame_description)과
       embed_query(transcript_text)의 코사인 유사도 계산

    주의: PROVIDER=openai인 경우 GPT-4o Vision 추가 호출 비용이 발생합니다.

    Args:
        frame_description (str): analyze_frame_with_vision_model() 반환값
        transcript_text (str): 동일 구간의 전사 텍스트

    Returns:
        float: 정렬 점수 (0.0~1.0)
    """
    prompt = get_eval_visual_text_alignment_prompt().format(
        frame_description=frame_description, transcript_text=transcript_text
    )
    raw = _llm_chat(prompt)
    match = re.search(r"\d+\.?\d*", raw)
    score = float(match.group()) if match else 0.0

    return min(max(score, 0.0), 1.0)
