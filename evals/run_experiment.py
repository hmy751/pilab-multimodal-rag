"""
run_experiment.py — 실험 자동화 CLI

사용법:
  # baseline: target에 필요한 단계를 전부 fresh 실행
  pipenv run python evals/run_experiment.py --target qa --dataset galaxy-trifold

  # compare: changed + downstream만 fresh, 나머지 필요 단계는 fixture 재사용
  pipenv run python evals/run_experiment.py --changed vision --target qa --dataset galaxy-trifold

  # QA만 재실행 (DB 기존 세그먼트 사용)
  pipenv run python evals/run_experiment.py --changed qa --target qa --media-id <id>

파일 구조:
  _common.py   — 상수, config/prompt 스냅샷, fixture I/O, 타이밍
  _planner.py  — CLI 검증, 실행 계획 수립 (fresh/fixture/skip)
  _stages.py   — 단계별 실행 함수 (transcribe, vision, embed, qa)
  run_experiment.py — 이 파일. 파싱 → 계획 → 실행 → 저장
"""

import argparse
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evals._common import (
    STAGES,
    find_media_id_or_exit,
    get_config_snapshot,
    get_prompt_snapshot,
    load_dataset,
    load_fixture_or_exit,
    save_result,
)
from evals._planner import determine_execution_plan, print_plan, validate_args
from evals._stages import run_embed_and_save, run_qa, run_transcribe, run_vision


def parse_args():
    parser = argparse.ArgumentParser(description="멀티모달 RAG 실험 자동화")
    parser.add_argument(
        "--target",
        required=True,
        choices=STAGES,
        help="어떤 결과물을 만들 것인가",
    )
    parser.add_argument(
        "--changed",
        help="내가 뭘 바꿨는가 (쉼표 구분 가능: transcribe,vision)",
    )
    parser.add_argument("--dataset", help="데이터셋 이름 (datasets/{name}/)")
    parser.add_argument("--media-id", help="DB의 기존 세그먼트 사용 (QA 전용)")
    parser.add_argument("--label", help="실험 라벨 (결과 파일명에 사용)")
    return parser.parse_args()


def main():
    args = parse_args()
    changed_stages = validate_args(args)

    plan = determine_execution_plan(args.target, changed_stages)
    print_plan(plan, args.target, changed_stages, args.dataset, args.media_id)

    config_snapshot = get_config_snapshot()
    prompt_snapshot = get_prompt_snapshot()
    latency = {}

    segments = None
    frame_analyses = None
    media_id = args.media_id
    dataset_info = load_dataset(args.dataset) if args.dataset else None

    # ── transcribe ──
    if plan["transcribe"] == "fresh":
        segments, latency["transcribe"] = run_transcribe(
            dataset_info["source_path"], args.dataset, config_snapshot
        )
    elif plan["transcribe"] == "fixture":
        segments = load_fixture_or_exit(
            "segments", args.dataset, config_snapshot, args.target
        )
        print(f"[transcribe] fixture 재사용 ({len(segments)}개 세그먼트)")

    # ── vision ──
    if plan["vision"] == "fresh":
        frame_analyses, latency["vision_total"] = run_vision(
            dataset_info["source_path"], args.dataset, config_snapshot
        )
    elif plan["vision"] == "fixture":
        frame_analyses = load_fixture_or_exit(
            "frame_analyses", args.dataset, config_snapshot, args.target
        )
        print(f"[vision] fixture 재사용 ({len(frame_analyses)}개 프레임)")

    # ── embed ──
    if plan["embed"] == "fresh":
        media_id, latency["embed_save"] = run_embed_and_save(
            segments, frame_analyses, config_snapshot
        )
    elif plan["embed"] == "fixture":
        media_id = find_media_id_or_exit(args.dataset, config_snapshot)

    # ── qa ──
    if plan["qa"] == "fresh":
        if not dataset_info or not dataset_info["questions"]:
            sys.exit("[ERROR] 질문 세트가 비어있습니다.")

        qa_results, metrics, latency["qa_total"] = run_qa(
            media_id, dataset_info["questions"], dataset_info["reference"]
        )

        result = {
            "label": args.label or "experiment",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "media_id": media_id,
            "dataset": args.dataset,
            "mode": "baseline" if changed_stages is None else "compare",
            "changed": changed_stages,
            "target": args.target,
            "config": config_snapshot,
            "prompts": prompt_snapshot,
            "latency_ms": latency,
            "qa_results": qa_results,
            "metrics": metrics,
        }

        path = save_result(result, args.label)
        print(f"\n[결과 저장] {path}")
    elif plan["qa"] == "skip":
        print(f"\n[완료] --target {args.target}까지 실행 완료")
        if segments:
            print(f"  segments: {len(segments)}개")
        if frame_analyses:
            print(f"  frame_analyses: {len(frame_analyses)}개")
        if media_id and plan["embed"] == "fresh":
            print(f"  media_id: {media_id}")

    print(f"\n소요 시간: {latency}")


if __name__ == "__main__":
    main()
