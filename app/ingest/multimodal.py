"""
ingest/multimodal.py — 전사 청크 + 비전 프레임 분석 결과를 임베딩용 컨텍스트로 합성.
"""

from typing import Dict, List

from langsmith import traceable


@traceable(name="ingest.7_multimodal", run_type="tool")
def combine_multimodal_context(
    transcript_chunks: List[Dict],
    frame_analyses: List[Dict],
    start: float,
    end: float,
) -> str:
    transcript_text = " ".join(chunk["text"] for chunk in transcript_chunks)

    if not frame_analyses:
        return f"[전사] {transcript_text}"

    relevant_frames = [f for f in frame_analyses if start <= f["timestamp"] < end]
    parts = [f"[전사] {transcript_text}"]
    for frame in relevant_frames:
        ts = frame["timestamp"]
        mm_ss = f"{int(ts // 60):02d}:{int(ts % 60):02d}"
        parts.append(f"[비전 {mm_ss}] {frame['description']}")

    return "\n".join(parts)
