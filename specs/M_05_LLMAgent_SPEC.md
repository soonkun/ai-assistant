# M_05 LLMAgent — 스펙

## 목적과 범위

### 목적
사내 오프라인 AI 비서 "새싹이"의 LLM 추론·대화 에이전트 계층을 제공한다. upstream `OpenAICompatibleLLM`(`AsyncLLM`)과 `BasicMemoryAgent`를 **컴포지션(보유 관계)** 로 감싼 `GemmaChatAgent`를 신규 작성하여, (a) Ollama 로컬 엔드포인트(`OLLAMA_BASE_URL`)로 `gemma4:e4b` 모델을 호출하고, (b) upstream의 OpenAI-호환 tool calling 루프를 재사용하며, (c) upstream 내부의 이질적 출력(`str` 토큰 / `tool_call_status` dict / `SentenceOutput` 등)을 본 프로젝트의 결정론적 **`AgentEvent`** 스트림으로 정규화한다.

### 범위 (In-Scope)
1. `GemmaChatAgent` 클래스 — Ollama `gemma4:e4b`에 맞춰 구성된 컴포지션 래퍼. `chat(batch) -> AsyncIterator[AgentEvent]`와 `handle_interrupt`, `set_memory_from_history`를 제공.
2. `AgentEvent` 계층(dataclass) — `TextChunk`, `ToolCallStart`, `ToolCallResult`, `EndOfTurn`, `AgentError`.
3. Ollama 사전 헬스체크(`/api/tags` 또는 `/api/version` 경유)와 **초기화 시 3회 재시도**(지수 backoff 0.5s, 1.0s, 2.0s). 실패 시 `AgentBackendError`.
4. **chat 루프 내부 재시도 금지**(중복 응답 방지). 런타임 커넥션 에러는 상위로 전파 후 한 번의 텍스트로 폴백.
5. `BatchInput` → upstream 내부 messages 포맷 변환은 **upstream `_to_messages` 로직을 그대로 위임**. 본 모듈은 upstream 에이전트의 출력만 어댑트.
6. upstream `BasicMemoryAgent`의 `sentence_divider`/`tts_filter`/`actions_extractor`/`display_processor` 데코레이터 체인은 **우회**한다. 본 모듈은 raw token 스트림과 tool call dict를 소비하는 **별도 경로**(`_run_raw`)를 upstream 내부 메서드 재사용으로 구성.
7. `AppConfig.agent` 서브스키마(pydantic) 정의.
8. `build_chat_agent(app_config, ollama_config, tool_manager, tool_executor, system_prompt, extra_tool_specs=None)` 빌더.
9. M_01 `AppServiceContext.load_app_services` 통합 지점(본 스펙은 M_01 변경 요청을 포함한다 — §배선).
10. 단위·통합 테스트 (정상 ≥5, 엣지 ≥5, 적대적 ≥3). upstream Ollama는 실제 접속 없이 전량 mock.

### 범위 외 (Out-of-Scope, 명시적 제외)
- **프롬프트 엔지니어링의 최종 튜닝**(페르소나 프롬프트, 감정 태그 규칙 등). 페르소나·감정 태그 프롬프트는 `prompts/persona/saessagi.txt`(M_08/M_12 범위)에서 관리. 본 모듈은 **주입받은 `system_prompt`를 수정하지 않고 그대로 사용**.
- **문장 분할·TTS 전처리·립싱크 액션 추출**. upstream `sentence_divider`/`tts_filter`/`actions_extractor`/`display_processor`는 **upstream `ConversationOrchestrator` 쪽에서** M_04 TTS 호출 직전에 적용한다. 본 모듈은 raw text chunk만 흘려 보낸다. (ARCHITECTURE.md §3.1 경로 유지 — M_04와의 경계 명확화)
- **tool 실행 자체**. `ToolRouter`(M_05b)가 `ToolExecutor`에 주입된 `MCPClient` 어댑터로 수행. 본 모듈은 tool call 메타만 방출한다.
- **자연어 날짜 파싱**. `add_event` 인자의 ISO datetime 변환은 LLM 자체가 담당(스파이크 통과). 실패 시 `ToolResult(ok=False)`를 받아 LLM이 재질문.
- **멀티모달 이미지 입력의 전처리**. `BatchInput.images`는 이미 base64 data URL로 채워져 있다는 전제(M_05b `ScreenshotService`가 채움).
- **그룹 대화(`start_group_conversation`)**. REQUIREMENTS.md §10 "다중 사용자 불가" → 본 모듈은 method를 상속하지 않음(컴포지션이라 노출 자체가 없음).
- **upstream Claude 경로**(`_claude_tool_interaction_loop`). Ollama는 OpenAI 호환만 사용하므로 OpenAI 루프만 경유.
- **프롬프트 모드(tool JSON fallback)**. `gemma4:e4b`가 네이티브 tool을 지원하므로 `__API_NOT_SUPPORT_TOOLS__` 분기는 관찰만 하고 **즉시 `AgentError`로 승격**(네이티브 미지원은 모델 교체 사안).
- **토큰 카운팅·컨텍스트 트리밍**. V1은 `max_context_tokens=131_000` 선언만 유지. 실제 슬라이딩은 upstream `BasicMemoryAgent._memory` 그대로. V2에서 별도 CR.
- **Ollama `keep_alive` 제어**. `OllamaConfig.keep_alive_seconds`는 **요청 바디의 `keep_alive` 필드**로 전달하지 않는다(OpenAI 호환 API는 지원 안 함). 대신 배포 스크립트에서 `ollama run` 시 `OLLAMA_KEEP_ALIVE` 환경변수로 설정(본 모듈 범위 밖).

---

## 요구사항 연결

| REQUIREMENTS.md 항목 | M_05 기여 |
|---|---|
| §0 완전 오프라인 | Ollama base_url은 loopback/RFC1918만 허용(검증은 M_01 `enforce_private_url` 위임). 런타임에 외부 도메인 호출 0건 |
| §0 Windows 10/11 | Ollama for Windows 전제. asyncio/httpx 기반 (Windows 이벤트 루프 호환) |
| §1.1 전이중 (사용자 인터럽트) | `handle_interrupt(heard_text)` → upstream `BasicMemoryAgent.handle_interrupt` 위임 + 진행 중 `chat` 스트림에 `asyncio.CancelledError` 전파 |
| §1.2 텍스트·음성 히스토리 통합 컨텍스트 | `set_memory_from_history(conf_uid, history_uid)` → upstream 위임. upstream이 `chat_history_manager.get_history`로 파일 JSON에서 로드 |
| §2.2 문서 RAG + 인용 | `search_docs` tool call 호출·결과 주입 경로 제공. 본 모듈은 tool 이름·인자만 전달, 실제 검색은 M_05b → M_07 |
| §4.1 일정 등록(함수 호출) | Gemma 네이티브 tool calling — upstream `OpenAICompatibleLLM.chat_completion`의 `tools=` 파라미터 사용 |
| §6 화면 인식(이미지 입력) | `BatchInput.images`를 upstream `_to_messages`가 `image_url` 블록으로 변환. Ollama `gemma4:e4b`가 멀티모달 지원하는 전제(R-06 스파이크 필수) |
| §8 LLM: `gemma4:e4b` | `GemmaChatAgent.model` 기본값 `"gemma4:e4b"` |
| §9 응답 지연 (GPU 2s / CPU 6s) | `faster_first_response=True` 설정(R-01 완화). 본 모듈 단독 SLA는 §성능 참조. CPU에서 미달은 R-01로 수용 |
| §9 메모리 상한 | 본 모듈 자체 RSS 기여 < 50 MB(Python 프로세스). Ollama 별도 프로세스 8.5 GB는 인프라 예산 |
| §9 외부 네트워크 호출 금지 | `base_url`이 `enforce_private_url` 통과한 경우에만 클라이언트 생성. 생성 후에는 추가 URL을 생성하지 않음 |
| §10 다중 사용자 불가 | `GemmaChatAgent` 인스턴스 1개 전제. 내부 state(`_interrupt_handled`, `_memory`)는 upstream `BasicMemoryAgent`가 보유. 동시 `chat` 호출은 `asyncio.Lock`으로 직렬화 |

---

## upstream 재사용 분석

### 분류: **EXTEND (컴포지션 방식)**

