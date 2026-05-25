"""
snapshot.py — config + prompt 스냅샷 단일 진실 공급원

config-규약 "Snapshot 단일화" 항목 구현.
diagnostics.py(런타임 API 응답용)와 evals/_common.py(CLI 실험용)가
모두 이 모듈을 import한다.

출력 키는 evals/results/ JSON 형식과 동일하게 유지한다.
"""

from typing import Any, Dict

from .config import get_stage_config
from .prompts import (
    CORRECTION_PROMPTS,
    CURRENT_CORRECTION_VERSION,
    CURRENT_EVAL_ANSWER_RELEVANCE_VERSION,
    CURRENT_EVAL_GROUNDEDNESS_VERSION,
    CURRENT_EVAL_RETRIEVAL_PRECISION_VERSION,
    CURRENT_EVAL_VISUAL_TEXT_ALIGNMENT_VERSION,
    CURRENT_HYDE_VERSION,
    CURRENT_LLM_RERANK_VERSION,
    CURRENT_QA_SYSTEM_VERSION,
    CURRENT_RERANK_DOC_VERSION,
    CURRENT_VISION_VERSION,
    EVAL_ANSWER_RELEVANCE_PROMPTS,
    EVAL_GROUNDEDNESS_PROMPTS,
    EVAL_RETRIEVAL_PRECISION_PROMPTS,
    EVAL_VISUAL_TEXT_ALIGNMENT_PROMPTS,
    HYDE_PROMPTS,
    LLM_RERANK_PROMPTS,
    QA_SYSTEM_PROMPTS,
    RERANK_DOC_TEMPLATES,
    TRANSCRIPTION_PROMPTS,
    VISION_PROMPTS,
)


def get_config_snapshot() -> Dict[str, Any]:
    """현재 CONFIG 상태를 실험/API 응답에 포함할 dict로 반환한다.

    Stage Config의 provider를 기준으로 각 stage의 활성 모델을 개별 결정한다.
    기존 is_local(단일 provider 시대 잔재)을 제거하고 stage별 provider로 전환.
    """
    cfg = get_stage_config()
    transcription = cfg.transcription
    vision = cfg.vision
    embedding = cfg.embedding
    retrieval = cfg.retrieval
    qa = cfg.qa

    return {
        # ── Transcription ──
        "transcription_provider": transcription.provider,
        "whisper_model_size": transcription.whisper_model_size,
        "openai_whisper_model": transcription.openai_whisper_model,
        "whisper_prompt_version": transcription.whisper_prompt_version,
        # ── Vision ──
        "vision_provider": vision.provider,
        "vision_model": (
            vision.openai_vision_model
            if vision.provider == "openai"
            else vision.ollama_vision_model
        ),
        "prompt_version": CURRENT_VISION_VERSION,
        "frames_per_minute": vision.frames_per_minute,
        # ── Embedding ──
        "embedding_provider": embedding.provider,
        "embed_model": (
            embedding.openai_embedding_model
            if embedding.provider == "openai"
            else embedding.ollama_embed_model
        ),
        "embedding_dim": embedding.embedding_dim,
        "chunk_window_seconds": embedding.chunk_window_seconds,
        "chunk_overlap_seconds": embedding.chunk_overlap_seconds,
        "chunking_strategy": embedding.chunking_strategy,
        "semantic_breakpoint_percentile": embedding.semantic_breakpoint_percentile,
        "semantic_min_chunk_seconds": embedding.semantic_min_chunk_seconds,
        # ── Correction ──
        "use_correction": cfg.correction.enabled,
        "correction_provider": cfg.correction.provider,
        "correction_model": (
            cfg.correction.openai_chat_model
            if cfg.correction.provider == "openai"
            else cfg.correction.ollama_chat_model
        ),
        "correction_prompt_version": CURRENT_CORRECTION_VERSION,
        # ── QA ──
        "chat_provider": qa.provider,
        "chat_model": (
            qa.openai_chat_model if qa.provider == "openai" else qa.ollama_chat_model
        ),
        "qa_prompt_version": CURRENT_QA_SYSTEM_VERSION,
        # ── Judge ──
        "judge_provider": cfg.judge.provider,
        # ── Retrieval / Rerank ──
        "search_threshold": retrieval.search_threshold,
        "top_k": retrieval.top_k,
        "use_rerank": retrieval.use_rerank,
        "rerank_provider": retrieval.rerank_provider,
        "rerank_model": retrieval.rerank_model,
        "rerank_top_k": retrieval.rerank_top_k,
        "rerank_pool_size": retrieval.rerank_pool_size,
        "llm_rerank_prompt_version": retrieval.llm_rerank_prompt_version,
        # ── Hybrid ──
        "use_hybrid": retrieval.use_hybrid,
        "hybrid_rrf_k": retrieval.hybrid_rrf_k,
        "hybrid_bm25_top_k": retrieval.hybrid_bm25_top_k,
        # ── HyDE ──
        "use_hyde": retrieval.use_hyde,
        "hyde_prompt_version": retrieval.hyde_prompt_version,
    }


