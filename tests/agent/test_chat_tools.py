# tests/agent/test_chat_tools.py
"""tool calling 경로 테스트 (N-3, E-2, A-3, A-5)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from open_llm_vtuber.agent.input_types import BatchInput, TextData, TextSource

from src.agent.events import (
    AgentError,
    EndOfTurn,
    TextChunk,
    ToolCallResult,
    ToolCallStart,
)

from .conftest import _build_agent_async
from .fakes import make_fake_tool_executor, make_fake_tool_manager


def make_text_batch(text: str = "안녕") -> BatchInput:
    return BatchInput(texts=[TextData(source=TextSource.INPUT, content=text)])


async def collect_events(agent: Any, batch: BatchInput) -> list[Any]:
    events = []
    async for ev in agent.chat(batch):
        events.append(ev)
    return events


# N-3: tool call 1회
@pytest.mark.asyncio
async def test_tool_call_single_round() -> None:
    """N-3: tool 1회 호출 → 순서대로 TextChunk x2, ToolCallStart, ToolCallResult, TextChunk, EndOfTurn."""
    tm = make_fake_tool_manager()
    te = make_fake_tool_executor()
    agent = await _build_agent_async(tool_manager=tm, tool_executor=te, use_mcpp=True)

    tool_loop_items = [
        "일정을 ",
        "등록할게요.",
        {
            "type": "tool_call_status",
            "tool_id": "t1",
            "tool_name": "add_event",
            "status": "running",
            "content": 'Input: {"date": "2025-01-01", "title": "미팅"}',
        },
        {
            "type": "tool_call_status",
            "tool_id": "t1",
            "tool_name": "add_event",
            "status": "completed",
            "content": "이벤트 ID 42로 등록됨",
        },
        "등록 완료했어요.",
    ]

    async def mock_tool_loop(messages: Any, tools: Any) -> AsyncIterator[Any]:
        for item in tool_loop_items:
            yield item

    agent._inner._openai_tool_interaction_loop = mock_tool_loop

    events = await collect_events(agent, make_text_batch("일정 추가해줘"))

    kinds = [e.kind for e in events]
    assert "text_chunk" in kinds
    assert "tool_call_start" in kinds
    assert "tool_call_result" in kinds
    assert "end_of_turn" in kinds

    tool_start = next(e for e in events if isinstance(e, ToolCallStart))
    assert tool_start.name == "add_event"
    assert tool_start.tool_id == "t1"
    assert isinstance(tool_start.arguments, dict)
    assert tool_start.arguments.get("date") == "2025-01-01"

    tool_result = next(e for e in events if isinstance(e, ToolCallResult))
    assert tool_result.ok is True
    assert "42" in tool_result.content

    eot = next(e for e in events if isinstance(e, EndOfTurn))
    assert "일정을" in eot.assistant_text_total
    assert "등록 완료했어요" in eot.assistant_text_total


# E-2: tool만 있고 텍스트 없음
@pytest.mark.asyncio
async def test_tool_only_no_text_response() -> None:
    """E-2: tool call만 있고 텍스트 응답 없음 → 폴백 TextChunk."""
    tm = make_fake_tool_manager()
    te = make_fake_tool_executor()
    agent = await _build_agent_async(tool_manager=tm, tool_executor=te, use_mcpp=True)

    tool_loop_items = [
        {
            "type": "tool_call_status",
            "tool_id": "t2",
            "tool_name": "search_docs",
            "status": "running",
            "content": "Input: {}",
        },
        {
            "type": "tool_call_status",
            "tool_id": "t2",
            "tool_name": "search_docs",
            "status": "completed",
            "content": "검색 결과 없음",
        },
        # 텍스트 없음 (2차 LLM 호출도 빈 응답)
    ]

    async def mock_tool_loop(messages: Any, tools: Any) -> AsyncIterator[Any]:
        for item in tool_loop_items:
            yield item

    agent._inner._openai_tool_interaction_loop = mock_tool_loop

    events = await collect_events(agent, make_text_batch("문서 검색"))

    text_chunks = [e for e in events if isinstance(e, TextChunk)]
    eot = [e for e in events if isinstance(e, EndOfTurn)]
    tool_starts = [e for e in events if isinstance(e, ToolCallStart)]
    tool_results = [e for e in events if isinstance(e, ToolCallResult)]

    assert len(tool_starts) == 1
    assert len(tool_results) == 1

    # 폴백 텍스트
    assert any("도구 실행 결과" in chunk.text for chunk in text_chunks)
    assert len(eot) == 1


# A-3: __API_NOT_SUPPORT_TOOLS__ 방출
@pytest.mark.asyncio
async def test_api_not_support_tools_error() -> None:
    """A-3: upstream이 __API_NOT_SUPPORT_TOOLS__ yield → AgentError 단일 이벤트, EndOfTurn 없음."""
    tm = make_fake_tool_manager()
    te = make_fake_tool_executor()
    agent = await _build_agent_async(tool_manager=tm, tool_executor=te, use_mcpp=True)

    async def mock_tool_loop(messages: Any, tools: Any) -> AsyncIterator[Any]:
        yield "__API_NOT_SUPPORT_TOOLS__"

    agent._inner._openai_tool_interaction_loop = mock_tool_loop

    events = await collect_events(agent, make_text_batch("안녕"))

    assert len(events) == 1
    assert isinstance(events[0], AgentError)
    assert events[0].code == "api_not_support_tools"

    # prompt_mode_flag가 변경되지 않음
    assert agent._inner.prompt_mode_flag is False


# A-5: tool arguments 손상된 JSON
@pytest.mark.asyncio
async def test_tool_error_result() -> None:
    """A-5: ToolExecutor가 error status_update yield → ToolCallResult(ok=False)."""
    tm = make_fake_tool_manager()
    te = make_fake_tool_executor()
    agent = await _build_agent_async(tool_manager=tm, tool_executor=te, use_mcpp=True)

    tool_loop_items: list[Any] = [
        {
            "type": "tool_call_status",
            "tool_id": "t3",
            "tool_name": "add_event",
            "status": "error",
            "content": "Error: Invalid arguments format for tool 'add_event'.",
        },
        "다시 알려주세요",
    ]

    async def mock_tool_loop(messages: Any, tools: Any) -> AsyncIterator[Any]:
        for item in tool_loop_items:
            yield item

    agent._inner._openai_tool_interaction_loop = mock_tool_loop

    events = await collect_events(agent, make_text_batch("일정 추가"))

    tool_result_events = [e for e in events if isinstance(e, ToolCallResult)]
    assert len(tool_result_events) == 1
    assert tool_result_events[0].ok is False
    assert "Error" in tool_result_events[0].content

    # 이후 LLM 응답
    text_chunks = [e for e in events if isinstance(e, TextChunk)]
    assert any("다시" in chunk.text for chunk in text_chunks)


# final_tool_results는 None 반환
@pytest.mark.asyncio
async def test_translate_tool_event_final_results() -> None:
    """final_tool_results → None 반환."""
    agent = await _build_agent_async(use_mcpp=False, tool_manager=None, tool_executor=None)

    result = agent._translate_tool_event(
        {"type": "final_tool_results", "results": [{"tool_id": "t1", "content": "ok"}]}
    )
    assert result is None


# unknown dict type → None 반환
@pytest.mark.asyncio
async def test_translate_tool_event_unknown_type() -> None:
    """알 수 없는 dict type → None."""
    agent = await _build_agent_async(use_mcpp=False, tool_manager=None, tool_executor=None)

    result = agent._translate_tool_event({"type": "unknown_type", "data": "something"})
    assert result is None
