"""
ingest_pipeline.py — 미디어 1건의 ingest 오케스트레이션 (route와 util 사이의 pipeline 층)

main.py:process_media_background에 붙어 있던 "audio 추출 → 전사 → 프레임 분석 →
교정 → 청킹/임베딩/저장" 흐름을 하나로 모은 pipeline. qa_pipeline.run_qa와 짝을
이루는 두 번째 pipeline으로 pipelines/ 폴더가 성립한다.

LangSmith trace 구조 (이름 규칙: 루트/묶음은 도메인 prefix만, 말단은 번호):
    ingest.request (root, chain)
      ├─ ingest.transcribe       (chain)
      │   ├─ ingest.1_audio_extract  (tool)
      │   └─ ingest.2_transcribe     (tool)
      ├─ ingest.vision           (chain)
      │   ├─ ingest.3_extract_frames (tool)
      │   └─ ingest.4_analyze_frame  (llm) × 프레임 수
      ├─ ingest.5_correct        (llm)    # 실제 교정이 돌 때만
      └─ ingest.embed            (chain)
          ├─ ingest.6_chunk         (tool)
          ├─ ingest.7_multimodal    (tool) × 청크 수
          └─ ingest.8_embed_chunk   (embedding) × 청크 수
"""

import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Tuple

from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree
from openai import AuthenticationError as OpenAIAuthError

from ..config import CONFIG, get_stage_config
from ..diagnostics import (
    StageTimer,
    attach_config_to_run,
    attach_stage_cfg_to_run,
    timer,
)
from ..embedding import embed_chunk
from ..ingest.chunking import chunk_segments
from ..ingest.correction import correct_transcription_with_vision
from ..ingest.multimodal import combine_multimodal_context
from ..ingest.transcription import extract_audio_from_video, transcribe_audio
from ..ingest.vision import analyze_frame_with_vision_model, extract_key_frames
from ..supabase_utils import (
    SupabaseOperationError,
    save_media_file,
    save_segment,
    update_media_status,
)

_VIDEO_EXTS = {"mp4", "mov", "avi", "mkv", "webm"}
_VISION_CONCURRENCY = 2  # OpenAI Vision API rate limit 대비 동시 실행 수


def _is_video_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in _VIDEO_EXTS


@traceable(name="ingest.transcribe", run_type="chain")
def _trace_transcribe(
    file_path: str,
    media_id: str,
    is_video: bool,
) -> Tuple[List[Dict[str, Any]], int, int]:
    cfg = get_stage_config().transcription
    attach_stage_cfg_to_run("transcription", cfg)

    with timer() as t_audio:
        if is_video:
            audio_path = os.path.join(CONFIG.upload_dir, f"{media_id}_audio.mp3")
            extract_audio_from_video(file_path, audio_path)
        else:
            audio_path = file_path

    with timer() as t_transcribe:
        segments = transcribe_audio(audio_path, cfg=cfg)

    return segments, t_audio(), t_transcribe()


def _analyze_frames_parallel(frames: List[Dict[str, Any]], cfg) -> List[Dict[str, Any]]:
    if not frames:
        return []

    # ThreadPoolExecutor 워커 스레드는 메인 스레드의 contextvars를 상속하지 않으므로
    # LangSmith 부모 run을 명시적으로 전달해야 ingest.4_analyze_frame이 orphan root로
    # 찍히지 않고 ingest.vision 아래 자식 run으로 붙는다.
    parent_run = get_current_run_tree()

    def _analyze_one(frame):
        description = analyze_frame_with_vision_model(
            frame["frame_path"],
            frame["timestamp"],
            cfg=cfg,
            langsmith_extra={"parent": parent_run},
        )
        return {"timestamp": frame["timestamp"], "description": description}

    with ThreadPoolExecutor(max_workers=_VISION_CONCURRENCY) as executor:
        return list(executor.map(_analyze_one, frames))


@traceable(name="ingest.vision", run_type="chain")
def _trace_vision(
    file_path: str,
    media_id: str,
) -> Tuple[List[Dict[str, Any]], int]:
    cfg = get_stage_config().vision
    attach_stage_cfg_to_run("vision", cfg)

    with timer() as t_vision:
        frames_dir = os.path.join(CONFIG.frames_dir, media_id)
        os.makedirs(frames_dir, exist_ok=True)
        frames = extract_key_frames(
            file_path,
            frames_dir,
            frames_per_minute=cfg.frames_per_minute,
        )
        frame_analyses = _analyze_frames_parallel(frames, cfg)

    return frame_analyses, t_vision()


