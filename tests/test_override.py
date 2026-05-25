"""
override_config() context manager 테스트.

저장/복원, 예외 시 복원, 중첩 override, 잘못된 인자 처리를 검증한다.
"""

import pytest

from app.config import CONFIG, override_config


class TestOverrideConfig:
    def test_value_changes_inside_block(self):
        original = CONFIG.frames_per_minute
        with override_config(vision={"frames_per_minute": 99}):
            assert CONFIG.frames_per_minute == 99
        assert CONFIG.frames_per_minute == original

    def test_value_restored_after_block(self):
        original = CONFIG.chunk_window_seconds
        with override_config(embedding={"chunk_window_seconds": 999.0}):
            pass
        assert CONFIG.chunk_window_seconds == original

    def test_value_restored_on_exception(self):
        original = CONFIG.top_k
        try:
            with override_config(retrieval={"top_k": 50}):
                assert CONFIG.top_k == 50
                raise RuntimeError("의도적 예외")
        except RuntimeError:
            pass
        assert CONFIG.top_k == original

    def test_multiple_stages_overridden(self):
        orig_fpm = CONFIG.frames_per_minute
        orig_topk = CONFIG.top_k
        with override_config(
            vision={"frames_per_minute": 10},
            retrieval={"top_k": 20},
        ):
            assert CONFIG.frames_per_minute == 10
            assert CONFIG.top_k == 20
        assert CONFIG.frames_per_minute == orig_fpm
        assert CONFIG.top_k == orig_topk

    def test_nested_override_restores_correctly(self):
        orig = CONFIG.frames_per_minute
        with override_config(vision={"frames_per_minute": 5}):
            with override_config(vision={"frames_per_minute": 10}):
                assert CONFIG.frames_per_minute == 10
            assert CONFIG.frames_per_minute == 5
        assert CONFIG.frames_per_minute == orig

    def test_unknown_stage_raises(self):
        with pytest.raises(ValueError, match="알 수 없는 stage"):
            with override_config(nonexistent={"foo": 1}):
                pass

    def test_unknown_field_raises(self):
        with pytest.raises(ValueError, match="알 수 없는 필드"):
            with override_config(vision={"nonexistent_field": 1}):
                pass

    def test_get_stage_config_reflects_override(self):
        from app.config import get_stage_config
        orig = CONFIG.frames_per_minute
        with override_config(vision={"frames_per_minute": 42}):
            cfg = get_stage_config()
            assert cfg.vision.frames_per_minute == 42
        assert get_stage_config().vision.frames_per_minute == orig
