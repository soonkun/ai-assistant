# tests/agent/test_init.py
"""GemmaChatAgent 초기화 테스트 (N-1, A-1, A-2, A-4, A-6)."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from src.agent.errors import AgentBackendError, AgentInitError
from src.agent.gemma_chat_agent import GemmaChatAgent

from .conftest import (
    LOOPBACK_URL,
    LOOPBACK_URL_V1,
    MODEL,
    SYSTEM_PROMPT,
    _build_agent_async,
    make_model_missing_probe,
    make_unreachable_probe,
)


# N-1: 초기화 성공
@pytest.mark.asyncio
async def test_init_success_basic() -> None:
    """N-1: 헬스체크 1회 통과 → 인스턴스 생성 성공."""
    agent = await _build_agent_async()

    assert agent.model == MODEL
    assert isinstance(agent._chat_lock, asyncio.Lock)
    assert agent.system_prompt == SYSTEM_PROMPT
    assert agent.temperature == 0.7
    assert agent.max_context_tokens == 131_000


@pytest.mark.asyncio
async def test_init_llm_base_url_normalized() -> None:
    """E-3: base_url에 /v1 없어도 내부적으로 /v1 포함 URL 사용."""
    agent = await _build_agent_async(base_url=LOOPBACK_URL)

    assert agent._llm.base_url == LOOPBACK_URL_V1


@pytest.mark.asyncio
async def test_init_llm_base_url_already_v1() -> None:
    """E-3: /v1 suffix 있는 base_url → 중복 추가 안 됨."""
    agent = await _build_agent_async(base_url=LOOPBACK_URL_V1)

    assert agent._llm.base_url == LOOPBACK_URL_V1


@pytest.mark.asyncio
async def test_init_empty_base_url_raises() -> None:
    """빈 base_url → AgentInitError."""
    with pytest.raises(AgentInitError, match="base_url required"):
        await GemmaChatAgent.create(base_url="", system_prompt=SYSTEM_PROMPT, use_mcpp=False)


@pytest.mark.asyncio
async def test_init_invalid_scheme_raises() -> None:
    """ftp:// scheme → AgentInitError."""
    with pytest.raises(AgentInitError, match="scheme must be http/https"):
        await GemmaChatAgent.create(
            base_url="ftp://127.0.0.1:11434",
            system_prompt=SYSTEM_PROMPT,
            use_mcpp=False,
        )


@pytest.mark.asyncio
async def test_init_temperature_out_of_range_raises() -> None:
    """temperature > 2.0 → AgentInitError."""
    with pytest.raises(AgentInitError, match="temperature out of range"):
        await GemmaChatAgent.create(
            base_url=LOOPBACK_URL,
            system_prompt=SYSTEM_PROMPT,
            temperature=3.0,
            use_mcpp=False,
        )


@pytest.mark.asyncio
async def test_init_negative_temperature_raises() -> None:
    """temperature < 0.0 → AgentInitError."""
    with pytest.raises(AgentInitError, match="temperature out of range"):
        await GemmaChatAgent.create(
            base_url=LOOPBACK_URL,
            system_prompt=SYSTEM_PROMPT,
            temperature=-0.1,
            use_mcpp=False,
        )


@pytest.mark.asyncio
async def test_init_use_mcpp_without_tools_raises() -> None:
    """use_mcpp=True인데 tool_manager=None → AgentInitError."""
    with pytest.raises(AgentInitError, match="tool_manager required"):
        await GemmaChatAgent.create(
            base_url=LOOPBACK_URL,
            system_prompt=SYSTEM_PROMPT,
            use_mcpp=True,
            tool_manager=None,
            tool_executor=None,
        )


@pytest.mark.asyncio
async def test_init_system_prompt_none_raises() -> None:
    """system_prompt=None → AgentInitError."""
    with pytest.raises(AgentInitError, match="system_prompt must be str"):
        await GemmaChatAgent.create(  # type: ignore[arg-type]
            base_url=LOOPBACK_URL,
            system_prompt=None,
            use_mcpp=False,
        )