**상속 대신 컴포지션을 선택한 근거**:
1. upstream `BasicMemoryAgent.chat`은 `sentence_divider`/`tts_filter`/`actions_extractor`/`display_processor` 4겹 데코레이터로 감싸져 `SentenceOutput` 또는 `dict`를 yield한다. 본 프로젝트는 이 단계를 M_04 TTS 호출 직전으로 이동해야 하므로(ARCHITECTURE.md §3.1), 데코레이터 체인을 그대로 상속받으면 **M_05와 M_04 사이에 타입 불일치**가 발생한다.
2. 상속 후 `_chat_function_factory`를 오버라이드해도 private 메서드(`_openai_tool_interaction_loop`, `_to_messages`, `_add_message`)에 의존하게 되어, upstream 리팩터링에 취약해진다.
3. 컴포지션으로 `BasicMemoryAgent` 인스턴스를 내부에 보유하되, `chat()` 만 **우회 구현**하여 upstream의 `_to_messages`와 `_openai_tool_interaction_loop`를 **직접 호출**한다. 이 둘은 이름이 밑줄로 시작하나 안정적 public 시그니처를 가진다(파일 상단 주석·docstring 존재). upstream 업그레이드 시 시그니처 변경은 **M_05 단일 지점**에서 adapt.
4. `handle_interrupt`, `set_memory_from_history`는 **단순 위임**(delegation)으로 충분.

즉 `GemmaChatAgent`는 `BasicMemoryAgent`를 상속하지 않으며 **`AgentInterface`도 상속하지 않는다**. upstream이 기대하는 `AgentInterface` 구현은 **어댑터 레이어**(`BasicMemoryAgentAdapter`, 본 스펙 §공개 API)가 담당해 upstream `ConversationOrchestrator`가 그대로 사용할 수 있게 한다.

### REUSE (무수정 호출)

| upstream 경로 | 심볼 | 사용 방식 |
|---|---|---|
| `agent/stateless_llm/openai_compatible_llm.py` | `AsyncLLM` | `GemmaChatAgent.__init__`에서 인스턴스화. `base_url`, `model`, `temperature` 주입. Ollama OpenAI-호환 엔드포인트(`/v1/chat/completions`) 사용 |
| `agent/agents/basic_memory_agent.py` | `BasicMemoryAgent` | 컴포지션 보유. `_memory`, `_to_messages`, `_add_message`, `_openai_tool_interaction_loop`, `handle_interrupt`, `set_memory_from_history`, `reset_interrupt`, `prompt_mode_flag`, `set_system`을 이용 |
| `agent/input_types.py` | `BatchInput`, `TextData`, `ImageData`, `TextSource`, `ImageSource` | 그대로 import. 본 모듈에서 재정의 금지 |
| `agent/agents/agent_interface.py` | `AgentInterface` | `BasicMemoryAgentAdapter`가 상속(upstream `ConversationOrchestrator` 호환용) |
| `mcpp/tool_manager.py` | `ToolManager` | 생성자 주입. `get_formatted_tools("OpenAI")` 호출 |
| `mcpp/tool_executor.py` | `ToolExecutor` | 생성자 주입. upstream이 `_openai_tool_interaction_loop` 내부에서 호출 |
| `mcpp/types.py` | `ToolCallObject` | upstream이 내부에서 사용. 본 모듈은 **tool call dict로만** 관측(ToolCallObject 직접 조작 없음) |
| `chat_history_manager.py` | `get_history` | upstream `BasicMemoryAgent.set_memory_from_history`가 내부 호출 |

### DROP (사용 안 함)

| upstream 심볼 | 이유 |
|---|---|
| `BasicMemoryAgent._claude_tool_interaction_loop` | Ollama는 OpenAI 호환만 사용 |
| `BasicMemoryAgent.prompt_mode_flag` 활성화 경로 | `gemma4:e4b`가 네이티브 tool 지원. fallback 금지 |
| `BasicMemoryAgent.start_group_conversation` | 단일 사용자 전제 |
| `BasicMemoryAgent._chat_function_factory` | 데코레이터 체인이 본 모듈의 `AgentEvent` 계약과 충돌 |
| upstream `AgentFactory.create_agent` | **CR-03** B안에 의해 M_01 `AppServiceContext.init_agent` 오버라이드(M_04 `init_tts`와 동일 패턴)가 이 경로를 완전히 대체한다. upstream factory는 호출되지 않음 |
| `ollama_llm.py` | 존재하지 않거나 OpenAI 호환 경로로 통합됨 — 본 모듈은 `OpenAICompatibleLLM` 하나만 사용 |
| `agent/stateless_llm/claude_llm.py` | Claude 경로 비사용 |

### 배선 정책 (M_01 통합 — CR-03 확정안)

upstream `ServiceContext.load_from_config`는 `init_agent`가 `AgentFactory.create_agent`로
`self.agent_engine`을 초기화한다. **upstream 파일 수정 금지**이므로 **M_04 `init_tts`와 동일하게
`init_agent` 메서드 자체를 오버라이드**한다(CR-03 B안 채택).

**초기 대안(기각 이력)**: 이전 스펙은 `load_from_config` 오버라이드에서 `super()` 호출 **전에**
`self.tool_manager`/`self.tool_executor`/`self.agent_engine`을 pre-set해 upstream `init_agent`
가드를 통과시키는 방식을 제안했다. 그러나 upstream `_init_mcp_components`
(`service_context.py:102-105, 171`)가 `super().load_from_config` 내부에서
`self.tool_manager`/`self.tool_executor`를 **무조건 None으로 리셋 후 재생성**하므로 pre-set이
소실된다. 또한 `ToolRouter.to_upstream_tool_manager()`는 존재하지 않으며 M_05b §1.3-1은
"upstream ToolManager에 로컬 툴 등록 금지" 계약이다(로컬 툴은 `extra_tool_specs` 경로로만
전달). 이 두 이유로 기각되었다(CR-03 §이전 제안 기각 이력 참조).

**확정 방식**: `AppServiceContext.init_agent` 오버라이드.

1. **upstream 호출 지점**: upstream `service_context.py:300`의 `await self.init_agent(...)`.
   파이썬 MRO에 의해 우리 구현이 디스패치된다. upstream factory 경로는 실행되지 않는다.
2. **우리 `init_agent` 동작(요약)**:
   - idempotency 가드(agent_engine 존재 + agent_config/persona_prompt 동일 시 early return).
   - `system_prompt = await self.construct_system_prompt(persona_prompt)`.
   - `mcp_tool_manager`, `mcp_tool_executor` = 직전 `_init_mcp_components` 결과.
   - `tool_router_adapter is not None` → `CompositeToolExecutor` 생성, `self.tool_executor` 교체,
     `extra_specs = self.tool_router.tool_specs()`.
   - `gemma_agent = await build_chat_agent(..., extra_tool_specs=extra_specs)`.
   - `self.agent_engine = BasicMemoryAgentAdapter(gemma_agent)`.
   - `self.character_config.agent_config = agent_config; self.system_prompt = system_prompt`.
3. **책임 분리**: M_05 본 모듈은 `build_chat_agent(...)`, `BasicMemoryAgentAdapter`,
   `BasicMemoryAgentAdapter.close()` (CR-03에서 추가 — upstream close 체인이 httpx 클라이언트까지
   닫히도록)만 제공한다. 오버라이드 구현 자체는 **M_01 `AppServiceContext`가 소유**한다
   (상세는 M_01 스펙 §공개 API `init_agent`, `docs/CHANGE_REQUESTS.md` CR-03 참조).
4. **폴백 정책**: `build_chat_agent`가 `AgentInitError`/`AgentBackendError`를 던질 때 upstream
   `AgentFactory.create_agent`로 폴백하지 않는다(CR-03 §동작 계약). 예외는 `load_from_config`를
   통해 기동 실패로 전파된다.

---

## 공개 API

> Python 3.12 타입 힌트. 모든 `async def`는 `asyncio.CancelledError` 전파 허용. 에러는 아래 예외 타입으로만.

### 예외 타입

```python
# src/agent/errors.py
class AgentInitError(Exception):
    """GemmaChatAgent 초기화 단계 에러 (설정 위반, Ollama 헬스체크 실패 등)."""

class AgentBackendError(Exception):
    """초기화 재시도(3회) 모두 실패 또는 런타임 치명적 백엔드 에러."""

class AgentProtocolError(Exception):
    """upstream `__API_NOT_SUPPORT_TOOLS__` 등 본 모듈이 허용하지 않는 경로로 진입."""
```

### AgentEvent 계층

