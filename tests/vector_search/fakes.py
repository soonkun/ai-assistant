# tests/vector_search/fakes.py
"""FakeEmbedder: 결정론적 hash 기반 1024차원 벡터 생성 (BGE-M3 실모델 불필요)."""

from __future__ import annotations

import hashlib

import numpy as np


class FakeEmbedder:
    """결정론적 해시 기반 1024차원 벡터를 반환하는 테스트용 Embedder.

    동일 텍스트 → 동일 벡터. L2 정규화 포함.
    BGE-M3 실모델 없이도 VectorStore, RagService 테스트 가능.
    """

    DIM: int = 1024

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self.DIM), dtype=np.float32)
        result = np.stack([self._text_to_vec(t) for t in texts], axis=0)
        return result.astype(np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        sanitized = text if text.strip() else " "
        return self._text_to_vec(sanitized)

    def _text_to_vec(self, text: str) -> np.ndarray:
        """텍스트 해시 기반 결정론적 1024차원 L2 정규화 벡터."""
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        # 32바이트 seed → numpy rng seed
        seed = int.from_bytes(digest[:4], "big")
        rng = np.random.default_rng(seed)
        vec = rng.standard_normal(self.DIM).astype(np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec
