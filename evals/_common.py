"""
_common.py — evals 공유 유틸리티

config 스냅샷, fixture I/O, 타이밍 계측, 실험 결과 JSON 저장
"""

import json
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from app.snapshot import get_config_snapshot, get_prompt_snapshot  # noqa: F401

EVALS_DIR = Path(__file__).parent
FIXTURES_DIR = EVALS_DIR / "fixtures"
RESULTS_DIR = EVALS_DIR / "results"
DATASETS_DIR = EVALS_DIR / "datasets"

# 파이프라인 단계 순서 (포크 구조에서의 토폴로지 순서)
STAGES = ("transcribe", "vision", "embed", "qa")

# target을 만들기 위해 필요한 최소 단계 집합
TARGET_REQUIREMENTS = {
    "transcribe": {"transcribe"},
    "vision": {"vision"},
    "embed": {"transcribe", "vision", "embed"},
    "qa": {"transcribe", "vision", "embed", "qa"},
}

# changed가 영향을 미치는 단계 집합 (자기 자신 포함)
AFFECTS_DOWNSTREAM = {
    "transcribe": {"transcribe", "embed", "qa"},
    "vision": {"vision", "embed", "qa"},
    "embed": {"embed", "qa"},
    "qa": {"qa"},
}

# fixture별 config fingerprint 키
# 각 fixture는 자기 stage의 provider를 참조한다 (기존 단일 "provider" 키 제거).
FINGERPRINT_KEYS = {
    # ── Transcription fixture ──
    "segments": (
        "transcription_provider",
        "whisper_model_size",
        "openai_whisper_model",
        "whisper_prompt_version",
    ),
    # ── Vision fixture ──
    "frame_analyses": (
        "vision_provider",
        "vision_model",
        "prompt_version",
        "frames_per_minute",
    ),
    # ── Embed~QA (media_id) ──
    # DB에만 저장되므로 fixture 파일이 없다.
    # results/에서 동일 조건의 실험 결과를 찾아 media_id를 재사용한다.
    "media_id": (
        # transcription
        "transcription_provider",
        "whisper_model_size",
        "openai_whisper_model",
        "whisper_prompt_version",
        # vision
        "vision_provider",
        "vision_model",
        "prompt_version",
        "frames_per_minute",
        # correction — ON/OFF나 prompt 버전이 다르면 다른 DB 행이 생성됨
        "use_correction",
        "correction_prompt_version",
        # embedding
        "embedding_provider",
        "embed_model",
        "embedding_dim",
        "chunk_window_seconds",
        "chunk_overlap_seconds",
    ),
}


# ── 타이밍 ──


@contextmanager
def timer():
    """with timer() as t: ... → t() 호출하면 경과 ms 반환."""
    start = time.perf_counter()
    elapsed = {}

    def get_ms():
        return elapsed.get("ms", round((time.perf_counter() - start) * 1000))

    try:
        yield get_ms
    finally:
        elapsed["ms"] = round((time.perf_counter() - start) * 1000)


# ── fixture I/O ──


def _fixture_path(fixture_type: str, dataset: str) -> Path:
    return FIXTURES_DIR / f"{fixture_type}_{dataset}.json"


def save_fixture(fixture_type: str, dataset: str, data: list, config: dict, **meta):
    """fixture를 JSON으로 저장한다. config + data를 함께 기록."""
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset": dataset,
        "config": config,
        **meta,
        "data": data,
    }
    path = _fixture_path(fixture_type, dataset)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    return path


def load_fixture(fixture_type: str, dataset: str) -> dict:
    """fixture를 읽는다. 없으면 None을 반환한다."""
    path = _fixture_path(fixture_type, dataset)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def validate_fixture_fingerprint(
    fixture: dict, fixture_type: str, current_config: dict
) -> tuple[bool, list[str]]:
    """fixture의 config가 현재 config와 일치하는지 검증한다.

    fixture 저장 시 config에 필요한 키를 모두 포함하므로,
    fixture.config vs current_config를 FINGERPRINT_KEYS 기준으로 비교하면 된다.

    Returns:
        (valid, mismatches): valid=True면 재사용 가능, mismatches는 불일치 키 목록
    """
    keys = FINGERPRINT_KEYS.get(fixture_type, ())
    fixture_config = fixture.get("config", {})
    mismatches = []

    for key in keys:
        fixture_val = fixture_config.get(key)
        current_val = current_config.get(key)
        if fixture_val != current_val:
            mismatches.append(f"{key}: fixture={fixture_val} → current={current_val}")

    return len(mismatches) == 0, mismatches


