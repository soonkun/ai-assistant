# tests/vector_search/test_citation.py
"""N-3: format_citation 4종 경계 케이스 상세 테스트 (스펙 §7)."""

from __future__ import annotations

import uuid

import pytest

from vector_search.rag import RagService
from vector_search.types import SearchHit


def make_hit(
    doc_name: str,
    page: int | None,
    section: str | None,
    score: float = 0.9,
) -> SearchHit:
    return SearchHit(
        doc_id="d1",
        doc_name=doc_name,
        category=None,
        page=page,
        section=section,
        chunk_id=str(uuid.uuid4()),
        text="text",
        bbox=None,
        source_path="/docs/test",
        score=score,
    )


@pytest.fixture
def rag_service_no_deps() -> RagService:
    """format_citation만 테스트하므로 embedder/store는 None 대체 가능."""
    # RagService.__init__은 embedder/store를 저장만 하므로 any 객체 가능
    from unittest.mock import MagicMock

    return RagService(embedder=MagicMock(), store=MagicMock())  # type: ignore[arg-type]


class TestFormatCitation:
    """스펙 §7.1 테이블 4종 케이스."""

    def test_page_and_section(self, rag_service_no_deps: RagService) -> None:
        hit = make_hit("예산지침.pdf", page=12, section="예산 승인 절차")
        result = rag_service_no_deps.format_citation(hit)
        assert result == "`예산지침.pdf` 12페이지, '예산 승인 절차' 섹션"

    def test_page_only(self, rag_service_no_deps: RagService) -> None:
        hit = make_hit("예산지침.pdf", page=12, section=None)
        result = rag_service_no_deps.format_citation(hit)
        assert result == "`예산지침.pdf` 12페이지"

    def test_section_only(self, rag_service_no_deps: RagService) -> None:
        hit = make_hit("회의록.docx", page=None, section="1. 서론")
        result = rag_service_no_deps.format_citation(hit)
        assert result == "`회의록.docx` '1. 서론' 섹션"

    def test_no_page_no_section(self, rag_service_no_deps: RagService) -> None:
        hit = make_hit("메모.txt", page=None, section=None)
        result = rag_service_no_deps.format_citation(hit)
        assert result == "`메모.txt`"

    def test_section_empty_string_treated_as_absent(self, rag_service_no_deps: RagService) -> None:
        """section이 빈 문자열("")인 경우 section 없음으로 처리."""
        hit = make_hit("doc.pdf", page=5, section="")
        result = rag_service_no_deps.format_citation(hit)
        # section이 falsy면 생략
        assert result == "`doc.pdf` 5페이지"

    def test_doc_name_with_backtick_preserved(self, rag_service_no_deps: RagService) -> None:
        """doc_name에 특수문자가 있어도 그대로 반환."""
        hit = make_hit("파일 (복사본).pdf", page=1, section=None)
        result = rag_service_no_deps.format_citation(hit)
        assert "`파일 (복사본).pdf`" in result
        assert "1페이지" in result
