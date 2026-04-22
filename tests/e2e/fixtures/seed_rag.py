# tests/e2e/fixtures/seed_rag.py
"""RAG 시드 헬퍼 — E2E-04/08/22/10 공통.

M_06 HOLD 당시: VectorStore.upsert를 직접 호출해 청크를 삽입하던 방식.
M_06 DONE 이후: DocumentIngest.ingest_file 경로도 선택적으로 사용 가능.

사용 방법:
    # 기존 방식 (e2e_fast / e2e_model 모두에서 BGE-M3 필요):
    from tests.e2e.fixtures.seed_rag import seed_chunks_direct
    await seed_chunks_direct(vector_store, embedder)

    # M_06 경로 (e2e_model 환경, BGE-M3 실제 임베더 필요):
    from tests.e2e.fixtures.seed_rag import seed_via_ingest
    count = await seed_via_ingest(ingest, hwpx_path, category="테스트")
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from document_ingest.ingest import DocumentIngest
    from vector_search.store import VectorStore
    from vector_search.embedder import Embedder

_SEED_DIR = Path(__file__).parent / "rag_seed"


def seed_chunks_direct(
    vector_store: "VectorStore",
    embedder: "Embedder",
) -> int:
    """VectorStore.upsert를 직접 호출해 RAG 시드 청크를 삽입한다 (M_06 HOLD 당시 방식).

    M_06 DONE — 이제 DocumentIngest.ingest_file을 사용할 수 있음.
    하지만 이 함수는 e2e_fast에서도 동작하도록 유지한다(강제 교체 아님).

    E2E-04/08/22: BGE-M3 실제 임베더(e2e_model) 또는 FakeEmbedder(e2e_fast) 모두 수용.

    Returns:
        upsert된 청크 수.
    """
    from vector_search.types import DocumentChunk

    seed_file = _SEED_DIR / "budget_policy.md"
    seed_text = seed_file.read_text(encoding="utf-8")

    chunks = [
        DocumentChunk(
            doc_id="budget-policy-001",
            doc_name="규정.pdf",
            category="규정",
            page=12,
            section="예산 승인 절차",
            chunk_id="chunk-budget-001",
            text=seed_text[:500],
            bbox=None,
            source_path=str(seed_file),
        ),
        DocumentChunk(
            doc_id="budget-policy-001",
            doc_name="규정.pdf",
            category="규정",
            page=13,
            section="예산 집행 한도",
            chunk_id="chunk-budget-002",
            text=seed_text[500:800] if len(seed_text) > 500 else seed_text[:200],
            bbox=None,
            source_path=str(seed_file),
        ),
    ]

    meeting_file = _SEED_DIR / "meeting_minutes.md"
    meeting_text = meeting_file.read_text(encoding="utf-8")

    chunks.append(
        DocumentChunk(
            doc_id="meeting-minutes-001",
            doc_name="회의록.docx",
            category="회의록",
            page=None,
            section="1. 서론",
            chunk_id="chunk-meeting-001",
            text=meeting_text[:400],
            bbox=None,
            source_path=str(meeting_file),
        )
    )

    vectors = embedder.embed_passages([c.text for c in chunks])
    return vector_store.upsert(chunks, vectors)


async def seed_via_ingest(
    ingest: "DocumentIngest",
    file_path: str,
    category: str | None = None,
) -> int:
    """M_06 DocumentIngest.ingest_file 경로를 통해 시드.

    M_06 DONE 이후 사용 가능. e2e_model 환경(BGE-M3 실제 임베더)에서만 의미있는 결과.
    e2e_fast에서는 FakeEmbedder를 주입한 DocumentIngest 인스턴스를 사용하면 됨.

    Args:
        ingest:    DocumentIngest 인스턴스.
        file_path: 인제스트할 파일 경로 (절대경로 권장).
        category:  문서 카테고리 (선택).

    Returns:
        upsert된 청크 수.
    """
    return await ingest.ingest_file(file_path, category=category)
