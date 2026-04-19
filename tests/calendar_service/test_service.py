# tests/calendar_service/test_service.py
"""CalendarService CRUD 테스트.

케이스:
  정상 (N): N1~N5
  엣지 (E): E1, E2, E5
  적대적 (A): A4
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import pytest

from calendar_service.errors import CalendarDBError, CalendarValidationError, EventNotFoundError
from calendar_service.service import CalendarService, _KST


# ---------------------------------------------------------------------------
# 정상 케이스 (Normal)
# ---------------------------------------------------------------------------


class TestNormal:
    """N1~N5: 정상 흐름 테스트."""

    def test_n1_add_get_round_trip(self, svc: CalendarService) -> None:
        """N1: add_event → get_event 왕복.

        반환된 Event의 id/title/duration/start tz-aware 필드가 일치해야 한다.
        """
        start = datetime(2026, 4, 20, 15, 0, 0, tzinfo=_KST)
        event = svc.add_event("회의", start, 60, "기획")

        assert event.id >= 1
        assert event.title == "회의"
        assert event.duration_minutes == 60
        assert event.description == "기획"
        assert event.start.tzinfo is not None

        retrieved = svc.get_event(event.id)
        assert retrieved is not None
        assert retrieved.id == event.id
        assert retrieved.title == event.title
        assert retrieved.duration_minutes == event.duration_minutes
        assert retrieved.description == event.description
        # start: UTC 변환 후 KST 복원이므로 동일 시각
        assert retrieved.start == event.start
        assert retrieved.created_at.tzinfo is not None

    def test_n2_get_events_range_filter(self, svc: CalendarService) -> None:
        """N2: 날짜 범위 필터링.

        9/1, 9/15, 9/30 세 건 등록 → get_events(9/10, 9/20) → 9/15 단 1건, start ASC.
        """
        tz = _KST
        sep1 = datetime(2026, 9, 1, 9, 0, tzinfo=tz)
        sep15 = datetime(2026, 9, 15, 9, 0, tzinfo=tz)
        sep30 = datetime(2026, 9, 30, 9, 0, tzinfo=tz)

        svc.add_event("sep1", sep1, 30)
        ev15 = svc.add_event("sep15", sep15, 30)
        svc.add_event("sep30", sep30, 30)

        start_range = datetime(2026, 9, 10, 0, 0, tzinfo=tz)
        end_range = datetime(2026, 9, 20, 0, 0, tzinfo=tz)
        results = svc.get_events(start_range, end_range)

        assert len(results) == 1
        assert results[0].id == ev15.id
        assert results[0].title == "sep15"

    def test_n3_events_due_within_exact_match(
        self, svc: CalendarService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """N3: events_due_within 정확 매치.

        now+5min 이벤트 1건 + now+20min 이벤트 1건 → events_due_within(10) → 앞 1건만.
        """
        fixed_now = datetime(2026, 4, 20, 10, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr("calendar_service.service._now_utc", lambda: fixed_now)

        svc.add_event("soon", fixed_now + timedelta(minutes=5), 30)
        svc.add_event("later", fixed_now + timedelta(minutes=20), 30)

        results = svc.events_due_within(10)
        assert len(results) == 1
        assert results[0].title == "soon"

    def test_n4_events_due_within_empty(
        self, svc: CalendarService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """N4: 모든 이벤트가 now+30min 이후 → events_due_within(10) → []."""
        fixed_now = datetime(2026, 4, 20, 10, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr("calendar_service.service._now_utc", lambda: fixed_now)

        svc.add_event("far_future", fixed_now + timedelta(minutes=30), 30)

        results = svc.events_due_within(10)
        assert results == []

    def test_n5_close_idempotent(self, db_path: str) -> None:
        """N5: close() 두 번 호출해도 예외 없음. 두 번째는 no-op."""
        svc = CalendarService(db_path)
        svc.close()
        svc.close()  # 예외 없음


# ---------------------------------------------------------------------------
# 엣지 케이스 (Edge)
# ---------------------------------------------------------------------------


class TestEdge:
    """E1, E2, E5: 경계 동작 테스트."""

    def test_e1_naive_datetime_assumed_kst(
        self, svc: CalendarService, caplog: pytest.LogCaptureFixture
    ) -> None:
        """E1: tz-naive 입력 → default_tz(KST) 가정, 경고 로그 1회."""
        naive_start = datetime(2026, 4, 20, 15, 0, 0)  # tz 없음

        with caplog.at_level(logging.WARNING, logger="calendar_service.service"):
            event = svc.add_event("회의", naive_start, 60)

        # 반환 event의 start tzinfo는 KST여야 함
        assert event.start.tzinfo is not None
        assert event.start.utcoffset() == _KST.utcoffset(event.start)

        # 경고 로그 확인
        warning_msgs = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any("naive datetime" in msg for msg in warning_msgs)

    def test_e2_start_equals_end_returns_empty(self, svc: CalendarService) -> None:
        """E2: get_events(t, t) → 빈 리스트 (반열린 구간에서 공집합)."""
        t = datetime(2026, 4, 20, 12, 0, tzinfo=_KST)
        svc.add_event("event", t, 30)
        results = svc.get_events(t, t)
        assert results == []

    def test_e5_update_start_reorders(self, svc: CalendarService) -> None:
        """E5: B를 나중으로 update 후 get_events 정렬 순서 확인.

        A=9/10, B=9/15, C=9/20 → B를 9/25로 update → [A, C, B] 순서.
        """
        tz = _KST
        a = svc.add_event("A", datetime(2026, 9, 10, 9, 0, tzinfo=tz), 30)
        b = svc.add_event("B", datetime(2026, 9, 15, 9, 0, tzinfo=tz), 30)
        c = svc.add_event("C", datetime(2026, 9, 20, 9, 0, tzinfo=tz), 30)

        svc.update_event(b.id, start=datetime(2026, 9, 25, 9, 0, tzinfo=tz))

        results = svc.get_events(
            datetime(2026, 9, 1, 0, 0, tzinfo=tz),
            datetime(2026, 9, 30, 0, 0, tzinfo=tz),
        )
        ids = [r.id for r in results]
        assert ids == [a.id, c.id, b.id]


# ---------------------------------------------------------------------------
# 에러 경로 케이스 (Error Path)
# ---------------------------------------------------------------------------


class TestErrorPaths:
    """스펙 §10 에러 정책 — update_event/delete_event/events_due_within 에러 경로."""

    def test_update_event_not_found_raises(self, svc: CalendarService) -> None:
        """존재하지 않는 event_id로 update_event 호출 → EventNotFoundError.

        DB에 999999 id가 없는 빈 상태에서 실행. 메시지에 id 또는 "not found" 포함.
        """
        with pytest.raises(EventNotFoundError) as exc_info:
            svc.update_event(event_id=999999, title="new")
        error_msg = str(exc_info.value).lower()
        assert "999999" in error_msg or "not found" in error_msg

    def test_delete_event_not_found_returns_false(self, svc: CalendarService) -> None:
        """존재하지 않는 event_id로 delete_event 호출 → False 반환 (예외 아님).

        스펙 §10: delete_event → False (event_id 미존재).
        """
        result = svc.delete_event(event_id=999999)
        assert result is False

    def test_events_due_within_nonpositive_raises(self, svc: CalendarService) -> None:
        """minutes=0 및 minutes=-5 → CalendarValidationError.

        스펙 §7: events_due_within의 minutes는 1 이상.
        """
        with pytest.raises(CalendarValidationError):
            svc.events_due_within(minutes=0)

        with pytest.raises(CalendarValidationError):
            svc.events_due_within(minutes=-5)


# ---------------------------------------------------------------------------
# 적대적 케이스 (Adversarial)
# ---------------------------------------------------------------------------


class TestAdversarial:
    """A4: close 이후 사용 테스트."""

    def test_a4_use_after_close(self, db_path: str) -> None:
        """A4: close() 후 add_event 호출 → CalendarDBError.

        DB 파일에 신규 행이 없어야 한다.
        """
        svc = CalendarService(db_path)
        svc.close()

        start = datetime(2026, 4, 20, 15, 0, tzinfo=_KST)
        with pytest.raises(CalendarDBError, match="calendar service is closed"):
            svc.add_event("test", start, 30)

        # 다른 인스턴스로 DB 확인 — 신규 행 없음
        svc2 = CalendarService(db_path)
        try:
            results = svc2.get_events(
                datetime(2026, 4, 20, 0, 0, tzinfo=_KST),
                datetime(2026, 4, 21, 0, 0, tzinfo=_KST),
            )
            assert results == []
        finally:
            svc2.close()
