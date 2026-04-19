# tests/agent/test_builder.py
"""build_chat_agent 빌더 테스트."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.agent.builder import build_chat_agent
from src.agent.errors import AgentInitError
from src.agent.gemma_chat_agent import GemmaChatAgent
from src.app.config import AgentConfig, AppConfig, OllamaConfig

from .conftest import make_healthy_probe
from .fakes import make_fake_tool_executor, make_fake_tool_manager


def make_app_config(
    temperature: float = 0.7,
    max_context_tokens: int = 131_000,
    faster_first_response: bool = True,
    interrupt_method: str = "user",
    use_mcpp: bool = True,
) -> AppConfig:
    return AppConfig(
        agent=AgentConfig(
            temperature=temperature,
            max_context_tokens=max_context_tokens,
            faster_first_response=faster_first_response,
            interrupt_method=interrupt_method,  # type: ignore[arg-type]
            use_mcpp=use_mcpp,
        )
    )


def make_ollama_config(
    base_url: str = "http://127.0.0.1:11434",
    model: str = "gemma4:e4b",
) -> OllamaConfig:
    return OllamaConfig(base_url=base_url, model=model)


@pytest.mark.asyncio
async def test_build_with_tools() -> None:
    """빌더: tool_manager/tool_executor 있으면 use_mcpp=True."""
    app_config = make_app_config()
    ollama_config = make_ollama_config()
    tm = make_fake_tool_manager()
    te = make_fake_tool_executor()
    probe = make_healthy_probe()

    with patch("src.agent.gemma_chat_agent.probe_ollama", return_value=probe):
        agent = await build_chat_agent(
            app_config=app_config,
            ollama_config=ollama_config,
            tool_manager=tm,
            tool_executor=te,
            system_prompt="시스템 프롬프트",
        )

    assert isinstance(agent, GemmaChatAgent)
    assert agent._use_mcpp is True
    assert agent.model == "gemma4:e4b"
    assert agent.temperature == 0.7


@pytest.mark.asyncio
async def test_build_without_tools() -> None:
    """빌더: tool_manager=None이면 use_mcpp=False."""
    app_config = make_app_config(use_mcpp=False)
    ollama_config = make_ollama_config()
    probe = make_healthy_probe()

    with patch("src.agent.gemma_chat_agent.probe_ollama", return_value=probe):
        agent = await build_chat_agent(
            app_config=app_config,
            ollama_config=ollama_config,
            tool_manager=None,
            tool_executor=None,
            system_prompt="",
        )

    assert agent._use_mcpp is False


@pytest.mark.asyncio
async def test_build_custom_temperature() -> None:
    """빌더: 커스텀 temperature 전달."""
    app_config = make_app_config(temperature=1.5, use_mcpp=False)
    ollama_config = make_ollama_config()
    probe = make_healthy_probe()

    with patch("src.agent.gemma_chat_agent.probe_ollama", return_value=probe):
        agent = await build_chat_agent(
            app_config=app_config,
            ollama_config=ollama_config,
            tool_manager=None,
            tool_executor=None,
            system_prompt="",
        )

    assert agent.temperature == 1.5


@pytest.mark.asyncio
async def test_build_public_host_raises() -> None:
    """빌더: 공개 호스트 URL → AgentInitError."""
    app_config = make_app_config(use_mcpp=False)
    ollama_config = OllamaConfig(base_url="https://api.openai.com/v1")

    with pytest.raises(AgentInitError, match="loopback or private IP"):
        await build_chat_agent(
            app_config=app_config,
            ollama_config=ollama_config,
            tool_manager=None,
            tool_executor=None,
            system_prompt="",
        )