```python
# src/agent/events.py
from dataclasses import dataclass, field
from typing import Literal, Any

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
    text: str = ""   # 빈 문자열은 yield하지 않는다(상위가 무시해도 무방).

@dataclass(frozen=True)
class ToolCallStart:
    """tool 실행 직전 방출. arguments는 이미 JSON 파싱된 dict."""
    kind: Literal["tool_call_start"] = field(default="tool_call_start", init=False)
    tool_id: str       # upstream `ToolCallObject.id` 또는 executor가 생성한 fallback id
    name: str
    arguments: dict[str, Any]

@dataclass(frozen=True)
class ToolCallResult:
    """tool 실행 완료 직후 방출."""
    kind: Literal["tool_call_result"] = field(default="tool_call_result", init=False)
    tool_id: str
    name: str
    ok: bool
    content: str       # upstream status_update["content"] 그대로(error시 "Error: ..." 포함)
    # 이미지 등 풍부 content는 V1 범위 밖. V2에서 `items: list[dict]` 추가.

@dataclass(frozen=True)
class EndOfTurn:
    """한 턴 종료 마커. chat() AsyncIterator가 종료되기 직전에 1회만 방출."""
    kind: Literal["end_of_turn"] = field(default="end_of_turn", init=False)
    assistant_text_total: str   # 이번 턴에 누적된 최종 assistant 텍스트(메모리에도 기록됨)

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
    ]
    message: str       # 사용자 친화 한국어 메시지 (하드코드된 템플릿)

AgentEvent = TextChunk | ToolCallStart | ToolCallResult | EndOfTurn | AgentError
```

### GemmaChatAgent

```python
# src/agent/gemma_chat_agent.py
from collections.abc import AsyncIterator
import asyncio
from open_llm_vtuber.agent.input_types import BatchInput  # upstream REUSE
from open_llm_vtuber.agent.agents.basic_memory_agent import BasicMemoryAgent
from open_llm_vtuber.agent.stateless_llm.openai_compatible_llm import (
    AsyncLLM as OpenAICompatibleAsyncLLM,
)
from open_llm_vtuber.mcpp.tool_manager import ToolManager
from open_llm_vtuber.mcpp.tool_executor import ToolExecutor

class GemmaChatAgent:
    """Ollama `gemma4:e4b`에 맞춰 구성된 대화 에이전트 (컴포지션).

    내부적으로 upstream `BasicMemoryAgent` 인스턴스를 보유하되, `chat()`만 본 모듈에서
    직접 구현해 upstream의 `_to_messages`와 `_openai_tool_interaction_loop`를 호출한다.
    출력은 본 프로젝트의 `AgentEvent`로 정규화된다.
    """

    base_url: str
    model: str
    temperature: float
    max_context_tokens: int
    system_prompt: str
    _llm: OpenAICompatibleAsyncLLM
    _inner: BasicMemoryAgent
    _chat_lock: asyncio.Lock     # 단일 사용자 전제. 동시 chat 호출 직렬화.

    def __init__(
        self,
        base_url: str,
        model: str = "gemma4:e4b",
        system_prompt: str = "",
        tool_manager: ToolManager | None = None,
        tool_executor: ToolExecutor | None = None,
        temperature: float = 0.7,
        max_context_tokens: int = 131_000,
        faster_first_response: bool = True,
        interrupt_method: Literal["system", "user"] = "user",
        use_mcpp: bool = True,
        extra_tool_specs: list[dict[str, Any]] | None = None,
    ) -> None:
        """즉시 Ollama 헬스체크 수행 후 내부 LLM·BasicMemoryAgent 구성.

        Args:
            base_url: Ollama OpenAI-호환 엔드포인트 루트. 예: "http://127.0.0.1:11434/v1".
                     `/v1` suffix가 없으면 자동 추가한다(OpenAI SDK 요구).
            model: Ollama 모델 태그. 기본 "gemma4:e4b".
            system_prompt: 시스템 프롬프트(페르소나 포함, 이미 완성된 문자열).
            tool_manager: M_05b가 빌드한 upstream-호환 ToolManager. `use_mcpp=True`면 필수.
            tool_executor: M_05b가 빌드한 upstream-호환 ToolExecutor. `use_mcpp=True`면 필수.
            temperature: 0.0~2.0.
            max_context_tokens: V1은 선언값. 실제 트리밍은 미구현(Out-of-Scope).
            faster_first_response: upstream `BasicMemoryAgent`에 전달. True 고정 권장(R-01).
            interrupt_method: upstream 기본 "user".
            use_mcpp: True면 네이티브 tool calling 활성. False면 단순 스트리밍.
            extra_tool_specs: MCP 외 추가 tool 스키마 목록(OpenAI format). 기본 None.
                MCP 툴과 이름이 겹치면 AgentInitError 발생(FAIL-fast).

        Raises:
            AgentInitError:
              - base_url이 비어 있음, 스킴이 http/https 외, 포트 범위 밖
              - temperature가 0.0~2.0 밖
              - max_context_tokens <= 0
              - `use_mcpp=True`인데 tool_manager 또는 tool_executor 중 하나라도 None
              - system_prompt가 None (빈 문자열은 허용)
              - extra_tool_specs에 MCP tool과 이름이 겹치는 항목이 존재
            AgentBackendError:
              - Ollama 헬스체크 3회 재시도(0.5s, 1.0s, 2.0s) 모두 실패
              - `model`이 `/api/tags` 응답의 모델 목록에 없음
        """

    async def chat(self, batch: BatchInput) -> AsyncIterator[AgentEvent]:
        """한 턴의 대화를 AgentEvent 스트림으로 방출.

        순서:
          1) self._chat_lock 획득(동시 호출 직렬화).
          2) self._inner.reset_interrupt(), self._inner.prompt_mode_flag = False.
          3) messages = self._inner._to_messages(batch)  # upstream 위임
             - 이 단계에서 upstream이 이번 턴의 user message를 _memory에 append.
             - 이미지·클립보드·텍스트 전처리도 upstream이 수행.
          4) tools = self._formatted_tools_openai (use_mcpp=True일 때만. 아니면 []).
          5) if self._use_mcpp and tools:
                raw_stream = self._inner._openai_tool_interaction_loop(messages, tools)
             else:
                raw_stream = self._simple_stream(messages)   # 내부 헬퍼 (아래)
          6) 누적 텍스트 assistant_text_total = "".
          7) async for item in raw_stream:
                - isinstance(item, str) and item != "":
                    yield TextChunk(text=item); assistant_text_total += item
                - isinstance(item, dict):
                    event = self._translate_tool_event(item)
                    if event is not None:
                        yield event
                - isinstance(item, str) and item == "__API_NOT_SUPPORT_TOOLS__":
                    yield AgentError(code="api_not_support_tools",
                                     message="이 모델은 도구 호출을 지원하지 않습니다.")
                    break   # 루프 종료, EndOfTurn 없이 return
                - 기타: 로그 WARNING 후 무시.
          8) if not assistant_text_total and use_mcpp: (tool만 호출하고 텍스트 없는 희귀 케이스)
                assistant_text_total = "(도구 실행 결과를 확인했어요.)"
                yield TextChunk(text=assistant_text_total)
          9) yield EndOfTurn(assistant_text_total=assistant_text_total).

        Raises:
            - 직접 raise하지 않는다. 모든 에러는 AgentError 이벤트로 전달.
            - 단 `asyncio.CancelledError`는 finally에서 락 해제 후 **상위로 재전파**.
        """

    async def handle_interrupt(self, heard_text: str) -> None:
        """upstream BasicMemoryAgent.handle_interrupt에 단순 위임.

        upstream은 동기 메서드지만 본 시그니처는 async로 노출(상위 WebSocket 핸들러 호환).
        """

    async def set_memory_from_history(self, conf_uid: str, history_uid: str) -> None:
        """upstream BasicMemoryAgent.set_memory_from_history에 위임(동기 → 비동기 래핑)."""

    def set_system_prompt(self, prompt: str) -> None:
        """런타임 persona 교체용. upstream BasicMemoryAgent.set_system을 호출."""

    async def aclose(self) -> None:
        """리소스 정리. openai AsyncClient를 닫는다(`await self._llm.client.close()`).
        upstream AsyncLLM.client는 httpx.AsyncClient — GC에 맡기면 경고가 발생할 수 있으므로 명시적 close."""

    # --- 내부 헬퍼 ---

    async def _simple_stream(
        self,
        messages: list[dict[str, Any]],
    ) -> AsyncIterator[str | dict[str, Any]]:
        """tool 없는 경로. upstream AsyncLLM.chat_completion을 직접 소비해 str만 yield.
        - 빈 chunk는 드롭.
        - 예외 발생 시 AgentError를 yield하는 dict를 방출하고 종료.
        """

    def _translate_tool_event(
        self, item: dict[str, Any]
    ) -> AgentEvent | None:
        """upstream ToolExecutor가 yield하는 dict를 AgentEvent로 변환.

        매핑:
          item["type"] == "tool_call_status" and item["status"] == "running"
              -> ToolCallStart(tool_id, name, arguments=<파싱 결과, _parse_running_args 참조>)
          item["type"] == "tool_call_status" and item["status"] in ("completed","error")
              -> ToolCallResult(tool_id, name, ok=(status=="completed"), content=item["content"])
          item["type"] == "final_tool_results"
              -> None  (내부 state, 이벤트 아님)
          기타
              -> None + 로그 DEBUG
        """
```

