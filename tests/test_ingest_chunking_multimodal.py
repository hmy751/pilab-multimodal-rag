"""
chunk_segments(), combine_multimodal_context() 회귀 테스트.

media_utils.py 분할(app/ingest/chunking.py + app/ingest/multimodal.py) 후에도
두 함수의 동작이 보존되는지 검증한다.
"""

import pytest

from app.config import EmbeddingCfg
from app.ingest.chunking import chunk_segments
from app.ingest.multimodal import combine_multimodal_context


def _make_embedding_cfg(window_seconds: float, overlap_seconds: float) -> EmbeddingCfg:
    """테스트용 EmbeddingCfg 헬퍼."""
    return EmbeddingCfg(
        provider="local",
        chunk_window_seconds=window_seconds,
        chunk_overlap_seconds=overlap_seconds,
        ollama_embed_model="nomic-embed-text",
        openai_embedding_model="text-embedding-3-small",
        embedding_dim=768,
    )


# ── segment_transcript ──


class TestSegmentTranscript:
    """청킹 로직의 경계 조건과 기본 동작을 검증한다."""

    def _make_segments(self, ranges):
        """[(start, end, text), ...] → segments 리스트."""
        return [
            {"start": s, "end": e, "text": t}
            for s, e, t in ranges
        ]

    def test_empty_input(self):
        assert chunk_segments([]) == []

    def test_single_segment_within_window(self):
        segments = self._make_segments([(0.0, 5.0, "hello")])
        cfg = _make_embedding_cfg(window_seconds=20.0, overlap_seconds=5.0)
        chunks = chunk_segments(segments, cfg=cfg)
        assert len(chunks) == 1
        assert chunks[0]["text"] == "hello"
        assert chunks[0]["chunk_index"] == 0

    def test_chunk_index_sequential(self):
        segments = self._make_segments([
            (0.0, 10.0, "A"),
            (10.0, 20.0, "B"),
            (20.0, 30.0, "C"),
            (30.0, 40.0, "D"),
        ])
        cfg = _make_embedding_cfg(window_seconds=20.0, overlap_seconds=5.0)
        chunks = chunk_segments(segments, cfg=cfg)
        indices = [c["chunk_index"] for c in chunks]
        assert indices == list(range(len(chunks)))

    def test_overlap_includes_boundary_segments(self):
        """오버랩 구간에 걸친 세그먼트가 양쪽 청크에 포함되는지 확인."""
        segments = self._make_segments([
            (0.0, 8.0, "first"),
            (8.0, 12.0, "boundary"),
            (12.0, 20.0, "second"),
        ])
        cfg = _make_embedding_cfg(window_seconds=10.0, overlap_seconds=3.0)
        chunks = chunk_segments(segments, cfg=cfg)
        texts = [c["text"] for c in chunks]
        boundary_count = sum(1 for t in texts if "boundary" in t)
        assert boundary_count >= 2, "경계 세그먼트가 오버랩으로 2개 이상 청크에 포함되어야 함"

    def test_window_and_overlap_parameters_applied(self):
        """window_seconds, overlap_seconds가 실제 청크 크기에 반영되는지 확인."""
        segments = self._make_segments([
            (0.0, 5.0, "A"),
            (5.0, 10.0, "B"),
            (10.0, 15.0, "C"),
            (15.0, 20.0, "D"),
        ])
        # window=10, overlap=0 → step=10 → 2개 청크
        chunks_no_overlap = chunk_segments(
            segments, cfg=_make_embedding_cfg(window_seconds=10.0, overlap_seconds=0.0)
        )
        # window=10, overlap=5 → step=5 → 더 많은 청크
        chunks_with_overlap = chunk_segments(
            segments, cfg=_make_embedding_cfg(window_seconds=10.0, overlap_seconds=5.0)
        )
        assert len(chunks_with_overlap) > len(chunks_no_overlap)

    def test_chunk_start_end_within_bounds(self):
        segments = self._make_segments([
            (0.0, 10.0, "A"),
            (10.0, 25.0, "B"),
        ])
        cfg = _make_embedding_cfg(window_seconds=20.0, overlap_seconds=5.0)
        chunks = chunk_segments(segments, cfg=cfg)
        for chunk in chunks:
            assert chunk["start"] >= 0.0
            assert chunk["end"] <= 25.0


# ── combine_multimodal_context ──


class TestCombineMultimodalContext:
    """멀티모달 컨텍스트 조합 로직을 검증한다."""

    def test_transcript_only(self):
        chunks = [{"text": "hello world"}]
        result = combine_multimodal_context(chunks, [], 0.0, 10.0)
        assert result == "[전사] hello world"

    def test_with_relevant_frames(self):
        chunks = [{"text": "hello"}]
        frames = [{"timestamp": 5.0, "description": "사람이 손을 흔든다"}]
        result = combine_multimodal_context(chunks, frames, 0.0, 10.0)
        assert "[전사] hello" in result
        assert "[비전 00:05]" in result
        assert "사람이 손을 흔든다" in result

    def test_frame_outside_range_excluded(self):
        chunks = [{"text": "hello"}]
        frames = [{"timestamp": 15.0, "description": "범위 밖 프레임"}]
        result = combine_multimodal_context(chunks, frames, 0.0, 10.0)
        assert "범위 밖 프레임" not in result

    def test_multiple_frames(self):
        chunks = [{"text": "content"}]
        frames = [
            {"timestamp": 2.0, "description": "frame A"},
            {"timestamp": 7.0, "description": "frame B"},
        ]
        result = combine_multimodal_context(chunks, frames, 0.0, 10.0)
        assert "frame A" in result
        assert "frame B" in result

    def test_timestamp_format_mm_ss(self):
        chunks = [{"text": "x"}]
        frames = [{"timestamp": 125.0, "description": "desc"}]
        result = combine_multimodal_context(chunks, frames, 120.0, 130.0)
        assert "[비전 02:05]" in result
