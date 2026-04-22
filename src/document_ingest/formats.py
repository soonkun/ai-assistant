# src/document_ingest/formats.py
"""지원 확장자 테이블 (M_06 스펙 §4.3)."""

from __future__ import annotations

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".pdf",
        ".docx",
        ".pptx",
        ".hwpx",
        ".txt",
        ".md",
        ".markdown",
    }
)
# 대소문자 무시. 내부적으로 .casefold() 비교.
# .markdown은 .md와 동일 처리.
# .doc / .ppt / .hwp(바이너리) 는 미지원 → UnsupportedFormatError.
