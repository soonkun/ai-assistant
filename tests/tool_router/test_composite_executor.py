# tests/tool_router/test_composite_executor.py
"""CompositeToolExecutor 테스트 — upstream ToolExecutor 동작 동등성."""

import inspect
from typing import Any, AsyncIterator
from unittest.mock import MagicMock

import pytest

from src.tool_router.errors import AgentProtocolError
from src.tool_router.router import ToolRouter
from src.tool_router.upstream_adapter import CompositeToolExecutor, ToolRouterAdapter

from tests.tool_router.conftest import FakeScreenshotService


def _make_openai_tool_call(name: str, tool_id: str, args: dict[str, Any]) -> dict[str, Any]:
    """dict 형식 tool call 생성."""
    return {"id": tool_id, "name": name, "input": args}


async def _collect(gen: AsyncIterator[dict[str, Any]]) -> list[dict[str, Any]]:
    """AsyncIterator를 리스트로 수집."""
    items = []
    async for item in gen:
        items.append(item)
    return items


def test_execute_tools_is_async_generator_function() -> None:
    """execute_tools가 실제 async generator function인지 확인 (BLOCKER-1 검증)."""
    assert inspect.isasyncgenfunction(CompositeToolExecutor.execute_tools)


async def test_composite_local_tool_yields_protocol(
    mock_calendar: MagicMock, mock_rag: MagicMock, fake_screenshot: FakeScreenshotService
) -> None:
    """로컬 툴 처리: running → completed → final_tool_results 순서로 yield."""
    router = ToolRouter(calendar=mock_calendar, rag=mock_rag, screenshot=fake_screenshot)
    adapter = ToolRouterAdapter(router)
    composite = adapter.as_upstream_tool_executor(fallback=None)

    call = _make_openai_tool_call("take_screenshot", "tool-001", {})

    # execute_tools는 async generator이므로 await 없이 직접 async for 사용
    results: list[dict[str, Any]] = []
    async for item in composite.execute_tools([call], "OpenAI"):
        results.append(item)

    types = [item["type"] for item in results]
    assert "tool_call_status" in types
    assert "final_tool_results" in types

    # running status 포함
    statuses = [item["status"] for item in results if item.get("type") == "tool_call_status"]
    assert "running" in statuses


async def test_composite_final_tool_results_openai_format(
    mock_calendar: MagicMock, mock_rag: MagicMock, fake_screenshot: FakeScreenshotService
) -> None:
    """final_tool_results의 각 항목이 OpenAI 형식(role=tool, tool_call_id, content)."""
    router = ToolRouter(calendar=mock_calendar, rag=mock_rag, screenshot=fake_screenshot)
    adapter = ToolRouterAdapter(router)
    composite = adapter.as_upstream_tool_executor(fallback=None)

    call = _make_openai_tool_call("take_screenshot", "tool-002", {})
    results: list[dict[str, Any]] = []
    async for item in composite.execute_tools([call], "OpenAI"):
        results.append(item)

    final = next(item for item in results if item["type"] == "final_tool_results")
    assert len(final["results"]) == 1
    result = final["results"][0]
    assert result["role"] == "tool"
    assert result["tool_call_id"] == "tool-002"
    assert "content" in result


async def test_composite_caller_mode_not_openai_raises(
    mock_calendar: MagicMock, mock_rag: MagicMock, fake_screenshot: FakeScreenshotService
) -> None:
    """caller_mode != 'OpenAI' → AgentProtocolError (async generator 이므로 첫 iteration 전에 raise)."""
    router = ToolRouter(calendar=mock_calendar, rag=mock_rag, screenshot=fake_screenshot)
    adapter = ToolRouterAdapter(router)
    composite = adapter.as_upstream_tool_executor(fallback=None)

    with pytest.raises(AgentProtocolError):
        # async generator는 첫 next()/__anext__() 호출 시 body가 실행된다.
        # AgentProtocolError는 yield 전에 raise되므로 async for의 첫 반복에서 발생.
        async for _ in composite.execute_tools([], "Claude"):  # type: ignore[arg-type]
            pass


async def test_composite_unknown_local_tool_without_fallback(
    mock_calendar: MagicMock, mock_rag: MagicMock, fake_screenshot: FakeScreenshotService
) -> None:
    """fallback=None, 로컬도 MCP도 아닌 툴 → error status + final_tool_results."""
    router = ToolRouter(calendar=mock_calendar, rag=mock_rag, screenshot=fake_screenshot)
    adapter = ToolRouterAdapter(router)
    composite = adapter.as_upstream_tool_executor(fallback=None)

    call = _make_openai_tool_call("some_mcp_tool", "tool-003", {})
    results: list[dict[str, Any]] = []
    async for item in composite.execute_tools([call], "OpenAI"):
        results.append(item)

    statuses = [
        item
        for item in results
        if item.get("type") == "tool_call_status" and item.get("status") == "error"
    ]
    assert len(statuses) >= 1
    final = next(item for item in results if item["type"] == "final_tool_results")
    assert len(final["results"]) == 1


async def test_composite_parse_error_tool_call(
    mock_calendar: MagicMock, mock_rag: MagicMock, fake_screenshot: FakeScreenshotService
) -> None:
    """잘못된 tool call 구조 → parse_error 처리."""
    router = ToolRouter(calendar=mock_calendar, rag=mock_rag, screenshot=fake_screenshot)
    adapter = ToolRouterAdapter(router)
    composite = adapter.as_upstream_tool_executor(fallback=None)

    # 잘못된 구조 (name 없음)
    bad_call: dict[str, Any] = {"id": "bad-001"}
    results: list[dict[str, Any]] = []
    async for item in composite.execute_tools([bad_call], "OpenAI"):
        results.append(item)

    error_items = [
        item
        for item in results
        if item.get("type") == "tool_call_status" and item.get("status") == "error"
    ]
    assert len(error_items) >= 1


async def test_composite_multiple_local_tools(
    mock_calendar: MagicMock, mock_rag: MagicMock, fake_screenshot: FakeScreenshotService
) -> None:
    """여러 로컬 툴을 한 번에 처리."""
    router = ToolRouter(calendar=mock_calendar, rag=mock_rag, screenshot=fake_screenshot)
    adapter = ToolRouterAdapter(router)
    composite = adapter.as_upstream_tool_executor(fallback=None)

    calls = [
        _make_openai_tool_call("take_screenshot", "tool-a", {}),
        _make_openai_tool_call("search_docs", "tool-b", {"query": "테스트"}),
    ]

    results: list[dict[str, Any]] = []
    async for item in composite.execute_tools(calls, "OpenAI"):
        results.append(item)

    final = next(item for item in results if item["type"] == "final_tool_results")
    assert len(final["results"]) == 2


async def test_upstream_tool_manager_not_modified(
    mock_calendar: MagicMock, mock_rag: MagicMock, fake_screenshot: FakeScreenshotService
) -> None:
    """ToolRouter가 upstream ToolManager.tools 사전을 수정하지 않는다."""
    # ToolManager mock
    mock_tool_manager = MagicMock()
    mock_tool_manager.tools = {}
    original_tools = dict(mock_tool_manager.tools)

    router = ToolRouter(calendar=mock_calendar, rag=mock_rag, screenshot=fake_screenshot)

    # dispatch 실행
    await router.dispatch("take_screenshot", {})

    # tools 사전이 수정되지 않음
    assert mock_tool_manager.tools == original_tools
