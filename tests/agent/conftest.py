# tests/agent/conftest.py
"""pytest fixtures for agent tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest
import pytest_asyncio

from open_llm_vtuber.agent.input_types import (
    BatchInput,
    ImageData,
    ImageSource,
    TextData,
    TextSource,
)
from open_llm_vtuber.mcpp.tool_executor import ToolExecutor
from open_llm_vtuber.mcpp.tool_manager import ToolManager
from unittest.mock import MagicMock

from src.agent.gemma_chat_agent import GemmaChatAgent
from src.agent.health import OllamaHealth

from .fakes import make_fake_tool_executor, make_fake_tool_manager


LOOPBACK_URL = "http://127.0.0.1:11434"
LOOPBACK_URL_V1 = "http://127.0.0.1:11434/v1"
MODEL = "gemma4:e4b"
SYSTEM_PROMPT = "너는 사내 AI 비서 새싹이야."


def make_healthy_probe() -> OllamaHealth:
    """성공 헬스체크 결과."""
    return OllamaHealth(
        reachable=True,
        version="0.5.0",
        model_available=True,
        base_url_normalized=LOOPBACK_URL_V1,
        error=None,
    )


def make_unreachable_probe() -> OllamaHealth:
    """연결 실패 헬스체크 결과."""
    return OllamaHealth(
        reachable=False,
        version=None,
        model_available=False,
        base_url_normalized=LOOPBACK_URL_V1,
        error="ConnectionRefused",
    )


def make_model_missing_probe() -> OllamaHealth:
    """모델 없는 헬스체크 결과."""
    return OllamaHealth(
        reachable=True,
        version="0.5.0",
        model_available=False,
        base_url_normalized=LOOPBACK_URL_V1,
        error=f"Model '{MODEL}' not found in Ollama",
    )


@pytest.fixture
def tool_manager() -> MagicMock:
    return make_fake_tool_manager()


@pytest.fixture
def tool_executor() -> MagicMock:
    return make_fake_tool_executor()


@pytest.fixture
def healthy_probe() -> OllamaHealth:
    return make_healthy_probe()


@pytest.fixture
def unreachable_probe() -> OllamaHealth:
    return make_unreachable_probe()


@pytest.fixture
def model_missing_probe() -> OllamaHealth:
    return make_model_missing_probe()


async def _build_agent_async(
    base_url: str = LOOPBACK_URL,
    model: str = MODEL,
    system_prompt: str = SYSTEM_PROMPT,
    tool_manager: ToolManager | None = None,
    tool_executor: ToolExecutor | None = None,
    use_mcpp: bool = True,
    temperature: float = 0.7,
    max_context_tokens: int = 131_000,
    interrupt_method: str = "user",
    faster_first_response: bool = True,
    probe_result: OllamaHealth | None = None,
) -> GemmaChatAgent:
    """헬스체크를 mock하고 GemmaChatAgent.create()로 생성."""
    if probe_result is None:
        probe_result = make_healthy_probe()

    if tool_manager is None and use_mcpp:
        tool_manager = make_fake_tool_manager()
    if tool_executor is None and use_mcpp:
        tool_executor = make_fake_tool_executor()

    with patch("src.agent.gemma_chat_agent.probe_ollama", return_value=probe_result):
        agent = await GemmaChatAgent.create(
            base_url=base_url,
            model=model,
            system_prompt=system_prompt,
            tool_manager=tool_manager,
            tool_executor=tool_executor,
            use_mcpp=use_mcpp,
            temperature=temperature,
            max_context_tokens=max_context_tokens,
            interrupt_method=interrupt_method,  # type: ignore[arg-type]
            faster_first_response=faster_first_response,
        )
    return agent


# 하위 호환을 위한 동기 래퍼 (기존 코드가 사용하는 경우 asyncio.run으로 감쌈)
# 새 테스트는 _build_agent_async 를 직접 사용한다.
def _build_agent(
    base_url: str = LOOPBACK_URL,
    model: str = MODEL,
    system_prompt: str = SYSTEM_PROMPT,
    tool_manager: ToolManager | None = None,
    tool_executor: ToolExecutor | None = None,
    use_mcpp: bool = True,
    temperature: float = 0.7,
    max_context_tokens: int = 131_000,
    interrupt_method: str = "user",
    faster_first_response: bool = True,
    probe_result: OllamaHealth | None = None,
) -> GemmaChatAgent:
    """헬스체크를 mock하고 GemmaChatAgent를 생성 (동기 래퍼).

    내부적으로 asyncio.run()을 사용해 create()를 호출한다.
    이미 실행 중인 이벤트 루프가 없는 환경(동기 테스트)에서만 사용.
    """
    import asyncio

    return asyncio.run(
        _build_agent_async(
            base_url=base_url,
            model=model,
            system_prompt=system_prompt,
            tool_manager=tool_manager,
            tool_executor=tool_executor,
            use_mcpp=use_mcpp,
            temperature=temperature,
            max_context_tokens=max_context_tokens,
            interrupt_method=interrupt_method,
            faster_first_response=faster_first_response,
            probe_result=probe_result,
        )
    )


@pytest_asyncio.fixture
async def agent(tool_manager: MagicMock, tool_executor: MagicMock) -> GemmaChatAgent:
    """기본 GemmaChatAgent fixture (헬스체크 mock)."""
    return await _build_agent_async(
        tool_manager=tool_manager,
        tool_executor=tool_executor,
    )


@pytest_asyncio.fixture
async def agent_no_tools() -> GemmaChatAgent:
    """tool 없는 GemmaChatAgent fixture."""
    return await _build_agent_async(use_mcpp=False, tool_manager=None, tool_executor=None)


@pytest.fixture
def simple_batch() -> BatchInput:
    return BatchInput(texts=[TextData(source=TextSource.INPUT, content="안녕하세요")])


@pytest.fixture
def empty_batch() -> BatchInput:
    return BatchInput(texts=[])


@pytest.fixture
def multimodal_batch() -> BatchInput:
    return BatchInput(
        texts=[TextData(source=TextSource.INPUT, content="이 화면 설명해줘")],
        images=[
            ImageData(
                source=ImageSource.SCREEN,
                data="data:image/png;base64,iVBORw0KGgo=",
                mime_type="image/png",
            )
        ],
    )
