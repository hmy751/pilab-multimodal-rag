"""
qa_pipeline.py — QA 한 건의 오케스트레이션 (route와 util 사이의 pipeline 층)

main.py /qa, evals/_stages.py:run_qa, evaluation_utils.run_full_evaluation에
중복돼 있던 "embedding → retrieve → generate" 흐름을 하나로 모은 shared boundary.
이번 PR에선 main.py만 이 함수를 호출하도록 교체하고, evals 쪽은 별도 PR에서 교체.

LangSmith trace 구조 (이름 규칙: 루트/묶음은 도메인 prefix만, 말단은 번호):
    qa.request (root, chain)
      ├─ qa.0_hyde             (llm, use_hyde=True일 때만)
      ├─ qa.1_embed_query      (embedding)
      ├─ qa.retrieve           (chain)
      │   ├─ qa.2_search           (chain, hybrid fusion 묶음)
      │   │   ├─ qa.2.1_vector_search   (retriever)
      │   │   ├─ qa.2.2_bm25_search     (retriever, use_hybrid=True일 때만)
      │   │   └─ qa.2.3_rrf_fuse        (tool, use_hybrid=True일 때만)
      │   └─ qa.3_rank_candidates  (chain, mode metadata)
      │       └─ qa.3.1_rerank     (retriever, rerank 모드일 때만)
      └─ qa.4_chat_completion  (llm)   # 1:1 래퍼(qa.generate) 생략

LANGCHAIN_TRACING_V2가 false이거나 키가 없으면 @traceable은 투명 pass-through로
동작하므로 로컬·CI 환경에서도 키 없이 그대로 돌아간다.
"""

from typing import Any, Dict, Optional

from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree

from ..config import PipelineConfig, get_stage_config
from ..diagnostics import attach_config_to_run, attach_stage_cfg_to_run, timer
from ..embedding import embed_query
from ..qa.chat import get_answer_by_chat_model
from ..qa.hyde import generate_hypothetical_answer
from ..qa.retrieval import retrieve_segments


@traceable(name="qa.request", run_type="chain")
def run_qa(
    query: str,
    media_id: str,
    cfg: Optional[PipelineConfig] = None,
    source: str = "app",
) -> Dict[str, Any]:
    """질문 1건을 처리해 답변·근거·구간별 latency·trace_id를 반환한다.

    응답 dict의 latency_ms shape은 기존 /qa 응답과 동일하게
    {embedding, retrieval, generation, total} 4-key를 유지한다.

    source는 LangSmith run에 "app" / "evals" / "evaluate"로 표식만 남긴다.
    """
    cfg = cfg or get_stage_config()
    attach_config_to_run(source)
    latency_ms: Dict[str, int] = {}

    # speakers는 화자 인지 프롬프트(v2-speaker)용 메타데이터. HyDE·rerank 중
    # 어느 쪽이든 {speaker_intro}를 쓰는 템플릿을 사용할 때만 조회한다.
    # 어느 쪽도 안 쓰면 DB 호출 스킵 (baseline v1 경로엔 오버헤드 없음).
    from ..prompts import (
        hyde_prompt_uses_speakers,
        llm_rerank_prompt_uses_speakers,
    )

    hyde_wants_speakers = (
        cfg.retrieval.use_hyde
        and hyde_prompt_uses_speakers(cfg.retrieval.hyde_prompt_version)
    )
    rerank_wants_speakers = (
        cfg.retrieval.use_rerank
        and cfg.retrieval.rerank_provider == "llm"
        and llm_rerank_prompt_uses_speakers(
            cfg.retrieval.llm_rerank_prompt_version
        )
    )
    speakers: list[str] = []
    if hyde_wants_speakers or rerank_wants_speakers:
        from ..supabase_utils import get_media_speakers

        speakers = get_media_speakers(media_id)

    # HyDE: 쿼리를 임베딩용 "가상 답변"으로 변형 (use_hyde=True일 때)
    # BM25/rerank는 원 쿼리를 계속 사용한다 (희귀 토큰 매칭·semantic rerank 유지).
    embed_input = query
    if cfg.retrieval.use_hyde:
        with timer() as t_hyde:
            embed_input = generate_hypothetical_answer(
                query,
                speakers=speakers,
                retrieval_cfg=cfg.retrieval,
                qa_cfg=cfg.qa,
            )
        latency_ms["hyde"] = t_hyde()

    with timer() as t_embed:
        query_embedding = embed_query(embed_input, cfg=cfg.embedding)
    latency_ms["embedding"] = t_embed()

    with timer() as t_retrieve:
        all_segments, accepted = run_retrieve(
            query, query_embedding, media_id, cfg, speakers=speakers
        )
    latency_ms["retrieval"] = t_retrieve()

    with timer() as t_gen:
        answer, context_text = get_answer_by_chat_model(
            query, accepted, cfg=cfg.qa
        )
    latency_ms["generation"] = t_gen()

    latency_ms["total"] = (
        latency_ms.get("hyde", 0)
        + latency_ms["embedding"]
        + latency_ms["retrieval"]
        + latency_ms["generation"]
    )

    run = get_current_run_tree()
    trace_id = str(run.id) if run is not None else None

    return {
        "answer": answer,
        "context_text": context_text,
        "all_segments": all_segments,
        "accepted": accepted,
        "latency_ms": latency_ms,
        "trace_id": trace_id,
    }


@traceable(name="qa.retrieve", run_type="chain")
def run_retrieve(
    query: str,
    query_embedding,
    media_id: str,
    cfg: PipelineConfig,
    speakers: Optional[list] = None,
):
    """검색 + 선별 단계를 trace의 child run으로 노출한다.

    speakers는 화자 인지 rerank 프롬프트로 전달된다.
    """
    attach_stage_cfg_to_run("retrieval", cfg.retrieval)
    return retrieve_segments(
        query, query_embedding, media_id, cfg=cfg.retrieval, speakers=speakers
    )
