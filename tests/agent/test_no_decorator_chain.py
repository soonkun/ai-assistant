# tests/agent/test_no_decorator_chain.py
"""DoD 검증: upstream 데코레이터 체인이 chat() 실행 중 호출되지 않음을 확인."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import patch

import pytest

from open_llm_vtuber.agent.input_types import BatchInput, TextData, TextSource

from .conftest import _build_agent_async


def make_text_batch(text: str = "안녕") -> BatchInput:
    return BatchInput(texts=[TextData(source=TextSource.INPUT, content=text)])


@pytest.mark.asyncio
async def test_decorator_chain_not_invoked() -> None:
    """DoD: chat() 실행 시 upstream 데코레이터 체인 4개가 호출되지 않음을 monkeypatch로 확인.

    sentence_divider, tts_filter, actions_extractor, display_processor 각각을
    sentinel MagicMock으로 대체 후 chat() 실행 → mock.called is False 검증.
    """
    agent = await _build_agent_async(use_mcpp=False, tool_manager=None, tool_executor=None)

    async def mock_stream(messages: Any, *args: Any, **kwargs: Any) -> AsyncIterator[str]:
        yield "안녕하세요"

    agent._llm.chat_completion = mock_stream
    batch = make_text_batch("안녕")

    with (
        patch("open_llm_vtuber.agent.agents.basic_memory_agent.sentence_divider") as mock_sd,
        patch("open_llm_vtuber.agent.agents.basic_memory_agent.tts_filter") as mock_tf,
        patch("open_llm_vtuber.agent.agents.basic_memory_agent.actions_extractor") as mock_ae,
        patch("open_llm_vtuber.agent.agents.basic_memory_agent.display_processor") as mock_dp,
    ):
        events = [ev async for ev in agent.chat(batch)]

    # 이벤트가 정상 방출됐는지 확인
    assert len(events) > 0

    # 데코레이터 체인은 호출되지 않아야 함
    assert not mock_sd.called, "sentence_divider가 호출됨 — 데코레이터 체인 우회 실패"
    assert not mock_tf.called, "tts_filter가 호출됨 — 데코레이터 체인 우회 실패"
    assert not mock_ae.called, "actions_extractor가 호출됨 — 데코레이터 체인 우회 실패"
    assert not mock_dp.called, "display_processor가 호출됨 — 데코레이터 체인 우회 실패"


@pytest.mark.asyncio
async def test_decorator_chain_not_invoked_with_tools() -> None:
    """DoD: tool 경로 chat() 실행 시도 데코레이터 체인이 호출되지 않음을 확인."""
    from .fakes import make_fake_tool_executor, make_fake_tool_manager

    tm = make_fake_tool_manager()
    te = make_fake_tool_executor()
    agent = await _build_agent_async(tool_manager=tm, tool_executor=te, use_mcpp=True)

    async def mock_tool_loop(messages: Any, tools: Any) -> AsyncIterator[Any]:
        yield "응답 텍스트"

    agent._inner._openai_tool_interaction_loop = mock_tool_loop
    batch = make_text_batch("이벤트 추가해줘")

    with (
        patch("open_llm_vtuber.agent.agents.basic_memory_agent.sentence_divider") as mock_sd,
        patch("open_llm_vtuber.agent.agents.basic_memory_agent.tts_filter") as mock_tf,
        patch("open_llm_vtuber.agent.agents.basic_memory_agent.actions_extractor") as mock_ae,
        patch("open_llm_vtuber.agent.agents.basic_memory_agent.display_processor") as mock_dp,
    ):
        events = [ev async for ev in agent.chat(batch)]

    assert len(events) > 0

    assert not mock_sd.called, "sentence_divider가 호출됨 — 데코레이터 체인 우회 실패"
    assert not mock_tf.called, "tts_filter가 호출됨 — 데코레이터 체인 우회 실패"
    assert not mock_ae.called, "actions_extractor가 호출됨 — 데코레이터 체인 우회 실패"
    assert not mock_dp.called, "display_processor가 호출됨 — 데코레이터 체인 우회 실패"