### upstream 호환 어댑터

```python
# src/agent/upstream_adapter.py
from open_llm_vtuber.agent.agents.agent_interface import AgentInterface

class BasicMemoryAgentAdapter(AgentInterface):
    """upstream ConversationOrchestrator가 기대하는 AgentInterface를 GemmaChatAgent로 만족시키는 얇은 어댑터.

    upstream 측은 `chat(batch) -> AsyncIterator[SentenceOutput | dict]`를 기대한다.
    본 어댑터는 GemmaChatAgent의 AgentEvent 스트림을 **문자열 토큰 스트림**으로 평탄화해
    upstream 데코레이터 체인(sentence_divider 등)을 프로젝트의 Orchestrator 레이어에서
    적용할 수 있게 한다.

    단, 프로젝트의 Orchestrator는 M_04 TTS 호출 직전에만 sentence_divider를 적용하므로
    본 어댑터는 단순히 AgentEvent를 'text_chunk' 문자열과 tool 관련 dict으로 downgrade한다.
    """

    def __init__(self, agent: GemmaChatAgent) -> None: ...

    async def chat(self, input_data: BatchInput) -> AsyncIterator[Union[str, dict[str, Any]]]:
        """GemmaChatAgent.chat를 소비해:
          - TextChunk → yield text(str)
          - ToolCallStart → yield {"type":"tool_call_start","tool_id","name","arguments"}
          - ToolCallResult → yield {"type":"tool_call_status","status":"completed"/"error",...}
          - EndOfTurn → 스트림 종료 (yield 안 함)
          - AgentError → yield "[오류: <message>]" (사용자 텍스트로 표출)
        """

    def handle_interrupt(self, heard_response: str) -> None:
        """동기 인터페이스 요구. asyncio.get_running_loop().create_task로 agent.handle_interrupt 스케줄."""

    def set_memory_from_history(self, conf_uid: str, history_uid: str) -> None:
        """동기 인터페이스 요구. asyncio 태스크 스케줄 또는 내부 BasicMemoryAgent에 직접 위임."""

    async def close(self) -> None:
        """**(CR-03 추가)** upstream `ServiceContext.close()`(service_context.py:197-198)의
        `hasattr(agent_engine, "close")` 가드를 통과시켜 GemmaChatAgent.aclose()까지 close
        체인을 연결한다.

        동작: `await self._agent.aclose()` 위임. 예외는 상위 close가 catch하므로 여기서는
        re-raise 가능.
        """
```

### 빌더

```python
# src/agent/builder.py
from src.app.config import AppConfig, OllamaConfig

def build_chat_agent(
    app_config: AppConfig,
    ollama_config: OllamaConfig,
    tool_manager: ToolManager | None,
    tool_executor: ToolExecutor | None,
    system_prompt: str,
    extra_tool_specs: list[dict[str, Any]] | None = None,
) -> GemmaChatAgent:
    """AppConfig.agent 서브스키마를 읽어 GemmaChatAgent를 생성한다.

    - ollama_config.base_url은 M_01이 enforce_private_url로 이미 검증된 상태여야 함(본 함수는 재검증 수행).
    - use_mcpp는 (tool_manager is not None and tool_executor is not None)로 결정.
    - faster_first_response는 app_config.agent.faster_first_response(기본 True).

    Raises:
        AgentInitError | AgentBackendError: GemmaChatAgent.__init__와 동일.
    """
```

### 모듈 공개 심볼 (`src/agent/__init__.py`)

```python
from .errors import AgentInitError, AgentBackendError, AgentProtocolError
from .events import (
    AgentEvent, AgentEventType,
    TextChunk, ToolCallStart, ToolCallResult, EndOfTurn, AgentError,
)
from .gemma_chat_agent import GemmaChatAgent
from .upstream_adapter import BasicMemoryAgentAdapter
from .builder import build_chat_agent
```

---

## 내부 데이터 구조

### Ollama 헬스체크 응답

```python
# src/agent/health.py
@dataclass(frozen=True)
class OllamaHealth:
    reachable: bool
    version: str | None          # /api/version 결과 or None
    model_available: bool        # /api/tags에 model이 포함되어 있는가
    base_url_normalized: str     # "/v1" suffix 포함
    error: str | None            # 실패 시 사람 읽을 수 있는 이유

async def probe_ollama(base_url: str, model: str, timeout_sec: float = 3.0) -> OllamaHealth:
    """httpx.AsyncClient로 GET {base_url}/api/version, {base_url}/api/tags 호출.

    base_url은 "http://host:port" 또는 "http://host:port/v1" 둘 다 수용. "/v1"은
    OpenAI 경로에 필요하나 /api/*는 Ollama 네이티브 경로이므로 원본 루트로 접근한다.
    즉 "http://host:port/v1"을 받으면 내부적으로 "http://host:port"를 사용.

    실패 조건:
      - 타임아웃, ConnectionError → reachable=False
      - HTTP 상태 != 200 → reachable=False
      - /api/tags 응답에 model 태그 부재 → model_available=False

    Raises: 자체 예외 없음. 모든 실패는 OllamaHealth로 반환.
    """
```

### 내부 상태 어트리뷰트

`GemmaChatAgent`는 상태를 추가 필드로 보유하지 않는다. 모든 대화 메모리는 `self._inner._memory`(upstream) 한 곳에만 존재. 동시성 제어 `_chat_lock`과 내부 `_formatted_tools_openai` 캐시만 추가.

---

## 설정 구조 (conf.yaml)

### 본 프로젝트 `AppConfig.agent` 신규 서브필드

M_01 `src/app/config.py`에 **`AppConfig.agent: AgentConfig` 필드 1개 추가**를 요청한다.
`AppConfig.ollama`는 이미 M_01에 존재하므로 재사용(중복 정의 금지).

```python
# src/app/config.py (M_05가 요청하는 추가)
class AgentConfig(BaseModel):
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_context_tokens: int = Field(default=131_000, ge=1024, le=1_048_576)
    faster_first_response: bool = Field(default=True)
    interrupt_method: Literal["system", "user"] = Field(default="user")
    use_mcpp: bool = Field(default=True)
    # 페르소나 프롬프트 경로·내용은 upstream character_config.persona_prompt를 그대로 사용
    # (별도 필드 추가 없음 — Out-of-Scope 참조)

class AppConfig(BaseModel):
    # 기존 필드들...
    agent: AgentConfig = Field(default_factory=AgentConfig)
```

### `conf.yaml` 예시

```yaml
# upstream 호환 (upstream init_agent 가드를 통과시키기 위한 최소 필드)
character_config:
  persona_prompt: |
    너는 사내 AI 비서 '새싹이'야. 한국어로 존댓말을 쓰고, 일정과 문서를 도와줘.
    감정 태그는 `[emotion:<neutral|happy|surprised|sad|worried|thinking|sleepy>]`
    형식으로만 붙여.
  agent_config:
    conversation_agent_choice: "basic_memory_agent"
    agent_settings:
      basic_memory_agent:
        use_mcpp: true
        mcp_enabled_servers: []
        # 본 프로젝트는 AgentFactory를 거치지 않으므로 세부 필드는 무시됨
    llm_configs:
      ollama_llm:
        base_url: "http://127.0.0.1:11434/v1"
        model: "gemma4:e4b"

# 본 프로젝트 고유 - 실제 에이전트 파라미터
app:
  ollama:
    base_url: "http://127.0.0.1:11434"   # 또는 dev에서 "http://192.168.219.109:11434"
    model: "gemma4:e4b"
    keep_alive_seconds: 300              # 본 모듈은 사용 안 함(메모)
    request_timeout_seconds: 120
  agent:
    temperature: 0.7
    max_context_tokens: 131000
    faster_first_response: true
    interrupt_method: "user"
    use_mcpp: true
```

