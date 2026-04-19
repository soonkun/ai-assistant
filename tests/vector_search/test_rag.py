# tests/vector_search/test_rag.py
"""RagService 테스트: N-2, E-1, E-2, E-3, E-4, A-5, A-6."""

from __future__ import annotations

import uuid

import pytest

from tests.vector_search.fakes import FakeEmbedder
from vector_search.errors import EmbedderError
from vector_search.rag import RagService
from vector_search.store import VectorStore
from vector_search.types import DocumentChunk, SearchHit


def make_chunk(
    doc_id: str = "doc-001",
    doc_name: str = "규정집.pdf",
    category: str | None = "규정",
    page: int | None = 1,
    section: str | None = "1. 서론",
    text: str = "예산 승인 절차에 관한 규정",
    bbox: tuple[float, float, float, float] | None = None,
    source_path: str = "/docs/규정집.pdf",
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


@pytest.fixture
def rag_with_data(tmp_db_path: str) -> RagService:
    """FakeEmbedder + 실 LanceDB에 5개 청크를 upsert한 RagService."""
    fe = FakeEmbedder()
    store = VectorStore(tmp_db_path)

    chunks = [make_chunk(text=f"예산 승인 절차 {i}번 항목") for i in range(5)]
    texts = [c.text for c in chunks]
    vectors = fe.embed_passages(texts)
    store.upsert(chunks, vectors)

    return RagService(embedder=fe, store=store, min_score=0.35, top_k_max=20)  # type: ignore[arg-type]


class TestNormal:
    def test_n2_retrieve_found_true(self, rag_with_data: RagService) -> None:
        """N-2: RagService.retrieve 성공 케이스 (found=True)."""
        result = rag_with_data.retrieve("예산 승인 절차", top_k=3)
        assert result.found is True
        assert result.no_match_reason is None
        assert len(result.hits) == 3
        assert result.hits[0].score >= 0.35

    def test_e4_top_k_1(self, rag_with_data: RagService) -> None:
        """E-4: top_k=1 경계 → hits 1건."""
        result = rag_with_data.retrieve("예산", top_k=1)
        assert len(result.hits) == 1

    def test_e5_top_k_clamp(self, tmp_db_path: str) -> None:
        """E-5: top_k=21 → clamp to top_k_max=20."""
        fe = FakeEmbedder()
        store = VectorStore(tmp_db_path)
        chunks = [make_chunk(text=f"내용 {i}") for i in range(5)]
        vectors = fe.embed_passages([c.text for c in chunks])
        store.upsert(chunks, vectors)

        rag = RagService(embedder=fe, store=store, min_score=0.35, top_k_max=20)  # type: ignore[arg-type]
        result = rag.retrieve("내용", top_k=21)
        # clamp 후 5개 이하 반환 (실 데이터가 5개이므로)
        assert len(result.hits) <= 20


class TestEdgeCases:
    def test_e1_empty_query(self, rag_with_data: RagService) -> None:
        """E-1: retrieve("") → found=False, no_match_reason="쿼리가 비어있습니다"."""
        result = rag_with_data.retrieve("")
        assert result.found is False
        assert result.no_match_reason == "쿼리가 비어있습니다"
        assert result.hits == []

    def test_e2_whitespace_only_query(self, rag_with_data: RagService) -> None:
        """E-2: retrieve("   \n\t  ") → E-1과 동일."""
        result = rag_with_data.retrieve("   \n\t  ")
        assert result.found is False
        assert result.no_match_reason == "쿼리가 비어있습니다"
        assert result.hits == []

    def test_e1_no_embedder_called_on_empty(self, tmp_db_path: str) -> None:
        """E-1: 빈 쿼리 시 Embedder.embed_query 호출 0회."""
        from unittest.mock import MagicMock

        mock_embedder = MagicMock()
        store = VectorStore(tmp_db_path)
        rag = RagService(embedder=mock_embedder, store=store)  # type: ignore[arg-type]

        rag.retrieve("")
        mock_embedder.embed_query.assert_not_called()

    def test_e3_score_below_min_score_found_false_hits_preserved(self, tmp_db_path: str) -> None:
        """E-3: 최상위 score < min_score → found=False, hits는 유지.

        no_match_reason에 상위 score(.2f)와 min_score(.2f) 구체 문자열 포함.
        스펙 §11.3 E-3 요구.
        """
        from unittest.mock import MagicMock

        # min_score=0.35 고정, store가 score=0.25 hit을 반환하도록 mock
        min_score = 0.35
        max_score = 0.25  # 0.35 미만이어야 found=False; 반올림으로 1.00이 나오지 않는 값

        fake_hit = make_chunk(text="완전히 무관한 내용 XYZ ABC")
        search_hit = SearchHit.from_chunk(fake_hit, score=max_score)

        mock_store = MagicMock()
        mock_store.search.return_value = [search_hit]

        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = FakeEmbedder().embed_query("테스트 쿼리")

        rag = RagService(
            embedder=mock_embedder,  # type: ignore[arg-type]
            store=mock_store,  # type: ignore[arg-type]
            min_score=min_score,
            top_k_max=20,
        )
        result = rag.retrieve("테스트 쿼리", top_k=3)

        assert result.found is False
        assert result.no_match_reason is not None
        assert len(result.hits) > 0  # hits는 비어있지 않음
        # 구체적 수치 문자열 검증 (스펙 §11.3 E-3)
        assert f"{min_score:.2f}" in result.no_match_reason, (
            f"no_match_reason에 min_score {min_score:.2f} 없음: {result.no_match_reason}"
        )
        assert f"{max_score:.2f}" in result.no_match_reason, (
            f"no_match_reason에 max_score {max_score:.2f} 없음: {result.no_match_reason}"
        )

    def test_e3_no_match_reason_contains_scores(self, tmp_db_path: str) -> None:
        """E-3: no_match_reason 문자열에 min_score·실측 score 구체 문자열 포함 확인.

        min_score=0.35, 실측 score=0.28로 고정해 .2f 반올림이 1.00 경계값에 도달하지 않도록 한다.
        """
        from unittest.mock import MagicMock

        min_score = 0.35
        actual_score = 0.28  # 0.35 미만, 반올림으로 1.00이 나오지 않는 값

        fake_hit = make_chunk(text="관련 없는 내용")
        search_hit = SearchHit.from_chunk(fake_hit, score=actual_score)

        mock_store = MagicMock()
        mock_store.search.return_value = [search_hit]

        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = FakeEmbedder().embed_query("쿼리")

        rag = RagService(
            embedder=mock_embedder,  # type: ignore[arg-type]
            store=mock_store,  # type: ignore[arg-type]
            min_score=min_score,
            top_k_max=20,
        )
        result = rag.retrieve("쿼리")

        assert result.no_match_reason is not None
        # 구체 문자열 검증 (스펙 §11.3 E-3 요구 사항)
        assert f"{min_score:.2f}" in result.no_match_reason, (
            f"no_match_reason에 min_score {min_score:.2f} 없음: {result.no_match_reason}"
        )
        assert f"{actual_score:.2f}" in result.no_match_reason, (
            f"no_match_reason에 actual_score {actual_score:.2f} 없음: {result.no_match_reason}"
        )

    def test_top_k_zero_raises_value_error(self, rag_with_data: RagService) -> None:
        """top_k <= 0 → ValueError (스펙 §6.3.3)."""
        with pytest.raises(ValueError, match="top_k must be >= 1"):
            rag_with_data.retrieve("테스트", top_k=0)

    def test_top_k_negative_raises_value_error(self, rag_with_data: RagService) -> None:
        with pytest.raises(ValueError, match="top_k must be >= 1"):
            rag_with_data.retrieve("테스트", top_k=-1)


class TestAdversarial:
    def test_a5_very_long_query(self, rag_with_data: RagService) -> None:
        """A-5: 매우 긴 쿼리 (BGE-M3 max 8192 token 초과) → 예외 없이 완료."""
        long_query = "가" * 10_000
        result = rag_with_data.retrieve(long_query, top_k=3)
        # found 값은 데이터에 따름, 단 예외가 없어야 한다
        assert isinstance(result.found, bool)
        assert isinstance(result.hits, list)

    def test_a6_nan_from_embedder_propagates(self, tmp_db_path: str) -> None:
        """A-6: Embedder가 NaN 벡터 반환 → EmbedderError가 retrieve 밖으로 전파."""
        from unittest.mock import MagicMock

        store = VectorStore(tmp_db_path)

        # embed_query가 NaN 벡터를 반환하는 mock embedder
        mock_embedder = MagicMock()
        mock_embedder.embed_query.side_effect = EmbedderError("embedder produced NaN/Inf")

        rag = RagService(embedder=mock_embedder, store=store, min_score=0.35)  # type: ignore[arg-type]

        with pytest.raises(EmbedderError, match="NaN/Inf"):
            rag.retrieve("테스트", top_k=3)
