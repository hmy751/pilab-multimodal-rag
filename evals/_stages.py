"""
_stages.py — 파이프라인 단계별 실행 함수

evals는 pipeline과 동일한 stage 경계를 사용하므로 각 stage를 app 쪽 pipeline helper에
위임한다. 덕분에 trace leaf가 고아 run으로 흩어지지 않고 `ingest.transcribe`,
`ingest.vision`, `ingest.embed`, `qa.request`가 각각 stage root로 묶여서 찍힌다.

- `_trace_*` helper 직접 호출 허용 근거: `.claude/rules/app-구조.md` §3 예외 조항.
- fixture 저장, audio/frames 임시파일 정리, media_files 행 life-cycle은 evals 고유 관심사.

각 함수는 (결과, 소요시간) 또는 evals 호출부가 기대하는 튜플을 반환한다.
"""

import os
import shutil
import uuid
from typing import Any, Dict, List, Optional, Tuple

from app.config import CONFIG, get_stage_config

from evals._common import save_fixture, timer

# evals 경로에서 _trace_* helper를 root로 부를 때 LangSmith run에 주입할 공통 표식.
# run_qa/run_ingest는 source 인자로 동일 효과를 보지만, _trace_*는 시그니처 변경을
# 피하려고 langsmith_extra(metadata+tags)로 대체한다.
_EVALS_TRACE_EXTRA = {"metadata": {"source": "evals"}, "tags": ["evals"]}

# ── transcribe ──


def run_transcribe(
    source_path: str, dataset: str, config_snapshot: dict
) -> Tuple[List[Dict], int]:
    """전사 stage 실행 + segments fixture 저장.

    pipeline helper(_trace_transcribe)를 호출하므로 오디오 추출·전사가
    `ingest.transcribe` root 아래 leaf(`ingest.1_audio_extract`,
    `ingest.2_transcribe`)로 묶인다.

    Returns:
        (segments, latency_ms)  — latency는 오디오 추출 + 전사 합산
    """
    from app.pipelines.ingest_pipeline import _trace_transcribe

    # audio 임시 파일 경로 충돌을 피하려고 실행마다 유니크한 id 부여
    temp_media_id = f"eval_{uuid.uuid4().hex[:8]}"
    audio_path = os.path.join(CONFIG.upload_dir, f"{temp_media_id}_audio.wav")

    print("[transcribe] 전사 stage 실행 중...")
    try:
        segments, audio_ms, transcribe_ms = _trace_transcribe(
            source_path, temp_media_id, is_video=True,
            langsmith_extra=_EVALS_TRACE_EXTRA,
        )
    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)

    total_ms = audio_ms + transcribe_ms
    print(f"[transcribe] 완료: {len(segments)}개 세그먼트 ({total_ms}ms)")

    save_fixture(
        "segments",
        dataset,
        segments,
        {
            "transcription_provider": config_snapshot["transcription_provider"],
            "whisper_model_size": config_snapshot["whisper_model_size"],
            "openai_whisper_model": config_snapshot["openai_whisper_model"],
            "whisper_prompt_version": config_snapshot.get("whisper_prompt_version", ""),
        },
        latency_ms=transcribe_ms,
    )

    return segments, total_ms


# ── vision ──


def run_vision(
    source_path: str, dataset: str, config_snapshot: dict
) -> Tuple[List[Dict], int]:
    """비전 stage 실행 + frame_analyses fixture 저장.

    pipeline helper(_trace_vision)를 호출하므로 프레임 추출·분석이
    `ingest.vision` root 아래로 묶이고, 프레임 분석은 pipeline에서 이미 4-worker
    ThreadPoolExecutor로 병렬 처리된다.

    Returns:
        (frame_analyses, latency_ms)
    """
    from app.pipelines.ingest_pipeline import _trace_vision

    temp_media_id = f"eval_{uuid.uuid4().hex[:8]}"
    frames_dir = os.path.join(CONFIG.frames_dir, temp_media_id)

    print("[vision] 비전 stage 실행 중...")
    try:
        frame_analyses, vision_ms = _trace_vision(
            source_path, temp_media_id,
            langsmith_extra=_EVALS_TRACE_EXTRA,
        )
    finally:
        if os.path.exists(frames_dir):
            shutil.rmtree(frames_dir)

    print(f"[vision] 완료: {len(frame_analyses)}개 프레임 ({vision_ms}ms)")

    save_fixture(
        "frame_analyses",
        dataset,
        frame_analyses,
        {
            "vision_provider": config_snapshot["vision_provider"],
            "vision_model": config_snapshot["vision_model"],
            "prompt_version": config_snapshot["prompt_version"],
            "frames_per_minute": config_snapshot["frames_per_minute"],
        },
        latency_ms=vision_ms,
    )

    return frame_analyses, vision_ms


# ── embed ──


