# src/document_ingest/parsers/txt.py
"""TXT 파서 — 표준 라이브러리 (M_06 스펙 §5.5)."""

from __future__ import annotations

import logging
from pathlib import Path

from document_ingest.segments import _Segment

logger = logging.getLogger(__name__)

# UTF-8 BOM (U+FEFF)
_UTF8_BOM = "﻿"


def _parse_txt(path: str) -> list[_Segment]:
    """TXT 파일에서 텍스트 세그먼트를 추출한다.

    - UTF-8 BOM 제거.
    - 인코딩 실패 시 errors="replace"로 무해하게 처리.
    - 빈 파일 → [] 반환.

    Args:
        path: 절대 또는 상대 경로 문자열.

    Returns:
        list[_Segment]: 0건 (빈 파일) 또는 1건.
    """
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        logger.warning(
            "TXT 읽기 실패: %s: %s",
            Path(path).name,
            exc,
            extra={"path": path, "reason": str(exc)},
        )
        return []

    # UTF-8 BOM 제거
    if text.startswith(_UTF8_BOM):
        text = text[1:]
        logger.warning(
            "TXT UTF-8 BOM 제거: %s",
            Path(path).name,
            extra={"path": path, "reason": "UTF-8 BOM stripped"},
        )

    if not text.strip():
        logger.warning(
            "TXT 빈 파일: %s",
            Path(path).name,
            extra={"path": path, "reason": "empty file"},
        )
        return []

    return [_Segment(text=text, page=None, section=None, bbox=None)]
