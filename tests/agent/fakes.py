# tests/agent/fakes.py
"""테스트용 가짜 객체 모음."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from open_llm_vtuber.agent.input_types import BatchInput, TextData, TextSource
from open_llm_vtuber.mcpp.tool_executor import ToolExecutor
from open_llm_vtuber.mcpp.tool_manager import ToolManager


def make_batch(text: str = "안녕") -> BatchInput:
    """기본 BatchInput 생성 헬퍼."""
    return BatchInput(texts=[TextData(source=TextSource.INPUT, content=text)])


def make_empty_batch() -> BatchInput:
    """빈 입력 BatchInput."""
    return BatchInput(texts=[])


def make_fake_tool_manager(tools: list[dict[str, Any]] | None = None) -> MagicMock:
    """ToolManager mock."""
    tm = MagicMock(spec=ToolManager)
    tm.get_formatted_tools.return_value = tools or [
        {"type": "function", "function": {"name": "add_event", "parameters": {}}}
    ]
    return tm


def make_fake_tool_executor() -> MagicMock:
    """ToolExecutor mock."""
    te = MagicMock(spec=ToolExecutor)
    return te


async def async_gen_from_list(items: list[Any]) -> AsyncIterator[Any]:
    """리스트를 AsyncIterator로 변환."""
    for item in items:
        yield item


def make_mock_llm_stream(chunks: list[Any]) -> AsyncMock:
    """chat_completion이 chunks를 yield하는 AsyncMock 반환."""

    async def _gen(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        for chunk in chunks:
            yield chunk

    mock_llm = MagicMock()
    mock_llm.chat_completion = _gen
    mock_llm._system = "system prompt"
    mock_llm.base_url = "http://127.0.0.1:11434/v1"
    mock_llm.model = "gemma4:e4b"
    mock_llm.temperature = 0.7
    mock_llm.client = AsyncMock()
    mock_llm.client.close = AsyncMock()
    mock_llm.support_tools = True
    return mock_llm


def make_tool_loop_items(
    text_before: list[str],
    tool_name: str,
    tool_id: str,
    tool_args_content: str,
    text_after: list[str],
) -> list[Any]:
    """_openai_tool_interaction_loop 출력 시뮬레이션 아이템 목록 생성."""
    items: list[Any] = []
    items.extend(text_before)
    items.append(
        {
            "type": "tool_call_status",
            "tool_id": tool_id,
            "tool_name": tool_name,
            "status": "running",
            "content": tool_args_content,
        }
    )
    items.append(
        {
            "type": "tool_call_status",
            "tool_id": tool_id,
            "tool_name": tool_name,
            "status": "completed",
            "content": f"{tool_name} 완료",
        }
    )
    items.extend(text_after)
    return items
