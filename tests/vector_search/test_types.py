# tests/vector_search/test_types.py
"""DocumentChunk, SearchHit, RetrievalResult, SearchHit.from_chunk 테스트."""

from __future__ import annotations

import uuid

import pytest

from vector_search.types import DocumentChunk, RetrievalResult, SearchHit


def make_chunk(
    doc_id: str = "doc-001",
    doc_name: str = "test.pdf",
    category: str | None = "규정",
    page: int | None = 1,
    section: str | None = "1. 서론",
    text: str = "테스트 텍스트",
    bbox: tuple[float, float, float, float] | None = None,
    source_path: str = "/docs/test.pdf",
) -> DocumentChunk:
    return DocumentChunk(
        doc_id=doc_id,
        doc_name=doc_name,
        category=category,
        page=page,
        section=section,
        chunk_id=str(uuid.uuid4()),
        text=text,
        bbox=bbox,
        source_path=source_path,
    )


class TestDocumentChunk:
    def test_frozen(self) -> None:
        chunk = make_chunk()
        with pytest.raises((AttributeError, TypeError)):
            chunk.doc_id = "new-id"  # type: ignore[misc]

    def test_fields_accessible(self) -> None:
        chunk = make_chunk(doc_id="abc", doc_name="file.pdf", page=5)
        assert chunk.doc_id == "abc"
        assert chunk.doc_name == "file.pdf"
        assert chunk.page == 5

    def test_optional_fields_none(self) -> None:
        chunk = make_chunk(category=None, page=None, section=None, bbox=None)
        assert chunk.category is None
        assert chunk.page is None
        assert chunk.section is None
        assert chunk.bbox is None


class TestSearchHitFromChunk:
    def test_from_chunk_basic(self) -> None:
        chunk = make_chunk(doc_id="d1", doc_name="doc.pdf", page=12, section="예산 승인 절차")
        hit = SearchHit.from_chunk(chunk, score=0.95)
        assert hit.doc_id == "d1"
        assert hit.doc_name == "doc.pdf"
        assert hit.page == 12
        assert hit.section == "예산 승인 절차"
        assert hit.score == pytest.approx(0.95)

    def test_from_chunk_none_fields(self) -> None:
        chunk = make_chunk(category=None, page=None, section=None, bbox=None)
        hit = SearchHit.from_chunk(chunk, score=0.5)
        assert hit.category is None
        assert hit.page is None
        assert hit.section is None
        assert hit.bbox is None

    def test_from_chunk_preserves_all_fields(self) -> None:
        chunk = make_chunk(
            doc_id="x",
            doc_name="a.pdf",
            category="cat",
            page=3,
            section="sec",
            text="text content",
            bbox=(1.0, 2.0, 3.0, 4.0),
            source_path="/path/to/a.pdf",
        )
        hit = SearchHit.from_chunk(chunk, score=0.8)
        assert hit.chunk_id == chunk.chunk_id
        assert hit.text == "text content"
        assert hit.bbox == (1.0, 2.0, 3.0, 4.0)
        assert hit.source_path == "/path/to/a.pdf"

    def test_hit_is_frozen(self) -> None:
        chunk = make_chunk()
        hit = SearchHit.from_chunk(chunk, score=0.7)
        with pytest.raises((AttributeError, TypeError)):
            hit.score = 0.0  # type: ignore[misc]


class TestRetrievalResult:
    def test_found_true(self) -> None:
        chunk = make_chunk()
        hit = SearchHit.from_chunk(chunk, score=0.9)
        result = RetrievalResult(hits=[hit], found=True, no_match_reason=None)
        assert result.found is True
        assert result.no_match_reason is None
        assert len(result.hits) == 1

    def test_found_false_with_reason(self) -> None:
        result = RetrievalResult(
            hits=[],
            found=False,
            no_match_reason="등록된 문서에서 관련 내용을 찾지 못했습니다",
        )
        assert result.found is False
        assert "찾지 못했습니다" in (result.no_match_reason or "")

    def test_result_is_frozen(self) -> None:
        result = RetrievalResult(hits=[], found=False, no_match_reason=None)
        with pytest.raises((AttributeError, TypeError)):
            result.found = True  # type: ignore[misc]
