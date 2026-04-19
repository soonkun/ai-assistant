# tests/e2e/test_e2e_24_dnd_drop.py
"""E2E-24: DND ON 상태에서 proactive emit 시도 → 드롭 + 쿨다운 기록 없음.

시나리오 ID: E2E-24-dnd-drop
REQUIREMENTS: §5 "방해 금지 모드"
관련 모듈: M_10 IdleMonitor, M_11 ProactiveDispatcher
마커: e2e_fast
실행 시간 목표: ≤ 5초
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.e2e_fast]


@pytest.mark.timeout(10)
async def test_e2e_24_dnd_drop(
    calendar_service: Any,
    fake_idle_monitor: Any,
    fake_send_text_collector: tuple[list[dict[str, Any]], Any],
) -> None:
    """DND ON 상태에서 emit → 드롭. DND OFF 후 emit → 성공.

    수락 기준:
    - DND ON: WS에 ai-speak-signal 프레임 0건.
    - emit() 반환값 False.
    - _last_emitted_at["idle_rest"] 변경 없음 (여전히 None).
    - DND OFF 후 재호출 시 즉시 emit 성공.
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
        dnd_enabled=True,  # DND ON으로 시작
        scheduler=scheduler,
    )
    await dispatcher.start()

    # DND ON 상태 확인
    assert dispatcher._dnd_enabled is True  # type: ignore[attr-defined]

    # 1. DND ON 상태에서 emit → 드롭
    result = await dispatcher.emit("idle_rest", context={"test": True})
    assert result is False, "DND ON 상태에서 emit()이 False를 반환해야 함"

    # 2. WS 프레임 0건
    idle_rest_frames = [f for f in frames if f.get("topic") == "idle_rest"]
    assert len(idle_rest_frames) == 0, f"DND ON 상태에서 프레임이 송신됨: {idle_rest_frames}"

    # 3. _last_emitted_at 변경 없음 (쿨다운 기록 없음)
    last_emitted = dispatcher._last_emitted_at.get("idle_rest")  # type: ignore[attr-defined]
    assert last_emitted is None, f"DND DROP 후 _last_emitted_at이 기록됨: {last_emitted}"

    # 4. DND OFF 후 emit → 성공
    dispatcher.set_dnd(False)
    result2 = await dispatcher.emit("idle_rest", context={"test": True})
    assert result2 is True, "DND OFF 후 emit()이 True를 반환해야 함"

    # 5. DND OFF 후 프레임 1건
    idle_rest_frames2 = [f for f in frames if f.get("topic") == "idle_rest"]
    assert len(idle_rest_frames2) == 1, f"DND OFF 후 프레임이 1건이어야 함: {idle_rest_frames2}"

    await dispatcher.stop()
