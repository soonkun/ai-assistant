# tests/tool_router/test_dispatch_adversarial.py
"""적대적 케이스 A-1 ~ A-8."""

import asyncio
import json
import sqlite3
from typing import Any
import pytest
from zoneinfo import ZoneInfo
from unittest.mock import MagicMock

from src.tool_router.router import ToolRouter
from src.tool_router.types import ToolResult
from src.tool_router.upstream_adapter import ToolRouterAdapter

from tests.tool_router.conftest import FakeScreenshotService

KST = ZoneInfo("Asia/Seoul")


async def test_a1_unknown_tool(
    router: ToolRouter, mock_calendar: MagicMock, mock_rag: MagicMock
) -> None:
    """A-1: 알 수 없는 tool 이름 → unknown_tool."""
    result = await router.dispatch("rm_rf_root", {"path": "/"})
    assert result.ok is False
    assert result.error_code == "unknown_tool"
    assert result.error == "unknown_tool: rm_rf_root"
    # 어떤 서비스도 호출되지 않음
    mock_calendar.add_event.assert_not_called()
    mock_rag.retrieve.assert_not_called()


async def test_a2_add_event_invalid_duration(router: ToolRouter, mock_calendar: MagicMock) -> None:
    """A-2: duration_minutes=-9999 → invalid_arguments."""
    result = await router.dispatch(
        "add_event",
        {
            "title": "x",
            "start": "2026-04-20T15:00:00+09:00",
            "duration_minutes": -9999,
        },
    )
    assert result.ok is False
    assert result.error_code == "invalid_arguments"
    assert result.error is not None
    assert "duration_minutes" in result.error
    mock_calendar.add_event.assert_not_called()


async def test_a3_search_docs_query_1mb(router: ToolRouter, mock_rag: MagicMock) -> None:
    """A-3: query 1MB 문자열 → invalid_arguments."""
    big_query = "x" * 1_048_576
    result = await router.dispatch("search_docs", {"query": big_query})
    assert result.ok is False
    assert result.error_code == "invalid_arguments"
    assert result.error is not None
    assert "query" in result.error
    mock_rag.retrieve.assert_not_called()


async def test_a4_add_event_title_boundary(router: ToolRouter, mock_calendar: MagicMock) -> None:
    """A-4: title 200자 → 성공, 201자 → invalid_arguments."""
    # 200자 — 성공
    result_ok = await router.dispatch(
        "add_event",
        {
            "title": "a" * 200,
            "start": "2026-04-20T15:00:00+09:00",
            "duration_minutes": 30,
        },
    )
    assert result_ok.ok is True

    # 201자 — 실패
    mock_calendar.add_event.reset_mock()
    result_fail = await router.dispatch(
        "add_event",
        {
            "title": "a" * 201,
            "start": "2026-04-20T15:00:00+09:00",
            "duration_minutes": 30,
        },
    )
    assert result_fail.ok is False
    assert result_fail.error_code == "invalid_arguments"


async def test_a5_handler_internal_exception(
    mock_rag: MagicMock, fake_screenshot: FakeScreenshotService, caplog: pytest.LogCaptureFixture
) -> None:
    """A-5: CalendarService.add_event가 sqlite3.OperationalError("disk full") raise → handler_exception."""
    mock_calendar = MagicMock()
    mock_calendar.add_event.side_effect = sqlite3.OperationalError("disk full")

    router = ToolRouter(calendar=mock_calendar, rag=mock_rag, screenshot=fake_screenshot)

    import logging

    with caplog.at_level(logging.ERROR, logger="src.tool_router.router"):
        result = await router.dispatch(
            "add_event",
            {
                "title": "회의",
                "start": "2026-04-20T15:00:00+09:00",
                "duration_minutes": 60,
            },
        )

    assert result.ok is False
    assert result.error_code == "handler_exception"
    assert result.error is not None
    assert result.error.startswith("OperationalError:")
    # 예외가 상위로 전파되지 않음 (여기까지 왔으면 성공)
    # MINOR-3: caplog에 OperationalError 관련 로그 기록 확인
    # r.message는 기본 포맷 메시지, exc_text나 getMessage()로 전체 포함
    full_log_text = "\n".join(r.getMessage() for r in caplog.records)
    assert "OperationalError" in full_log_text or any(
        r.exc_info and r.exc_info[1] and "OperationalError" in type(r.exc_info[1]).__name__
        for r in caplog.records
    )


