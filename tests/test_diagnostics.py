"""
diagnostics.attach_* helper 테스트.

LangSmith run이 있을 때와 없을 때의 부작용을 검증한다. 실제 LangSmith 서버
호출은 필요 없고, get_current_run_tree만 mock해서 RunTree 인터페이스 사용
여부만 관찰한다.
"""

from unittest.mock import MagicMock

import pytest

from app import diagnostics
from app.config import get_stage_config


class TestAttachConfigToRun:
    def test_returns_snapshot_even_when_run_is_none(self, monkeypatch):
        """LANGCHAIN_TRACING_V2=false처럼 run이 None인 환경에서도 snapshot은 반환돼야 한다."""
        monkeypatch.setattr(diagnostics, "get_current_run_tree", lambda: None)
        snap = diagnostics.attach_config_to_run("app")
        assert isinstance(snap, dict)
        assert "transcription_provider" in snap

    def test_attaches_inputs_and_metadata_when_run_exists(self, monkeypatch):
        fake_run = MagicMock()
        monkeypatch.setattr(diagnostics, "get_current_run_tree", lambda: fake_run)

        snap = diagnostics.attach_config_to_run("app")

        fake_run.add_inputs.assert_called_once()
        fake_run.add_metadata.assert_called_once()
        input_payload = fake_run.add_inputs.call_args[0][0]
        meta_payload = fake_run.add_metadata.call_args[0][0]
        assert input_payload == meta_payload
        assert input_payload["source"] == "app"
        assert input_payload["config"] is snap

    def test_source_is_propagated(self, monkeypatch):
        fake_run = MagicMock()
        monkeypatch.setattr(diagnostics, "get_current_run_tree", lambda: fake_run)

        diagnostics.attach_config_to_run("evals")

        assert fake_run.add_inputs.call_args[0][0]["source"] == "evals"
        assert fake_run.add_metadata.call_args[0][0]["source"] == "evals"


class TestAttachStageCfgToRun:
    def test_no_op_when_run_is_none(self, monkeypatch):
        monkeypatch.setattr(diagnostics, "get_current_run_tree", lambda: None)
        cfg = get_stage_config().transcription
        # 예외 없이 반환돼야 한다
        assert diagnostics.attach_stage_cfg_to_run("transcription", cfg) is None

    def test_attaches_stage_slice(self, monkeypatch):
        fake_run = MagicMock()
        monkeypatch.setattr(diagnostics, "get_current_run_tree", lambda: fake_run)
        cfg = get_stage_config().vision

        diagnostics.attach_stage_cfg_to_run("vision", cfg)

        payload = fake_run.add_inputs.call_args[0][0]
        assert set(payload.keys()) == {"vision_cfg"}
        assert payload["vision_cfg"] == cfg.model_dump()
        assert fake_run.add_metadata.call_args[0][0] == payload


class TestPipelineSignatures:
    """source 파라미터가 루트 pipeline 함수에 노출되어 있는지 확인한다."""

    def test_run_ingest_accepts_source(self):
        import inspect

        from app.pipelines.ingest_pipeline import run_ingest

        params = inspect.signature(run_ingest).parameters
        assert "source" in params
        assert params["source"].default == "app"

    def test_run_qa_accepts_source(self):
        import inspect

        from app.pipelines.qa_pipeline import run_qa

        params = inspect.signature(run_qa).parameters
        assert "source" in params
        assert params["source"].default == "app"
