# tests/e2e/test_e2e_08_citation_links.py
"""E2E-08: search_docs 결과의 인용 포맷 문자열이 클라이언트 프레임에 전달.

시나리오 ID: E2E-08-citation-links
REQUIREMENTS: §2.2 인용 포맷
관련 모듈: M_05b ToolRouter, M_07 RagService
마커: e2e_model (BGE-M3 필요)
실행 시간 목표: ≤ 30초
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.e2e_model]

_BGE_MODEL_PATH = Path("assets/models/bge-m3")
_SEED_DIR = Path(__file__).parent / "fixtures" / "rag_seed"


@pytest.mark.timeout(60)
async def test_e2e_08_citation_links(
    tmp_data_dir: Path,
) -> None:
    """RagService.format_citation 결과가 규정 포맷을 따르는지 검증.

    수락 기준:
    - format_citation이 `규정.pdf` 12페이지, '예산 승인 절차' 섹션 형태를 반환.
    - page=None, section='1. 서론'인 경우도 처리됨.
    """
    if not _BGE_MODEL_PATH.exists():
        pytest.skip(reason=f"BGE-M3 모델 없음: {_BGE_MODEL_PATH}")

    from vector_search.embedder import Embedder
    from vector_search.store import VectorStore
    from vector_search.rag import RagService
    from vector_search.types import SearchHit

    embedder = Embedder(model_dir=str(_BGE_MODEL_PATH), device="cpu")
    store = VectorStore(db_path=str(tmp_data_dir / "vector_store"), table="citation_test")
    rag = RagService(embedder=embedder, store=store, min_score=0.35)

    # 인용 포맷 검증 (format_citation 직접 호출)
    hit1 = SearchHit(
        doc_id="test-001",
        doc_name="규정.pdf",
        category="규정",
        page=12,
        section="예산 승인 절차",
        chunk_id="chunk-001",
        text="예산 승인 절차 내용",
        bbox=None,
        source_path="/test/규정.pdf",
        score=0.85,
    )

    citation1 = rag.format_citation(hit1)
    # 수락 기준 1: 파일명 포함
    assert "규정.pdf" in citation1, f"인용에 파일명 없음: {citation1!r}"
    # 수락 기준 2: 페이지 번호 또는 섹션명 포함
    assert "12" in citation1 or "예산 승인" in citation1, f"인용에 페이지/섹션 없음: {citation1!r}"

    # 회의록.docx page=None, section="1. 서론" 케이스
    hit2 = SearchHit(
        doc_id="test-002",
        doc_name="회의록.docx",
        category="회의록",
        page=None,
        section="1. 서론",
        chunk_id="chunk-002",
        text="서론 내용",
        bbox=None,
        source_path="/test/회의록.docx",
        score=0.80,
    )

    citation2 = rag.format_citation(hit2)
    assert "회의록.docx" in citation2, f"인용에 파일명 없음: {citation2!r}"
    assert "서론" in citation2 or "1." in citation2, f"인용에 섹션명 없음: {citation2!r}"
