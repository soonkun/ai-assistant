# src/agent/events.py
"""AgentEvent 계층 — GemmaChatAgent가 방출하는 결정론적 이벤트 타입."""

from dataclasses import dataclass, field
from typing import Any, Literal

AgentEventType = Literal[
    "text_chunk",
    "tool_call_start",
    "tool_call_result",
    "end_of_turn",
    "agent_error",
]


@dataclass(frozen=True)
class TextChunk:
    """LLM이 생성한 자연어 토큰 조각. 공백·줄바꿈 포함 raw 그대로."""

    kind: Literal["text_chunk"] = field(default="text_chunk", init=False)
    text: str = ""  # 빈 문자열은 yield하지 않는다(상위가 무시해도 무방).


@dataclass(frozen=True)
class ToolCallStart:
    """tool 실행 직전 방출. arguments는 이미 JSON 파싱된 dict."""

    kind: Literal["tool_call_start"] = field(default="tool_call_start", init=False)
    tool_id: str = ""  # upstream `ToolCallObject.id` 또는 executor가 생성한 fallback id
    name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolCallResult:
    """tool 실행 완료 직후 방출."""

    kind: Literal["tool_call_result"] = field(default="tool_call_result", init=False)
    tool_id: str = ""
    name: str = ""
    ok: bool = True
    content: str = ""  # upstream status_update["content"] 그대로(error시 "Error: ..." 포함)


@dataclass(frozen=True)
class EndOfTurn:
    """한 턴 종료 마커. chat() AsyncIterator가 종료되기 직전에 1회만 방출."""

    kind: Literal["end_of_turn"] = field(default="end_of_turn", init=False)
    assistant_text_total: str = ""  # 이번 턴에 누적된 최종 assistant 텍스트


@dataclass(frozen=True)
class AgentError:
    """백엔드·프로토콜 에러를 스트림으로 전달(상위가 UI 메시지로 표시)."""

    kind: Literal["agent_error"] = field(default="agent_error", init=False)
    code: Literal[
        "backend_unreachable",
        "empty_response",
        "api_not_support_tools",
        "invalid_tool_arguments",
        "cancelled",
        "unknown",
    ] = "unknown"
    message: str = ""  # 사용자 친화 한국어 메시지


AgentEvent = TextChunk | ToolCallStart | ToolCallResult | EndOfTurn | AgentError
