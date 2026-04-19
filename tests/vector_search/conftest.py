# tests/vector_search/conftest.py
"""공통 픽스처: tmp_db_path, FakeEmbedder, sample_chunks, slow marker."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from tests.vector_search.fakes import FakeEmbedder
from vector_search.types import DocumentChunk


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-slow",
        action="store_true",
        default=False,
        help="실제 BGE-M3 모델 로드가 필요한 slow 테스트를 실행",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "slow: BGE-M3 실모델 로드 테스트 (--run-slow 옵션 필요)")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if not config.getoption("--run-slow"):
        skip_slow = pytest.mark.skip(reason="--run-slow 옵션 없이는 실행되지 않음")
        for item in items:
            if item.get_closest_marker("slow"):
                item.add_marker(skip_slow)


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> str:
    return str(tmp_path / "lancedb_v1")


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    return FakeEmbedder()


@pytest.fixture
def sample_chunks() -> list[DocumentChunk]:
    """5개 더미 DocumentChunk."""
    return [
        DocumentChunk(
            doc_id="doc-001",
            doc_name="규정집.pdf",
            category="규정",
            page=1,
            section="1. 서론",
            chunk_id=str(uuid.uuid4()),
            text="예산 승인 절차에 관한 규정 내용입니다.",
            bbox=(10.0, 20.0, 100.0, 50.0),
            source_path="/docs/규정집.pdf",
        ),
        DocumentChunk(
            doc_id="doc-001",
            doc_name="규정집.pdf",
            category="규정",
            page=2,
            section="2. 절차",
            chunk_id=str(uuid.uuid4()),
            text="결재 라인은 팀장, 부서장, 대표이사 순입니다.",
            bbox=None,
            source_path="/docs/규정집.pdf",
        ),
        DocumentChunk(
            doc_id="doc-002",
            doc_name="매뉴얼.docx",
            category="매뉴얼",
            page=None,
            section="사용법",
            chunk_id=str(uuid.uuid4()),
            text="시스템 사용 매뉴얼입니다.",
            bbox=None,
            source_path="/docs/매뉴얼.docx",
        ),
        DocumentChunk(
            doc_id="doc-002",
            doc_name="매뉴얼.docx",
            category="매뉴얼",
            page=None,
            section=None,
            chunk_id=str(uuid.uuid4()),
            text="로그인 방법을 설명합니다.",
            bbox=None,
            source_path="/docs/매뉴얼.docx",
        ),
        DocumentChunk(
            doc_id="doc-003",
            doc_name="메모.txt",
            category=None,
            page=None,
            section=None,
            chunk_id=str(uuid.uuid4()),
            text="간단한 메모 내용입니다.",
            bbox=None,
            source_path="/docs/메모.txt",
        ),
    ]