### 필드 검증표

| 키 | 타입 | 기본 | 검증 |
|---|---|---|---|
| `app.ollama.base_url` | str | `"http://127.0.0.1:11434"` | `enforce_private_url`(M_01 제공). 스킴 http/https, 포트 1-65535 |
| `app.ollama.model` | str | `"gemma4:e4b"` | 길이 1 이상. Ollama `/api/tags` 응답에 포함되어야 함 |
| `app.ollama.request_timeout_seconds` | int | 120 | `[5, 600]` |
| `app.agent.temperature` | float | 0.7 | `[0.0, 2.0]` |
| `app.agent.max_context_tokens` | int | 131000 | `[1024, 1_048_576]` |
| `app.agent.faster_first_response` | bool | true | — |
| `app.agent.interrupt_method` | str | "user" | `{"user", "system"}` |
| `app.agent.use_mcpp` | bool | true | — |

---

## 에러 처리 정책

| 상황 | 반응 | 예외·이벤트 | 로그 레벨 |
|---|---|---|---|
| `base_url` 빈 문자열 | 즉시 실패 | `AgentInitError("base_url required")` | ERROR |
| `base_url` 스킴 불일치 | 즉시 실패 | `AgentInitError("scheme must be http/https")` | ERROR |
| `temperature` 범위 밖 | 즉시 실패 | `AgentInitError("temperature out of range")` | ERROR |
| `use_mcpp=True` but `tool_manager is None` | 즉시 실패 | `AgentInitError("tool_manager required when use_mcpp=True")` | ERROR |
| Ollama `/api/version` 연결 실패 | 3회 재시도(0.5/1.0/2.0s) | 모두 실패 시 `AgentBackendError("Ollama unreachable: ...")` | WARNING(재시도), ERROR(최종) |
| Ollama 응답했으나 `model` 부재 | 즉시 실패 | `AgentBackendError("model 'gemma4:e4b' not available in Ollama")` | ERROR |
| `chat()` 중 `APIConnectionError` | upstream AsyncLLM이 "Error calling the chat endpoint..." 문자열을 yield → 본 모듈은 이를 `AgentError(code="backend_unreachable")`로 변환 | `AgentError` 이벤트 | ERROR |
| `chat()` 중 upstream `__API_NOT_SUPPORT_TOOLS__` | 즉시 `AgentError(code="api_not_support_tools")` 방출 후 스트림 종료. **prompt mode로 전환하지 않음** | `AgentError` + 다음 호출부터 `use_mcpp` 강제 off 하지 않음(의도 존중. 설정 재검토 유도) | ERROR |
| `chat()` 중 tool arguments JSON 파싱 실패 | upstream ToolExecutor가 `is_error=True` status_update를 yield → `ToolCallResult(ok=False)` 방출 | — | WARNING |
| 빈 응답(턴 종료 시 `assistant_text_total == ""` and no tool call) | `TextChunk("(잠시만요, 생각이 정리되지 않았어요. 다시 질문해 주시겠어요?)")` + `EndOfTurn` | — | WARNING |
| `asyncio.CancelledError` | 락 해제 후 상위 재전파. 부분 누적 텍스트는 upstream `_memory`에 `_add_message`로 이미 기록됨(upstream 기본 동작) | (예외 없음) | DEBUG |
| `handle_interrupt` 중복 호출 | upstream이 자체 guard(`_interrupt_handled`) 보유 → 2번째는 no-op | — | DEBUG |
| `set_memory_from_history`의 history_uid 미존재 | upstream이 빈 리스트 반환 → memory는 빈 상태로 초기화 | — | WARNING |
| `system_prompt is None` | 즉시 실패 | `AgentInitError("system_prompt must be str (use '' for empty)")` | ERROR |
| `BatchInput.texts`가 빈 리스트 and `images`도 None | 즉시 `AgentError(code="empty_response", message="입력이 비어 있어요.")` 후 `EndOfTurn(assistant_text_total="")` | — | WARNING |
| Ollama keep_alive 언로드 상태에서 첫 요청 → TTFT 10~30s | 타임아웃 전이면 정상 진행. `request_timeout_seconds` 초과 시 upstream `APIConnectionError`로 처리 | AgentError(backend_unreachable) | WARNING |

### 원칙

- **초기화 실패는 앱 기동을 중단시킨다**. LLM 없이는 본 제품의 1차 기능 전부가 불가. M_01 `AppServiceContext.init_agent`(CR-03)는 `AgentInitError`/`AgentBackendError`를 **catch하지 않고 그대로 전파**한다. upstream `AgentFactory.create_agent`로 폴백하지 않는다(CR-03 §동작 계약). M_01 스펙 §에러 처리의 "LLM 초기화 실패" 항목과 일치.
- **런타임 실패는 턴 단위로 격리**. `chat()` AsyncIterator가 `AgentError` 이벤트 + `EndOfTurn`으로 정상 종료하여 다음 턴은 계속 시도 가능.
- **취소 전파**: 사용자 인터럽트 시 WebSocket 핸들러가 chat() task에 `cancel()`을 호출. 본 모듈은 락 해제·부분 메모리 저장 후 재전파. upstream `BasicMemoryAgent._memory`에는 부분 assistant 텍스트가 이미 저장되어 있으므로 `handle_interrupt`가 `heard_text + "..."`로 덮어쓴다(upstream 기본).

---

## 성능·메모리 요구사항

### 본 모듈 단독 예산 (Ollama 서버 제외)

| 항목 | 값 | 근거 |
|---|---|---|
| 프로세스 RSS 증가 | ≤ 50 MB | `openai` SDK + `httpx` + upstream BasicMemoryAgent 메모리 리스트(수천 엔트리 한계) |
| 초기화 시간(`__init__` → 헬스체크 완료) | ≤ 1.5 s (loopback Ollama, 1회 성공) | `/api/version` + `/api/tags` 각 100ms 수준 |
| 초기화 시간(3회 재시도 후 실패) | ≤ 5.0 s (0.5 + 1.0 + 2.0 + ~1.5 overhead) | 상수 |
| chat() TTFT (GPU Ollama, 단문) | ≤ 0.5 s | ARCHITECTURE.md §6.2 예산(Gemma 4 E4B GPU TTFT 0.5s) |
| chat() TTFT (CPU Ollama, 단문) | 10~30 s | R-01 개방. SLA 미달 수용. 본 모듈 단독 책임 아님 |
| 한 턴 처리 총 시간 (tool 0회, 100 토큰 응답, GPU) | ≤ 2.0 s | 스트리밍 기준 |
| 한 턴 처리 총 시간 (tool 1회: search_docs, GPU) | ≤ 3.5 s | LLM+tool 왕복 포함 |
| 동시 chat 호출 | **직렬 1개**(asyncio.Lock) | 단일 사용자 전제 |

### 메모리 상한 정책

- upstream `BasicMemoryAgent._memory`는 무제한 append. V1은 외부 트리밍 없음.
- 실질적 상한: `max_context_tokens = 131_000`에 도달하기 훨씬 전에 **Ollama가 내부적으로 트렁케이션**. Ollama 오류 발생 시 `AgentError(code="unknown")`로 사용자에게 표출.
- V2 후보: 슬라이딩 윈도우(`keep_last_n_turns`) 옵션 추가 — 본 스펙 out-of-scope.

### 동시성

- `GemmaChatAgent._chat_lock: asyncio.Lock` — `chat()` 시작 시 acquire, finally에서 release. 두 번째 `chat()` 호출은 첫 번째 완료 대기.
- `handle_interrupt`는 락을 **획득하지 않는다**. 동시에 실행되는 `chat()`을 cancel하는 것이 목적이므로 락 대기하면 데드락.
- `set_memory_from_history`는 락을 획득한다(메모리 변경과 chat의 `_to_messages` 경합 방지).

---

## 테스트 케이스

경로: `tests/agent/test_*.py`. pytest + `pytest-asyncio`. upstream `AsyncLLM.chat_completion`은 `AsyncMock`으로 교체. Ollama는 `httpx_mock` 또는 `respx` 중 기존 의존 가능한 쪽 선택(conftest에서 고정). 실제 네트워크 호출 0건.

### 정상 케이스 (≥5)

**N-1. 초기화 성공 (헬스체크 1회 통과)**
- mock: `probe_ollama`가 `OllamaHealth(reachable=True, model_available=True, ...)` 반환.
- 입력: `GemmaChatAgent(base_url="http://127.0.0.1:11434", model="gemma4:e4b", system_prompt="...", tool_manager=mock_tm, tool_executor=mock_te)`.
- 검증: 인스턴스 생성 성공. `agent.model == "gemma4:e4b"`, `agent._chat_lock`이 `asyncio.Lock` 인스턴스.

