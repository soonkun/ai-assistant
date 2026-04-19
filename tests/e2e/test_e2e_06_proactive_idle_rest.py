# tests/e2e/test_e2e_06_proactive_idle_rest.py
"""E2E-06: IdleMonitor 유휴 감지 → ProactiveDispatcher 콜백 → 발화 지시.

시나리오 ID: E2E-06-proactive-idle-rest
REQUIREMENTS: §5 휴식 권고
관련 모듈: M_10 IdleMonitor, M_11 ProactiveDispatcher, M_01
마커: e2e_fast
실행 시간 목표: ≤ 8초
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.e2e_fast]


@pytest.mark.timeout(15)
async def test_e2e_06_proactive_idle_rest(
    calendar_service: Any,
    fake_idle_monitor: Any,
    fake_send_text_collector: tuple[list[dict[str, Any]], Any],
) -> None:
    """idle_rest 콜백 직접 호출 → ai-speak-signal 수신 + 쿨다운 적용.

    수락 기준:
    - ai-speak-signal{topic:"idle_rest"} 프레임 1건 수신.
    - 같은 콜백 즉시 재호출 → 쿨다운으로 드롭.
    - 로그에 "idle_rest" 키워드 포함 INFO 이상 레벨 (간접 확인).
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
    await dispatcher.start()

    # 수락 기준 E2E-05 §startup hook: dispatcher.start() 호출 검증
    # (FakeScheduler 기반이므로 실제 AsyncIOScheduler 대신 start_call_count로 확인)
    assert scheduler.start_call_count == 1, "dispatcher.start()가 scheduler.start()를 호출해야 함"

    # 3. IdleMonitor 콜백 직접 호출 (백엔드 무관)
    await fake_idle_monitor.trigger_idle_event("idle_rest")

    # 수락 기준 1: ai-speak-signal {topic:"idle_rest"} 프레임 수신
    idle_frames = [
        f for f in frames if f.get("type") == "ai-speak-signal" and f.get("topic") == "idle_rest"
    ]
    assert len(idle_frames) >= 1, f"idle_rest 프레임이 수신되지 않음. 전체 프레임: {frames}"

    # 수락 기준 2: 쿨다운 — 즉시 재호출 시 드롭
    frames_before = len(frames)
    await fake_idle_monitor.trigger_idle_event("idle_rest")
    frames_after = len(frames)
    assert frames_before == frames_after, (
        "쿨다운 드롭이 작동하지 않음: 두 번째 호출에서도 프레임이 추가됨"
    )

    await dispatcher.stop()
