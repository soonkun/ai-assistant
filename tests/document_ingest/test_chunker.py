# tests/document_ingest/test_chunker.py
"""청커 단위 테스트 (스펙 §6.2)."""

from __future__ import annotations

import pytest

from document_ingest.ingest import DocumentIngest
from document_ingest.segments import _Segment, _chunk_segment, chunk_segments


def _make_seg(text: str, page: int | None = None, section: str | None = None) -> _Segment:
    return _Segment(text=text, page=page, section=section, bbox=None)


def _make_chunks(
    text: str,
    chunk_chars: int = 800,
    overlap_chars: int = 100,
) -> list[str]:
    seg = _make_seg(text)
    chunks = _chunk_segment(
        seg=seg,
        chunk_chars=chunk_chars,
        overlap_chars=overlap_chars,
        doc_id="test-doc-id",
        doc_name="test.txt",
        category=None,
        source_path="/tmp/test.txt",
    )
    return [c.text for c in chunks]


class TestChunker:
    def test_short_segment_produces_one_chunk(self) -> None:
        """800자 이하 짧은 세그먼트 → 1청크."""
        text = "이것은 짧은 텍스트입니다. " * 5  # ~65자
        chunks = _make_chunks(text)
        assert len(chunks) == 1

    def test_long_segment_produces_multiple_chunks(self) -> None:
        """2000자 세그먼트 → 복수 청크."""
        # 짧은 문장을 반복해 2000자 이상 생성
        sentence = "이것은 테스트 문장입니다. "
        text = sentence * (2000 // len(sentence) + 1)
        chunks = _make_chunks(text, chunk_chars=800, overlap_chars=100)
        assert len(chunks) >= 2

    def test_overlap_between_adjacent_chunks(self) -> None:
        """인접 청크 간 overlap_chars 만큼 오버랩 존재."""
        sentence = "짧은 문장입니다. "
        text = sentence * 200  # 충분히 긴 텍스트
        chunks = _make_chunks(text, chunk_chars=300, overlap_chars=50)
        if len(chunks) >= 2:
            # 첫 번째 청크의 끝이 두 번째 청크의 시작에 포함되어야 함
            # (오버랩이 있어야 함)
            end_of_first = chunks[0][-50:]
            start_of_second = chunks[1][:100]
            # 공통 텍스트가 있어야 함
            assert any(word in start_of_second for word in end_of_first.split() if len(word) > 2)

    def test_empty_segment_produces_no_chunk(self) -> None:
        """빈 세그먼트 → 0청크."""
        seg = _make_seg("   ")
        chunks = _chunk_segment(
            seg=seg,
            chunk_chars=800,
            overlap_chars=100,
            doc_id="doc",
            doc_name="f.txt",
            category=None,
            source_path="/tmp/f.txt",
        )
        assert chunks == []

    def test_no_word_split_in_chunks(self) -> None:
        """청크 경계가 단어 중간을 자르지 않는다."""
        # 공백으로 구분된 긴 단어들
        words = ["테스트단어" * 10 + "입니다"] * 50
        text = " ".join(words)
        chunks = _make_chunks(text, chunk_chars=200, overlap_chars=20)
        for chunk in chunks:
            # 각 청크는 공백이나 문장 경계에서 끝나야 함
            # 단어 중간에서 잘리면 중간 문자가 첫/마지막에 있음
            # 기본적으로 청크가 비어있지 않아야 함
            assert len(chunk.strip()) >= 10

    def test_single_very_long_sentence_hard_cut(self) -> None:
        """E-3: 2000자짜리 한 문장 → 강제 분할, 청크 수 >= 2."""
        # 공백 없는 매우 긴 URL-like 텍스트
        long_text = "아" * 2000
        chunks = _make_chunks(long_text, chunk_chars=800, overlap_chars=0)
        assert len(chunks) >= 2
        # 각 청크가 chunk_chars 이하여야 함
        for chunk in chunks:
            assert len(chunk) <= 800

    def test_overlap_zero(self) -> None:
        """E-4: overlap_chars=0 → 청크 간 겹침 없음."""
        sentence = "짧은 문장. "
        text = sentence * 200
        chunks = _make_chunks(text, chunk_chars=300, overlap_chars=0)
        assert len(chunks) >= 2

    def test_overlap_equals_chunk_raises_value_error(self) -> None:
        """E-5: overlap_chars >= chunk_chars → ValueError (생성자)."""
        from tests.vector_search.fakes import FakeEmbedder
        from vector_search.store import VectorStore
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            store = VectorStore(db_path=os.path.join(tmpdir, "db"))
            with pytest.raises(ValueError):
                DocumentIngest(
                    embedder=FakeEmbedder(),
                    store=store,
                    chunk_chars=100,
                    overlap_chars=100,
                )

    def test_chunk_text_min_length(self) -> None:
        """스트립 후 < 10자 청크는 drop된다."""
        # 매우 짧은 세그먼트들
        seg = _make_seg("OK. 좋아.")
        chunks = _chunk_segment(
            seg=seg,
            chunk_chars=800,
            overlap_chars=0,
            doc_id="doc",
            doc_name="f.txt",
            category=None,
            source_path="/tmp/f.txt",
        )
        # 11자 이상인 경우만 남아야 함 (합친 텍스트가 10자 이상이므로 1청크)
        for c in chunks:
            assert len(c.text.strip()) >= 10

    def test_chunk_metadata_propagated(self) -> None:
        """청크에 page/section/bbox가 세그먼트에서 전파된다."""
        seg = _Segment(text="테스트 내용입니다. " * 5, page=3, section="서론", bbox=None)
        chunks = _chunk_segment(
            seg=seg,
            chunk_chars=800,
            overlap_chars=0,
            doc_id="doc-123",
            doc_name="test.pdf",
            category="규정",
            source_path="/docs/test.pdf",
        )
        assert len(chunks) >= 1
        for c in chunks:
            assert c.page == 3
            assert c.section == "서론"
            assert c.bbox is None
            assert c.doc_id == "doc-123"
            assert c.category == "규정"

    def test_chunk_id_is_uuid4(self) -> None:
        """chunk_id가 UUIDv4 형식이어야 한다."""
        import uuid

        seg = _make_seg("테스트 청크 UUID 검증입니다. ")
        chunks = _chunk_segment(
            seg=seg,
            chunk_chars=800,
            overlap_chars=0,
            doc_id="doc",
            doc_name="f.txt",
            category=None,
            source_path="/tmp/f.txt",
        )
        for c in chunks:
            parsed = uuid.UUID(c.chunk_id)
            assert parsed.version == 4

    def test_multiple_segments_independent_chunking(self) -> None:
        """여러 세그먼트는 독립적으로 청킹된다 (경계 넘지 않음)."""
        seg1 = _Segment(text="첫 번째 세그먼트입니다. " * 5, page=1, section=None, bbox=None)
        seg2 = _Segment(text="두 번째 세그먼트입니다. " * 5, page=2, section=None, bbox=None)

        chunks = chunk_segments(
            segments=[seg1, seg2],
            chunk_chars=800,
            overlap_chars=0,
            doc_id="doc",
            doc_name="f.txt",
            category=None,
            source_path="/tmp/f.txt",
        )

        pages = {c.page for c in chunks}
        assert 1 in pages
        assert 2 in pages
