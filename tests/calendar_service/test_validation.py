# tests/calendar_service/test_validation.py
"""CalendarService 입력 검증 테스트.

케이스:
  엣지 (E): E3, E4
  적대적 (A): A1, A3
"""

from __future__ import annotations

from datetime import datetime

import pytest

from calendar_service.errors import CalendarValidationError
from calendar_service.service import CalendarService, _KST


# ---------------------------------------------------------------------------
# 엣지 케이스 (Edge)
# ---------------------------------------------------------------------------


class TestDurationBoundaries:
    """E3: duration_minutes 경계값 테스트."""

    def test_e3_duration_1_succeeds(self, svc: CalendarService) -> None:
        """duration=1 성공."""
        start = datetime(2026, 4, 20, 15, 0, tzinfo=_KST)
        event = svc.add_event("test", start, 1)
        assert event.duration_minutes == 1

    def test_e3_duration_1440_succeeds(self, svc: CalendarService) -> None:
        """duration=1440 성공."""
        start = datetime(2026, 4, 20, 15, 0, tzinfo=_KST)
        event = svc.add_event("test", start, 1440)
        assert event.duration_minutes == 1440

    def test_e3_duration_0_fails(self, svc: CalendarService) -> None:
        """duration=0 실패."""
        start = datetime(2026, 4, 20, 15, 0, tzinfo=_KST)
        with pytest.raises(CalendarValidationError):
            svc.add_event("test", start, 0)

    def test_e3_duration_1441_fails(self, svc: CalendarService) -> None:
        """duration=1441 실패."""
        start = datetime(2026, 4, 20, 15, 0, tzinfo=_KST)
        with pytest.raises(CalendarValidationError):
            svc.add_event("test", start, 1441)


class TestTitleBoundaries:
    """E4: title 길이 경계값 테스트."""

    def test_e4_title_1_char_succeeds(self, svc: CalendarService) -> None:
        """title 1자("A") 성공."""
        start = datetime(2026, 4, 20, 15, 0, tzinfo=_KST)
        event = svc.add_event("A", start, 30)
        assert event.title == "A"

    def test_e4_title_500_chars_succeeds(self, svc: CalendarService) -> None:
        """title 500자 성공."""
        start = datetime(2026, 4, 20, 15, 0, tzinfo=_KST)
        long_title = "A" * 500
        event = svc.add_event(long_title, start, 30)
        assert event.title == long_title

    def test_e4_title_empty_fails(self, svc: CalendarService) -> None:
        """title 빈 문자열 실패."""
        start = datetime(2026, 4, 20, 15, 0, tzinfo=_KST)
        with pytest.raises(CalendarValidationError):
            svc.add_event("", start, 30)

    def test_e4_title_501_chars_fails(self, svc: CalendarService) -> None:
        """title 501자 실패."""
        start = datetime(2026, 4, 20, 15, 0, tzinfo=_KST)
        with pytest.raises(CalendarValidationError):
            svc.add_event("A" * 501, start, 30)


# ---------------------------------------------------------------------------
# 적대적 케이스 (Adversarial)
# ---------------------------------------------------------------------------


class TestSQLInjection:
    """A1: SQL 인젝션 시도."""

    def test_a1_sql_injection_in_title(self, svc: CalendarService) -> None:
        """A1: SQL 인젝션 title 그대로 저장, 테이블 살아있음.

        prepared statement가 안전하게 처리해야 한다.
        """
        start = datetime(2026, 4, 20, 15, 0, tzinfo=_KST)
        injection_title = "'; DROP TABLE events; --"

        event = svc.add_event(injection_title, start, 30)
        assert event.id >= 1
        assert event.title == injection_title

        # 테이블이 살아있고 인젝션 title도 저장됨
        retrieved = svc.get_event(event.id)
        assert retrieved is not None
        assert retrieved.title == injection_title

        # get_events도 정상 작동
        results = svc.get_events(
            datetime(2026, 4, 20, 0, 0, tzinfo=_KST),
            datetime(2026, 4, 21, 0, 0, tzinfo=_KST),
        )
        assert len(results) >= 1


class TestAdversarialInputs:
    """A3: 다양한 적대적 입력 폭격."""

    def test_a3_duration_zero(self, svc: CalendarService) -> None:
        """duration=0 → CalendarValidationError, DB에 커밋 없음."""
        start = datetime(2026, 4, 20, 15, 0, tzinfo=_KST)
        with pytest.raises(CalendarValidationError):
            svc.add_event("test", start, 0)

        # DB에 커밋된 행 없음
        results = svc.get_events(
            datetime(2026, 4, 20, 0, 0, tzinfo=_KST),
            datetime(2026, 4, 21, 0, 0, tzinfo=_KST),
        )
        assert results == []

    def test_a3_duration_negative(self, svc: CalendarService) -> None:
        """duration=-1 → CalendarValidationError."""
        start = datetime(2026, 4, 20, 15, 0, tzinfo=_KST)
        with pytest.raises(CalendarValidationError):
            svc.add_event("test", start, -1)

    def test_a3_duration_overflow(self, svc: CalendarService) -> None:
        """duration=10**9 → CalendarValidationError."""
        start = datetime(2026, 4, 20, 15, 0, tzinfo=_KST)
        with pytest.raises(CalendarValidationError):
            svc.add_event("test", start, 10**9)

    def test_a3_title_none(self, svc: CalendarService) -> None:
        """title=None → CalendarValidationError."""
        start = datetime(2026, 4, 20, 15, 0, tzinfo=_KST)
        with pytest.raises(CalendarValidationError):
            svc.add_event(None, start, 30)  # type: ignore[arg-type]

    def test_a3_title_whitespace_only(self, svc: CalendarService) -> None:
        """title='   ' (공백만) → CalendarValidationError."""
        start = datetime(2026, 4, 20, 15, 0, tzinfo=_KST)
        with pytest.raises(CalendarValidationError):
            svc.add_event("   ", start, 30)

    def test_a3_description_too_long(self, svc: CalendarService) -> None:
        """description="x"*5000 → CalendarValidationError."""
        start = datetime(2026, 4, 20, 15, 0, tzinfo=_KST)
        with pytest.raises(CalendarValidationError):
            svc.add_event("test", start, 30, "x" * 5000)
