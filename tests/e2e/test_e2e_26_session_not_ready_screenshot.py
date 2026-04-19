# tests/e2e/test_e2e_26_session_not_ready_screenshot.py
"""E2E-26: 세션 준비 전 screenshot-trigger → 친화 에러.

시나리오 ID: E2E-26-session-not-ready-screenshot
REQUIREMENTS: §6 화면 인식 (비차단 에러 정책)
관련 모듈: M_01 ws_handler, M_05b ScreenshotService
마커: e2e_fast
실행 시간 목표: ≤ 5초
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.e2e_fast]


@pytest.mark.timeout(10)
async def test_e2e_26_session_not_ready_screenshot() -> None:
    """세션 준비 전 screenshot-trigger → error{message:"screenshot_failed: session not ready"}.

    수락 기준:
    - error{message:"screenshot_failed: session not ready"} 프레임 수신.
    - 서버 크래시 없음.
    - client_contexts에 client_uid 없음 (세션 미형성 조건 재현).
    """
    from app.ws_handler import AppWebSocketHandler
    from app.service_context import AppServiceContext

    # AppServiceContext mock
    ctx = MagicMock(spec=AppServiceContext)
    ctx.client_contexts = {}  # 빈 dict → 세션 미형성
    ctx.screenshot_service = MagicMock()
    ctx.avatar_state = None
    ctx.app_config = None
    ctx._active_ws = None
    ctx.tool_router = None
    ctx.tool_router_adapter = None

    # AppWebSocketHandler 생성 (upstream 초기화 우회)
    handler = AppWebSocketHandler.__new__(AppWebSocketHandler)
    handler.client_contexts = {}  # 직접 주입
    handler.default_context_cache = ctx
    handler._app_ctx = ctx
    handler._continuous_tasks = {}

    import asyncio

    handler._tasks_lock = asyncio.Lock()

    # WebSocket mock
    ws_responses: list[dict[str, Any]] = []
    ws = MagicMock()
    ws.send_json = AsyncMock(side_effect=lambda data: ws_responses.append(data))

    # 세션 준비 전 screenshot-trigger 송신
    await handler._handle_screenshot_trigger(
        ws,
        "test-client-001",
        {"type": "screenshot-trigger", "prompt": "화면 분석"},
    )

    # 수락 기준 1: error 프레임 수신
    assert ws_responses, "에러 응답이 없음"
    error_resp = ws_responses[0]
    assert error_resp.get("type") == "error", f"type이 'error'가 아님: {error_resp}"
    assert "session not ready" in error_resp.get("message", ""), (
        f"'session not ready' 메시지가 없음: {error_resp}"
    )
