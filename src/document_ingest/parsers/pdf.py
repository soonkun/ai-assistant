# src/document_ingest/parsers/pdf.py
"""PDF 파서 — pypdfium2 기반 (M_06 스펙 §5.1)."""

from __future__ import annotations

import logging
from pathlib import Path

from document_ingest.errors import ParseError
from document_ingest.segments import _Segment

logger = logging.getLogger(__name__)


def _parse_pdf(path: str) -> list[_Segment]:
    """PDF 파일에서 페이지 단위 텍스트 세그먼트를 추출한다.

    - V1: 페이지 전체 텍스트를 1 세그먼트로. bbox=None.
    - 스캔 PDF(텍스트 레이어 없음): 해당 페이지 skip. 전 페이지 빈 경우 [] 반환.

    Args:
        path: 절대 또는 상대 경로 문자열.

    Returns:
        list[_Segment]: 각 페이지 텍스트. 텍스트 있는 페이지만 포함.

    Raises:
        ParseError: pypdfium2 로드 실패(손상 파일 등).
    """
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise ParseError(f"pypdfium2 패키지가 설치되지 않았습니다: {exc}") from exc

    try:
        pdf = pdfium.PdfDocument(path)
    except Exception as exc:
        raise ParseError(f"PDF 열기 실패: {Path(path).name}: {exc}") from exc

    segments: list[_Segment] = []
    try:
        for page_idx, page in enumerate(pdf, start=1):
            try:
                textpage = page.get_textpage()
                raw_text: str = textpage.get_text_bounded() or ""
                textpage.close()
                page.close()
            except Exception as exc:
                logger.warning(
                    "PDF 페이지 텍스트 추출 실패 (page=%d): %s",
                    page_idx,
                    exc,
                    extra={"path": path, "page": page_idx, "reason": str(exc)},
                )
                continue

            text = raw_text.strip()
            if not text:
                logger.debug("PDF 스캔 페이지 skip (page=%d): %s", page_idx, Path(path).name)
                continue

            segments.append(
                _Segment(
                    text=text,
                    page=page_idx,
                    section=None,
                    bbox=None,
                )
            )
    finally:
        pdf.close()

    if not segments:
        logger.warning(
            "PDF 텍스트 없음 (모든 페이지 스캔 or 빈 문서): %s",
            Path(path).name,
            extra={"path": path, "reason": "no text layer"},
        )

    return segments
