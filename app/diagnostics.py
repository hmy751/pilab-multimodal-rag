"""
diagnostics.py — API 응답에 evals 수준 진단 데이터를 실어주는 유틸리티

evals/_common.py가 CLI 실험용이라면, 이 모듈은 런타임 API 응답용이다.
동일한 관심사(config 스냅샷, 타이밍 계측, LangSmith run 부착)를 app 컨텍스트에
맞게 제공한다.
"""

import time
from contextlib import contextmanager
from typing import Any, Dict, Optional

from langsmith.run_helpers import get_current_run_tree
from pydantic import BaseModel

from .snapshot import get_config_snapshot  # noqa: F401 — re-export for callers


# ── LangSmith run 부착 ──
#
# "기록 = 실행" 원칙: 현재 실행된 config를 run.inputs(CSV export의 컬럼)와
# run.metadata(LangSmith UI 필터/그룹핑) 양쪽에 박아둔다. 둘 다 부착하는 이유는
# CSV export와 UI가 서로 다른 소스를 보기 때문이다.


def attach_config_to_run(source: str) -> Dict[str, Any]:
    """루트 traceable 초입에서 호출. config_snapshot 전체를 현재 run에 부착한다.

    Args:
        source: "app" | "evals" | "evaluate" — 어느 경로에서 찍힌 run인지 구분

    Returns:
        이후 Supabase metadata 등에 재사용할 수 있도록 snapshot dict를 돌려준다.
        LangSmith가 꺼져 있을 때(run=None)도 snapshot 자체는 그대로 반환.
    """
    snap = get_config_snapshot()
    payload = {"source": source, "config": snap}
    run = get_current_run_tree()
    if run is not None:
        run.add_inputs(payload)
        run.add_metadata(payload)
    return snap


def attach_stage_cfg_to_run(stage_name: str, cfg: BaseModel) -> None:
    """stage 단위 traceable(`_trace_*`, `run_retrieve`) 초입에서 호출.

    stage 로컬 cfg 하나만 `{stage}_cfg` 키로 박는다. 루트(run_ingest/run_qa)가
    전체 snapshot을 이미 부착하므로 여기선 중복 없이 stage slice만.
    evals가 stage helper를 직접 root로 부를 때도 동일 경로로 기록된다.
    """
    run = get_current_run_tree()
    if run is None:
        return
    payload = {f"{stage_name}_cfg": cfg.model_dump()}
    run.add_inputs(payload)
    run.add_metadata(payload)

# ── 타이밍 계측 ──


@contextmanager
def timer():
    """경과 시간(ms)을 측정하는 컨텍스트 매니저.

    Usage:
        with timer() as elapsed:
            do_work()
        print(elapsed())  # → 1234 (ms)

    yield 시점부터 측정이 시작되며, 블록 종료 후 elapsed()는 최종 값을 반환한다.
    블록 내에서 elapsed()를 호출하면 그 시점까지의 중간 경과 시간을 얻는다.
    """
    start = time.perf_counter()
    snapshot: Dict[str, int] = {}

    def get_ms() -> int:
        return snapshot.get("ms", round((time.perf_counter() - start) * 1000))

    try:
        yield get_ms
    finally:
        snapshot["ms"] = round((time.perf_counter() - start) * 1000)


class StageTimer:
    """process_media_background 같은 다단계 작업의 구간별 latency를 수집한다.

    Usage:
        st = StageTimer()
        with st.measure("transcribe"):
            segments = transcribe_audio(path)
        with st.measure("vision"):
            frames = analyze_frames(...)
        print(st.result)  # {"transcribe": 3200, "vision": 8100, "total": 11300}
    """

    def __init__(self):
        self._start = time.perf_counter()
        self._stages: Dict[str, int] = {}

    @contextmanager
    def measure(self, stage_name: str):
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self._stages[stage_name] = round((time.perf_counter() - t0) * 1000)

    def record(self, stage_name: str, duration_ms: int) -> None:
        self._stages[stage_name] = duration_ms

    @property
    def result(self) -> Dict[str, int]:
        return {
            **self._stages,
            "total": round((time.perf_counter() - self._start) * 1000),
        }
