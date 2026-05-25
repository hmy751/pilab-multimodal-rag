"""
ingest/chunking.py — 전사 세그먼트를 청크로 분할.

chunking_strategy에 따라 분기:
  - "fixed":    sliding window (시간 기반)
  - "semantic": 임베딩 유사도 breakpoint 기반 (의미 기반 동적 청킹)
"""

import math
from typing import Dict, List

from langsmith import traceable

from ..config import EmbeddingCfg, get_stage_config
from ..embedding import embed_segment_for_boundary


@traceable(name="ingest.6_chunk", run_type="tool")
def chunk_segments(
    segments: List[Dict],
    cfg: EmbeddingCfg | None = None,
) -> List[Dict]:
    cfg = cfg or get_stage_config().embedding
    if not segments:
        return []

    if cfg.chunking_strategy == "semantic":
        return _chunk_semantic(segments, cfg)
    return _chunk_fixed(segments, cfg)


def _chunk_fixed(segments: List[Dict], cfg: EmbeddingCfg) -> List[Dict]:
    """고정 sliding window 기반 청킹."""
    window_seconds = cfg.chunk_window_seconds
    overlap_seconds = cfg.chunk_overlap_seconds
    step = window_seconds - overlap_seconds
    chunks: List[Dict] = []

    window_start = segments[0]["start"]
    max_end = segments[-1]["end"]

    while window_start < max_end:
        window_end = window_start + window_seconds
        texts = []

        for seg in segments:
            if seg["end"] > window_start and seg["start"] < window_end:
                texts.append(seg["text"].strip())

        if texts:
            actual_end = min(window_end, max_end)
            chunks.append(
                {
                    "start": window_start,
                    "end": actual_end,
                    "text": " ".join(texts),
                    "chunk_index": len(chunks),
                }
            )

        window_start += step

    return chunks


def _chunk_semantic(segments: List[Dict], cfg: EmbeddingCfg) -> List[Dict]:
    """임베딩 유사도 breakpoint 기반 청킹.

    각 segment를 임베딩한 뒤 인접 쌍의 코사인 거리를 계산한다. 거리가
    전체 분포의 `semantic_breakpoint_percentile` 이상이면 주제 전환으로
    간주하고 경계로 삼는다. `semantic_min_chunk_seconds`로 한 청크의
    최소 길이를 강제해 짧은 filler("네", "음")가 경계를 만드는 것을 막는다.
    """
    if len(segments) < 2:
        return [_build_chunk(segments, 0, len(segments) - 1, chunk_index=0)]

    embeddings = [embed_segment_for_boundary(s["text"], cfg) for s in segments]
    distances = _adjacent_cosine_distances(embeddings)
    threshold = _percentile(distances, cfg.semantic_breakpoint_percentile)

    return _merge_by_boundaries(
        segments, distances, threshold, cfg.semantic_min_chunk_seconds
    )


def _adjacent_cosine_distances(embeddings: List[List[float]]) -> List[float]:
    """인접한 두 임베딩의 (1 - 코사인 유사도). 값이 클수록 의미 전환."""
    return [
        1.0 - _cosine_similarity(embeddings[i], embeddings[i + 1])
        for i in range(len(embeddings) - 1)
    ]


def _cosine_similarity(v1: List[float], v2: List[float]) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)


def _percentile(values: List[float], p: float) -> float:
    """선형 보간 방식의 p-th percentile (0~100). numpy.percentile과 동일 결과."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * (p / 100.0)
    floor_idx = int(k)
    ceil_idx = min(floor_idx + 1, len(sorted_vals) - 1)
    if floor_idx == ceil_idx:
        return sorted_vals[floor_idx]
    fraction = k - floor_idx
    return sorted_vals[floor_idx] + (sorted_vals[ceil_idx] - sorted_vals[floor_idx]) * fraction


def _merge_by_boundaries(
    segments: List[Dict],
    distances: List[float],
    threshold: float,
    min_seconds: float,
) -> List[Dict]:
    """경계 판정을 따라 segment를 청크로 누적. 최소 길이 미달 경계는 무시."""
    chunks: List[Dict] = []
    buf_start = 0
    for i, seg in enumerate(segments):
        is_last = i == len(segments) - 1
        distance_to_next = distances[i] if i < len(distances) else None
        is_boundary = (
            distance_to_next is not None and distance_to_next >= threshold
        )
        duration = seg["end"] - segments[buf_start]["start"]

        if is_last or (is_boundary and duration >= min_seconds):
            chunks.append(
                _build_chunk(segments, buf_start, i, chunk_index=len(chunks))
            )
            buf_start = i + 1

    return chunks


def _build_chunk(
    segments: List[Dict], start_idx: int, end_idx: int, chunk_index: int
) -> Dict:
    texts = [segments[j]["text"].strip() for j in range(start_idx, end_idx + 1)]
    return {
        "start": segments[start_idx]["start"],
        "end": segments[end_idx]["end"],
        "text": " ".join(t for t in texts if t),
        "chunk_index": chunk_index,
    }
