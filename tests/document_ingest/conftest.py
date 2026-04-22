# tests/document_ingest/conftest.py
"""공통 픽스처: FakeEmbedder, VectorStore, DocumentIngest 인스턴스."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# FakeEmbedder는 M_07 테스트에서 정의된 것을 재사용 (스펙 §11.1)
sys.path.insert(0, str(Path(__file__).parent.parent))
from tests.vector_search.fakes import FakeEmbedder

from vector_search.store import VectorStore
from document_ingest.ingest import DocumentIngest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    return FakeEmbedder()


@pytest.fixture
def tmp_store(tmp_path: Path) -> VectorStore:
    return VectorStore(db_path=str(tmp_path / "lancedb_test"))


@pytest.fixture
def ingest_instance(tmp_store: VectorStore, fake_embedder: FakeEmbedder) -> DocumentIngest:
    return DocumentIngest(
        embedder=fake_embedder,
        store=tmp_store,
        chunk_chars=800,
        overlap_chars=100,
        embed_batch_size=32,
    )


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR
