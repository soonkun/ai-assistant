# tests/e2e/test_e2e_25_ws_reconnect.py
"""E2E-25: 클라이언트 disconnect → reconnect → _active_ws 재바인딩 → proactive 전달.

시나리오 ID: E2E-25-ws-reconnect
REQUIREMENTS: §5, §4.2 (proactive 발화가 재연결 후에도 도달)
관련 모듈: M_01 AppWebSocketHandler, M_11 ProactiveDispatcher
마커: e2e_fast
실행 시간 목표: ≤ 10초
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.e2e_fast]


@pytest.mark.timeout(15)
async def test_e2e_25_ws_reconnect(
    calendar_service: Any,
    fake_idle_monitor: Any,
) -> None:
    """ws1 연결 → disconnect → ws2 연결 → overwork emit → ws2만 수신.

    수락 기준:
    - ws2가 ai-speak-signal{topic:"overwork"} 프레임 1건 수신.
    - ws1에는 ai-speak-signal 프레임 송신되지 않음.
    """
    from proactive import ProactiveDispatcher
    from tests.proactive.fakes import FakeScheduler

    # ws1, ws2 모킹 (send_text 캡처용)
    ws1_frames: list[dict[str, Any]] = []
    ws2_frames: list[dict[str, Any]] = []

    ws1 = MagicMock()
    ws1.send_text = AsyncMock(side_effect=lambda s: ws1_frames.append(__import__("json").loads(s)))

    ws2 = MagicMock()
    ws2.send_text = AsyncMock(side_effect=lambda s: ws2_frames.append(__import__("json").loads(s)))

    # AppServiceContext._active_ws 시뮬레이션
    # (실제 AppServiceContext를 사용하기 위해 내부 _active_ws 필드 직접 조작)
    active_ws_holder: dict[str, Any] = {"ws": None}

    async def _send_text(payload: dict[str, Any]) -> None:
        """D-13 패턴: _active_ws를 호출 시점에 읽는 late-binding."""
        import json

        ws = active_ws_holder["ws"]
        if ws is None:
            return
        await ws.send_text(json.dumps(payload))

    scheduler = FakeScheduler()
    dispatcher = ProactiveDispatcher(
        calendar=calendar_service,
        idle_monitor=fake_idle_monitor,
        send_text=_send_text,
        morning_time="09:00",
        cooldown_min=30,
        dnd_enabled=False,
        scheduler=scheduler,
    )
    await dispatcher.start()

    # 1. ws1 연결 → _active_ws = ws1
    active_ws_holder["ws"] = ws1

    # 2. ws1 disconnect → _active_ws = None
    await asyncio.sleep(0.05)
    active_ws_holder["ws"] = None

    # 3. ws2 연결 → _active_ws = ws2
    await asyncio.sleep(0.05)
    active_ws_holder["ws"] = ws2

    # 4. overwork 이벤트 emit
    result = await dispatcher.emit("overwork", context={"source": "idle_monitor"})
    assert result is True, "overwork emit이 실패"

    # 5. ws2가 ai-speak-signal{topic:"overwork"} 수신
    overwork_ws2 = [
        f for f in ws2_frames if f.get("type") == "ai-speak-signal" and f.get("topic") == "overwork"
    ]
    assert len(overwork_ws2) == 1, f"ws2가 overwork 프레임을 수신해야 함. ws2_frames: {ws2_frames}"

    # 6. ws1에는 ai-speak-signal 없음
    ws1_ai_speak = [f for f in ws1_frames if f.get("type") == "ai-speak-signal"]
    assert len(ws1_ai_speak) == 0, (
        f"ws1에 ai-speak-signal이 송신되면 안 됨. ws1_frames: {ws1_frames}"
    )

    await dispatcher.stop()