**N-2. 단순 텍스트 스트리밍 (tool 없음)**
- 전제: `use_mcpp=False`. upstream `AsyncLLM.chat_completion`이 `"안", "녕", "하세요", ""`(빈 chunk 포함)를 yield.
- 입력: `batch = BatchInput(texts=[TextData(source=TextSource.INPUT, content="안녕")])`.
- 검증: `async for ev in agent.chat(batch)` 결과가 `[TextChunk("안"), TextChunk("녕"), TextChunk("하세요"), EndOfTurn(assistant_text_total="안녕하세요")]`. 빈 chunk는 드롭.

**N-3. tool call 1회 (add_event)**
- 전제: upstream `_openai_tool_interaction_loop`가 아래 순서로 yield:
  1. `"일정을 "` (str)
  2. `"등록할게요."` (str)
  3. `{"type":"tool_call_status","tool_id":"t1","tool_name":"add_event","status":"running","content":"Input: {...}"}` (dict)
  4. `{"type":"tool_call_status","tool_id":"t1","tool_name":"add_event","status":"completed","content":"이벤트 ID 42로 등록됨"}` (dict)
  5. `"등록 완료했어요."` (str, tool 결과 주입 후 2차 호출)
- 검증: 이벤트 순서 [TextChunk, TextChunk, ToolCallStart(name=add_event, arguments={...}), ToolCallResult(ok=True, content=...), TextChunk, EndOfTurn]. `assistant_text_total == "일정을 등록할게요.등록 완료했어요."`.
- ToolCallStart.arguments는 upstream status_update["content"] 문자열 `"Input: {...}"`에서 `{...}` JSON을 파싱한 dict.

**N-4. 멀티모달 (screenshot) 입력**
- 입력: `BatchInput(texts=[TextData(INPUT, "이 화면 설명해줘")], images=[ImageData(SCREEN, "data:image/png;base64,iVBORw0...", "image/png")])`.
- 검증: upstream `_to_messages`가 호출되면 messages 마지막 user content에 `{"type":"image_url", "image_url":{"url":"data:image/png;base64,...", "detail":"auto"}}` 블록이 포함. `AsyncLLM.chat_completion` mock의 `call_args.args[0]` 검사.
- stream은 간단한 TextChunk 시퀀스 → EndOfTurn.

**N-5. 인터럽트 처리**
- 전제: 첫 번째 `chat()`가 실행 중(task). 0.1s 후 두 번째 태스크에서 `await agent.handle_interrupt("제가 들은 건 여기까지예요")`.
- 검증: upstream `_memory`의 마지막 assistant 메시지가 `"<heard_text>..."`로 업데이트. 그 다음 `{"role": "user", "content": "[Interrupted by user]"}`가 추가. chat()은 cancelled.

**N-6. 히스토리에서 메모리 복원**
- 전제: upstream `chat_history_manager.get_history` mock이 10개 메시지 반환.
- 호출: `await agent.set_memory_from_history("conf123", "hist456")`.
- 검증: `agent._inner._memory` 길이 10. 각 메시지 role이 `"user"` 또는 `"assistant"`.

**N-7. 연속 턴 (메모리 누적)**
- 턴1: `chat(BatchInput(texts=[TextData(INPUT,"내 이름은 새싹이야")]))`. mock 응답 `"알겠습니다."`.
- 턴2: `chat(BatchInput(texts=[TextData(INPUT,"내 이름 뭐였지?")]))`. mock 응답 `"새싹이입니다."`.
- 검증: 턴2의 `_to_messages` 호출 시 messages에 턴1 user+assistant가 포함. `agent._inner._memory` 길이 4.

### 엣지 케이스 (≥5)

**E-1. 빈 입력 (texts=[], images=None)**
- 입력: `BatchInput(texts=[])`.
- 검증: `[AgentError(code="empty_response"), EndOfTurn(assistant_text_total="")]` 만 방출. upstream LLM 호출 없음.

**E-2. tool call만 있고 텍스트 응답 없음 (희귀 경로)**
- 전제: mock이 tool_call_status dict 2개(running/completed)만 yield하고 텍스트 없음. 2차 LLM 호출도 빈 응답.
- 검증: `[ToolCallStart, ToolCallResult, TextChunk("(도구 실행 결과를 확인했어요.)"), EndOfTurn]`.

**E-3. base_url에 `/v1` suffix 있음 vs 없음**
- 입력 A: `base_url="http://127.0.0.1:11434"` → `probe_ollama`는 `/api/version` 호출. AsyncLLM은 `http://127.0.0.1:11434/v1` 사용.
- 입력 B: `base_url="http://127.0.0.1:11434/v1"` → 동일 결과. 내부 normalize.
- 검증: 두 경우 모두 `agent._llm.base_url`이 `/v1` 포함 형태로 통일.

**E-4. 첫 토큰이 빈 chunk, 중간에도 빈 chunk**
- mock: `"", "반", "", "갑", "", "습니다"` yield.
- 검증: TextChunk 3개(`"반"`,`"갑"`,`"습니다"`), 빈 chunk 드롭.

**E-5. `interrupt_method="system"` 설정**
- 입력: `interrupt_method="system"`로 초기화 후 `handle_interrupt("안")`.
- 검증: upstream `_memory`에 `{"role":"system","content":"[Interrupted by user]"}` 추가.

**E-6. 동시 chat 호출 직렬화**
- 전제: 두 개의 `chat()` 태스크를 gather로 동시 시작. 각 턴 응답은 고유 식별자.
- 검증: 두 응답이 겹치지 않고 순서대로 완료. 첫 태스크의 EndOfTurn 이후에만 두 번째 태스크의 첫 TextChunk 방출.

**E-7. `max_context_tokens` 경계값**
- 입력: `max_context_tokens=1024` (최소값).
- 검증: 초기화 성공. 별도 트리밍 동작은 없지만(Out-of-Scope), 설정값이 내부 속성에 기록됨.

**E-8. Ollama keep_alive 언로드 후 첫 요청 지연**
- mock: 첫 번째 `chat_completion` 호출이 3초 delay 후 `"지"`,`"금"` yield.
- 검증: 정상 완료. SLA는 위반이지만 본 모듈은 타임아웃 내면 수용.

### 적대적 케이스 (≥3)

**A-1. Ollama 완전 불가 (3회 재시도 모두 실패)**
- mock: `probe_ollama`가 `OllamaHealth(reachable=False, error="ConnectionRefused")` 반환.
- 입력: `GemmaChatAgent(base_url="http://127.0.0.1:11434", ...)` (3회 재시도 내부 구현).
- 검증: `AgentBackendError` raise. 재시도 대기 시간 합 ≤ 4.0s(0.5+1.0+2.0 + overhead). 호출 횟수 3회.

**A-2. 모델 태그 부재**
- mock: `/api/tags` 응답에 `"gemma4:e4b"` 없고 `"llama3:8b"`만 있음.
- 검증: `AgentBackendError("model 'gemma4:e4b' not available in Ollama")`.

**A-3. `__API_NOT_SUPPORT_TOOLS__` 방출**
- mock: upstream AsyncLLM이 첫 응답으로 `"__API_NOT_SUPPORT_TOOLS__"` yield.
- 검증: `[AgentError(code="api_not_support_tools")]` 단일 이벤트 방출 후 스트림 종료(EndOfTurn 없음). upstream `prompt_mode_flag`는 **변경되지 않음**(본 모듈이 사용하지 않으므로).

**A-4. base_url이 공개 호스트 (`https://api.openai.com`)**
- 입력: `GemmaChatAgent(base_url="https://api.openai.com/v1", ...)`.
- 검증: `AgentInitError("base_url must be loopback or private IP")` — 본 모듈에서도 `enforce_private_url`를 재호출(2중 방어).

**A-5. tool arguments가 손상된 JSON**
- mock: upstream `ToolExecutor.parse_tool_call` 결과 `parse_error=True`. executor가 `{"type":"tool_call_status","status":"error","tool_name":"add_event","content":"Error: Invalid arguments..."}` yield.
- 검증: `ToolCallResult(ok=False, content="Error: Invalid arguments...")` 방출. 이후 LLM의 재호출 분기가 mock에서 `"다시 알려주세요"` yield → TextChunk → EndOfTurn.