async def test_a6_screenshot_interval_too_small(
    router: ToolRouter, fake_screenshot: FakeScreenshotService
) -> None:
    """A-6: interval_seconds=0.5 → invalid_arguments (schema minimum=1.0)."""
    result = await router.dispatch(
        "take_screenshot",
        {"continuous": True, "interval_seconds": 0.5},
    )
    assert result.ok is False
    assert result.error_code == "invalid_arguments"
    # start_continuous와 send_text 호출 없음
    assert len(fake_screenshot.start_continuous_calls) == 0
    assert len(fake_screenshot.send_text_calls) == 0


async def test_a7_cancelled_error_propagation(
    mock_rag: MagicMock, fake_screenshot: FakeScreenshotService
) -> None:
    """A-7: 핸들러 내부에서 CancelledError 발생 → 상위로 재전파."""
    mock_calendar = MagicMock()
    mock_calendar.add_event.side_effect = asyncio.CancelledError()

    router = ToolRouter(calendar=mock_calendar, rag=mock_rag, screenshot=fake_screenshot)

    with pytest.raises(asyncio.CancelledError):
        await router.dispatch(
            "add_event",
            {
                "title": "회의",
                "start": "2026-04-20T15:00:00+09:00",
                "duration_minutes": 60,
            },
        )


async def test_a7b_continuous_cancelled_error_no_task_leak(
    mock_rag: MagicMock,
) -> None:
    """A-7b: continuous=True dispatch 중 start_continuous 호출 직후 CancelledError 발생 시
    stop_continuous가 호출되어 task 누수 없음을 검증."""

    class CancelAfterStartScreenshot(FakeScreenshotService):
        """start_continuous 완료 후 CancelledError를 raise하는 가짜 서비스."""

        async def start_continuous(
            self,
            interval_seconds: float,
            on_frame: Any = None,
        ) -> None:
            # 먼저 start_continuous 기록 (실제로 실행됨으로 표시)
            await super().start_continuous(interval_seconds, on_frame=on_frame)
            # task가 생성된 후 CancelledError 발생 시뮬레이션
            raise asyncio.CancelledError()

    fake_ss = CancelAfterStartScreenshot(continuous_running=False)
    router = ToolRouter(calendar=MagicMock(), rag=mock_rag, screenshot=fake_ss)

    with pytest.raises(asyncio.CancelledError):
        await router.dispatch(
            "take_screenshot",
            {"continuous": True, "interval_seconds": 5.0},
        )

    # stop_continuous가 호출되어 정리됨
    assert fake_ss.stop_continuous_calls >= 1
    # is_continuous_running이 False로 복원됨
    assert not fake_ss.is_continuous_running


async def test_a8_execute_tool_non_serializable_payload(
    mock_calendar: MagicMock, mock_rag: MagicMock, fake_screenshot: FakeScreenshotService
) -> None:
    """A-8: execute_tool — 비직렬화 가능 payload → adapter_exception JSON 반환."""
    router = ToolRouter(calendar=mock_calendar, rag=mock_rag, screenshot=fake_screenshot)
    adapter = ToolRouterAdapter(router)

    # dispatch가 non-serializable 객체를 포함한 ToolResult 반환하도록 patch
    from datetime import datetime as _dt

    non_serial_result = ToolResult(
        ok=True,
        payload={"bad": _dt(2026, 4, 20)},  # datetime is not JSON serializable by default
    )

    original_dispatch = router.dispatch

    async def patched_dispatch(name: str, arguments: dict) -> ToolResult:
        if name == "get_events":
            return non_serial_result
        return await original_dispatch(name, arguments)

    router.dispatch = patched_dispatch  # type: ignore[method-assign]

    result_str = await adapter.execute_tool(
        "get_events",
        {"start": "2026-04-20T00:00:00+09:00", "end": "2026-04-21T00:00:00+09:00"},
    )
    obj = json.loads(result_str)
    assert obj["ok"] is False
    assert "adapter_exception" in obj["error"]
    assert obj["error_code"] == "handler_exception"
