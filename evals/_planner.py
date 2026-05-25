"""
_planner.py — 실행 계획 수립

CLI 인자를 검증하고, 파이프라인 각 단계의 실행 방식(fresh/fixture/skip)을 결정한다.

파이프라인 구조:
    transcribe ─┐
                ├→ embed → qa
    vision ─────┘
"""

import sys
from argparse import Namespace
from typing import List, Optional

from evals._common import AFFECTS_DOWNSTREAM, STAGES, TARGET_REQUIREMENTS


def validate_args(args: Namespace) -> Optional[List[str]]:
    """CLI 인자 조합의 유효성을 검증한다.

    Args:
        args: argparse 결과. 필수 속성: target, dataset, media_id, changed.

    Returns:
        changed 단계 리스트. --changed 없으면 None.
    """
    if not args.dataset and not args.media_id:
        sys.exit("[ERROR] --dataset 또는 --media-id 중 하나를 지정하세요.")

    if args.media_id and args.target != "qa":
        sys.exit("[ERROR] --media-id는 --target qa와만 사용할 수 있습니다.")

    if args.media_id and args.dataset:
        sys.exit("[ERROR] --media-id와 --dataset은 동시에 사용할 수 없습니다.")

    if not args.changed:
        return None

    changed_stages = [s.strip() for s in args.changed.split(",")]
    required = TARGET_REQUIREMENTS[args.target]

    for s in changed_stages:
        if s not in STAGES:
            sys.exit(f"[ERROR] 알 수 없는 단계: {s}")
        if not (AFFECTS_DOWNSTREAM[s] & required):
            sys.exit(
                f"[ERROR] --changed {s}는 --target {args.target}에 영향을 주지 않습니다."
            )

    return changed_stages


def determine_execution_plan(target: str, changed_stages: Optional[List[str]]) -> dict:
    """각 단계별 실행 방식을 결정한다.

    target을 만들기 위해 필요한 최소 단계(required)를 구하고,
    그 안에서 fresh/fixture/skip을 결정한다.

    규칙:
        - baseline (changed 없음): required 전부 fresh
        - compare (changed 있음): changed + downstream ∩ required = fresh, 나머지 required = fixture

    Returns:
        dict: {stage: "fresh" | "fixture" | "skip"}
    """
    required = TARGET_REQUIREMENTS[target]

    if changed_stages is None:
        return {stage: "fresh" if stage in required else "skip" for stage in STAGES}

    fresh_set = set()
    for cs in changed_stages:
        fresh_set |= AFFECTS_DOWNSTREAM[cs]
    fresh_set &= required

    return {
        stage: (
            "fresh"
            if stage in fresh_set
            else "fixture" if stage in required else "skip"
        )
        for stage in STAGES
    }


def print_plan(plan, target, changed_stages, dataset=None, media_id=None):
    """실행 계획을 출력한다."""
    mode = "baseline" if changed_stages is None else "compare"
    source = f"dataset={dataset}" if dataset else f"media-id={media_id}"
    changed_str = ",".join(changed_stages) if changed_stages else "-"

    print(f"\n{'='*50}")
    print(f"  mode: {mode} | target: {target} | changed: {changed_str}")
    print(f"  source: {source}")
    print(f"{'='*50}")

    for stage in STAGES:
        action = plan.get(stage, "skip")
        icon = {"fresh": "🔄", "fixture": "📦", "skip": "─"}[action]
        print(f"  {icon} {stage:15s} → {action}")
    print()