def get_prompt_snapshot() -> Dict[str, Any]:
    """현재 프롬프트 버전 + 전문을 기록할 dict로 반환한다.

    config-규약 "누락 추가" 항목: rerank doc prompt, EVAL_* 4종 포함.
    """
    transcription_cfg = get_stage_config().transcription
    prompt_ver = transcription_cfg.whisper_prompt_version
    return {
        "transcription": {
            "version": prompt_ver or "(none)",
            "text": TRANSCRIPTION_PROMPTS.get(prompt_ver, ""),
        },
        "vision": {
            "version": CURRENT_VISION_VERSION,
            "text": VISION_PROMPTS[CURRENT_VISION_VERSION],
        },
        "qa_system": {
            "version": CURRENT_QA_SYSTEM_VERSION,
            "text": QA_SYSTEM_PROMPTS[CURRENT_QA_SYSTEM_VERSION],
        },
        "hyde": {
            "version": CURRENT_HYDE_VERSION,
            "text": HYDE_PROMPTS[CURRENT_HYDE_VERSION],
        },
        "correction": {
            "version": CURRENT_CORRECTION_VERSION,
            "text": CORRECTION_PROMPTS[CURRENT_CORRECTION_VERSION],
        },
        "rerank_doc": {
            "version": CURRENT_RERANK_DOC_VERSION,
            "text": RERANK_DOC_TEMPLATES[CURRENT_RERANK_DOC_VERSION],
        },
        "llm_rerank": {
            "version": CURRENT_LLM_RERANK_VERSION,
            "text": LLM_RERANK_PROMPTS[CURRENT_LLM_RERANK_VERSION],
        },
        "eval_answer_relevance": {
            "version": CURRENT_EVAL_ANSWER_RELEVANCE_VERSION,
            "text": EVAL_ANSWER_RELEVANCE_PROMPTS[CURRENT_EVAL_ANSWER_RELEVANCE_VERSION],
        },
        "eval_groundedness": {
            "version": CURRENT_EVAL_GROUNDEDNESS_VERSION,
            "text": EVAL_GROUNDEDNESS_PROMPTS[CURRENT_EVAL_GROUNDEDNESS_VERSION],
        },
        "eval_retrieval_precision": {
            "version": CURRENT_EVAL_RETRIEVAL_PRECISION_VERSION,
            "text": EVAL_RETRIEVAL_PRECISION_PROMPTS[
                CURRENT_EVAL_RETRIEVAL_PRECISION_VERSION
            ],
        },
        "eval_visual_text_alignment": {
            "version": CURRENT_EVAL_VISUAL_TEXT_ALIGNMENT_VERSION,
            "text": EVAL_VISUAL_TEXT_ALIGNMENT_PROMPTS[
                CURRENT_EVAL_VISUAL_TEXT_ALIGNMENT_VERSION
            ],
        },
    }
