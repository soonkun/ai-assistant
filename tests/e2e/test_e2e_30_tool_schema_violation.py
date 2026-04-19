# tests/e2e/test_e2e_30_tool_schema_violation.py
"""E2E-30: Gemma 잘못된 인자로 툴 호출 → ToolRouter JSON Schema 에러, 크래시 없음.

시나리오 ID: E2E-30-tool-schema-violation
REQUIREMENTS: M_05b §에러 정책
관련 모듈: M_05b ToolRouter
마커: e2e_fast (FakeAgent 결정론)
실행 시간 목표: ≤ 10초
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.e2e_fast]


@pytest.mark.timeout(15)
async def test_e2e_30_tool_schema_violation(
    calendar_service: Any,
) -> None:
    """스키마 위반 툴 호출 → ToolResult.ok=False + 스키마 에러 메시지.

    수락 기준:
    - ToolResult.ok == False.
    - ToolResult.error에 스키마 에러 메시지 포함.
    - CalendarService.add_event 호출 횟수 0.
    - 서버 프로세스 크래시 없음.
    """
    from tool_router.router import ToolRouter
    from tool_router.screenshot import ScreenshotService

    # ScreenshotService mock (capture_once는 사용 안 함)
    screenshot_svc = MagicMock(spec=ScreenshotService)
    screenshot_svc.capture_once = AsyncMock(return_value="data:image/png;base64,AA==")

    router = ToolRouter(
        calendar=calendar_service,
        rag=None,
        screenshot=screenshot_svc,
    )

    # CalendarService.add_event 호출 카운트 추적
    original_add_event = calendar_service.add_event
    add_event_call_count = 0

    def _tracking_add_event(*args: Any, **kwargs: Any) -> Any:
        nonlocal add_event_call_count
        add_event_call_count += 1
        return original_add_event(*args, **kwargs)

    calendar_service.add_event = _tracking_add_event

    # 스키마 위반 인자: start="not-a-date", duration_minutes=-5
    result = await router.dispatch(
        "add_event",
        {
            "title": "X",
            "start": "not-a-date",
            "duration_minutes": -5,
        },
    )

    # 수락 기준 1: ToolResult.ok == False
    assert result.ok is False, f"ToolResult.ok가 True: {result}"

    # 수락 기준 2: ToolResult.error에 스키마 에러 메시지 포함
    assert result.error is not None, "ToolResult.error가 None"
    # JSON Schema validator 에러 메시지 형태 확인
    error_lower = result.error.lower()
    assert any(
        keyword in error_lower
        for keyword in ["schema", "valid", "duration", "start", "-5", "not-a-date", "error"]
    ), f"ToolResult.error에 스키마 에러 메시지가 없음: {result.error!r}"

    # 수락 기준 3: CalendarService.add_event 호출 0회
    assert add_event_call_count == 0, (
        f"스키마 위반 시 CalendarService.add_event가 {add_event_call_count}회 호출됨"
    )
