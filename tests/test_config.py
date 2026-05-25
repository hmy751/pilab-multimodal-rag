"""
Config 회귀 테스트.

provider 분리, embedding_dim 모델 기준 결정, Stage Config 빌드를 검증한다.
"""

import os
from unittest.mock import patch

import pytest


class TestEmbeddingDim:
    """embedding_dim이 embedding_provider + 모델명 기준으로 결정되는지 검증한다."""

    def test_local_nomic(self):
        from app.config import Config

        cfg = Config()
        cfg.embedding_provider = "local"
        cfg.ollama_embed_model = "nomic-embed-text"
        assert cfg.embedding_dim == 768

    def test_local_bge_m3(self):
        from app.config import Config

        cfg = Config()
        cfg.embedding_provider = "local"
        cfg.ollama_embed_model = "bge-m3"
        assert cfg.embedding_dim == 1024

    def test_openai_small(self):
        from app.config import Config

        cfg = Config()
        cfg.embedding_provider = "openai"
        cfg.openai_embedding_model = "text-embedding-3-small"
        assert cfg.embedding_dim == 1536

    def test_openai_large(self):
        from app.config import Config

        cfg = Config()
        cfg.embedding_provider = "openai"
        cfg.openai_embedding_model = "text-embedding-3-large"
        assert cfg.embedding_dim == 3072

    def test_unknown_model_fallback(self):
        from app.config import Config

        cfg = Config()
        cfg.embedding_provider = "local"
        cfg.ollama_embed_model = "unknown-model"
        assert cfg.embedding_dim == 768

    @patch.dict(os.environ, {"EMBEDDING_DIM": "512"})
    def test_env_override(self):
        from app.config import Config

        cfg = Config()
        cfg.embedding_provider = "openai"
        assert cfg.embedding_dim == 512


class TestProviderSeparation:
    """역할별 provider가 독립적으로 동작하는지 검증한다."""

    def test_no_ghost_provider_field(self):
        from app.config import Config

        cfg = Config()
        assert not hasattr(cfg, "provider")

    def test_stage_providers_exist(self):
        from app.config import Config

        cfg = Config()
        for attr in (
            "transcribe_provider",
            "vision_provider",
            "chat_provider",
            "embedding_provider",
            "judge_provider",
        ):
            assert hasattr(cfg, attr)


class TestStageConfig:
    """get_stage_config()가 올바르게 빌드되는지 검증한다."""

    def test_stage_config_builds(self):
        from app.config import get_stage_config

        cfg = get_stage_config()
        assert cfg.transcription.provider
        assert cfg.vision.provider
        assert cfg.embedding.provider
        assert cfg.qa.provider
        assert cfg.judge.provider

    def test_embedding_dim_in_stage_config(self):
        from app.config import get_stage_config

        cfg = get_stage_config()
        assert isinstance(cfg.embedding.embedding_dim, int)
        assert cfg.embedding.embedding_dim > 0


class TestDefaultParams:
    """파이프라인 기본 파라미터가 보존되는지 검증한다."""

    def test_chunking_params(self):
        from app.config import Config

        cfg = Config()
        assert cfg.chunk_window_seconds == 20.0
        assert cfg.chunk_overlap_seconds == 5.0

    def test_search_params(self):
        from app.config import Config

        cfg = Config()
        assert cfg.search_threshold == 0.3
        assert cfg.top_k == 3
