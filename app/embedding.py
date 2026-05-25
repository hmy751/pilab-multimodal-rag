"""
embedding.py — 텍스트 임베딩 (ingest + qa 공유 도메인)

임베딩은 ingest에서는 문서 청크를 벡터화하고, qa에서는 쿼리를 벡터화하는
양쪽 경계에 걸쳐 있어 특정 도메인 폴더에 속하지 않는다. 기능 단위 이름으로
루트에 독립시키되, /shared/ 같은 범용 서랍장은 만들지 않는다.

LangSmith trace에는 여러 맥락이 섞이지 않도록 얇은 래퍼로 분리한다:
- embed_query                (qa.1_embed_query)        : 질문 1건을 쿼리 벡터로
- embed_chunk                (ingest.8_embed_chunk)    : ingest 중 청크 1건을 문서 벡터로
- embed_segment_for_boundary (ingest.6.1_embed_boundary): semantic 청킹의 경계 탐지용 segment 임베딩
세 함수 모두 같은 내부 로직(_embed_text)을 호출하지만 trace 이름과 도메인이
다르므로 LangSmith UI에서 충돌 없이 필터·집계가 가능하다.
"""

import time
from typing import List

import requests
from langsmith import traceable

from .config import EmbeddingCfg, get_stage_config


def _embed_text(text: str, cfg: EmbeddingCfg | None = None) -> List[float]:
    cfg = cfg or get_stage_config().embedding
    if cfg.provider == "openai":
        from openai import OpenAI, RateLimitError

        client = OpenAI(api_key=cfg.openai_api_key)
        for attempt in range(5):
            try:
                resp = client.embeddings.create(
                    model=cfg.openai_embedding_model,
                    input=text,
                    dimensions=cfg.embedding_dim,
                )
                return resp.data[0].embedding
            except RateLimitError:
                wait = min(2**attempt, 10)
                print(
                    f"[embedding] Rate limit hit, retrying in {wait}s... ({attempt + 1}/5)"
                )
                time.sleep(wait)
        raise RuntimeError("OpenAI embedding rate limit: 5회 재시도 후에도 실패")
    else:
        response = requests.post(
            f"{cfg.ollama_base}/api/embeddings",
            json={"model": cfg.ollama_embed_model, "prompt": text},
        )
        return response.json()["embedding"]


@traceable(name="qa.1_embed_query", run_type="embedding")
def embed_query(text: str, cfg: EmbeddingCfg | None = None) -> List[float]:
    """사용자 질문을 벡터로 임베딩 (QA 파이프라인 전용 trace 이름)."""
    return _embed_text(text, cfg)


@traceable(name="ingest.8_embed_chunk", run_type="embedding")
def embed_chunk(text: str, cfg: EmbeddingCfg | None = None) -> List[float]:
    """ingest 중 멀티모달 컨텍스트(청크+프레임) 1건을 벡터로 임베딩."""
    return _embed_text(text, cfg)


@traceable(name="ingest.6.1_embed_boundary", run_type="embedding")
def embed_segment_for_boundary(
    text: str, cfg: EmbeddingCfg | None = None
) -> List[float]:
    """semantic 청킹의 경계 탐지용 segment 임베딩.

    chunk 임베딩(embed_chunk)과 목적이 다르다. 이 결과는 DB에 저장되지 않고
    오직 인접 segment 간 유사도 계산에만 쓰인다.
    """
    return _embed_text(text, cfg)
