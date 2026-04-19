# src/vector_search/types.py
"""M_07 VectorSearch 공개 데이터 타입."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentChunk:
    """문서 청크. M_06 DocumentIngest가 생성하고 M_07이 저장·검색.

    `embedding` 벡터는 이 타입이 **아니라** 별도 `vectors: np.ndarray` 파라미터로
    `VectorStore.upsert(chunks, vectors)`에 전달된다. 이는 numpy 배열이
    frozen dataclass에 담기지 않는 Python 특성과 배치 임베딩 효율을 고려한 분리다.

    M_06 DocumentIngest가 이 타입을 `from vector_search.types import DocumentChunk`로
    import한다 (M_07이 먼저 구현되므로 M_07에 단 1곳 정의).
    """

    doc_id: str  # SHA-256 of (source_path + mtime)
    doc_name: str  # 사용자 표시용 (basename)
    category: str | None  # 상위 폴더명. None 허용
    page: int | None  # PDF/PPTX; DOCX/HWPX/TXT/MD는 None
    section: str | None  # HWPX 섹션명·MD 헤더·DOCX Heading
    chunk_id: str  # UUIDv4 문자열
    text: str  # 청크 본문(전처리 후, 빈 문자열 금지)
    bbox: tuple[float, float, float, float] | None  # PDF만 (x0, y0, x1, y1). 그 외 None
    source_path: str  # 절대 경로 (Windows 경로 가능)


@dataclass(frozen=True)
class SearchHit:
    """VectorStore.search가 반환하는 단일 검색 결과.

    설계 결정: DocumentChunk를 중첩하지 않고 **필드를 평면으로 복제**한다(스펙 §15.2).
    - doc_name / page / section / chunk_id / text / bbox / source_path를 최상위로 노출.
    - score(0..1 cosine similarity)를 추가.
    - embedding 벡터는 포함하지 않는다(직렬화·메모리 절감).

    근거:
    1. `src/tool_router/router.py`가 `hit.doc_name`, `hit.page`, `hit.section`,
       `hit.chunk_id`, `hit.text` 등 **평면 접근**을 이미 사용한다.
    2. 중첩(`hit.chunk.doc_name`) 대비 JSON 직렬화가 단순.
    3. LanceDB row를 직접 매핑하기 쉽다(Arrow record → SearchHit dataclass 1:1).
    """

    # --- DocumentChunk에서 복제 (embedding 제외, category 포함) ---
    doc_id: str
    doc_name: str
    category: str | None
    page: int | None
    section: str | None
    chunk_id: str
    text: str
    bbox: tuple[float, float, float, float] | None
    source_path: str

    # --- 검색 결과 고유 ---
    score: float  # cosine similarity 0..1 (정규화 후)

    @staticmethod
    def from_chunk(chunk: DocumentChunk, score: float) -> SearchHit:
        """DocumentChunk + score로 SearchHit 생성하는 정적 헬퍼."""
        return SearchHit(
            doc_id=chunk.doc_id,
            doc_name=chunk.doc_name,
            category=chunk.category,
            page=chunk.page,
            section=chunk.section,
            chunk_id=chunk.chunk_id,
            text=chunk.text,
            bbox=chunk.bbox,
            source_path=chunk.source_path,
            score=score,
        )


@dataclass(frozen=True)
class RetrievalResult:
    """RagService.retrieve의 유일한 반환 타입."""

    hits: list[SearchHit]  # 항상 리스트. found=False여도 상위 top_k를 담는다(스펙 §6.3.2).
    found: bool  # 최상위 hit score >= min_score
    no_match_reason: str | None  # found=False일 때 한국어 설명. found=True면 None.
