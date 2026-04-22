# src/document_ingest/errors.py
"""M_06 DocumentIngest 예외 타입."""

from __future__ import annotations


class DocumentIngestError(Exception):
    """M_06 공통 기본 예외."""


class UnsupportedFormatError(DocumentIngestError):
    """확장자가 지원 목록(.pdf/.docx/.pptx/.hwpx/.txt/.md) 밖."""


class ParseError(DocumentIngestError):
    """파일이 손상되었거나 해당 포맷 파서가 텍스트 추출 실패."""


class IngestIOError(DocumentIngestError):
    """경로 부재·권한 부족·mtime 조회 실패 등 파일 시스템 레벨 오류."""
