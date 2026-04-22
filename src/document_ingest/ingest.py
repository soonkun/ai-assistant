# src/document_ingest/ingest.py
"""DocumentIngest 클래스 — 파싱 + 청킹 + 임베딩 오케스트레이션 (M_06 스펙 §4.2)."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

from document_ingest.errors import (
    IngestIOError,
    ParseError,
    UnsupportedFormatError,
)
from document_ingest.formats import SUPPORTED_EXTENSIONS
from document_ingest.parsers.docx import _parse_docx
from document_ingest.parsers.hwpx import _parse_hwpx
from document_ingest.parsers.md import _parse_md
from document_ingest.parsers.pdf import _parse_pdf
from document_ingest.parsers.pptx import _parse_pptx
from document_ingest.parsers.txt import _parse_txt
from document_ingest.segments import _Segment, chunk_segments
from vector_search.types import DocumentChunk

if TYPE_CHECKING:
    import numpy as np
    from vector_search import Embedder, VectorStore

logger = logging.getLogger(__name__)

# 파일 크기 한도 (스펙 §8.4)
_WARN_SIZE_BYTES: int = 100 * 1024 * 1024  # 100 MB
_ERROR_SIZE_BYTES: int = 1024 * 1024 * 1024  # 1 GB

# category 제어문자 체크 정규식
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f]")


def _make_doc_id(abs_path: Path) -> str:
    """doc_id = SHA-256(abs_path)[:32] (Critic M-1 수정: path-only).

    mtime은 doc_id에 포함하지 않는다. 파일 수정 시 mtime이 바뀌어도
    doc_id가 동일하게 유지되어야 재-ingest 시 기존 청크가 올바르게 교체된다.
    (mtime을 포함하면 delete_by_doc_id가 다른 doc_id를 삭제 시도해 구 청크 누적 발생)

    mtime 조회 실패 시 예외를 발생시키지 않는다 — doc_id 생성은 파일 경로만으로 충분.
    """
    raw = str(abs_path).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


def _derive_category(
    file_path: Path,
    ingest_root: Path | None,
    category_from_subdirs: bool,
    explicit_category: str | None,
) -> str | None:
    """category 결정 로직 (스펙 §6.5).

    Raises:
        ValueError: category 값에 제어문자 포함, 또는 file_path가 ingest_root 밖.
    """
    if explicit_category is not None:
        if _CONTROL_CHAR_RE.search(explicit_category):
            raise ValueError(f"category에 제어문자가 포함되어 있습니다: {repr(explicit_category)}")
        return explicit_category.strip() or None

    if ingest_root is None or not category_from_subdirs:
        return None

    try:
        rel = file_path.resolve().relative_to(ingest_root.resolve())
    except ValueError as exc:
        raise ValueError(
            f"file_path가 ingest_root 범위 밖입니다: {file_path} not under {ingest_root}"
        ) from exc

    parts = rel.parts
    if len(parts) <= 1:
        # ingest_root 직속 파일
        return None

    cat = parts[0].strip()
    if _CONTROL_CHAR_RE.search(cat):
        raise ValueError(f"category(폴더명)에 제어문자가 포함되어 있습니다: {repr(cat)}")
    return cat or None


def _select_parser(ext: str) -> type:
    """확장자(casefold) → 파서 함수 반환."""
    mapping = {
        ".pdf": _parse_pdf,
        ".docx": _parse_docx,
        ".pptx": _parse_pptx,
        ".hwpx": _parse_hwpx,
        ".txt": _parse_txt,
        ".md": _parse_md,
        ".markdown": _parse_md,
    }
    return mapping[ext]  # type: ignore[return-value]


def _check_file_size(path: Path) -> None:
    """파일 크기 체크 (스펙 §8.4).

    Raises:
        IngestIOError: 1 GB 초과.
    """
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise IngestIOError(f"파일 크기 조회 실패: {path}: {exc}") from exc

    if size > _ERROR_SIZE_BYTES:
        raise IngestIOError(f"file too large: {size} bytes > 1GB limit: {path.name}")
    if size > _WARN_SIZE_BYTES:
        logger.warning(
            "대용량 파일 경고 (>100MB): %s (%d bytes)",
            path.name,
            size,
            extra={"path": str(path), "reason": f"size={size}"},
        )


class DocumentIngest:
    """파일/폴더 단위 인제스트 파이프라인 (M_06 스펙 §4.2).

    모든 공개 메서드는 async def. 내부의 파서·임베더·스토어 호출은 blocking이므로
    asyncio.to_thread(...)로 감싸 이벤트 루프를 점유하지 않는다.

    Args:
        embedder: M_07 Embedder 인스턴스.
        store:    M_07 VectorStore 인스턴스.
        chunk_chars:      청크 윈도우 크기(문자 단위). 기본 800.
        overlap_chars:    청크 간 오버랩 크기. 기본 100.
        embed_batch_size: embed_passages 배치 크기. 기본 32.

    Raises:
        ValueError: chunk_chars <= 0 또는 overlap_chars >= chunk_chars.
    """

    def __init__(
        self,
        embedder: "Embedder",
        store: "VectorStore",
        chunk_chars: int = 800,
        overlap_chars: int = 100,
        embed_batch_size: int = 32,
    ) -> None:
        if chunk_chars <= 0:
            raise ValueError(f"chunk_chars must be > 0, got {chunk_chars}")
        if overlap_chars >= chunk_chars:
            raise ValueError(
                f"overlap_chars must be < chunk_chars, "
                f"got overlap_chars={overlap_chars}, chunk_chars={chunk_chars}"
            )

        self._embedder = embedder
        self._store = store
        self._chunk_chars = chunk_chars
        self._overlap_chars = overlap_chars
        self._embed_batch_size = embed_batch_size

        logger.info(
            "DocumentIngest 초기화: chunk_chars=%d, overlap_chars=%d, embed_batch_size=%d",
            chunk_chars,
            overlap_chars,
            embed_batch_size,
        )

    def _parse_and_chunk(
        self,
        abs_path: Path,
        category: str | None,
    ) -> tuple[str, list[DocumentChunk]]:
        """동기 파싱 + 청킹. asyncio.to_thread 호출용.

        Returns:
            (doc_id, chunks) 튜플
        """
        ext = abs_path.suffix.casefold()
        parser = _select_parser(ext)

        segments: list[_Segment] = parser(str(abs_path))

        if not segments:
            logger.warning(
                "빈 문서 — 세그먼트 없음: %s",
                abs_path.name,
                extra={"path": str(abs_path), "reason": "no segments"},
            )
            doc_id = _make_doc_id(abs_path)
            return doc_id, []

        doc_id = _make_doc_id(abs_path)
        doc_name = abs_path.name
        source_path = str(abs_path)

        chunks = chunk_segments(
            segments=segments,
            chunk_chars=self._chunk_chars,
            overlap_chars=self._overlap_chars,
            doc_id=doc_id,
            doc_name=doc_name,
            category=category,
            source_path=source_path,
        )

        return doc_id, chunks

    def _embed_and_upsert(
        self,
        doc_id: str,
        chunks: list[DocumentChunk],
    ) -> int:
        """동기 임베딩 + upsert. asyncio.to_thread 호출용.

        Returns:
            upsert된 청크 수.
        """
        import numpy as np

        # 기존 청크 삭제 (재-ingest 멱등, 스펙 §7)
        deleted = self._store.delete_by_doc_id(doc_id)
        if deleted > 0:
            logger.debug("재-ingest: 기존 %d건 삭제 (doc_id=%s)", deleted, doc_id)

        if not chunks:
            return 0

        # 배치 임베딩 (배치 크기 embed_batch_size)
        texts = [c.text for c in chunks]
        all_vectors: list[np.ndarray] = []

        for i in range(0, len(texts), self._embed_batch_size):
            batch_texts = texts[i : i + self._embed_batch_size]
            batch_vecs: np.ndarray = self._embedder.embed_passages(batch_texts)
            all_vectors.append(batch_vecs)

        vectors: np.ndarray = np.concatenate(all_vectors, axis=0)

        count = self._store.upsert(chunks, vectors)
        logger.debug("upsert 완료: %d건 (doc_id=%s)", count, doc_id)
        return count

    async def ingest_file(
        self,
        path: str,
        category: str | None = None,
    ) -> int:
        """단일 파일을 읽어 청크 생성 → 임베딩 → upsert (스펙 §4.2).

        Returns:
            upsert된 청크 수.

        Raises:
            IngestIOError: 파일 부재·권한 부족·mtime 조회 실패.
            UnsupportedFormatError: 확장자 미지원.
            ParseError: 파서 내부 실패.
        """
        abs_path = Path(path).resolve()

        # 1. 경로 존재 확인
        if not abs_path.exists():
            raise IngestIOError(f"파일을 찾을 수 없습니다: {path}")
        if not abs_path.is_file():
            raise IngestIOError(f"디렉토리가 아닌 파일을 지정하세요: {path}")

        # 2. 파일 크기 체크
        _check_file_size(abs_path)

        # 3. 확장자 확인
        ext = abs_path.suffix.casefold()
        if ext not in SUPPORTED_EXTENSIONS:
            raise UnsupportedFormatError(
                f"지원하지 않는 파일 형식: {abs_path.suffix!r} ({abs_path.name})"
            )

        # 4. category 검증
        if category is not None and _CONTROL_CHAR_RE.search(category):
            raise ValueError(f"category에 제어문자가 포함되어 있습니다: {repr(category)}")

        logger.info("ingest_file: %s (category=%s)", abs_path.name, category)

        # 5. 파싱 + 청킹 (blocking → to_thread)
        doc_id, chunks = await asyncio.to_thread(self._parse_and_chunk, abs_path, category)

        if not chunks:
            logger.warning(
                "ingest_file: 0 청크 — 빈 문서: %s",
                abs_path.name,
                extra={"path": str(abs_path), "reason": "0 chunks"},
            )
            return 0

        # 6-7. 임베딩 + upsert (blocking → to_thread)
        count = await asyncio.to_thread(self._embed_and_upsert, doc_id, chunks)

        logger.info("ingest_file 완료: %s → %d 청크", abs_path.name, count)
        return count

    async def ingest_directory(
        self,
        path: str,
        recursive: bool = True,
        category_from_subdirs: bool = True,
    ) -> int:
        """디렉토리 내 지원 확장자 파일을 일괄 인제스트 (스펙 §4.2).

        개별 파일 실패(ParseError/UnsupportedFormatError)는 로그 경고 + skip.
        IO 레벨 치명 오류(IngestIOError, 디렉토리 자체 부재)는 즉시 raise.

        Returns:
            전체 성공 파일들의 upsert된 청크 수 합.

        Raises:
            IngestIOError: 디렉토리 부재·권한 부족.
        """
        ingest_root = Path(path).resolve()

        if not ingest_root.exists():
            raise IngestIOError(f"디렉토리를 찾을 수 없습니다: {path}")
        if not ingest_root.is_dir():
            raise IngestIOError(f"디렉토리 경로를 지정하세요: {path}")

        logger.info(
            "ingest_directory: %s (recursive=%s, category_from_subdirs=%s)",
            ingest_root,
            recursive,
            category_from_subdirs,
        )

        # 파일 수집
        if recursive:
            all_files = list(ingest_root.rglob("*"))
        else:
            all_files = list(ingest_root.iterdir())

        # 지원 확장자 + 파일만 필터 (symlink 탈출 방어 포함)
        target_files: list[Path] = []
        for f in all_files:
            if not f.is_file():
                continue
            ext = f.suffix.casefold()
            if ext not in SUPPORTED_EXTENSIONS:
                logger.debug(
                    "미지원 확장자 skip: %s",
                    f.name,
                    extra={"path": str(f), "reason": f"unsupported ext={f.suffix}"},
                )
                continue

            # A-4: 심볼릭 링크 탈출 방어 — resolve() 후 ingest_root에 속하는지 확인
            try:
                resolved = f.resolve()
                resolved.relative_to(ingest_root)
            except ValueError:
                logger.warning(
                    "symlink 탈출 시도 skip: %s → %s",
                    f,
                    resolved,
                    extra={"path": str(f), "reason": "symlink escape"},
                )
                continue

            target_files.append(f)

        logger.info("ingest_directory: 대상 파일 %d건", len(target_files))

        total_count = 0
        for f in target_files:
            try:
                # category 결정
                cat = _derive_category(
                    file_path=f,
                    ingest_root=ingest_root,
                    category_from_subdirs=category_from_subdirs,
                    explicit_category=None,
                )

                _check_file_size(f)

                doc_id, chunks = await asyncio.to_thread(self._parse_and_chunk, f, cat)

                if not chunks:
                    logger.warning(
                        "ingest_directory: 0 청크 skip: %s",
                        f.name,
                        extra={"path": str(f), "reason": "0 chunks"},
                    )
                    continue

                count = await asyncio.to_thread(self._embed_and_upsert, doc_id, chunks)
                total_count += count

            except IngestIOError:
                # IO 치명 오류는 전파 (스펙 §9.1)
                raise
            except (ParseError, UnsupportedFormatError) as exc:
                # 파서 실패·미지원 포맷만 skip (Critic M-2: 화이트리스트로 좁힘)
                # EmbedderError, VectorStoreError, ValueError 등은 전파
                logger.warning(
                    "파서 실패, 파일 skip: %s — %s",
                    f.name,
                    exc,
                    extra={"path": str(f), "reason": str(exc)},
                )
                continue

        logger.info(
            "ingest_directory 완료: %s, 총 %d 청크 upsert",
            ingest_root,
            total_count,
        )
        return total_count

    async def remove_document(self, doc_id: str) -> int:
        """특정 doc_id의 모든 청크를 삭제 (스펙 §4.2).

        존재하지 않는 doc_id는 0 반환.

        Returns:
            삭제된 row 수.
        """
        logger.debug("remove_document: doc_id=%s", doc_id)
        count = await asyncio.to_thread(self._store.delete_by_doc_id, doc_id)
        if count == 0:
            logger.debug("remove_document: doc_id=%s 존재하지 않음 (0 반환)", doc_id)
        else:
            logger.info("remove_document: doc_id=%s → %d건 삭제", doc_id, count)
        return count
