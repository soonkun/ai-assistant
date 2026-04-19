# src/agent/upstream_adapter.py
"""BasicMemoryAgentAdapter — upstream AgentInterface 호환 어댑터."""

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any, Union

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .gemma_chat_agent import GemmaChatAgent


def _make_adapter_class() -> type:
    """동적으로 BasicMemoryAgentAdapter 클래스를 생성해 mypy Any 서브클래싱 에러 우회."""
    from open_llm_vtuber.agent.agents.agent_interface import AgentInterface
    from open_llm_vtuber.agent.input_types import BatchInput

    from .events import AgentError, EndOfTurn, TextChunk, ToolCallResult, ToolCallStart

    class _BasicMemoryAgentAdapter(AgentInterface):  # type: ignore[misc]
        """upstream ConversationOrchestrator가 기대하는 AgentInterface를 GemmaChatAgent로 만족시키는 얇은 어댑터.

        upstream 측은 `chat(batch) -> AsyncIterator[SentenceOutput | dict]`를 기대한다.
        본 어댑터는 GemmaChatAgent의 AgentEvent 스트림을 **문자열 토큰 스트림**으로 평탄화해
        upstream 데코레이터 체인(sentence_divider 등)을 프로젝트의 Orchestrator 레이어에서
        적용할 수 있게 한다.
        """

        def __init__(self, agent: "GemmaChatAgent") -> None:
            super().__init__()
            self._agent = agent
            self._pending_tasks: set[asyncio.Task[None]] = set()

        async def chat(self, input_data: BatchInput) -> AsyncIterator[Union[str, dict[str, Any]]]:
            """GemmaChatAgent.chat를 소비해:
            - TextChunk → yield text(str)
            - ToolCallStart → yield {"type":"tool_call_start","tool_id","name","arguments"}
            - ToolCallResult → yield {"type":"tool_call_status","status":"completed"/"error",...}
            - EndOfTurn → 스트림 종료 (yield 안 함)
            - AgentError → yield "[오류: <message>]" (사용자 텍스트로 표출)
            """
            async for event in self._agent.chat(input_data):
                if isinstance(event, TextChunk):
                    if event.text:
                        yield event.text
                elif isinstance(event, ToolCallStart):
                    yield {
                        "type": "tool_call_start",
                        "tool_id": event.tool_id,
                        "name": event.name,
                        "arguments": event.arguments,
                    }
                elif isinstance(event, ToolCallResult):
                    yield {
                        "type": "tool_call_status",
                        "status": "completed" if event.ok else "error",
                        "tool_id": event.tool_id,
                        "tool_name": event.name,
                        "content": event.content,
                    }
                elif isinstance(event, EndOfTurn):
                    return  # 스트림 종료
                elif isinstance(event, AgentError):
                    logger.warning(f"AgentError를 텍스트로 변환: code={event.code}")
                    yield f"[오류: {event.message}]"

        def handle_interrupt(self, heard_response: str) -> None:
            """동기 인터페이스 요구. asyncio 태스크로 스케줄."""
            try:
                loop = asyncio.get_running_loop()
                task = loop.create_task(self._agent.handle_interrupt(heard_response))
                self._pending_tasks.add(task)
                task.add_done_callback(self._pending_tasks.discard)
                logger.debug(f"handle_interrupt 태스크 스케줄: {heard_response!r}")
            except RuntimeError:
                # 이벤트 루프가 없는 경우 — upstream이 동기 환경에서 호출한 케이스
                logger.warning(
                    "handle_interrupt: 실행 중인 이벤트 루프 없음 — upstream _inner에 직접 위임"
                )
                self._agent._inner.handle_interrupt(heard_response)

        def set_memory_from_history(self, conf_uid: str, history_uid: str) -> None:
            """동기 인터페이스 요구. upstream BasicMemoryAgent에 직접 위임."""
            self._agent._inner.set_memory_from_history(conf_uid, history_uid)

        async def close(self) -> None:
            """GemmaChatAgent 내부 httpx 클라이언트 종료 (누수 방지).

            upstream ServiceContext.close()가 hasattr(agent_engine, "close") 가드로
            이 메서드를 호출한다 (CR-03).
            """
            await self._agent.aclose()

    return _BasicMemoryAgentAdapter


BasicMemoryAgentAdapter: type = _make_adapter_class()