# A-1: Ollama 3회 재시도 모두 실패 + 호출 횟수 검증
@pytest.mark.asyncio
async def test_init_ollama_unreachable_raises() -> None:
    """A-1: Ollama 3회 재시도 모두 실패 → AgentBackendError. probe_ollama 호출 3회 확인."""
    unreachable = make_unreachable_probe()
    call_count = 0

    async def counting_probe(base_url: str, model: str, timeout_sec: float = 3.0):  # type: ignore[no-untyped-def]
        nonlocal call_count
        call_count += 1
        return unreachable

    with patch(
        "src.agent.gemma_chat_agent.probe_ollama",
        side_effect=counting_probe,
    ):
        with pytest.raises(AgentBackendError, match="Ollama unreachable"):
            await GemmaChatAgent.create(
                base_url=LOOPBACK_URL,
                system_prompt=SYSTEM_PROMPT,
                use_mcpp=False,
            )

    # 3회 probe 시도 확인
    assert call_count == 3


# A-2: 모델 태그 부재
@pytest.mark.asyncio
async def test_init_model_not_available_raises() -> None:
    """A-2: /api/tags에 모델 없음 → AgentBackendError."""
    missing = make_model_missing_probe()

    with patch(
        "src.agent.gemma_chat_agent.probe_ollama",
        return_value=missing,
    ):
        with pytest.raises(AgentBackendError, match="not available in Ollama"):
            await GemmaChatAgent.create(
                base_url=LOOPBACK_URL,
                model=MODEL,
                system_prompt=SYSTEM_PROMPT,
                use_mcpp=False,
            )


# A-4: 공개 호스트
@pytest.mark.asyncio
async def test_init_public_host_raises() -> None:
    """A-4: 공개 호스트 base_url → AgentInitError."""
    with pytest.raises(AgentInitError, match="loopback or private IP"):
        await GemmaChatAgent.create(
            base_url="https://api.openai.com/v1",
            system_prompt=SYSTEM_PROMPT,
            use_mcpp=False,
        )


# E-7: max_context_tokens 경계값
@pytest.mark.asyncio
async def test_init_min_context_tokens() -> None:
    """E-7: max_context_tokens=1024 (최소값) → 초기화 성공."""
    agent = await _build_agent_async(max_context_tokens=1024)
    assert agent.max_context_tokens == 1024


@pytest.mark.asyncio
async def test_init_max_context_tokens_zero_raises() -> None:
    """max_context_tokens <= 0 → AgentInitError."""
    with pytest.raises(AgentInitError, match="max_context_tokens must be > 0"):
        await GemmaChatAgent.create(
            base_url=LOOPBACK_URL,
            system_prompt=SYSTEM_PROMPT,
            max_context_tokens=0,
            use_mcpp=False,
        )


# A-6: 초기화 중 CancelledError
# BLOCKER-4: aclose() GC 경고 없음 검증
@pytest.mark.asyncio
async def test_aclose_closes_client() -> None:
    """aclose() 호출 후 내부 httpx 클라이언트가 닫혀야 함."""
    agent = await _build_agent_async()

    await agent.aclose()

    # AsyncOpenAI 클라이언트가 닫혔는지 확인
    # upstream AsyncLLM은 self.client(AsyncOpenAI)를 노출하며
    # AsyncOpenAI 내부 httpx 클라이언트가 닫혀있어야 함
    assert agent._llm.client.is_closed()


# A-6: 초기화 중 CancelledError
@pytest.mark.asyncio
async def test_init_cancelled_error_propagates() -> None:
    """A-6: probe_ollama가 1초 sleep 중 태스크 cancel → CancelledError 전파."""

    async def slow_probe(base_url: str, model: str, timeout_sec: float = 3.0):  # type: ignore[no-untyped-def]
        await asyncio.sleep(1.0)
        from .conftest import make_healthy_probe

        return make_healthy_probe()

    async def create_task() -> GemmaChatAgent:
        with patch("src.agent.gemma_chat_agent.probe_ollama", side_effect=slow_probe):
            return await GemmaChatAgent.create(
                base_url=LOOPBACK_URL,
                system_prompt=SYSTEM_PROMPT,
                use_mcpp=False,
            )

    task = asyncio.create_task(create_task())

    # 0.1s 후 취소
    await asyncio.sleep(0.1)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
