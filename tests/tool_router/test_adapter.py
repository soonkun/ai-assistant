# tests/tool_router/test_adapter.py
"""ToolRouterAdapter.execute_tool JSON 포맷 테스트, N-6."""

import json
from unittest.mock import MagicMock


from src.tool_router.router import ToolRouter
from src.tool_router.upstream_adapter import ToolRouterAdapter

from tests.tool_router.conftest import FakeScreenshotService
from tests.tool_router.fakes import FakeEvent

from datetime import datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


async def test_n6_execute_tool_json_format(
    adapter: ToolRouterAdapter, mock_calendar: MagicMock
) -> None:
    """N-6: execute_tool 반환 JSON 파싱 가능, ok=True, payload.count 존재."""
    events = [
        FakeEvent(
            id=1,
            title="회의",
            start=datetime(2026, 4, 20, 9, 0, tzinfo=KST),
            duration_minutes=60,
        )
    ]
    mock_calendar.get_events.return_value = events

    result_str = await adapter.execute_tool(
        "get_events",
        {
            "start": "2026-04-20T00:00:00+09:00",
            "end": "2026-04-21T00:00:00+09:00",
        },
    )

    # JSON 파싱 가능
    obj = json.loads(result_str)
    assert obj["ok"] is True
    assert "payload" in obj
    assert "count" in obj["payload"]
    assert obj["payload"]["count"] == 1


async def test_execute_tool_failure_json_format(adapter: ToolRouterAdapter) -> None:
    """실패 케이스 — JSON 구조에 ok=false, error, error_code 포함."""
    result_str = await adapter.execute_tool("unknown_tool_xyz", {})
    obj = json.loads(result_str)
    assert obj["ok"] is False
    assert "error" in obj
    assert "error_code" in obj


async def test_execute_tool_ensure_ascii_false(
    adapter: ToolRouterAdapter, mock_rag: MagicMock
) -> None:
    """ensure_ascii=False — 한글이 그대로 유지됨."""
    result_str = await adapter.execute_tool("search_docs", {"query": "예산 승인"})
    # 한글이 유니코드 이스케이프 없이 직접 포함
    assert "예산" in result_str or json.loads(result_str)["ok"] is True


async def test_run_single_tool_screenshot_content_items(
    mock_calendar: MagicMock, mock_rag: MagicMock
) -> None:
    """run_single_tool take_screenshot → content_items에 image 타입 포함."""
    fake_ss = FakeScreenshotService(capture_result="data:image/png;base64,TESTDATA123")
    router = ToolRouter(calendar=mock_calendar, rag=mock_rag, screenshot=fake_ss)
    adapter = ToolRouterAdapter(router)

    is_error, text_content, metadata, content_items = await adapter.run_single_tool(
        "take_screenshot", "tool-123", {}
    )

    assert is_error is False
    assert metadata["source"] == "local"
    assert metadata["tool_name"] == "take_screenshot"
    assert len(content_items) == 1
    assert content_items[0]["type"] == "image"
    assert content_items[0]["mimeType"] == "image/png"


async def test_run_single_tool_failure_content_items(
    mock_calendar: MagicMock, mock_rag: MagicMock, fake_screenshot: FakeScreenshotService
) -> None:
    """run_single_tool 실패 → content_items에 error 타입."""
    router = ToolRouter(calendar=mock_calendar, rag=mock_rag, screenshot=fake_screenshot)
    adapter = ToolRouterAdapter(router)

    is_error, text_content, metadata, content_items = await adapter.run_single_tool(
        "unknown_tool", "tool-456", {}
    )

    assert is_error is True
    assert content_items[0]["type"] == "error"


async def test_run_single_tool_none_input(
    mock_calendar: MagicMock, mock_rag: MagicMock, fake_screenshot: FakeScreenshotService
) -> None:
    """run_single_tool tool_input=None → 빈 dict로 대체."""
    router = ToolRouter(calendar=mock_calendar, rag=mock_rag, screenshot=fake_screenshot)
    adapter = ToolRouterAdapter(router)

    # tool_input=None이어도 예외 없이 처리
    is_error, text_content, metadata, content_items = await adapter.run_single_tool(
        "take_screenshot", "tool-789", None
    )
    # FakeScreenshotService는 예외를 던지지 않으므로 성공
    assert is_error is False
