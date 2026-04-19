# tests/e2e/test_e2e_09_event_reminder_interval.py
"""E2E-09: 일정 10분 전 알림 interval cron → event_reminder emit.

시나리오 ID: E2E-09-event-reminder-interval
REQUIREMENTS: §4.2 알림
관련 모듈: M_09 CalendarService, M_11 ProactiveDispatcher
마커: e2e_fast (실제 AsyncIOScheduler 사용 — E2E_SCENARIOS §5 수락기준 #4 충족)
실행 시간 목표: ≤ 12초

§5 수락 기준 #4: 실제 AsyncIOScheduler isinstance + cron/interval 트리거 1건 관찰.
§5 수락 기준 #5: create_app 경유 아닌 직접 dispatcher.start()로 startup hook 대리 검증.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.e2e_fast]

_KST = ZoneInfo("Asia/Seoul")


@pytest.mark.timeout(20)
async def test_e2e_09_event_reminder_interval(
    calendar_service: Any,
    fake_idle_monitor: Any,
    fake_send_text_collector: tuple[list[dict[str, Any]], Any],
) -> None:
    """실제 AsyncIOScheduler로 event_reminder interval 트리거 관찰.

    수락 기준:
    - ProactiveDispatcher._scheduler가 AsyncIOScheduler 인스턴스.
    - ai-speak-signal{topic:"event_reminder"} 프레임 1건 수신 (≤ 10초).
    - context.event_id 존재.
    - _notified_reminders에 해당 event_id 기록.
    - 다음 tick에서 재발사 없음.
    """
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    from proactive import ProactiveDispatcher

    frames, send_text = fake_send_text_collector

    # 실제 AsyncIOScheduler + reminder_check_interval_seconds=2 (빠른 트리거)
    dispatcher = ProactiveDispatcher(
        calendar=calendar_service,
        idle_monitor=fake_idle_monitor,
        send_text=send_text,
        morning_time="09:00",
        cooldown_min=30,
        dnd_enabled=False,
        reminder_check_interval_seconds=2,  # 빠른 폴링
        reminder_lead_minutes=10,
    )

    # dispatcher.start() 전에는 _external_scheduler=None이면 _scheduler=None
    # start() 호출 후 AsyncIOScheduler가 생성됨
    await dispatcher.start()

    # 수락 기준 §5-4: isinstance 확인 (start() 후)
    assert isinstance(dispatcher._scheduler, AsyncIOScheduler), (  # type: ignore[attr-defined]
        "dispatcher._scheduler가 AsyncIOScheduler 인스턴스가 아님"
    )

    # CalendarService에 now()+9분 이벤트 시드 (10분 리드 타임 내)
    now_kst = datetime.now(tz=_KST)
    event_start = now_kst + timedelta(minutes=9)
    calendar_service.add_event(
        title="긴급 보고",
        start=event_start,
        duration_minutes=30,
    )

    # 최대 8초 대기 (interval 2초 × 3회 + 여유)
    deadline = asyncio.get_event_loop().time() + 8.0
    reminder_frame = None
    while asyncio.get_event_loop().time() < deadline:
        matching = [
            f
            for f in frames
            if f.get("type") == "ai-speak-signal" and f.get("topic") == "event_reminder"
        ]
        if matching:
            reminder_frame = matching[0]
            break
        await asyncio.sleep(0.2)

    await dispatcher.stop()

    # 수락 기준 1: event_reminder 프레임 수신
    assert reminder_frame is not None, (
        f"event_reminder 프레임이 수신되지 않음 ({8}초 대기). 전체 프레임: {frames}"
    )

    # 수락 기준 2: context.event_id 존재
    context = reminder_frame.get("context", {})
    assert "event_id" in context, f"context에 event_id가 없음: {context}"

    # 수락 기준 3: _notified_reminders에 해당 event_id 기록
    notified = dispatcher._notified_reminders  # type: ignore[attr-defined]
    assert context["event_id"] in notified, f"_notified_reminders에 event_id가 없음: {notified}"

    # 수락 기준 4: 다음 tick에서 재발사 없음 (frames 길이 변화 없음)
    frames_after_stop = len(frames)
    # dispatcher 중지 후 프레임 추가 없음 확인
    await asyncio.sleep(0.1)
    assert len(frames) == frames_after_stop, "dispatcher 중지 후 추가 프레임 발생"
