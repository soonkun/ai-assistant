# tests/e2e/test_e2e_05_proactive_morning_briefing.py
"""E2E-05: 아침 브리핑 cron 트리거 → WebSocket 발화 지시.

시나리오 ID: E2E-05-proactive-morning-briefing
REQUIREMENTS: §4.2 아침 첫 실행 시 오늘 일정 브리핑
관련 모듈: M_09 CalendarService, M_11 ProactiveDispatcher, M_01
마커: e2e_fast (FakeScheduler 기반 직접 트리거)
실행 시간 목표: ≤ 15초

수락 기준 §5-4/5 (startup hook + AsyncIOScheduler):
  - E2E-05의 FakeScheduler 버전에서는 scheduler.start_call_count로 start() 검증.
  - 실제 AsyncIOScheduler isinstance는 E2E-09에서 검증.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.e2e_fast]

_KST = ZoneInfo("Asia/Seoul")


@pytest.mark.timeout(20)
async def test_e2e_05_proactive_morning_briefing(
    calendar_service: Any,
    fake_idle_monitor: Any,
    fake_send_text_collector: tuple[list[dict[str, Any]], Any],
) -> None:
    """아침 브리핑 잡 직접 트리거 → ai-speak-signal 수신 + events 2건 포함.

    수락 기준:
    - ai-speak-signal{type, topic:"morning_briefing", context.events} 프레임 1건.
    - context.events 길이 = 2.
    - dispatcher.start()가 scheduler.start()를 호출.
    - 쿨다운 기록이 남음 (_last_emitted_at["morning_briefing"]).
    """
    from proactive import ProactiveDispatcher
    from tests.proactive.fakes import FakeScheduler

    frames, send_text = fake_send_text_collector
    scheduler = FakeScheduler()

    dispatcher = ProactiveDispatcher(
        calendar=calendar_service,
        idle_monitor=fake_idle_monitor,
        send_text=send_text,
        morning_time="09:00",
        cooldown_min=30,
        dnd_enabled=False,
        scheduler=scheduler,
    )

    # CalendarService에 오늘 일정 2건 시드
    now_kst = datetime.now(tz=_KST)
    today_start = now_kst.replace(hour=0, minute=0, second=0, microsecond=0)
    calendar_service.add_event(
        title="팀 회의",
        start=today_start.replace(hour=10),
        duration_minutes=60,
    )
    calendar_service.add_event(
        title="점심 약속",
        start=today_start.replace(hour=12),
        duration_minutes=60,
    )

    # startup hook 검증: dispatcher.start() 호출
    await dispatcher.start()
    assert scheduler.start_call_count == 1, (
        "dispatcher.start()가 scheduler.start()를 호출해야 함 (startup hook 검증)"
    )

    # morning_briefing 잡 직접 트리거
    await scheduler.trigger_job("morning_briefing")

    # 수락 기준 1: ai-speak-signal {topic:"morning_briefing"} 프레임 수신
    briefing_frames = [
        f
        for f in frames
        if f.get("type") == "ai-speak-signal" and f.get("topic") == "morning_briefing"
    ]
    assert len(briefing_frames) >= 1, (
        f"morning_briefing 프레임이 수신되지 않음. 전체 프레임: {frames}"
    )

    # 수락 기준 2: context.events 길이 = 2
    context_events = briefing_frames[0].get("context", {}).get("events", [])
    assert len(context_events) == 2, f"context.events 길이가 2가 아님: {len(context_events)}"

    # 수락 기준 3: 쿨다운 기록 남음
    last_emitted = dispatcher._last_emitted_at.get("morning_briefing")  # type: ignore[attr-defined]
    assert last_emitted is not None, "_last_emitted_at['morning_briefing']가 기록되지 않음"

    await dispatcher.stop()
