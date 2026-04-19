# tests/proactive/test_dispatcher.py
"""ProactiveDispatcher 정상(N) + 엣지(E) + 적대적(A) 테스트."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from proactive.dispatcher import ProactiveDispatcher

from .fakes import FakeCalendar, FakeClock, FakeEvent, FakeIdleMonitor, FakeScheduler


# ──────────────────────────────────────────────────────────────────────
# 헬퍼 팩토리
# ──────────────────────────────────────────────────────────────────────


def make_dispatcher(
    send_text: AsyncMock | None = None,
    clock: FakeClock | None = None,
    scheduler: FakeScheduler | None = None,
    calendar: FakeCalendar | None = None,
    idle_monitor: FakeIdleMonitor | None = None,
    dnd_enabled: bool = False,
    cooldown_min: int = 30,
) -> ProactiveDispatcher:
    if send_text is None:
        send_text = AsyncMock()
    if clock is None:
        clock = FakeClock()
    if scheduler is None:
        scheduler = FakeScheduler()
    if calendar is None:
        calendar = FakeCalendar()
    if idle_monitor is None:
        idle_monitor = FakeIdleMonitor()

    return ProactiveDispatcher(
        calendar=calendar,
        idle_monitor=idle_monitor,
        send_text=send_text,
        cooldown_min=cooldown_min,
        dnd_enabled=dnd_enabled,
        clock=clock,
        scheduler=scheduler,
    )


# ──────────────────────────────────────────────────────────────────────
# N (정상) 케이스
# ──────────────────────────────────────────────────────────────────────


class TestNormal:
    """정상 케이스 N-1~N-7."""

    @pytest.mark.asyncio
    async def test_n1_emit_morning_briefing_success(self) -> None:
        """N-1: emit("morning_briefing") 성공 — send_text 1회 호출, 쿨다운 기록."""
        send_text = AsyncMock()
        dispatcher = make_dispatcher(send_text=send_text)
        await dispatcher.start()

        result = await dispatcher.emit("morning_briefing", {"events": []})

        assert result is True
        send_text.assert_called_once()
        call_payload = send_text.call_args[0][0]
        assert call_payload["type"] == "ai-speak-signal"
        assert call_payload["topic"] == "morning_briefing"
        assert "morning_briefing" in dispatcher._last_emitted_at

    @pytest.mark.asyncio
    async def test_n2_emit_event_reminder_success(self) -> None:
        """N-2: emit("event_reminder") 성공 + 쿨다운 기록."""
        send_text = AsyncMock()
        dispatcher = make_dispatcher(send_text=send_text)
        await dispatcher.start()

        context = {
            "event_id": 1,
            "title": "회의",
            "start": "2026-04-19T15:00:00+09:00",
            "minutes_until": 10,
        }
        result = await dispatcher.emit("event_reminder", context)

        assert result is True
        call_payload = send_text.call_args[0][0]
        assert call_payload["topic"] == "event_reminder"
        assert "회의" in call_payload["text"]

    @pytest.mark.asyncio
    async def test_n3_idle_rest_callback(self) -> None:
        """N-3: IdleMonitor 콜백 → idle_rest emit."""
        send_text = AsyncMock()
        idle_monitor = FakeIdleMonitor()
        dispatcher = make_dispatcher(send_text=send_text, idle_monitor=idle_monitor)
        await dispatcher.start()

        await idle_monitor.trigger_idle_event("idle_rest")

        send_text.assert_called_once()
        call_payload = send_text.call_args[0][0]
        assert call_payload["topic"] == "idle_rest"

    @pytest.mark.asyncio
    async def test_n4_overwork_callback(self) -> None:
        """N-4: IdleMonitor 콜백 → overwork emit."""
        send_text = AsyncMock()
        idle_monitor = FakeIdleMonitor()
        dispatcher = make_dispatcher(send_text=send_text, idle_monitor=idle_monitor)
        await dispatcher.start()

        await idle_monitor.trigger_idle_event("overwork")

        send_text.assert_called_once()
        call_payload = send_text.call_args[0][0]
        assert call_payload["topic"] == "overwork"

    @pytest.mark.asyncio
    async def test_n5_cooldown_expires_resend(self) -> None:
        """N-5: 쿨다운 만료 후 재emit 성공 — send_text 2회 호출."""
        send_text = AsyncMock()
        clock = FakeClock(initial=datetime(2026, 4, 19, 9, 0, 0))
        dispatcher = make_dispatcher(send_text=send_text, clock=clock, cooldown_min=30)
        await dispatcher.start()

        r1 = await dispatcher.emit("idle_rest", {})
        assert r1 is True

        clock.advance(timedelta(minutes=31))
        r2 = await dispatcher.emit("idle_rest", {})
        assert r2 is True

        assert send_text.call_count == 2

    @pytest.mark.asyncio
    async def test_n6_emit_with_dnd_off(self) -> None:
        """N-6: DND OFF 상태에서 정상 emit → True 반환."""
        send_text = AsyncMock()
        dispatcher = make_dispatcher(send_text=send_text, dnd_enabled=False)
        await dispatcher.start()

        result = await dispatcher.emit("idle_rest", {})

        assert result is True

    @pytest.mark.asyncio
    async def test_n7_start_stop_normal(self) -> None:
        """N-7: start()/stop() 정상 호출 — FakeScheduler에 2건 잡 등록, 콜백 해제."""
        scheduler = FakeScheduler()
        idle_monitor = FakeIdleMonitor()
        dispatcher = make_dispatcher(scheduler=scheduler, idle_monitor=idle_monitor)

        await dispatcher.start()

        assert scheduler.add_job_call_count == 2
        assert scheduler.start_call_count == 1
        assert idle_monitor._callback is not None  # 콜백 등록됨

        await dispatcher.stop()

        assert scheduler.shutdown_call_count == 1
        assert idle_monitor._callback is None  # 콜백 해제됨


# ──────────────────────────────────────────────────────────────────────
# E (엣지) 케이스
# ──────────────────────────────────────────────────────────────────────


class TestEdge:
    """엣지 케이스 E-1~E-7."""

    @pytest.mark.asyncio
    async def test_e1_cooldown_blocks_resend(self) -> None:
        """E-1: 쿨다운 중 emit → False, send_text 1회만 호출."""
        send_text = AsyncMock()
        clock = FakeClock(initial=datetime(2026, 4, 19, 9, 0, 0))
        dispatcher = make_dispatcher(send_text=send_text, clock=clock, cooldown_min=30)
        await dispatcher.start()

        r1 = await dispatcher.emit("idle_rest", {})
        assert r1 is True

        clock.advance(timedelta(minutes=29, seconds=59))
        r2 = await dispatcher.emit("idle_rest", {})
        assert r2 is False

        assert send_text.call_count == 1

    @pytest.mark.asyncio
    async def test_e2_dnd_blocks_all_topics(self) -> None:
        """E-2: DND ON → 모든 토픽 drop, send_text 0회."""
        send_text = AsyncMock()
        dispatcher = make_dispatcher(send_text=send_text)
        await dispatcher.start()
        dispatcher.set_dnd(True)

        for topic in ["morning_briefing", "event_reminder", "idle_rest", "overwork"]:
            result = await dispatcher.emit(topic, {})  # type: ignore[arg-type]
            assert result is False

        send_text.assert_not_called()
        # _last_emitted_at 갱신 없음
        assert len(dispatcher._last_emitted_at) == 0

    @pytest.mark.asyncio
    async def test_e3_topic_cooldown_independent(self) -> None:
        """E-3: 토픽별 쿨다운 독립 (D-3 회귀) — 서로 다른 토픽은 쿨다운 간섭 없음."""
        send_text = AsyncMock()
        dispatcher = make_dispatcher(send_text=send_text, cooldown_min=30)
        await dispatcher.start()

        r1 = await dispatcher.emit("morning_briefing", {"events": []})
        r2 = await dispatcher.emit("event_reminder", {"event_id": 1, "title": "회의"})

        assert r1 is True
        assert r2 is True
        assert send_text.call_count == 2

    @pytest.mark.asyncio
    async def test_e4_job_morning_no_events(self) -> None:
        """E-4: morning briefing 잡, events 0건 — 발송됨."""
        send_text = AsyncMock()
        calendar = FakeCalendar(all_events=[])
        dispatcher = make_dispatcher(send_text=send_text, calendar=calendar)
        await dispatcher.start()

        await dispatcher._job_morning_briefing()

        send_text.assert_called_once()
        call_payload = send_text.call_args[0][0]
        assert "등록된 일정이 없어요" in call_payload["text"]

    @pytest.mark.asyncio
    async def test_e5_event_reminder_dedup(self) -> None:
        """E-5: event_reminder 중복 방지 — 같은 이벤트는 1회만 알림."""
        send_text = AsyncMock()
        from datetime import timezone as tz

        ev = FakeEvent(id=1, title="회의", start=datetime.now(tz.utc) + timedelta(minutes=8))
        calendar = FakeCalendar(due_events=[ev], all_events=[ev])
        dispatcher = make_dispatcher(send_text=send_text, calendar=calendar, cooldown_min=1)
        await dispatcher.start()

        await dispatcher._job_event_reminder()
        await dispatcher._job_event_reminder()

        # 쿨다운이 있으므로 첫 번째만 성공, 두 번째는 쿨다운으로 drop
        # _notified_reminders에 1이 추가되어야 함
        assert 1 in dispatcher._notified_reminders

    @pytest.mark.asyncio
    async def test_e6_start_idempotent(self) -> None:
        """E-6: start() 중복 호출 — 두 번째는 no-op, 잡 2건만 등록."""
        scheduler = FakeScheduler()
        dispatcher = make_dispatcher(scheduler=scheduler)

        await dispatcher.start()
        await dispatcher.start()  # 두 번째 호출

        assert scheduler.add_job_call_count == 2  # 잡은 2건만
        assert scheduler.start_call_count == 1  # start는 1회만

    @pytest.mark.asyncio
    async def test_e7_invalid_topic_raises(self) -> None:
        """E-7: 잘못된 topic → ValueError."""
        dispatcher = make_dispatcher()
        await dispatcher.start()

        with pytest.raises(ValueError, match="unknown topic"):
            await dispatcher.emit("unknown_topic", {})  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────
# A (적대적) 케이스
# ──────────────────────────────────────────────────────────────────────


class TestAdversarial:
    """적대적 케이스 A-1~A-4."""

    @pytest.mark.asyncio
    async def test_a1_apscheduler_init_failure(self) -> None:
        """A-1: APScheduler 초기화 실패 → _enabled=False, 앱 기동 계속 (D-8 회귀)."""
        broken_scheduler = FakeScheduler(start_side_effect=RuntimeError("scheduler broken"))
        dispatcher = make_dispatcher(scheduler=broken_scheduler)

        # 예외가 전파되면 안 됨
        await dispatcher.start()

        assert dispatcher._enabled is False

        # 후속 emit은 False 반환
        result = await dispatcher.emit("idle_rest", {})
        assert result is False

    @pytest.mark.asyncio
    async def test_a2_send_text_exception_swallowed(self) -> None:
        """A-2: send_text 예외 → False 반환, 쿨다운 미갱신, 본 모듈 생존 (D-7 회귀)."""
        send_text = AsyncMock(side_effect=ConnectionError("ws closed"))
        dispatcher = make_dispatcher(send_text=send_text)
        await dispatcher.start()

        result = await dispatcher.emit("idle_rest", {})

        assert result is False
        # 쿨다운 미갱신 → 다음 틱에 재시도 가능
        assert "idle_rest" not in dispatcher._last_emitted_at

        # 후속 emit 정상 동작 (send_text는 계속 예외지만 모듈은 살아있음)
        result2 = await dispatcher.emit("overwork", {})
        assert result2 is False  # 같은 이유로 False지만 예외는 없음

    @pytest.mark.asyncio
    async def test_a3_clock_regression(self) -> None:
        """A-3: 시계 역행 — 쿨다운 체크 왜곡, 예외 없이 허용."""
        send_text = AsyncMock()
        clock = FakeClock(initial=datetime(2026, 4, 19, 9, 0, 0))
        dispatcher = make_dispatcher(send_text=send_text, clock=clock, cooldown_min=30)
        await dispatcher.start()

        r1 = await dispatcher.emit("idle_rest", {})
        assert r1 is True

        # 시계를 과거로 역행
        clock.set(datetime(2026, 4, 19, 8, 0, 0))  # 1시간 전으로

        # 쿨다운 체크: (now - last).total_seconds() < 0 → 만료로 간주 → 발송
        r2 = await dispatcher.emit("idle_rest", {})
        assert r2 is True  # 예외 없이 허용

        assert send_text.call_count == 2

    @pytest.mark.asyncio
    async def test_a4_ten_events_same_tick(self) -> None:
        """A-4: 한 틱에 10개 이벤트 — event_reminder 토픽 쿨다운으로 첫 1건만 성공.

        D-3 trade-off: 동일 토픽에서 같은 틱에 여러 이벤트가 있으면
        쿨다운으로 인해 첫 1건만 나감.
        """
        send_text = AsyncMock()
        from datetime import timezone as tz

        events = [
            FakeEvent(
                id=i,
                title=f"일정{i}",
                start=datetime.now(tz.utc) + timedelta(minutes=5 + i),
            )
            for i in range(10)
        ]
        calendar = FakeCalendar(due_events=events, all_events=events)
        dispatcher = make_dispatcher(
            send_text=send_text,
            calendar=calendar,
            cooldown_min=30,
        )
        await dispatcher.start()

        await dispatcher._job_event_reminder()

        # event_reminder 토픽 쿨다운으로 첫 1건만 성공
        assert send_text.call_count == 1
        assert len(dispatcher._notified_reminders) == 1


# ──────────────────────────────────────────────────────────────────────
# M1: _cleanup_notified_reminders 테스트 (§5.3.1)
# ──────────────────────────────────────────────────────────────────────


class TestCleanupNotifiedReminders:
    """_cleanup_notified_reminders TTL 로직 검증."""

    @pytest.mark.asyncio
    async def test_m1a_expired_event_removed_after_ttl(self) -> None:
        """M1-a: 이미 종료된 이벤트(start + duration < now)는 _notified_reminders에서 제거."""
        from datetime import timezone as tz

        # 이미 지난 이벤트: start가 1시간 전, duration=30분 → 종료 30분 전
        past_start = datetime.now(tz.utc) - timedelta(hours=1)
        ev = FakeEvent(id=42, title="지난 회의", start=past_start, duration_minutes=30)
        calendar = FakeCalendar(all_events=[ev])
        dispatcher = make_dispatcher(calendar=calendar)
        await dispatcher.start()

        # 수동으로 set에 추가
        dispatcher._notified_reminders.add(42)
        assert 42 in dispatcher._notified_reminders

        # 청소 실행
        await dispatcher._cleanup_notified_reminders()

        # TTL 경과 → 제거되어야 함
        assert 42 not in dispatcher._notified_reminders

    @pytest.mark.asyncio
    async def test_m1b_active_event_preserved_within_ttl(self) -> None:
        """M1-b: 아직 종료되지 않은 이벤트(start + duration > now)는 보존."""
        from datetime import timezone as tz

        # 미래 이벤트: start가 30분 후, duration=60분
        future_start = datetime.now(tz.utc) + timedelta(minutes=30)
        ev = FakeEvent(id=99, title="미래 회의", start=future_start, duration_minutes=60)
        calendar = FakeCalendar(all_events=[ev])
        dispatcher = make_dispatcher(calendar=calendar)
        await dispatcher.start()

        dispatcher._notified_reminders.add(99)
        assert 99 in dispatcher._notified_reminders

        await dispatcher._cleanup_notified_reminders()

        # TTL 내 → 보존되어야 함
        assert 99 in dispatcher._notified_reminders

    @pytest.mark.asyncio
    async def test_m1c_deleted_event_removed(self) -> None:
        """M1-c: DB에서 삭제된 이벤트(get_event → None)는 제거."""
        # 어느 이벤트도 all_events에 없음 → get_event → None
        calendar = FakeCalendar(all_events=[])
        dispatcher = make_dispatcher(calendar=calendar)
        await dispatcher.start()

        dispatcher._notified_reminders.add(55)
        assert 55 in dispatcher._notified_reminders

        await dispatcher._cleanup_notified_reminders()

        # None(삭제됨) → 제거
        assert 55 not in dispatcher._notified_reminders


# ──────────────────────────────────────────────────────────────────────
# M2: calendar 예외 삼킴 테스트 (dispatcher.py L292~294, L317~319)
# ──────────────────────────────────────────────────────────────────────


class TestCalendarExceptionSwallowed:
    """calendar 예외 삼킴 분기 검증."""

    @pytest.mark.asyncio
    async def test_m2a_morning_briefing_calendar_exception_swallowed(self) -> None:
        """M2-a: _job_morning_briefing 실행 중 calendar.get_events 예외 → topic drop + 예외 전파 없음."""
        send_text = AsyncMock()

        # get_events가 예외를 던지는 FakeCalendar
        class BrokenCalendar(FakeCalendar):
            def get_events(self, start: datetime, end: datetime) -> list:  # type: ignore[override]
                raise RuntimeError("DB 연결 실패")

        calendar = BrokenCalendar()
        dispatcher = make_dispatcher(send_text=send_text, calendar=calendar)
        await dispatcher.start()

        # 예외가 전파되면 안 됨
        await dispatcher._job_morning_briefing()

        # send_text 호출 없음 (topic drop)
        send_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_m2b_event_reminder_calendar_exception_swallowed(self) -> None:
        """M2-b: _job_event_reminder 실행 중 calendar.events_due_within 예외 → topic drop + 예외 전파 없음."""
        send_text = AsyncMock()

        class BrokenCalendar(FakeCalendar):
            def events_due_within(self, minutes: int) -> list:  # type: ignore[override]
                raise RuntimeError("DB 잠김")

        calendar = BrokenCalendar()
        dispatcher = make_dispatcher(send_text=send_text, calendar=calendar)
        await dispatcher.start()

        await dispatcher._job_event_reminder()

        send_text.assert_not_called()


# ──────────────────────────────────────────────────────────────────────
# M3: 생성자 검증 4분기 테스트 (dispatcher.py L84/91/95/100)
# ──────────────────────────────────────────────────────────────────────


class TestConstructorValidation:
    """생성자 검증 4분기: ValueError/TypeError 발생 검증."""

    def test_m3a_send_text_not_callable_raises_typeerror(self) -> None:
        """M3-a: send_text가 callable이 아님 → TypeError."""
        with pytest.raises(TypeError, match="send_text must be callable"):
            ProactiveDispatcher(
                calendar=FakeCalendar(),
                idle_monitor=FakeIdleMonitor(),
                send_text="not_callable",  # type: ignore[arg-type]
            )

    def test_m3b_bad_morning_time_format_raises_valueerror(self) -> None:
        """M3-b: morning_time 포맷 불량(HH:MM 아님) → ValueError."""
        with pytest.raises(ValueError):
            ProactiveDispatcher(
                calendar=FakeCalendar(),
                idle_monitor=FakeIdleMonitor(),
                send_text=AsyncMock(),
                morning_time="9시",  # 잘못된 포맷
            )

    def test_m3c_reminder_lead_minutes_out_of_range_raises_valueerror(self) -> None:
        """M3-c: reminder_lead_minutes <= 0 → ValueError."""
        with pytest.raises(ValueError, match="reminder_lead_minutes"):
            ProactiveDispatcher(
                calendar=FakeCalendar(),
                idle_monitor=FakeIdleMonitor(),
                send_text=AsyncMock(),
                reminder_lead_minutes=0,
            )

    def test_m3d_cooldown_min_out_of_range_raises_valueerror(self) -> None:
        """M3-d: cooldown_min <= 0 → ValueError."""
        with pytest.raises(ValueError, match="cooldown_min"):
            ProactiveDispatcher(
                calendar=FakeCalendar(),
                idle_monitor=FakeIdleMonitor(),
                send_text=AsyncMock(),
                cooldown_min=0,
            )


# ──────────────────────────────────────────────────────────────────────
# M4: test_e5 dedup 수정 — clock.advance로 쿨다운 우회 후 _notified_reminders 검증
# ──────────────────────────────────────────────────────────────────────


class TestEventReminderDedupFixed:
    """E-5 dedup 재검증: _notified_reminders 메커니즘이 실제로 작동하는지 확인."""

    @pytest.mark.asyncio
    async def test_m4_dedup_blocks_second_emit_after_cooldown(self) -> None:
        """M4: 쿨다운을 넘긴 후 같은 event_id → _notified_reminders로 드롭.

        clock.advance로 cooldown(1분) + 여유(1초)를 넘겨 쿨다운 드롭이 아닌
        _notified_reminders 드롭임을 증명한다.
        """
        send_text = AsyncMock()
        from datetime import timezone as tz

        clock = FakeClock(initial=datetime.now(tz.utc))

        ev = FakeEvent(id=1, title="회의", start=datetime.now(tz.utc) + timedelta(minutes=8))
        calendar = FakeCalendar(due_events=[ev], all_events=[ev])
        dispatcher = make_dispatcher(
            send_text=send_text,
            calendar=calendar,
            cooldown_min=1,
            clock=clock,
        )
        await dispatcher.start()

        # 첫 번째 틱 — 성공해서 _notified_reminders에 id=1 추가
        await dispatcher._job_event_reminder()
        assert 1 in dispatcher._notified_reminders
        first_call_count = send_text.call_count
        assert first_call_count == 1

        # 쿨다운(1분) + 여유 1초 전진 → 쿨다운은 통과해야 함
        clock.advance(timedelta(minutes=1, seconds=1))

        # 두 번째 틱 — 쿨다운은 통과하지만 _notified_reminders로 드롭
        await dispatcher._job_event_reminder()
        second_call_count = send_text.call_count

        # _notified_reminders가 없으면 두 번째도 성공(call_count==2)했을 것
        # _notified_reminders가 있으므로 드롭 → call_count 변화 없어야 함
        assert second_call_count == first_call_count, (
            f"두 번째 틱에서 send_text가 호출됨 (call_count={second_call_count}). "
            "_notified_reminders 드롭이 작동하지 않음."
        )