def load_fixture_or_exit(
    fixture_type: str, dataset: str, config_snapshot: dict, target: str
) -> list:
    """fixture를 로드하고 fingerprint를 검증한다. 없거나 불일치하면 sys.exit으로 종료.

    main()에서 transcribe/vision fixture 로드 패턴이 동일하므로 헬퍼로 추출.

    Returns:
        list: fixture["data"]
    """
    path = _fixture_path(fixture_type, dataset)
    fixture = load_fixture(fixture_type, dataset)
    if fixture is None:
        sys.exit(
            f"[ERROR] {fixture_type} fixture가 없습니다.\n"
            f"  → baseline을 먼저 실행하세요: "
            f"pipenv run python evals/run_experiment.py --target {target} --dataset {dataset}"
        )

    print(
        f"[fixture] {path.name} 로드 완료 (created: {fixture.get('created_at', '?')})"
    )

    valid, mismatches = validate_fixture_fingerprint(
        fixture, fixture_type, config_snapshot
    )
    if not valid:
        sys.exit(
            f"[ERROR] {fixture_type} fixture의 config가 현재와 다릅니다:\n"
            + "\n".join(f"  - {m}" for m in mismatches)
            + "\n  → baseline을 다시 실행하세요."
        )

    keys = FINGERPRINT_KEYS.get(fixture_type, ())
    fingerprint = {k: fixture.get("config", {}).get(k) for k in keys}
    print(f"[fixture] fingerprint 검증 통과: {fingerprint}")

    return fixture["data"]


# ── media_id 탐색 ──


def find_media_id_or_exit(dataset: str, config_snapshot: dict) -> str:
    """results/에서 동일 dataset + config fingerprint인 실험 결과를 찾아 media_id를 반환한다.

    embed 단계는 fixture 파일이 없고 DB에만 결과가 존재하므로,
    이전 실험 결과 JSON에서 media_id를 가져온다.

    탐색 순서: 가장 최근(timestamp 역순) 결과부터 검사.

    Returns:
        str: media_id
    """
    if not RESULTS_DIR.exists():
        sys.exit(
            f"[ERROR] results/ 디렉토리가 없습니다.\n"
            f"  → baseline을 먼저 실행하세요: "
            f"pipenv run python evals/run_experiment.py --target qa --dataset {dataset}"
        )

    keys = FINGERPRINT_KEYS["media_id"]

    # 결과 파일을 최신순으로 정렬
    result_files = sorted(RESULTS_DIR.glob("exp_*.json"), reverse=True)

    for path in result_files:
        try:
            result = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        if result.get("dataset") != dataset:
            continue
        if not result.get("media_id"):
            continue

        # fingerprint 검증
        result_config = result.get("config", {})
        mismatches = []
        for key in keys:
            result_val = result_config.get(key)
            if result_val != config_snapshot.get(key):
                mismatches.append(
                    f"{key}: result={result_val} → current={config_snapshot.get(key)}"
                )

        if not mismatches:
            media_id = result["media_id"]
            print(f"[embed] 이전 실험에서 media_id 탐색 완료: {media_id}")
            print(f"  source: {path.name} ({result.get('timestamp', '?')})")
            fingerprint = {k: result_config.get(k) for k in keys}
            print(f"  fingerprint 검증 통과: {fingerprint}")
            return media_id

    # 매칭 실패
    current_fp = {k: config_snapshot.get(k) for k in keys}
    sys.exit(
        f"[ERROR] dataset={dataset}에 대해 현재 config와 일치하는 media_id를 찾을 수 없습니다.\n"
        f"  현재 config: {current_fp}\n"
        f"  → baseline을 먼저 실행하세요: "
        f"pipenv run python evals/run_experiment.py --target qa --dataset {dataset}"
    )


# ── 결과 저장 ──


def save_result(result: dict, label: str = None) -> Path:
    """실험 결과 JSON을 results/에 저장한다."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    name = f"exp_{label}_{ts}.json" if label else f"exp_{ts}.json"
    path = RESULTS_DIR / name
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return path


# ── 데이터셋 ──


def load_dataset(dataset: str) -> dict:
    """datasets/{dataset}/ 에서 questions.json과 reference.txt를 읽는다.

    Returns:
        {"name": str, "questions": list, "reference": str|None, "source_path": str|None}
    """
    ds_dir = DATASETS_DIR / dataset
    if not ds_dir.exists():
        raise FileNotFoundError(f"데이터셋 '{dataset}'을 찾을 수 없습니다: {ds_dir}")

    questions_path = ds_dir / "questions.json"
    if not questions_path.exists():
        raise FileNotFoundError(f"questions.json이 없습니다: {questions_path}")

    questions = json.loads(questions_path.read_text())

    reference_path = ds_dir / "reference.txt"
    reference = reference_path.read_text().strip() if reference_path.exists() else None

    source_path = ds_dir / "source.mp4"
    if not source_path.exists():
        # 심링크나 다른 확장자 검색
        sources = list(ds_dir.glob("source.*"))
        source_path = sources[0] if sources else None

    return {
        "name": dataset,
        "questions": questions,
        "reference": reference,
        "source_path": str(source_path) if source_path else None,
    }
