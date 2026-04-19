# tests/proactive/test_cooldown_dnd.py
"""쿨다운·DND 드롭 회귀 전용 테스트."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from proactive.dispatcher import ProactiveDispatcher

from .fakes import FakeCalendar, FakeClock, FakeIdleMonitor, FakeScheduler


def make_dispatcher(
    send_text: AsyncMock | None = None,
    clock: FakeClock | None = None,
    cooldown_min: int = 30,
    dnd_enabled: bool = False,
) -> ProactiveDispatcher:
    return ProactiveDispatcher(
        calendar=FakeCalendar(),
        idle_monitor=FakeIdleMonitor(),
        send_text=send_text or AsyncMock(),
        cooldown_min=cooldown_min,
        dnd_enabled=dnd_enabled,
        clock=clock or FakeClock(),
        scheduler=FakeScheduler(),
    )


@pytest.mark.asyncio
async def test_cooldown_same_topic() -> None:
    """동일 토픽은 쿨다운 내 재emit이 드롭된다."""
    send_text = AsyncMock()
    clock = FakeClock(initial=datetime(2026, 4, 19, 10, 0, 0))
    dispatcher = make_dispatcher(send_text=send_text, clock=clock, cooldown_min=30)
    await dispatcher.start()

    r1 = await dispatcher.emit("idle_rest", {})
    assert r1 is True

    clock.advance(timedelta(minutes=15))  # 쿨다운 미만
    r2 = await dispatcher.emit("idle_rest", {})
    assert r2 is False

    assert send_text.call_count == 1


@pytest.mark.asyncio
async def test_cooldown_different_topics_no_interference() -> None:
    """다른 토픽은 쿨다운 간섭이 없다 (D-3 회귀)."""
    send_text = AsyncMock()
    dispatcher = make_dispatcher(send_text=send_text, cooldown_min=30)
    await dispatcher.start()

    r1 = await dispatcher.emit("morning_briefing", {"events": []})
    r2 = await dispatcher.emit("idle_rest", {})
    r3 = await dispatcher.emit("overwork", {})

    assert r1 is True
    assert r2 is True
    assert r3 is True
    assert send_text.call_count == 3


@pytest.mark.asyncio
async def test_dnd_on_blocks_all() -> None:
    """DND ON 시 모든 토픽이 드롭된다."""
    send_text = AsyncMock()
    dispatcher = make_dispatcher(send_text=send_text, dnd_enabled=True)
    await dispatcher.start()

    for topic in ["morning_briefing", "event_reminder", "idle_rest", "overwork"]:
        result = await dispatcher.emit(topic, {})  # type: ignore[arg-type]
        assert result is False

    send_text.assert_not_called()


@pytest.mark.asyncio
async def test_dnd_toggle_off_allows_emit() -> None:
    """DND 해제 후 emit이 성공한다."""
    send_text = AsyncMock()
    dispatcher = make_dispatcher(send_text=send_text, dnd_enabled=True)
    await dispatcher.start()

    r1 = await dispatcher.emit("idle_rest", {})
    assert r1 is False

    dispatcher.set_dnd(False)
    r2 = await dispatcher.emit("idle_rest", {})
    assert r2 is True

    assert send_text.call_count == 1


@pytest.mark.asyncio
async def test_set_dnd_propagates_to_idle_monitor() -> None:
    """set_dnd() 호출 시 IdleMonitor에도 동일 값이 전파된다 (D-2 회귀)."""
    idle_monitor = FakeIdleMonitor()
    dispatcher = ProactiveDispatcher(
        calendar=FakeCalendar(),
        idle_monitor=idle_monitor,
        send_text=AsyncMock(),
        scheduler=FakeScheduler(),
    )
    await dispatcher.start()

    dispatcher.set_dnd(True)
    assert idle_monitor.last_dnd_value is True
    assert idle_monitor.set_dnd_call_count == 1

    dispatcher.set_dnd(False)
    assert idle_monitor.last_dnd_value is False
    assert idle_monitor.set_dnd_call_count == 2


@pytest.mark.asyncio
async def test_set_dnd_type_error() -> None:
    """set_dnd에 bool이 아닌 값 전달 → TypeError."""
    dispatcher = make_dispatcher()
    await dispatcher.start()

    with pytest.raises(TypeError):
        dispatcher.set_dnd("yes")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_cooldown_exact_boundary() -> None:
    """쿨다운 경계값: cooldown_min × 60초 미만이면 드롭, 이상이면 통과."""
    send_text = AsyncMock()
    clock = FakeClock(initial=datetime(2026, 4, 19, 10, 0, 0))
    dispatcher = make_dispatcher(send_text=send_text, clock=clock, cooldown_min=10)
    await dispatcher.start()

    r1 = await dispatcher.emit("idle_rest", {})
    assert r1 is True

    # 정확히 9분 59초 — 아직 쿨다운 중
    clock.advance(timedelta(seconds=10 * 60 - 1))
    r2 = await dispatcher.emit("idle_rest", {})
    assert r2 is False

    # 정확히 10분 — 쿨다운 만료 (>= 기준)
    clock.advance(timedelta(seconds=1))
    r3 = await dispatcher.emit("idle_rest", {})
    assert r3 is True

    assert send_text.call_count == 2
