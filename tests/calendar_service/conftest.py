# tests/calendar_service/conftest.py
"""CalendarService 테스트 공통 픽스처."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Generator

import pytest

from calendar_service.service import CalendarService


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    """임시 SQLite DB 파일 경로."""
    return str(tmp_path / "test_calendar.db")


@pytest.fixture
def svc(db_path: str) -> Generator[CalendarService, None, None]:
    """CalendarService 인스턴스 (테스트 종료 시 close)."""
    service = CalendarService(db_path)
    yield service
    service.close()


@pytest.fixture
def kst_dt() -> datetime:
    """테스트용 KST 기준 datetime (2026-04-20T15:00:00+09:00)."""
    from zoneinfo import ZoneInfo

    return datetime(2026, 4, 20, 15, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))
