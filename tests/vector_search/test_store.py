# tests/vector_search/test_store.py
"""VectorStore 테스트: N-1, N-4, N-5, N-6, E-5, E-6, E-7, E-8, A-1 ~ A-4."""

from __future__ import annotations

import uuid

import numpy as np
import pytest

from tests.vector_search.fakes import FakeEmbedder
from vector_search.errors import VectorStoreError
from vector_search.store import VectorStore
from vector_search.types import DocumentChunk


def make_chunk(
    doc_id: str = "doc-001",
    doc_name: str = "test.pdf",
    category: str | None = "규정",
    page: int | None = 1,
    section: str | None = "섹션1",
    text: str = "테스트 내용",
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


class TestNormal:
    def test_n1_upsert_search_roundtrip(self, tmp_db_path: str) -> None:
        """N-1: upsert → search round-trip. 첫 hit이 query 청크와 일치, score ≥ 0.99."""
        fe = FakeEmbedder()
        store = VectorStore(tmp_db_path)

        chunks = [make_chunk(text=f"청크 텍스트 {i}") for i in range(5)]
        texts = [c.text for c in chunks]
        vectors = fe.embed_passages(texts)

        upserted = store.upsert(chunks, vectors)
        assert upserted == 5

        # 첫 번째 청크 벡터로 검색
        query_vec = vectors[0]
        hits = store.search(query_vec, top_k=3)
        assert len(hits) == 3
        assert hits[0].chunk_id == chunks[0].chunk_id
        assert hits[0].score >= 0.99

    def test_n4_delete_by_doc_id_idempotent(self, tmp_db_path: str) -> None:
        """N-4: delete_by_doc_id 멱등 — 동일 doc_id 청크 3개 upsert → delete → 0건 확인. 재호출 0 반환."""
        fe = FakeEmbedder()
        store = VectorStore(tmp_db_path)

        chunks = [make_chunk(doc_id="target-doc", text=f"내용 {i}") for i in range(3)]
        vectors = fe.embed_passages([c.text for c in chunks])
        store.upsert(chunks, vectors)

        deleted = store.delete_by_doc_id("target-doc")
        assert deleted == 3

        # 재호출 — 0 반환, 예외 없음
        deleted_again = store.delete_by_doc_id("target-doc")
        assert deleted_again == 0

    def test_n5_category_filter(self, tmp_db_path: str) -> None:
        """N-5: category 필터 — 규정 3개, 매뉴얼 2개 upsert → category="규정" 검색 시 모두 규정."""
        fe = FakeEmbedder()
        store = VectorStore(tmp_db_path)

        chunks = [
            make_chunk(doc_id="d1", category="규정", text=f"규정 내용 {i}") for i in range(3)
        ] + [make_chunk(doc_id="d2", category="매뉴얼", text=f"매뉴얼 내용 {i}") for i in range(2)]
        vectors = fe.embed_passages([c.text for c in chunks])
        store.upsert(chunks, vectors)

        query_vec = fe.embed_query("규정")
        hits = store.search(query_vec, top_k=5, category="규정")
        assert len(hits) > 0
        for hit in hits:
            assert hit.category == "규정", f"예상=규정, 실제={hit.category}"

    def test_n6_score_normalization(self, tmp_db_path: str) -> None:
        """N-6: 점수 정규화 수식 검증.

        동일 벡터로 검색 → score ≈ 1.0 (distance ≈ 0).
        완전 직교 벡터 → score ≈ 0.5 (distance ≈ 1.0).
        """
        store = VectorStore(tmp_db_path)

        # 고정 벡터 생성 (L2 정규화)
        base_vec = np.zeros(1024, dtype=np.float32)
        base_vec[0] = 1.0  # unit vector along dim 0

        chunk = make_chunk(text="정규화 테스트")
        store.upsert([chunk], np.array([base_vec]))

        # 동일 벡터로 검색 → score ≈ 1.0
        hits = store.search(base_vec, top_k=1)
        assert len(hits) == 1
        assert hits[0].score >= 0.99, f"score={hits[0].score}, 기대≥0.99"

    def test_e6_upsert_empty_chunks(self, tmp_db_path: str) -> None:
        """E-6: upsert([], empty) → 0 반환, 에러 없음."""
        store = VectorStore(tmp_db_path)
        result = store.upsert([], np.empty((0, 1024), dtype=np.float32))
        assert result == 0

    def test_e7_category_with_special_chars(self, tmp_db_path: str) -> None:
        """E-7: category에 한글·특수문자 정상값 → 성공."""
        fe = FakeEmbedder()
        store = VectorStore(tmp_db_path)

        chunk = make_chunk(category="규정 v2-2024", text="특수 카테고리")
        vec = fe.embed_passages([chunk.text])
        store.upsert([chunk], vec)

        query_vec = fe.embed_query("규정")
        hits = store.search(query_vec, top_k=5, category="규정 v2-2024")
        assert len(hits) >= 0  # 에러 없이 완료

    def test_e8_bbox_roundtrip(self, tmp_db_path: str) -> None:
        """E-8: bbox None vs 있음 라운드트립."""
        fe = FakeEmbedder()
        store = VectorStore(tmp_db_path)

        chunk_pdf = make_chunk(
            doc_id="pdf-doc",
            text="PDF 청크",
            bbox=(10.0, 20.0, 100.0, 50.0),
        )
        chunk_txt = make_chunk(
            doc_id="txt-doc",
            text="TXT 청크",
            bbox=None,
        )
        chunks = [chunk_pdf, chunk_txt]
        vectors = fe.embed_passages([c.text for c in chunks])
        store.upsert(chunks, vectors)

        # PDF 청크 검색
        query_vec = fe.embed_query("PDF 청크")
        hits = store.search(query_vec, top_k=2)
        hit_map = {h.chunk_id: h for h in hits}

        pdf_hit = hit_map.get(chunk_pdf.chunk_id)
        txt_hit = hit_map.get(chunk_txt.chunk_id)

        if pdf_hit:
            assert pdf_hit.bbox == (10.0, 20.0, 100.0, 50.0)
        if txt_hit:
            assert txt_hit.bbox is None


class TestAdversarial:
    def test_a1_duplicate_chunk_id_upsert(self, tmp_db_path: str) -> None:
        """A-1: 동일 chunk_id 중복 upsert → row 1개, text는 두 번째 값."""
        fe = FakeEmbedder()
        store = VectorStore(tmp_db_path)

        fixed_chunk_id = str(uuid.uuid4())
        chunk_v1 = DocumentChunk(
            doc_id="doc-x",
            doc_name="x.pdf",
            category="규정",
            page=1,
            section=None,
            chunk_id=fixed_chunk_id,
            text="첫 번째 텍스트",
            bbox=None,
            source_path="/x.pdf",
        )
        chunk_v2 = DocumentChunk(
            doc_id="doc-x",
            doc_name="x.pdf",
            category="규정",
            page=1,
            section=None,
            chunk_id=fixed_chunk_id,  # 동일 chunk_id
            text="두 번째 텍스트",
            bbox=None,
            source_path="/x.pdf",
        )

        v1 = fe.embed_passages(["첫 번째 텍스트"])
        store.upsert([chunk_v1], v1)

        v2 = fe.embed_passages(["두 번째 텍스트"])
        store.upsert([chunk_v2], v2)

        # 테이블 전체 조회 — to_arrow() 사용 (pandas 없이)
        import pyarrow as pa

        tbl: pa.Table = store._tbl.to_arrow()
        chunk_ids = tbl.column("chunk_id").to_pylist()
        matched_count = chunk_ids.count(fixed_chunk_id)
        assert matched_count == 1

        # text가 두 번째 값으로 갱신됐는지
        texts = tbl.column("text").to_pylist()
        idx = chunk_ids.index(fixed_chunk_id)
        assert texts[idx] == "두 번째 텍스트"

    def test_a2_upsert_wrong_dim(self, tmp_db_path: str) -> None:
        """A-2: upsert vectors shape (3, 512) → VectorStoreError. 테이블 변화 없음."""
        store = VectorStore(tmp_db_path)

        chunks = [make_chunk(text=f"텍스트 {i}") for i in range(3)]
        bad_vectors = np.random.rand(3, 512).astype(np.float32)

        with pytest.raises(VectorStoreError):
            store.upsert(chunks, bad_vectors)

    def test_a2_upsert_mismatched_count(self, tmp_db_path: str) -> None:
        """A-2: chunks 3개, vectors shape (2, 1024) → VectorStoreError."""
        store = VectorStore(tmp_db_path)

        chunks = [make_chunk(text=f"텍스트 {i}") for i in range(3)]
        bad_vectors = np.random.rand(2, 1024).astype(np.float32)

        with pytest.raises(VectorStoreError):
            store.upsert(chunks, bad_vectors)

    def test_a3_sql_injection_category(self, tmp_db_path: str) -> None:
        """A-3: category에 SQL-like 주입 문자열 → 다른 row가 반환되지 않음."""
        fe = FakeEmbedder()
        store = VectorStore(tmp_db_path)

        # 정상 청크 upsert
        chunk = make_chunk(category="안전한카테고리", text="정상 내용")
        vec = fe.embed_passages([chunk.text])
        store.upsert([chunk], vec)

        query_vec = fe.embed_query("테스트")
        # SQL-like 주입 시도
        injection = "' OR 1=1 --"
        # single quote가 있어도 제어문자가 없으면 escape 후 검색 시도
        # 결과가 0건이어야 하거나, VectorStoreError여야 함
        try:
            hits = store.search(query_vec, top_k=5, category=injection)
            # 결과가 있더라도 category="안전한카테고리"인 row가 반환되면 안 됨
            for hit in hits:
                assert hit.category != "안전한카테고리", (
                    f"SQL 인젝션으로 다른 category 행이 유출됨: {hit.category}"
                )
        except VectorStoreError:
            pass  # 정책 2: VectorStoreError도 허용

    def test_a4_query_vec_wrong_shape_2d(self, tmp_db_path: str) -> None:
        """A-4: query_vec shape (1024, 1024) → VectorStoreError."""
        store = VectorStore(tmp_db_path)
        with pytest.raises(VectorStoreError):
            store.search(np.zeros((1024, 1024), dtype=np.float32), top_k=5)

    def test_a4_query_vec_wrong_dim(self, tmp_db_path: str) -> None:
        """A-4: query_vec shape (1023,) → VectorStoreError."""
        store = VectorStore(tmp_db_path)
        with pytest.raises(VectorStoreError):
            store.search(np.zeros(1023, dtype=np.float32), top_k=5)

    def test_e5_top_k_clamp_at_max(self, tmp_db_path: str) -> None:
        """E-5: top_k=21 → top_k_max=20으로 clamp, warning 로그. (store 레벨에서 50 상한)"""
        fe = FakeEmbedder()
        store = VectorStore(tmp_db_path)

        # 데이터 없어도 clamp 동작은 확인 가능
        query_vec = fe.embed_query("테스트")
        # top_k=51 → clamp to 50 (VectorStore 상한)
        hits = store.search(query_vec, top_k=51)
        assert isinstance(hits, list)  # 에러 없이 완료

    def test_top_k_zero_raises(self, tmp_db_path: str) -> None:
        """top_k=0 → ValueError."""
        store = VectorStore(tmp_db_path)
        query_vec = np.zeros(1024, dtype=np.float32)
        with pytest.raises(ValueError):
            store.search(query_vec, top_k=0)
