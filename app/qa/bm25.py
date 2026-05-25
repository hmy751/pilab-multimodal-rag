"""
qa/bm25.py — 키워드 기반(BM25) 후보 검색

Dense(vector) 검색이 놓치는 고유명사·숫자·희귀 토큰을 잡기 위한 sparse 검색.
corpus는 media_id로 필터링된 "이 영상의 청크들"로 한정한다.
IDF 통계도 이 영상 내부 기준이며 매 쿼리마다 재계산한다.
"""

import re
from typing import Any, Dict, List

from langsmith import traceable
from rank_bm25 import BM25Okapi

from ..config import RetrievalCfg, get_stage_config

_TOKEN_RE = re.compile(r"[A-Za-z0-9가-힣]+")


def _tokenize(text: str) -> List[str]:
    """한글/영숫자 연속 구간만 추출하고 소문자화한다.

    한국어 형태소 분석기는 외부 의존성이 커서 도입 보류. "2021년"은 하나의
    토큰으로 남아 쿼리에도 "2021년"이 있어야 매칭되지만, 대부분의 질문이
    완전 토큰을 포함하므로 실용적으로 충분하다.
    """
    if not text:
        return []
    return _TOKEN_RE.findall(text.lower())


@traceable(name="qa.2.2_bm25_search", run_type="retriever")
def bm25_search(
    query: str,
    media_id: str,
    cfg: RetrievalCfg | None = None,
) -> List[Dict[str, Any]]:
    """BM25로 media 내부 청크에 점수를 매기고 상위 hybrid_bm25_top_k개를 반환한다.

    반환 dict 포맷은 search_similar_segments와 호환 — 단, similarity 대신
    `bm25_score` 필드가 채워진다 (similarity 필드는 없음).
    """
    cfg = cfg or get_stage_config().retrieval
    from ..supabase_utils import get_media_segments

    segments = get_media_segments(media_id)
    if not segments:
        print(f"[bm25] media_id={media_id}: 청크 없음 — BM25 skip")
        return []

    corpus_tokens = [_tokenize(s.get("text") or "") for s in segments]
    query_tokens = _tokenize(query)
    print(f"[bm25] corpus={len(segments)}개 청크, " f"query_tokens={query_tokens}")

    if not query_tokens:
        print("[bm25] query 토큰 없음 — BM25 skip")
        return []

    bm25 = BM25Okapi(corpus_tokens)
    scores = bm25.get_scores(query_tokens)

    scored = [
        {**seg, "bm25_score": float(score)} for seg, score in zip(segments, scores)
    ]
    scored.sort(key=lambda s: s["bm25_score"], reverse=True)
    top = scored[: cfg.hybrid_bm25_top_k]

    preview = [
        f"chunk={s.get('chunk_index')} score={s['bm25_score']:.3f}" for s in top[:5]
    ]
    print(f"[bm25] top-{len(top)} (first 5): {preview}")
    return top