@traceable(name="ingest.embed", run_type="chain")
def _trace_embed(
    media_id: str,
    segments: List[Dict[str, Any]],
    frame_analyses: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], int]:
    embed_cfg = get_stage_config().embedding
    attach_stage_cfg_to_run("embedding", embed_cfg)

    with timer() as t_embed:
        chunks = chunk_segments(segments, cfg=embed_cfg)

        for chunk in chunks:
            context_text = combine_multimodal_context(
                [chunk], frame_analyses, chunk["start"], chunk["end"]
            )

            embedding = embed_chunk(context_text, cfg=embed_cfg)
            matched_frames = [
                f
                for f in frame_analyses
                if chunk["start"] <= f["timestamp"] <= chunk["end"]
            ]

            def _fmt_ts(sec: float) -> str:
                m, s = divmod(int(sec), 60)
                return f"{m}분 {s}초" if m else f"{s}초"

            frame_desc = (
                "\n".join(
                    f"[{_fmt_ts(f['timestamp'])}] {f['description']}"
                    for f in matched_frames
                )
                if matched_frames
                else None
            )
            save_segment(
                media_id=media_id,
                chunk_index=chunk["chunk_index"],
                text=chunk["text"],
                start_time=chunk["start"],
                end_time=chunk["end"],
                embedding=embedding,
                frame_description=frame_desc,
            )

    return chunks, t_embed()


@traceable(name="ingest.request", run_type="chain")
def run_ingest(
    job_id: str,
    media_id: str,
    file_path: str,
    filename: str,
    job_store: Dict[str, Dict[str, Any]],
    source: str = "app",
) -> None:
    """미디어 1건을 전사·비전·교정·임베딩 단계로 돌려 저장까지 마친다.

    job_store에 status 전이(transcribing → analyzing_frames → embedding → ready/failed)와
    최종 결과(media_id, latency_ms, stats, error)를 in-place로 기록한다. HTTP 상태 관리는
    route 레이어가 담당하지만, 파이프라인 진행 상태 전이 자체는 오케스트레이션 내부 관심사라
    이 함수 안에서 갱신한다.
    """
    try:
        is_video = _is_video_file(filename)
        st = StageTimer()

        snapshot = attach_config_to_run(source)
        job_store[job_id]["config"] = snapshot

        job_store[job_id]["status"] = "transcribing"
        segments, audio_extract_ms, transcribe_ms = _trace_transcribe(
            file_path, media_id, is_video
        )
        st.record("audio_extract", audio_extract_ms)
        st.record("transcribe", transcribe_ms)

        duration = segments[-1]["end"] if segments else 0.0
        full_transcript = " ".join(seg["text"].strip() for seg in segments)
        save_media_file(
            media_id=media_id,
            filename=filename,
            file_type="video" if is_video else "audio",
            duration=duration,
            metadata={"source": source, "config": snapshot},
            full_transcript=full_transcript,
            file_path=file_path,
        )

        frame_analyses: List[Dict[str, Any]] = []
        frame_count = 0
        if is_video:
            job_store[job_id]["status"] = "analyzing_frames"
            frame_analyses, vision_ms = _trace_vision(file_path, media_id)
            st.record("vision_total", vision_ms)
            frame_count = len(frame_analyses)

        correction_cfg = get_stage_config().correction
        if correction_cfg.enabled and frame_analyses:
            segments = correct_transcription_with_vision(
                segments, frame_analyses, cfg=correction_cfg
            )

        job_store[job_id]["status"] = "embedding"
        chunks, embed_ms = _trace_embed(media_id, segments, frame_analyses)
        st.record("embed_save", embed_ms)

        update_media_status(media_id, "ready", segment_count=len(chunks))

        job_store[job_id]["status"] = "ready"
        job_store[job_id]["media_id"] = media_id
        job_store[job_id]["latency_ms"] = st.result
        job_store[job_id]["stats"] = {
            "duration_seconds": duration,
            "segment_count": len(chunks),
            "frame_count": frame_count,
        }

    except OpenAIAuthError:
        job_store[job_id]["status"] = "failed"
        job_store[job_id]["error"] = (
            "OpenAI API 키가 유효하지 않습니다. OPENAI_API_KEY를 확인하세요."
        )
        try:
            update_media_status(media_id, "failed")
        except Exception:
            pass
    except SupabaseOperationError as e:
        job_store[job_id]["status"] = "failed"
        job_store[job_id]["error"] = str(e)
    except Exception as e:
        job_store[job_id]["status"] = "failed"
        job_store[job_id]["error"] = str(e)
        try:
            update_media_status(media_id, "failed")
        except Exception:
            pass
        raise