**A-6. 초기화 중 `asyncio.CancelledError`**
- 전제: `probe_ollama` mock이 1초 sleep. 0.1s 후 태스크 cancel.
- 검증: `CancelledError`가 상위로 전파. 생성된 httpx 클라이언트는 `__init__` 실패 경로에서도 정리(try/finally).

**A-7. chat 도중 backend 5xx 반복**
- mock: upstream AsyncLLM이 첫 chunk로 `"Error calling the chat endpoint: ..."` 문자열 yield(upstream의 APIError 경로 결과).
- 검증: 본 모듈이 이 문자열을 감지해 `AgentError(code="backend_unreachable")` 이벤트로 변환. **재시도하지 않고** EndOfTurn(assistant_text_total="") 방출. (재시도는 초기화 전용 정책)

**A-8. 매우 긴 user 입력 (100KB 텍스트)**
- 입력: 10만자 텍스트 → upstream `_to_messages`가 그대로 전달 → mock LLM이 응답.
- 검증: 본 모듈이 자체 트렁케이션 없이 진행. 응답 정상 스트리밍. (V1 정책: 트렁케이션은 Ollama 위임)

---

## 오프라인 빌드 메모

### pyproject.toml 추가 / 확인

| 패키지 | 버전 핀 | 용도 | 비고 |
|---|---|---|---|
| `openai` | `>=1.30,<2` | upstream AsyncLLM이 사용 | upstream 이미 요구. 버전 재확인 |
| `httpx` | `>=0.27,<1` | `probe_ollama` | upstream 이미 요구 |
| `pytest-asyncio` | `>=0.23` | 테스트 | 기존 |
| `respx` (옵션) | `>=0.21,<1` | httpx 모킹 | conftest에서 사용. 없으면 `pytest-httpx` 대체 |

새 의존성은 `openai`, `httpx`가 이미 upstream에 있으므로 추가 없음. `respx`만 테스트용으로 후보.

### 환경변수

M_01 `src/app/main.py`에서 이미 설정하는 변수 외에 **본 모듈 고유 추가 없음**. `OLLAMA_BASE_URL` 해석은 M_01 담당.

### 네트워크 검증

- CI 단계 `grep -rE "https?://[^/\s]*(?!127\.0\.0\.1|localhost|192\.168|10\.|172\.)"` 정규식 검사로 외부 URL 하드코딩 금지.
- `probe_ollama`·`AsyncLLM`은 오직 `base_url`만 사용. 추가 호스트 생성 금지.

### 모델 아티팩트

- 본 모듈은 모델 파일을 **로드하지 않는다**. Ollama가 이미 `ollama pull gemma4:e4b`로 확보해야 함(오프라인 번들에서 `ollama/models/` 사전 채움 — ARCHITECTURE.md §7).
- `scripts/bundle_deps.sh` 변경 불필요(Ollama 모델 번들링은 기존 스크립트에 포함 전제).

---

## Definition of Done

### 공통 (CLAUDE.md "산출물 체크리스트")
- [ ] `specs/M_05_LLMAgent_SPEC.md` (본 문서) 사용자 승인.
- [ ] `src/agent/` 구현 (`__init__.py`, `errors.py`, `events.py`, `health.py`, `gemma_chat_agent.py`, `upstream_adapter.py`, `builder.py`).
- [ ] `tests/agent/` 테스트: 본 스펙 N/E/A 전체 (정상 ≥5, 엣지 ≥5, 적대적 ≥3).
- [ ] `ruff format .`, `ruff check .`, `mypy src/agent/`, `pytest tests/agent/ -v` 모두 통과.
- [ ] `reviews/M_05_LLMAgent_REVIEW.md` Critic PASS.
- [ ] `docs/MODULES.md`의 M_05 상태가 ✅ DONE으로 갱신.

### M_05 고유

- [ ] `GemmaChatAgent`가 `BasicMemoryAgent`를 상속하지 않고 **컴포지션**으로 보유함을 코드에서 확인.
- [ ] `AgentInterface`는 `BasicMemoryAgentAdapter`만 구현한다(GemmaChatAgent는 구현하지 않음).
- [ ] `probe_ollama`가 `/api/version` 및 `/api/tags` 두 경로를 호출하고 `/v1` suffix 유무 모두 정규화한다.
- [ ] 초기화 재시도 3회의 대기 시간이 `[0.5, 1.0, 2.0]`초로 고정(변경 시 스펙 재승인).
- [ ] `chat()` 진입부에 `asyncio.Lock` 획득·해제 로직 존재.
- [ ] upstream `_to_messages`·`_openai_tool_interaction_loop`를 직접 호출하며, upstream 데코레이터 체인(`sentence_divider` 등)을 **호출하지 않음**을 테스트로 확인(monkeypatch로 데코레이터 모듈에 sentinel 삽입 후 touch 안 됨 확인).
- [ ] tool call dict → `AgentEvent` 변환 규칙이 `_translate_tool_event`에 격리되어 있고, 미지 type은 None 반환 + 로그.
- [ ] `__API_NOT_SUPPORT_TOOLS__` 수신 시 `AgentError(code="api_not_support_tools")` 방출 후 즉시 종료. prompt mode로 fallback하지 않음을 단위 테스트로 확인.
- [ ] `BatchInput.texts=[]` and `images is None`인 입력에서 LLM 호출 없이 AgentError + EndOfTurn 방출.
- [ ] `handle_interrupt`는 락을 획득하지 않고, 동시 `chat()` 태스크를 실제로 취소함을 통합 테스트에서 확인.
- [ ] `aclose()`가 내부 httpx 클라이언트를 닫고, GC 경고(`RuntimeWarning: coroutine was never awaited` 혹은 `unclosed transport`)가 발생하지 않음을 pytest `-W error` 설정에서 확인.
- [ ] **(CR-03)** `BasicMemoryAgentAdapter.close()`가 `self._agent.aclose()`를 await하며, upstream `ServiceContext.close()`의 `hasattr(agent_engine, "close")` 가드를 통과해 GC 경고 없이 종료됨을 테스트로 증명.
- [ ] 외부 네트워크 호출 0건: 테스트 실행 중 `respx` 또는 `httpx_mock`로 모든 HTTP 호출을 잡아 실제 소켓이 열리지 않음을 확인.
- [ ] `upstream/Open-LLM-VTuber/src/open_llm_vtuber/**` 파일이 수정되지 않았음을 git diff로 확인.
- [ ] M_01 `AppConfig`에 `agent: AgentConfig` 필드 추가를 위한 변경 요청이 M_01 스펙 갱신 항목으로 등록됨(본 스펙 §배선).
- [x] **(CR-03 구현 완료)** M_01 `AppServiceContext.init_agent` 오버라이드(M_04 `init_tts`와 동일 패턴)가 `BasicMemoryAgentAdapter` + `CompositeToolExecutor` 배선을 수행하도록 M_01 스펙/구현에 반영됨. 이전 "load_from_config pre-set" 기술은 기각됨. M_01 AppServiceContext.init_agent 오버라이드 구현이 M_01 CR-03에 포함됨.
- [ ] R-06(Gemma 4 E4B vision 변형) 스파이크 스크립트가 `scripts/spike_gemma_vision.py`로 작성·실행되어 결과가 `docs/research/gemma_vision_spike.md`에 기록됨.

---

## 의존성

### Python 패키지

| 패키지 | 사유 | 상태 |
|---|---|---|
| `openai` | upstream `AsyncLLM` 내부 | 이미 있음 |
| `httpx` | `probe_ollama` 및 upstream `AsyncLLM` | 이미 있음 |
| `pydantic` | `AgentConfig` 스키마 | 이미 있음 |
| `loguru` | 로그 | 이미 있음 |

### 런타임 전제

- Python 3.12+.
- upstream 소스 트리가 `upstream/Open-LLM-VTuber/src`에 있고 `sys.path`에 포함(M_01 설정).
- Ollama 프로세스가 `base_url`에서 실행 중이어야 초기화 성공. 빌드 타임에는 mock.
- `OLLAMA_BASE_URL` 환경변수는 M_01이 해석·검증한 결과가 `ollama_config.base_url`로 전달됨.

### 모듈 의존

| 대상 | 관계 |
|---|---|
| M_01 AppCore | `AppConfig.agent`/`AppConfig.ollama` 스키마 소유. `enforce_private_url` 재사용. `AppServiceContext.init_agent` 오버라이드 주입 지점(CR-03) |
| M_05b ToolRouter | `tool_manager: ToolManager`, `tool_executor: ToolExecutor`를 생성·주입. 생성 결과는 upstream 타입과 호환 |
| upstream `BasicMemoryAgent` | 컴포지션 보유 |
| upstream `OpenAICompatibleLLM.AsyncLLM` | 생성자에 주입 |
| upstream `AgentInterface` | `BasicMemoryAgentAdapter`가 구현 |
| upstream `ToolManager`, `ToolExecutor` | 타입만 소비(본 모듈에서 생성 안 함) |

