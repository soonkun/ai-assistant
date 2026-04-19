# tests/e2e/fakes/fake_agent.py
"""FakeAgent — M_05 GemmaChatAgent 공개 API 호환 결정론적 Mock.

Q-6 승인 (2026-04-19): E2E-30/31/33 적대 시나리오 재현성 확보용.
M_05 GemmaChatAgent 공개 API (chat, handle_interrupt)만 구현한다.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from agent.events import (
    AgentEvent,
    EndOfTurn,
    TextChunk,
    ToolCallStart,
    ToolCallResult,
)


class FakeAgent:
    """결정론적 응답을 반환하는 GemmaChatAgent Mock.

    responses 큐에 넣은 응답 시퀀스를 순서대로 방출.
    각 응답은 AgentEvent 리스트 또는 str (str이면 TextChunk + EndOfTurn으로 변환).
    큐가 소진되면 기본 응답("FakeAgent: 응답 없음")을 반환.
    """

    def __init__(
        self,
        responses: list[list[AgentEvent] | str] | None = None,
    ) -> None:
        self._responses: list[list[AgentEvent] | str] = list(responses or [])
        self._call_count: int = 0
        self._interrupted: bool = False
        self._interrupt_count: int = 0
        self._last_batch: Any = None

    def queue_response(self, response: list[AgentEvent] | str) -> None:
        """응답을 큐에 추가."""
        self._responses.append(response)

    @property
    def call_count(self) -> int:
        return self._call_count

    @property
    def interrupt_count(self) -> int:
        return self._interrupt_count

    async def chat(self, batch: Any) -> AsyncIterator[AgentEvent]:
        """GemmaChatAgent.chat 시그니처 호환 — async generator (yield 직접)."""
        self._call_count += 1
        self._interrupted = False
        self._last_batch = batch

        if self._responses:
            response = self._responses.pop(0)
        else:
            response = f"FakeAgent: 응답 없음 (call #{self._call_count})"

        if isinstance(response, str):
            if response:
                yield TextChunk(text=response)
            yield EndOfTurn(assistant_text_total=response)
        else:
            for event in response:
                if self._interrupted:
                    break
                yield event
                await asyncio.sleep(0)  # 이벤트 루프 양보

    async def handle_interrupt(self, heard_text: str) -> None:
        """GemmaChatAgent.handle_interrupt 시그니처 호환."""
        self._interrupted = True
        self._interrupt_count += 1


# ── 사전 정의 응답 팩토리 ──────────────────────────────────────────────────


def make_emotion_response(
    text: str = "정말 기쁜 소식이에요!",
    emotion_tag: str = "happy",
) -> list[AgentEvent]:
    """감정 태그 포함 응답 시퀀스 (E2E-07, E2E-31 용)."""
    full_text = f"{text} [emotion:{emotion_tag}]"
    return [
        TextChunk(text=full_text),
        EndOfTurn(assistant_text_total=full_text),
    ]


def make_tool_call_response(
    tool_name: str,
    tool_args: dict[str, Any],
    after_tool_text: str = "완료했습니다.",
    tool_result_content: str = '{"ok": true}',
) -> list[AgentEvent]:
    """툴 호출 포함 응답 시퀀스 (E2E-30 용)."""
    return [
        ToolCallStart(tool_id="fake-001", name=tool_name, arguments=tool_args),
        ToolCallResult(
            tool_id="fake-001",
            name=tool_name,
            ok=True,
            content=tool_result_content,
        ),
        TextChunk(text=after_tool_text),
        EndOfTurn(assistant_text_total=after_tool_text),
    ]


def make_long_text_response(
    char_count: int = 1200,
    chunk_size: int = 50,
) -> list[AgentEvent]:
    """긴 텍스트 응답 (E2E-33 인터럽트 시나리오 용)."""
    text = "가나다라마바사아자차카타파하" * (char_count // 14 + 1)
    text = text[:char_count]
    events: list[AgentEvent] = []
    for i in range(0, len(text), chunk_size):
        events.append(TextChunk(text=text[i : i + chunk_size]))
    events.append(EndOfTurn(assistant_text_total=text))
    return events


def make_invalid_tool_call_response() -> list[AgentEvent]:
    """스키마 위반 툴 호출 (E2E-30 적대 시나리오 용).

    add_event에 잘못된 인자(start="not-a-date", duration_minutes=-5)를 보낸다.
    """
    return [
        ToolCallStart(
            tool_id="fake-bad-001",
            name="add_event",
            arguments={
                "title": "X",
                "start": "not-a-date",
                "duration_minutes": -5,
            },
        ),
        # ToolRouter가 검증 실패 후 에러 ToolCallResult를 방출 → 실제 Agent처럼 동작
        ToolCallResult(
            tool_id="fake-bad-001",
            name="add_event",
            ok=False,
            content="Error: schema validation failed",
        ),
        TextChunk(text="오류가 발생했습니다."),
        EndOfTurn(assistant_text_total="오류가 발생했습니다."),
    ]