def run_embed_and_save(
    segments: List[Dict], frame_analyses: List[Dict], config_snapshot: dict
) -> Tuple[str, int]:
    """Vision-guided 교정 → media_files 행 생성 → 청킹·임베딩·저장 → status=ready.

    청킹·임베딩·세그먼트 저장은 pipeline helper(_trace_embed) 내부에서 수행.
    correction과 media_files 행 life-cycle은 run_ingest의 오케스트레이션 순서를
    그대로 재현한다. 다만 evals용 metadata(source="evals", config snapshot)는 여기서 주입.

    Returns:
        (media_id, latency_ms)  — latency는 correction + embed + status update 합산
    """
    from app.ingest.correction import correct_transcription_with_vision
    from app.pipelines.ingest_pipeline import _trace_embed
    from app.supabase_utils import save_media_file, update_media_status

    media_id = str(uuid.uuid4())

    with timer() as t_total:
        correction_cfg = get_stage_config().correction
        if correction_cfg.enabled and frame_analyses:
            print("[embed] Vision-guided 전사 교정 중...")
            segments = correct_transcription_with_vision(
                segments, frame_analyses, correction_cfg
            )

        total_duration = max((s["end"] for s in segments), default=0)
        full_transcript = " ".join(seg.get("text", "").strip() for seg in segments)
        save_media_file(
            media_id=media_id,
            filename=f"eval_{media_id}",
            file_type="video",
            duration=total_duration,
            metadata={"source": "evals", "config": config_snapshot},
            full_transcript=full_transcript,
        )

        print(f"[embed] 청킹·임베딩 중... (media_id={media_id})")
        chunks, embed_ms = _trace_embed(
            media_id, segments, frame_analyses,
            langsmith_extra=_EVALS_TRACE_EXTRA,
        )

        update_media_status(media_id, "ready", segment_count=len(chunks))

    print(
        f"[embed] {len(chunks)}개 세그먼트 저장 완료 "
        f"(전체 {t_total()}ms, embed 순수 {embed_ms}ms)"
    )
    return media_id, t_total()


# ── qa ──


def run_qa(
    media_id: str,
    questions: List[Dict],
    reference: Optional[str],
) -> Tuple[List[Dict], Dict[str, Any], int]:
    """QA 실행 + 메트릭 계산.

    각 질문마다 pipeline의 run_qa를 호출해서 embedding·retrieval·generation이
    `qa.request` root 아래 묶이게 한다. 메트릭 계산과 WER은 evals 고유 책임.

    Returns:
        (qa_results, metrics, latency_ms)
    """
    # pipeline의 run_qa는 이름이 같으니 alias로 import (evals._stages.run_qa 자신)
    from app.pipelines.qa_pipeline import run_qa as _pipeline_run_qa
    from app.evaluation_utils import (
        calculate_answer_relevance,
        calculate_groundedness,
        calculate_retrieval_precision,
        calculate_wer_cer,
    )
    from app.supabase_utils import get_media_by_id, get_media_segments

    print(f"[qa] {len(questions)}개 질문으로 QA 실행 중...")

    qa_results = []
    with timer() as t_qa_total:
        for i, q in enumerate(questions, 1):
            query = q["query"]
            with timer() as t_question:
                result = _pipeline_run_qa(query, media_id, source="evals")
                all_candidates = result["all_segments"]
                accepted = result["accepted"]
                answer = result["answer"]
                context_text = result["context_text"]

                relevance = calculate_answer_relevance(query, answer)
                groundedness = calculate_groundedness(answer, context_text)
                precision = calculate_retrieval_precision(accepted, query)

            qa_results.append(
                {
                    "test_id": q.get("test_id", f"T{i}"),
                    "test_type": q.get("test_type", ""),
                    "query": query,
                    "answer": answer,
                    "context_text": context_text,
                    "sources": [
                        {
                            "chunk_index": s.get("chunk_index"),
                            "similarity": s.get("similarity"),
                            "accepted": s.get("accepted"),
                            "text": s.get("text", "")[:200],
                        }
                        for s in all_candidates
                    ],
                    "metrics": {
                        "answer_relevance": relevance,
                        "groundedness": groundedness,
                        "retrieval_precision": precision,
                    },
                    "latency_ms": t_question(),
                    "latency_breakdown": result.get("latency_ms"),
                    "trace_id": result.get("trace_id"),
                }
            )
            print(
                f"  [{i}/{len(questions)}] "
                f"AR={relevance:.2f} GR={groundedness:.2f} RP={precision:.2f} "
                f"({t_question()}ms)"
            )

    # WER + CER (reference가 있을 때만)
    wer_score = None
    cer_score = None
    if reference:
        media = get_media_by_id(media_id)
        full_transcript = media.get("full_transcript") if media else None
        if not full_transcript:
            # fallback: full_transcript 컬럼이 없는 기존 데이터
            segments = get_media_segments(media_id)
            full_transcript = " ".join(seg.get("text", "") for seg in segments)
        wer_score, cer_score = calculate_wer_cer(reference, full_transcript)
        print(f"[qa] WER={wer_score:.3f}  CER={cer_score:.3f}")

    def avg(key):
        vals = [r["metrics"][key] for r in qa_results]
        return sum(vals) / len(vals) if vals else 0.0

    metrics = {
        "wer": wer_score,
        "cer": cer_score,
        "answer_relevance": round(avg("answer_relevance"), 4),
        "groundedness": round(avg("groundedness"), 4),
        "retrieval_precision": round(avg("retrieval_precision"), 4),
    }

    print(f"[qa] 완료 ({t_qa_total()}ms)")
    print(f"[qa] 메트릭: {metrics}")

    return qa_results, metrics, t_qa_total()
