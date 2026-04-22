# src/document_ingest/parsers/md.py
"""Markdown 파서 — markdown-it-py 기반 (M_06 스펙 §5.6)."""

from __future__ import annotations

import logging
from pathlib import Path

from document_ingest.errors import ParseError
from document_ingest.segments import _Segment

logger = logging.getLogger(__name__)

_PENDING_HEADING = "__pending_heading__"


def _parse_md(path: str) -> list[_Segment]:
    """Markdown 파일에서 헤더 기반 섹션 세그먼트를 추출한다.

    - section: 가장 최근 # / ## / ### 헤더 텍스트.
    - page: None (MD는 페이지 개념 없음).

    Args:
        path: 절대 또는 상대 경로 문자열.

    Returns:
        list[_Segment]

    Raises:
        ParseError: markdown-it-py 로드 실패.
    """
    try:
        import markdown_it
    except ImportError as exc:
        raise ParseError(f"markdown-it-py 패키지가 설치되지 않았습니다: {exc}") from exc

    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        raise ParseError(f"MD 파일 읽기 실패: {Path(path).name}: {exc}") from exc

    md = markdown_it.MarkdownIt("commonmark")
    tokens = md.parse(text)

    segments: list[_Segment] = []
    current_heading: str | None = None
    buffer: list[str] = []

    for tok in tokens:
        if tok.type == "heading_open":
            # flush 이전 섹션
            if buffer:
                content = "\n".join(buffer).strip()
                if content:
                    segments.append(
                        _Segment(
                            text=content,
                            page=None,
                            section=current_heading,
                            bbox=None,
                        )
                    )
                buffer = []
            current_heading = _PENDING_HEADING
        elif tok.type == "inline" and current_heading == _PENDING_HEADING:
            current_heading = tok.content.strip() or None
        elif tok.type == "inline":
            content = tok.content.strip()
            if content:
                buffer.append(content)

    # 마지막 섹션 flush
    if buffer:
        content = "\n".join(buffer).strip()
        if content:
            segments.append(
                _Segment(
                    text=content,
                    page=None,
                    section=current_heading,
                    bbox=None,
                )
            )

    return segments
