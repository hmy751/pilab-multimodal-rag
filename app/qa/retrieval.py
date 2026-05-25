"""
qa/retrieval.py — 검색 결과 선별 (Rerank / Threshold)

retrieve_segments: 검색 → 선별 → accepted 마킹까지의 공통 흐름.
rerank_segments:   Cohere Rerank 호출 (retrieve_segments 내부에서 사용).
"""

from typing import List, Dict, Any, Tuple

from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree

from ..config import RetrievalCfg, get_stage_config
from ..prompts import format_rerank_document


@traceable(name="qa.3.1_cohere_rerank", run_type="retriever")
def rerank_segments(
    query: str,
    segments: List[Dict[str, Any]],
    cfg: RetrievalCfg | None = None,
) -> List[Dict[str, Any]]:
    """
    Cohere Rerank로 segments를 재정렬하여 상위 top_n개를 반환한다.
    COHERE_API_KEY가 없거나 API 호출 실패 시 원본을 그대로 반환 (fallback).

    fallback 경로 진입 시 run.metadata에 `skipped` 키로 사유를 남겨
    LangSmith trace만 보고도 "실제 Cohere 호출이 있었는지"를 판별할 수 있다.
    """
    cfg = cfg or get_stage_config().retrieval
    top_k = cfg.rerank_top_k
    run = get_current_run_tree()

    if not cfg.cohere_api_key:
        print("[rerank] COHERE_API_KEY 없음 — rerank 생략")
        if run is not None:
            run.add_metadata({"skipped": "no_api_key"})
        return segments[:top_k]

    if not segments:
        return segments

    try:
        import cohere

        client = cohere.ClientV2(api_key=cfg.cohere_api_key)

        documents = [format_rerank_document(seg) for seg in segments]

        response = client.rerank(
            model=cfg.rerank_model,
            query=query,
            documents=documents,
            top_n=top_k,
        )

        reranked = []
        for result in response.results:
            seg = segments[result.index].copy()
            seg["rerank_score"] = result.relevance_score
            seg["accepted"] = True
            reranked.append(seg)

        scores = [f"{s['rerank_score']:.3f}" for s in reranked]
        print(f"[rerank] {len(segments)}개 → {len(reranked)}개 선별 (scores: {scores})")
        return reranked

    except Exception as e:
        print(f"[rerank] 실패, fallback 사용 — {e}")
        if run is not None:
            run.add_metadata({"skipped": "api_error", "error": str(e)})
        return segments[:top_k]


@traceable(name="qa.3_rank_candidates", run_type="chain")
def _rank_candidates(
    candidates: List[Dict[str, Any]],
    query: str,
    cfg: RetrievalCfg,
    speakers: List[str] | None = None,
) -> List[Dict[str, Any]]:
    """검색 결과 후보를 rerank 또는 threshold로 선별한다.

    cfg.use_rerank로 분기한다. 이전엔 rerank는 retrieval_utils, threshold는
    supabase_utils에 흩어져 있었지만 "선별"이라는 동일 관심사를 한 함수로 통합.

    speakers는 화자 인지 rerank 프롬프트(v2-speaker)에 주입된다. Cohere
    경로는 speakers를 사용하지 않는다 (cross-encoder에 메타데이터 주입 불가).

    LangSmith trace에는 mode metadata로 분기를 노출 — UI에서 rerank/threshold
    경로를 한 run 이름(candidate_ranking) 안에서 비교할 수 있도록.
    """
    run = get_current_run_tree()
    if cfg.use_rerank:
        if run is not None:
            run.add_metadata(
                {
                    "mode": "rerank",
                    "rerank_provider": cfg.rerank_provider,
                    "rerank_top_k": cfg.rerank_top_k,
                }
            )
        if cfg.rerank_provider == "llm":
            from .llm_rerank import llm_rerank_segments

            return llm_rerank_segments(
                query, candidates, speakers=speakers, cfg=cfg
            )
        return rerank_segments(query, candidates, cfg=cfg)

    if run is not None:
        run.add_metadata(
            {"mode": "threshold", "threshold": cfg.search_threshold}
        )
    return [c for c in candidates if c.get("similarity", 0) >= cfg.search_threshold]


