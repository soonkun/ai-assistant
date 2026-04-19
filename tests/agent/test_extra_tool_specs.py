# tests/agent/test_extra_tool_specs.py
"""CR-04: extra_tool_specs 파라미터 관련 테스트.

N-1: 회귀 — extra_tool_specs=None이면 기존 동작과 동일.
N-2: 병합 — MCP 툴 3개 + extras 1개 → 길이 4, 순서 MCP 먼저, 마지막이 extras.
E-1: 이름 충돌 — MCP와 extras에 같은 이름 → AgentInitError.
E-2: 얕은 복사 — create() 후 호출자 리스트 변조 → agent 내부 불변.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from src.agent.builder import build_chat_agent
from src.agent.errors import AgentInitError
from src.agent.gemma_chat_agent import GemmaChatAgent
from src.app.config import AgentConfig, AppConfig, OllamaConfig

from .conftest import make_healthy_probe, LOOPBACK_URL
from .fakes import make_fake_tool_executor, make_fake_tool_manager


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

_ADD_EVENT_SPEC: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "add_event",
        "description": "캘린더에 일정을 등록한다.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "start": {"type": "string"},
            },
            "required": ["title", "start"],
        },
    },
}

_SEARCH_DOCS_SPEC: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "search_docs",
        "description": "문서를 검색한다.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
}


def _make_mcp_tools(names: list[str]) -> list[dict[str, Any]]:
    """지정 이름으로 MCP tool 목록 생성."""
    return [
        {
            "type": "function",
            "function": {"name": n, "description": f"{n} tool", "parameters": {}},
        }
        for n in names
    ]


def _make_app_config(use_mcpp: bool = True) -> AppConfig:
    return AppConfig(
        agent=AgentConfig(
            temperature=0.7,
            max_context_tokens=131_000,
            faster_first_response=True,
            interrupt_method="user",  # type: ignore[arg-type]
            use_mcpp=use_mcpp,
        )
    )


def _make_ollama_config() -> OllamaConfig:
    return OllamaConfig(base_url=LOOPBACK_URL, model="gemma4:e4b")


# ---------------------------------------------------------------------------
# N-1: 회귀 — extra_tool_specs=None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_n1_regression_extra_none() -> None:
    """N-1: extra_tool_specs=None이면 _formatted_tools_openai 길이가 MCP 툴 수와 동일."""
    mcp_tools = _make_mcp_tools(["tool_a", "tool_b"])
    tm = make_fake_tool_manager(tools=mcp_tools)
    te = make_fake_tool_executor()
    probe = make_healthy_probe()

    with patch("src.agent.gemma_chat_agent.probe_ollama", return_value=probe):
        agent = await GemmaChatAgent.create(
            base_url=LOOPBACK_URL,
            model="gemma4:e4b",
            system_prompt="",
            tool_manager=tm,
            tool_executor=te,
            use_mcpp=True,
            extra_tool_specs=None,
        )

    assert len(agent._formatted_tools_openai) == len(mcp_tools)
    assert agent._formatted_tools_openai == mcp_tools


# ---------------------------------------------------------------------------
# N-2: 병합 — MCP 3개 + extras 1개
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_n2_merge_mcp_and_extras() -> None:
    """N-2: MCP 3개 + extras 1개 → 길이 4, 순서 MCP 먼저, 마지막이 add_event."""
    mcp_tools = _make_mcp_tools(["tool_x", "tool_y", "tool_z"])
    tm = make_fake_tool_manager(tools=mcp_tools)
    te = make_fake_tool_executor()
    probe = make_healthy_probe()

    with patch("src.agent.gemma_chat_agent.probe_ollama", return_value=probe):
        agent = await GemmaChatAgent.create(
            base_url=LOOPBACK_URL,
            model="gemma4:e4b",
            system_prompt="",
            tool_manager=tm,
            tool_executor=te,
            use_mcpp=True,
            extra_tool_specs=[_ADD_EVENT_SPEC],
        )

    assert len(agent._formatted_tools_openai) == 4
    # 순서: MCP 먼저
    assert agent._formatted_tools_openai[:3] == mcp_tools
    # 마지막이 add_event
    assert agent._formatted_tools_openai[-1]["function"]["name"] == "add_event"


# ---------------------------------------------------------------------------
# N-2b: build_chat_agent 경유 병합 검증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_n2b_build_chat_agent_merge() -> None:
    """N-2b: build_chat_agent에서 extra_tool_specs 전달 시 동일하게 병합."""
    mcp_tools = _make_mcp_tools(["tool_x", "tool_y", "tool_z"])
    tm = make_fake_tool_manager(tools=mcp_tools)
    te = make_fake_tool_executor()
    probe = make_healthy_probe()

    with patch("src.agent.gemma_chat_agent.probe_ollama", return_value=probe):
        agent = await build_chat_agent(
            app_config=_make_app_config(use_mcpp=True),
            ollama_config=_make_ollama_config(),
            tool_manager=tm,
            tool_executor=te,
            system_prompt="",
            extra_tool_specs=[_ADD_EVENT_SPEC],
        )

    assert len(agent._formatted_tools_openai) == 4
    assert agent._formatted_tools_openai[-1]["function"]["name"] == "add_event"


# ---------------------------------------------------------------------------
# E-1: 이름 충돌 → AgentInitError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e1_name_conflict_raises_agent_init_error() -> None:
    """E-1: MCP에 search_docs 있고 extras에도 search_docs → AgentInitError."""
    mcp_tools = _make_mcp_tools(["search_docs", "tool_a"])
    tm = make_fake_tool_manager(tools=mcp_tools)
    te = make_fake_tool_executor()
    probe = make_healthy_probe()

    with patch("src.agent.gemma_chat_agent.probe_ollama", return_value=probe):
        with pytest.raises(AgentInitError, match="tool name conflict") as exc_info:
            await GemmaChatAgent.create(
                base_url=LOOPBACK_URL,
                model="gemma4:e4b",
                system_prompt="",
                tool_manager=tm,
                tool_executor=te,
                use_mcpp=True,
                extra_tool_specs=[_SEARCH_DOCS_SPEC],
            )

    assert "search_docs" in str(exc_info.value)


# ---------------------------------------------------------------------------
# E-2: 얕은 복사 — 호출자 변조 영향 없음
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2_shallow_copy_caller_mutation_no_effect() -> None:
    """E-2: create() 후 호출자가 extras 리스트를 변조해도 agent 내부는 불변."""
    mcp_tools = _make_mcp_tools(["tool_x"])
    tm = make_fake_tool_manager(tools=mcp_tools)
    te = make_fake_tool_executor()
    probe = make_healthy_probe()

    caller_extras: list[dict[str, Any]] = [_ADD_EVENT_SPEC]

    with patch("src.agent.gemma_chat_agent.probe_ollama", return_value=probe):
        agent = await GemmaChatAgent.create(
            base_url=LOOPBACK_URL,
            model="gemma4:e4b",
            system_prompt="",
            tool_manager=tm,
            tool_executor=te,
            use_mcpp=True,
            extra_tool_specs=caller_extras,
        )

    initial_count = len(agent._formatted_tools_openai)  # 1 MCP + 1 extras = 2

    # 호출자가 나중에 extras를 변조
    caller_extras.append(
        {
            "type": "function",
            "function": {"name": "evil_tool", "parameters": {}},
        }
    )

    # agent 내부는 변하지 않아야 함
    assert len(agent._formatted_tools_openai) == initial_count


# ---------------------------------------------------------------------------
# 추가: use_mcpp=False인데 extras만 있는 경우 → extras만 반영
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extras_only_when_use_mcpp_false() -> None:
    """use_mcpp=False일 때 extras만 _formatted_tools_openai에 들어가는지 확인."""
    probe = make_healthy_probe()

    with patch("src.agent.gemma_chat_agent.probe_ollama", return_value=probe):
        agent = await GemmaChatAgent.create(
            base_url=LOOPBACK_URL,
            model="gemma4:e4b",
            system_prompt="",
            tool_manager=None,
            tool_executor=None,
            use_mcpp=False,
            extra_tool_specs=[_ADD_EVENT_SPEC],
        )

    assert len(agent._formatted_tools_openai) == 1
    assert agent._formatted_tools_openai[0]["function"]["name"] == "add_event"
