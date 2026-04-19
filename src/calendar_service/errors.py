# src/calendar_service/errors.py
"""CalendarService 예외 클래스 5종."""

from __future__ import annotations


class CalendarError(Exception):
    """CalendarService 최상위 기본 예외."""


class CalendarInitError(CalendarError):
    """DB 파일 생성·스키마 초기화 실패(기동 실패)."""


class CalendarValidationError(CalendarError, ValueError):
    """입력 검증 실패(title 길이, duration 범위 등).

    ValueError 다중 상속으로 호출자가 `except ValueError`로도 잡을 수 있다.
    """


class CalendarDBError(CalendarError):
    """sqlite3.OperationalError / IntegrityError wrap."""


class EventNotFoundError(CalendarError):
    """update_event에서 event_id 미존재.

    delete_event는 False 반환으로 처리.
    """