@traceable(name="qa.2.3_rrf_fuse", run_type="tool")
def _rrf_fuse(
    rankings: List[List[Dict[str, Any]]],
    k: int,
) -> List[Dict[str, Any]]:
    """Reciprocal Rank Fusion — 여러 ranking 리스트를 하나로 병합한다.

    공식:
        final(doc) = Σ  1 / (k + rank_i(doc) + 1)
                    각 ranking i 대해

    왜 "점수 자체"가 아니라 "순위"만 쓰나:
      vector similarity(0~1)와 BM25 score(unbounded)는 스케일이 달라
      직접 가중합하면 한쪽이 지배한다. RRF는 순위만 쓰므로 스케일 무관.

    k의 역할:
      분모의 오프셋. k=60이면 1등은 1/61 ≈ 0.0164, 10등은 1/71 ≈ 0.0141.
      k가 클수록 상위/하위 격차가 완만해짐. 60은 원 논문 권장값이며
      Elasticsearch·Weaviate 등도 기본값으로 채택.

    +1의 이유:
      rank는 0-based(0이 1등). k=0일 때 0으로 나눠지는 걸 막고,
      1-based처럼 해석되게 한다.

    같은 chunk가 여러 ranking에 등장하면:
      점수는 각 ranking에서 받은 값을 "누적"한다 (fusion의 본질).
      dict 본체(similarity, text 등 필드)는 **첫 등장한 ranking의 것**을 보존.
      vector_ranking을 먼저 넘기면 vector 쪽 similarity 값이 유지되므로
      하위 단계(rerank 등)에서 similarity를 참조할 때 문제 없음.
    """
    # chunk_index → 누적 RRF 점수
    scores: Dict[Any, float] = {}
    # chunk_index → 원본 segment dict (similarity, text 등 보존)
    doc_map: Dict[Any, Dict[str, Any]] = {}

    # 각 ranking을 돌며 점수를 누적한다.
    for ranking in rankings:
        # enumerate: (0, 1등 doc), (1, 2등 doc), ...
        for rank, doc in enumerate(ranking):
            key = doc.get("chunk_index")
            # chunk_index가 없으면 합산 키를 만들 수 없으므로 skip (방어적)
            if key is None:
                continue
            # 기존 점수에 이 ranking에서의 기여분을 더한다.
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            # 처음 본 chunk만 저장 → vector ranking을 먼저 넘기면 vector dict가 남는다
            if key not in doc_map:
                doc_map[key] = doc

    # 누적 점수 기준 내림차순 정렬
    fused_keys = sorted(scores, key=lambda x: scores[x], reverse=True)

    # 원본 dict에 rrf_score 필드를 추가해서 반환 (디버깅/관측용)
    fused = [{**doc_map[key], "rrf_score": scores[key]} for key in fused_keys]

    preview = [
        f"chunk={d.get('chunk_index')} rrf={d['rrf_score']:.4f}"
        for d in fused[:5]
    ]
    print(f"[rrf] fused {len(fused)}개 (first 5): {preview}")
    return fused