**M_05는 M_02/M_03/M_04/M_06/M_07/M_09에 직접 의존하지 않는다.** 이들은 M_05b를 경유해서만 본 모듈과 연결된다.

---

## 디렉토리 구조

```
src/agent/
├── __init__.py              # 공개 심볼
├── errors.py                # AgentInitError, AgentBackendError, AgentProtocolError
├── events.py                # TextChunk, ToolCallStart, ToolCallResult, EndOfTurn, AgentError, AgentEvent alias
├── health.py                # probe_ollama, OllamaHealth
├── gemma_chat_agent.py      # GemmaChatAgent
├── upstream_adapter.py      # BasicMemoryAgentAdapter (+ close() CR-03)
└── builder.py               # build_chat_agent

tests/agent/
├── __init__.py
├── conftest.py              # mock AsyncLLM, mock ToolManager/ToolExecutor, respx/httpx_mock 고정
├── fakes.py                 # FakeAsyncLLM(상세 응답 시나리오 조립), FakeToolExecutor
├── test_health.py           # probe_ollama (A-1, A-2, A-4, A-6 일부)
├── test_init.py             # 초기화 (N-1, A-1, A-2, A-4, A-6)
├── test_chat_simple.py      # 단순 스트리밍 (N-2, E-1, E-4, E-8, A-7, A-8)
├── test_chat_tools.py       # tool 경로 (N-3, E-2, A-3, A-5)
├── test_multimodal.py       # 이미지 입력 (N-4)
├── test_interrupt.py        # 인터럽트 (N-5, E-5, E-6)
├── test_memory.py           # 히스토리·연속 턴 (N-6, N-7)
├── test_adapter.py          # BasicMemoryAgentAdapter 동작 + close() 위임(CR-03)
└── test_builder.py          # build_chat_agent 분기
```

---

## 스펙 외 사항 (명시적 제외)

본 모듈의 책임이 **아닌** 항목:

1. **문장 분할·TTS 텍스트 전처리**: upstream `sentence_divider`/`tts_filter`. 프로젝트 Orchestrator가 M_04 직전에 적용.
2. **감정 태그(`[emotion:happy]`) 추출**: M_08 AvatarState. 본 모듈은 태그를 텍스트에 그대로 포함한 채 TextChunk로 전달.
3. **tool 실제 실행**: M_05b `ToolRouter` + upstream `ToolExecutor`가 담당. 본 모듈은 call/result의 **관찰자**.
4. **자연어 날짜·시간 파싱**: LLM 자체 또는 M_09 `CalendarService`의 자체 검증. 본 모듈은 pass-through.
5. **Ollama 서버 수명관리**(start/stop/keep_alive): 인프라 스크립트. 본 모듈은 **클라이언트**.
6. **토큰 카운팅·컨텍스트 트리밍**: V2 후보. 본 모듈은 무제한 메모리 append(upstream 기본).
7. **Claude 백엔드 지원**: upstream에 존재하나 본 프로젝트는 Ollama 전용.
8. **Prompt mode tool fallback**: `__API_NOT_SUPPORT_TOOLS__` 시 즉시 에러. 우회 전환 금지.
9. **그룹 대화, 멀티 사용자 세션 분리**: REQUIREMENTS.md §10으로 제외.
10. **LLM 응답의 PII 마스킹**: M_01 logging의 `pii_mask` 필터가 로그 단계에서 처리. 본 모듈은 원문 그대로 전달.
11. **upstream `AgentFactory` 확장**: 팩토리 수정 금지. M_01 `AppServiceContext.init_agent` 오버라이드(CR-03)가 팩토리 자체를 호출 경로에서 제거.
12. **페르소나·감정 태그 프롬프트 저작**: prompts/ 리포지터리 및 `prompts/persona/saessagi.txt` 소관. 본 모듈은 외부에서 주입받은 문자열을 사용.
13. **화면 캡처 PNG 생성**: M_05b `ScreenshotService`. 본 모듈은 `BatchInput.images`에 이미 base64가 채워졌다는 전제.
14. **R-06 Gemma vision 변형 확인 스파이크의 실행 자체**: 본 스펙은 DoD에 스파이크 결과 보관만 요구. 실제 검증은 M_05 구현 시작 직전 Researcher/Builder 협업 산출물.

---

## 부록: upstream 경로·심볼 인덱스 (실재 확인)

본 스펙 작성 중 `/mnt/c/projects/ai-assistant/upstream/Open-LLM-VTuber/src/open_llm_vtuber/` 하의 실제 파일을 읽어 시그니처를 확정했다:

- `agent/agents/basic_memory_agent.py` L33~L703:
  - `BasicMemoryAgent.__init__(llm, system, live2d_model, tts_preprocessor_config=None, faster_first_response=True, segment_method="pysbd", use_mcpp=False, interrupt_method="user", tool_prompts=None, tool_manager=None, tool_executor=None, mcp_prompt_string="")`.
  - `_to_messages(input_data: BatchInput) -> list[dict]` L242~L288. user message append + `_add_message` 호출 부작용.
  - `_openai_tool_interaction_loop(initial_messages, tools) -> AsyncIterator[str | dict]` L403~L579. tool call 시 dict yield, 텍스트는 str yield.
  - `handle_interrupt(heard_response: str) -> None` L195~L223. 동기.
  - `set_memory_from_history(conf_uid, history_uid) -> None` L176~L193. 동기.
  - `reset_interrupt()` L673~L675.
  - `set_system(system: str)` L119~L126.
  - `prompt_mode_flag: bool` — 본 모듈은 항상 False 유지.
- `agent/agents/agent_interface.py` L1~L55: `AgentInterface` ABC — `chat`, `handle_interrupt`, `set_memory_from_history` 추상.
- `agent/input_types.py` L1~L95: `BatchInput(texts, images, files, metadata)`, `TextData(source, content, from_name)`, `ImageData(source, data, mime_type)`, `TextSource`/`ImageSource` enum.
- `agent/stateless_llm/openai_compatible_llm.py` L24~L237: `AsyncLLM(model, base_url, llm_api_key="z", organization_id="z", project_id="z", temperature=1.0)`. `chat_completion(messages, system, tools=NOT_GIVEN) -> AsyncIterator[str | list[ChoiceDeltaToolCall]]`. APIConnectionError/RateLimitError/APIError catch 후 문자열 yield(`"Error calling the chat endpoint..."` 등). `"__API_NOT_SUPPORT_TOOLS__"` 센티널 yield.
- `mcpp/tool_manager.py` L1~L51: `ToolManager(formatted_tools_openai, formatted_tools_claude, initial_tools_dict)`. `get_formatted_tools("OpenAI") -> list[dict]`.
- `mcpp/tool_executor.py` L18~L383: `ToolExecutor(mcp_client, tool_manager)`. `execute_tools(tool_calls, caller_mode) -> AsyncIterator[dict]` yield하는 dict 타입: `{"type":"tool_call_status", "tool_id", "tool_name", "status":"running"|"completed"|"error", "content", "timestamp"}`, `{"type":"final_tool_results", "results": [...]}`.
- `mcpp/types.py` L45~L93: `ToolCallObject(id, type, index, function)`, `ToolCallFunctionObject(name, arguments)`.
- `service_context.py` L190~L199: `close()` — `hasattr(agent_engine, "close")` 가드로 `agent_engine.close()` 호출. CR-03이 `BasicMemoryAgentAdapter.close()`를 신규 추가하는 근거.
- `service_context.py` L249~L312: `load_from_config` 흐름 `init_live2d → init_asr → init_tts → init_vad → tool_adapter → _init_mcp_components → init_agent → init_translate`. L300 `await self.init_agent(...)` 호출이 CR-03 오버라이드 디스패치 지점.
- `service_context.py` L364~L405: `init_agent(agent_config, persona_prompt)` 원본. idempotency 가드(L368-374). CR-03 오버라이드가 동일 가드를 차용 후 `AgentFactory` 대신 `build_chat_agent`를 호출.
- `chat_history_manager.py`(상단 export): `get_history(conf_uid, history_uid) -> list[dict]`. upstream `BasicMemoryAgent.set_memory_from_history`가 호출.