@traceable(name="qa.2_search", run_type="chain")
def _hybrid_search(
    query: str,
    query_embedding: List[float],
    media_id: str,
    cfg: RetrievalCfg,
) -> List[Dict[str, Any]]:
    """Dense(vector) 검색과 BM25 검색을 병렬로 돌려 RRF로 병합한다.

    cfg.use_hybrid=False면 vector 결과만 반환 (rollback 경로).
    rerank 모드일 때 vector 검색은 rerank_pool_size까지, threshold 모드일 때는
    top_k까지 가져온다.
    """
    from ..supabase_utils import search_similar_segments
    from .bm25 import bm25_search

    vec_limit = cfg.rerank_pool_size if cfg.use_rerank else cfg.top_k
    vec_cfg = cfg.model_copy(update={"top_k": vec_limit})
    print(
        f"[hybrid] use_hybrid={cfg.use_hybrid} use_rerank={cfg.use_rerank} "
        f"vec_limit={vec_limit} bm25_top_k={cfg.hybrid_bm25_top_k}"
    )

    vector_results = search_similar_segments(
        query_embedding, media_id, cfg=vec_cfg, skip_threshold=True,
    )
    vec_preview = [
        f"chunk={r.get('chunk_index')} sim={r.get('similarity', 0):.3f}"
        for r in vector_results[:5]
    ]
    print(f"[hybrid] vector top-{len(vector_results)} (first 5): {vec_preview}")

    if not cfg.use_hybrid:
        print("[hybrid] use_hybrid=False — BM25/RRF skip, vector only")
        return vector_results

    bm25_results = bm25_search(query, media_id, cfg=cfg)
    fused = _rrf_fuse(
        [vector_results, bm25_results], k=cfg.hybrid_rrf_k,
    )
    return fused


def _enrich_with_speakers(
    segments: List[Dict[str, Any]], media_id: str
) -> None:
    # rerank 이전에 호출해야 rerank 프롬프트에서도 speaker_id 참조 가능.
    # 미디어에 화자 라벨이 없을 때는 caller에서 skip하는 것이 정답.
    # 여기서 호출되면 "라벨이 있다"가 전제.
    from ..supabase_utils import get_speakers_by_chunks

    chunk_indices = [
        s["chunk_index"] for s in segments if s.get("chunk_index") is not None
    ]
    if not chunk_indices:
        return
    speaker_map = get_speakers_by_chunks(media_id, chunk_indices)
    for seg in segments:
        seg["speaker_id"] = speaker_map.get(seg.get("chunk_index"))


def retrieve_segments(
    query: str,
    query_embedding: List[float],
    media_id: str,
    cfg: RetrievalCfg | None = None,
    speakers: List[str] | None = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    검색 → 선별(rerank/threshold) → accepted 마킹까지 한번에 처리.

    speakers는 화자 인지 rerank 프롬프트용 메타데이터. 미지정 시 rerank는
    speaker 단서 없이 동작한다.

    Returns:
        (all_segments, accepted_segments)
        - all_segments: 전체 후보 (accepted 필드 마킹됨)
        - accepted_segments: 최종 선별된 세그먼트
    """
    cfg = cfg or get_stage_config().retrieval

    all_segments = _hybrid_search(query, query_embedding, media_id, cfg)

    # speaker enrich은 미디어에 화자 라벨이 있을 때만 의미 있다. 라벨이
    # 없으면 get_speakers_by_chunks가 전부 None을 반환하므로 DB 쿼리가
    # 낭비된다. qa_pipeline이 미디어 메타데이터에서 speakers를 이미
    # 가져왔고, 빈 리스트면 라벨 미부여 미디어 → skip.
    if speakers:
        _enrich_with_speakers(all_segments, media_id)

    accepted_segments = _rank_candidates(
        all_segments, query, cfg, speakers=speakers
    )

    # accepted 마킹 (응답/결과 JSON의 sources에서 선별 여부 표시)
    # rerank은 .copy()된 객체를 반환하므로 id()가 아닌 chunk_index로 비교
    accepted_indices = {s.get("chunk_index") for s in accepted_segments}
    for seg in all_segments:
        seg["accepted"] = seg.get("chunk_index") in accepted_indices

    accepted_preview = [
        f"chunk={s.get('chunk_index')}" for s in accepted_segments
    ]
    print(f"[retrieve] accepted={len(accepted_segments)}개: {accepted_preview}")

    return all_segments, accepted_segments
