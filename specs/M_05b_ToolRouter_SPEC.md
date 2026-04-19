# M_05b ToolRouter — 스펙

> 분류: **NEW** — upstream에는 대응물이 없다. upstream `mcpp/`의 `ToolManager`/`ToolExecutor`/`MCPClient`는 **외부 MCP 서버**(filesystem 등)를 위한 것이며, 본 모듈은 **로컬 파이썬 핸들러**(Calendar/RAG/Screenshot) 디스패처이다.
>
> 작성 근거: `docs/MODULES.md` M_05b 계약, `specs/M_05_LLMAgent_SPEC.md` §스펙 외 사항, `REQUIREMENTS.md` §2.2/§4.1/§4.2/§6/§9, `upstream/Open-LLM-VTuber/src/open_llm_vtuber/mcpp/tool_executor.py`, `mcpp/tool_manager.py`.

---

## 1. 목적과 범위

### 1.1 목적

Gemma 4 E4B(Ollama `gemma4:e4b`)가 네이티브 tool calling으로 방출하는 `tool_call` dict를, 본 프로젝트가 직접 작성·제어하는 **로컬 파이썬 핸들러**로 결정론적으로 디스패치한다. 4개 기본 툴(`add_event`, `get_events`, `search_docs`, `take_screenshot`)의 JSON Schema 공급·인자 검증·예외 격리·upstream 호환 어댑터까지 한 모듈에 집중한다.

### 1.2 In-Scope

1. `ToolRouter` 클래스 — 4개 툴의 JSON Schema 공급(`tool_specs()`)과 디스패치(`dispatch(name, arguments)`) 두 메서드.
2. `ToolResult` 데이터클래스 — `ok`/`payload`/`error` 3필드. 본 모듈의 **유일한 반환 타입**.
3. `ScreenshotService` — `mss` 기반 Windows 전체 화면 캡처 + base64 data URL 변환 + 연속 모드(주기 캡처 + privacy 경고).
4. `ToolRouterAdapter` — upstream `ToolExecutor`/`MCPClient` 계열 호출부와의 경계 어댑터. `execute_tool(name, arguments) -> str`(사용자 요구 시그니처) 및 `run_single_tool(...)`(upstream 포맷 호환) 두 가지 인터페이스를 병렬 제공.
5. JSON Schema 검증 — `jsonschema` 라이브러리(Draft 2020-12) Validator를 **모듈 로드 시 1회 컴파일**하고 `dispatch` 마다 재사용.
6. `GemmaChatAgent` 병합 경계 — `ToolRouter.tool_specs()` 반환값과 upstream `ToolManager.get_formatted_tools("OpenAI")`를 **Agent 측에서** 합쳐 `/v1/chat/completions tools=`에 싣는다. 본 모듈은 upstream `ToolManager`에 **등록하지 않는다**.
7. 단위 테스트(정상 ≥5, 엣지 ≥5, 적대적 ≥3).

### 1.3 Out-of-Scope (명시적 제외)

1. **filesystem / ddg-search / time 등 외부 MCP 툴**. upstream `ToolManager`+`ToolExecutor`+`MCPClient` 경로로 처리한다. 본 모듈은 **이들과 이름이 겹치지 않는 4개 툴만** 소유한다(중복 등록 금지).
2. **자연어 날짜 파싱**. `add_event`의 `start` 인자는 LLM이 ISO 8601로 변환한 문자열로 도착해야 한다. 파싱 실패 시 Calendar가 `ValueError`를 던지고 본 모듈은 `ToolResult(ok=False)`로 감싼다. M_09/M_05 스펙의 경계와 일치.
3. **LLM 호출·응답 스트리밍**. 본 모듈은 LLM을 호출하지 않는다.
4. **tool call 결과의 LLM 재주입**. upstream `BasicMemoryAgent._openai_tool_interaction_loop`가 수행한다. 본 모듈은 결과만 반환.
5. **PII 마스킹**. 로깅 계층에서 적용(M_01 공통 필터).
6. **카테고리 필터 UI**. `search_docs`의 `category` 인자는 스키마에 존재하되 V1에서는 프론트가 설정하지 않는다. V2 대비(M_07 스펙과 일치).
7. **리랭커 호출**. RISKS.md 결정에 따라 V1 제외.
8. **연속 스크린샷 모드의 프레임 드롭/인코딩 최적화**. V1은 고정 주기 PNG 풀 프레임만 지원.
9. **화면 영역 선택·특정 창 캡처**. 전체 화면(primary monitor) 1장 고정.
10. **추가 툴의 런타임 등록**. V1은 **고정 4종**. 동적 추가/제거 API 없음.

---

## 2. 요구사항 연결

| REQUIREMENTS.md 항목 | M_05b 기여 |
|---|---|
| §0 완전 오프라인 / §9 외부 네트워크 금지 | `mss`(네이티브 Windows), `jsonschema`(순수 Python), `Pillow`(PNG 인코딩) — 모두 오프라인 실행. 네트워크 호출 0건. |
| §0 Windows 10/11 전용 | `mss`는 Windows BitBlt/DXGI 경로 사용. 다른 OS에서도 import는 되지만 본 모듈은 `platform.system() != "Windows"`일 때 `ScreenshotService.__init__`에서 `ScreenshotInitError` 발생. |
| §2.2 문서 RAG 질의응답(인용 포함) | `search_docs` 툴 → `RagService.retrieve()` 호출 → 결과와 `RagService.format_citation(hit)` 문자열 목록을 `ToolResult.payload`에 포함. |
| §4.1 일정 등록(function calling) | `add_event` 툴 → `CalendarService.add_event()` → 생성된 `Event`의 id·title·start·duration을 payload로 반환. |
| §4.2 알림/조회 | `get_events(start, end)` 툴 → `CalendarService.get_events()` → 이벤트 목록(JSON serializable) 반환. |
| §6 화면 인식 | `take_screenshot` 툴 → `ScreenshotService.capture_once()` → base64 data URL을 payload로 반환. 연속 모드는 `continuous=True`로 진입하며 `ScreenshotService.start_continuous(interval_seconds)`가 `privacy_warning` 이벤트를 송신 후 주기 캡처. |
| §9 응답 지연 | `dispatch` 자체 오버헤드 < 5 ms(JSON Schema 검증 + 함수 분기). 스크린샷 캡처는 GPU 유무 무관 < 300 ms(1920x1080 기준, mss 공식 벤치). |
| §9 메모리 상한 | 본 모듈 자체 RSS 기여 < 30 MB. mss 상주 + 연속 모드 큐. PNG 프레임은 즉시 base64 직렬화 후 참조 해제. |

---

## 3. 아키텍처 다이어그램

```
                          ┌─────────────────────────────────────────┐
                          │           GemmaChatAgent (M_05)         │
                          │                                         │
                          │  tools_for_api = (                      │
                          │    ToolManager.get_formatted_tools      │
                          │      ("OpenAI")          # upstream MCP │
                          │    + ToolRouter.tool_specs()            │
                          │      # 로컬 4종                         │
                          │  )                                      │
                          │                                         │
                          │  ↓  /v1/chat/completions tools=...      │
                          │  ↓                                      │
                          │  tool_call dict 수신 시                 │
                          │  (upstream _openai_tool_interaction_    │
                          │   loop 내부 execute_tools 경로)         │
                          └────────────────┬────────────────────────┘
                                           │ name, arguments
                                           ▼
           ┌───────────────────────────────────────────────────────────┐
           │                 ToolRouterAdapter                         │
           │                                                           │
           │  if name in LOCAL_TOOL_NAMES:                             │
           │      result = await router.dispatch(name, arguments)      │
           │      return json.dumps(result.payload | error_obj)        │
           │  else:                                                    │
           │      raise RuntimeError(                                  │
           │        "adapter: not a local tool; route via MCPClient")  │
           └────────────────┬──────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         ToolRouter                                  │
│                                                                     │
│  dispatch(name, arguments):                                         │
│    1) validator = self._validators[name]   # 미지 → unknown_tool    │
│    2) validator.validate(arguments)        # 실패 → invalid_args    │
│    3) match name:                                                   │
│         "add_event"      → _handle_add_event(arguments)             │
│         "get_events"     → _handle_get_events(arguments)            │
│         "search_docs"    → _handle_search_docs(arguments)           │
│         "take_screenshot"→ _handle_take_screenshot(arguments)       │
│    4) 서비스 None → ToolResult(ok=False, error="service_unavail..") │
│    5) 예외 발생 → ToolResult(ok=False, error="<exception.__class__> │
│                            : <str(e)>") (raise 금지)                │
└───┬────────────────┬────────────────┬─────────────────┬─────────────┘
    │                │                │                 │
    ▼                ▼                ▼                 ▼
 M_09             M_07             M_05b             (out)
 CalendarService  RagService       Screenshot        base64 data URL
 (SQLite)         (Embedder +      Service            → BatchInput.images
                   VectorStore     (mss + Pillow)     (주입은 M_05 측)
                   + citations)    + continuous mode
```

### 3.1 배선 순서(M_01에서 조립)

```
M_01 AppServiceContext.load_app_services:
  calendar_service  = CalendarService(db_path=...)        # M_09
  rag_service       = RagService(embedder, store, ...)    # M_07
  screenshot_service= ScreenshotService(                  # M_05b 내부
        send_text=ws_handler.send_text_to_client)
  tool_router       = ToolRouter(calendar_service,
                                 rag_service,
                                 screenshot_service)
  tool_router_adapter = ToolRouterAdapter(tool_router)

  gemma_agent = build_chat_agent(
        ollama_config, tool_manager=mcp_tool_manager,
        tool_executor=tool_router_adapter.as_upstream_tool_executor(
                          mcp_tool_executor),  # §8 참조
        system_prompt=...,
        extra_tool_specs=tool_router.tool_specs())   # M_05 CR
```

본 스펙은 `M_01`에 대해 `build_chat_agent(..., extra_tool_specs=)` 파라미터 신설을 **변경 요청**으로 포함한다(§12 DoD 참조, M_05 스펙과 정합).

---

## 4. 공개 API

### 4.1 예외 타입

```python
# src/tool_router/errors.py
class ToolRouterError(Exception):
    """M_05b 공통 기본 예외."""

class ScreenshotInitError(ToolRouterError):
    """OS/권한/의존 라이브러리 문제로 ScreenshotService 초기화 실패."""

class ScreenshotCaptureError(ToolRouterError):
    """런타임 캡처 실패(디스플레이 분리, DPI 변경 등). dispatch()는 이를 catch해서 ToolResult(ok=False)로 변환."""
```

> **원칙**: 본 모듈의 공개 API(`ToolRouter.dispatch`, `ToolRouterAdapter.execute_tool`)는 **예외를 raise하지 않는다**. 모든 오류는 `ToolResult(ok=False, error=...)`로 변환된다. 내부에서만 위 예외를 사용.

### 4.2 데이터 클래스

```python
# src/tool_router/types.py
from dataclasses import dataclass, field
from typing import Any, Literal

ToolSpec = dict[str, Any]   # OpenAI function-calling JSON schema

ToolErrorCode = Literal[
    "unknown_tool",
    "invalid_arguments",
    "service_unavailable",
    "handler_exception",
    "screenshot_failed",
    "continuous_already_running",
    "continuous_not_running",
]

@dataclass(frozen=True)
class ToolResult:
    """ToolRouter.dispatch의 유일한 반환 타입."""
    ok: bool
    payload: dict[str, Any] = field(default_factory=dict)
    error: str | None = None        # ok=False일 때만 채운다. 사람이 읽을 수 있는 한국어 또는 jsonschema 원문.
    error_code: ToolErrorCode | None = None  # 프로그램 분기용. ok=True일 때는 None.
```

### 4.3 ToolRouter

```python
# src/tool_router/router.py
from collections.abc import Callable, Awaitable
from typing import Any
from jsonschema import Draft202012Validator

class ToolRouter:
    """Gemma tool_call → 로컬 파이썬 핸들러 디스패처.

    생성자 주입 서비스가 None이면 해당 툴은 런타임에 service_unavailable을 반환한다.
    (초기화는 성공하되, 호출 시 실패하는 정책 — 부트 시 일부 서비스가 없어도 나머지 툴은 동작)
    """

    def __init__(
        self,
        calendar: "CalendarService | None",
        rag: "RagService | None",
        screenshot: "ScreenshotService",
    ) -> None:
        """
        Args:
            calendar: M_09 CalendarService 인스턴스. None이면 add_event/get_events가 service_unavailable.
            rag: M_07 RagService 인스턴스. None이면 search_docs가 service_unavailable.
            screenshot: M_05b 내부 ScreenshotService 인스턴스. **None 금지**(항상 제공).

        Raises:
            TypeError: screenshot is None.
        """

    def tool_specs(self) -> list[ToolSpec]:
        """4개 툴의 OpenAI function-calling JSON schema 리스트를 반환.

        반환 리스트는 **호출마다 새 사본**(list copy)이다. 호출 측의 수정이 내부 상태를
        오염시키지 않도록 보호한다. 단, 각 dict 객체는 공유될 수 있으므로 호출 측이
        수정하면 안 된다(명시적 불변 계약).
        """

    async def dispatch(
        self, name: str, arguments: dict[str, Any]
    ) -> ToolResult:
        """tool_call 이름·인자를 받아 핸들러를 호출.

        순서:
          1) name이 LOCAL_TOOL_NAMES에 없으면
             → ToolResult(ok=False, error="unknown_tool: <name>", error_code="unknown_tool")
          2) arguments가 dict가 아니면
             → ToolResult(ok=False, error="arguments must be dict, got <type>",
                          error_code="invalid_arguments")
          3) self._validators[name].validate(arguments) 실패 → jsonschema.ValidationError
             → ToolResult(ok=False, error=<human readable 첫 번째 에러 경로>,
                          error_code="invalid_arguments")
          4) 해당 서비스 attribute가 None
             → ToolResult(ok=False, error="service_unavailable: <tool>",
                          error_code="service_unavailable")
          5) 핸들러 호출. 성공 시 ToolResult(ok=True, payload=<tool별 스키마>).
          6) 핸들러 내부 예외
             → logger.exception 기록 후
               ToolResult(ok=False,
                          error=f"{type(e).__name__}: {e}",
                          error_code="handler_exception")

        취소:
          asyncio.CancelledError는 catch하지 않고 상위로 재전파한다. 단, 연속 스크린샷
          모드를 시작한 직후 취소되는 경우 stop_continuous를 try/finally로 호출(누수 방지).

        Args:
            name: tool 이름. 대소문자 엄격 일치.
            arguments: 파싱된 dict. 상위에서 JSON 문자열은 이미 dict로 변환되어 도착.

        Returns:
            ToolResult. 항상 반환하며 예외를 raise하지 않는다.
        """

    # --- 내부 ---
    LOCAL_TOOL_NAMES: frozenset[str] = frozenset({
        "add_event", "get_events", "search_docs", "take_screenshot"
    })

    async def _handle_add_event(self, args: dict[str, Any]) -> ToolResult: ...
    async def _handle_get_events(self, args: dict[str, Any]) -> ToolResult: ...
    async def _handle_search_docs(self, args: dict[str, Any]) -> ToolResult: ...
    async def _handle_take_screenshot(self, args: dict[str, Any]) -> ToolResult: ...
```

### 4.4 ScreenshotService

```python
# src/tool_router/screenshot.py
from collections.abc import Awaitable, Callable
from typing import Any

SendTextCallback = Callable[[dict[str, Any]], Awaitable[None]]

class ScreenshotService:
    """Windows 전체 화면 캡처 + 연속 모드.

    외부 모듈 의존 없음(M_05b 내부 전용). 연속 모드는 단일 인스턴스에서 **동시 1개**만
    허용한다. 다중 모니터 환경에서는 `monitor=1`(primary) 고정(V1).
    """

    def __init__(
        self,
        send_text: SendTextCallback | None = None,
        interval_min: float = 1.0,
        interval_max: float = 60.0,
    ) -> None:
        """
        Args:
            send_text: 연속 모드 진입 시 `{"type":"privacy_warning","text":...}` 이벤트를
                       전송할 비동기 콜백(WebSocket send_text). None이면 경고는 로그로만.
            interval_min: 연속 모드 허용 최소 주기(초). 기본 1.0.
            interval_max: 연속 모드 허용 최대 주기(초). 기본 60.0.

        Raises:
            ScreenshotInitError: platform.system() != "Windows", mss import 실패, 권한 부족.
        """

    async def capture_once(self) -> str:
        """단건 캡처. primary monitor 전체 화면을 PNG로 압축해 base64 data URL 반환.

        반환 형식: "data:image/png;base64,iVBORw0KGgo..."

        Raises:
            ScreenshotCaptureError: 디스플레이 핸들 획득 실패, 인코딩 실패.
        """

    async def start_continuous(
        self,
        interval_seconds: float,
        on_frame: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        """연속 모드 시작.

        1) interval_seconds가 [interval_min, interval_max] 밖이면 ValueError.
        2) 이미 실행 중이면 ScreenshotCaptureError("continuous_already_running").
        3) 첫 작업: send_text로 privacy_warning 이벤트 emit.
             {"type": "privacy_warning",
              "text": "연속 화면 공유를 시작합니다. 개인정보가 포함될 수 있습니다.",
              "interval_seconds": interval_seconds}
        4) asyncio.create_task로 _loop(interval_seconds, on_frame) 스케줄.
        5) 각 틱마다:
             frame = await self.capture_once()
             if on_frame: await on_frame(frame)
           예외는 logger.exception 후 다음 틱 계속(단, ScreenshotInitError는 루프 중단).
        """

    async def stop_continuous(self) -> None:
        """연속 모드 종료. 실행 중이 아니면 no-op(에러 아님)."""

    @property
    def is_continuous_running(self) -> bool: ...

    async def aclose(self) -> None:
        """종료 정리. stop_continuous() + mss 리소스 해제."""
```

### 4.5 ToolRouterAdapter (upstream 경계)

```python
# src/tool_router/upstream_adapter.py
import json
from typing import Any

class ToolRouterAdapter:
    """upstream 호출부(`ToolExecutor`/`BasicMemoryAgent._openai_tool_interaction_loop`)가
    기대하는 인터페이스 두 가지를 동시에 제공한다.

    1) `execute_tool(name, arguments) -> str` — 본 프로젝트 내부 약속. ToolResult.payload
       또는 error 객체를 **JSON 문자열로 직렬화**해 반환. 예외는 raise하지 않는다.
    2) `run_single_tool(tool_name, tool_id, tool_input) -> (is_error, text_content, metadata,
       content_items)` — upstream `ToolExecutor.run_single_tool` 시그니처와 동일.
       `ToolExecutor.execute_tools`가 이 메서드를 호출하므로, **로컬 툴에 한해**
       upstream ToolExecutor를 **monkey-patch하지 않고 대체 인스턴스**로 공급할 수 있다.

    병행 ToolExecutor 구성:
      GemmaChatAgent는 tool_call dict의 name을 검사해
        - name in LOCAL_TOOL_NAMES → ToolRouterAdapter 경로
        - else → upstream ToolExecutor 경로(MCP 툴)
      로 분기한다. 본 어댑터는 upstream ToolExecutor를 감싸지 않는다(책임 분리).

    그러므로 본 어댑터가 제공하는 `as_upstream_tool_executor(fallback)`은
    **로컬 툴은 직접 처리하고, 나머지는 fallback(원본 upstream ToolExecutor)에 위임**하는
    얇은 래퍼 `CompositeToolExecutor`를 생성한다.
    """

    def __init__(self, router: ToolRouter) -> None: ...

    async def execute_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """사용자 요구 시그니처.

        반환 JSON 구조:
          - 성공: {"ok": true, "payload": {...}}
          - 실패: {"ok": false, "error": "...", "error_code": "..."}

        예외는 raise하지 않는다. 내부 예상 밖 실패는
          {"ok": false, "error": "adapter_exception: ...", "error_code": "handler_exception"}

        주의: LLM이 이 JSON 문자열을 읽고 다음 답변을 생성한다. 스키마를 바꾸면 LLM
        프롬프트 연계가 깨질 수 있으므로 변경 시 M_05 스펙과 동기화 필요.
        """

    async def run_single_tool(
        self, tool_name: str, tool_id: str, tool_input: Any
    ) -> tuple[bool, str, dict[str, Any], list[dict[str, Any]]]:
        """upstream `ToolExecutor.run_single_tool`과 동일 시그니처.

        반환: (is_error, text_content, metadata, content_items)
          - is_error: not result.ok
          - text_content: JSON 직렬화 문자열(execute_tool과 동일 바디)
          - metadata: {"source": "local", "tool_name": tool_name, "tool_id": tool_id}
          - content_items:
              take_screenshot 성공 시 [{"type":"image","data":<base64 raw>,"mimeType":"image/png"}]
              그 외 성공 시 [{"type":"text","text":<json>}]
              실패 시 [{"type":"error","text":<error msg>}]

        tool_input이 None이면 빈 dict로 대체(upstream 관례).
        """

    def as_upstream_tool_executor(
        self, fallback: "ToolExecutor | None" = None
    ) -> "CompositeToolExecutor":
        """upstream과 동일 인터페이스의 대체 ToolExecutor를 생성해 반환.

        Args:
            fallback: 원본 upstream ToolExecutor (MCP 기반). 로컬 툴이 아닌 이름이
                      오면 여기로 위임. None이면 로컬 툴 외 모든 호출이 unknown_tool.
        """

class CompositeToolExecutor:
    """`execute_tools(tool_calls, caller_mode) -> AsyncIterator[dict]`를 upstream과
    동일 형식으로 구현. 로컬 툴만 ToolRouter로, 나머지는 fallback.execute_tools로 위임.

    upstream의 yield 프로토콜과 100% 호환:
      {"type":"tool_call_status","tool_id","tool_name","status":"running"|"completed"|"error",
       "content","timestamp"}
      {"type":"final_tool_results","results":[<format_tool_result 결과>, ...]}

    본 래퍼는 upstream의 format_tool_result와 동일한 규칙을 재현한다(caller_mode="OpenAI"만 지원).
    Claude/Prompt 모드는 AgentProtocolError(M_05 스펙의 api_not_support_tools 경로 참조).
    """
    ...
```

### 4.6 모듈 공개 심볼 (`src/tool_router/__init__.py`)

```python
from .errors import ToolRouterError, ScreenshotInitError, ScreenshotCaptureError
from .types import ToolSpec, ToolResult, ToolErrorCode
from .router import ToolRouter
from .screenshot import ScreenshotService, SendTextCallback
from .upstream_adapter import ToolRouterAdapter, CompositeToolExecutor
```

---

## 5. ToolSpec JSON Schema (4종 전문)

OpenAI function-calling 형식. `type: "function"`, `function: {name, description, parameters}`.
모든 스키마는 `$schema: "https://json-schema.org/draft/2020-12/schema"`로 Draft 2020-12를 사용한다(Validator 버전과 일치).

### 5.1 add_event

```json
{
  "type": "function",
  "function": {
    "name": "add_event",
    "description": "일정을 달력에 등록합니다. 자연어 시간 표현은 반드시 ISO 8601 문자열(예: 2026-04-20T15:00:00+09:00)로 변환해서 전달하세요. 시간대가 없으면 Asia/Seoul로 해석됩니다.",
    "parameters": {
      "$schema": "https://json-schema.org/draft/2020-12/schema",
      "type": "object",
      "additionalProperties": false,
      "required": ["title", "start", "duration_minutes"],
      "properties": {
        "title": {
          "type": "string",
          "minLength": 1,
          "maxLength": 200,
          "description": "일정 제목."
        },
        "start": {
          "type": "string",
          "format": "date-time",
          "minLength": 10,
          "maxLength": 40,
          "description": "ISO 8601 시작 시각. 예: 2026-04-20T15:00:00+09:00."
        },
        "duration_minutes": {
          "type": "integer",
          "minimum": 1,
          "maximum": 1440,
          "description": "일정 길이(분). 1~1440."
        },
        "description": {
          "type": "string",
          "maxLength": 2000,
          "description": "선택. 일정 상세 설명."
        }
      }
    }
  }
}
```

### 5.2 get_events

```json
{
  "type": "function",
  "function": {
    "name": "get_events",
    "description": "지정한 날짜 범위의 일정을 조회합니다. start와 end는 ISO 8601 문자열이며 end는 start 이상이어야 합니다.",
    "parameters": {
      "$schema": "https://json-schema.org/draft/2020-12/schema",
      "type": "object",
      "additionalProperties": false,
      "required": ["start", "end"],
      "properties": {
        "start": {
          "type": "string",
          "format": "date-time",
          "minLength": 10,
          "maxLength": 40
        },
        "end": {
          "type": "string",
          "format": "date-time",
          "minLength": 10,
          "maxLength": 40
        }
      }
    }
  }
}
```

`start > end`는 스키마에서 막지 않고(JSON Schema로 교차 필드 비교 불가) 핸들러가 **빈 리스트 반환 + `ok=True`** 로 처리한다(E-5 테스트).

### 5.3 search_docs

```json
{
  "type": "function",
  "function": {
    "name": "search_docs",
    "description": "사내 등록 문서에서 관련 구절을 검색하고 인용 문자열과 함께 반환합니다. 관련 문서가 없으면 found=false로 표시됩니다.",
    "parameters": {
      "$schema": "https://json-schema.org/draft/2020-12/schema",
      "type": "object",
      "additionalProperties": false,
      "required": ["query"],
      "properties": {
        "query": {
          "type": "string",
          "minLength": 1,
          "maxLength": 2000,
          "description": "자연어 질의."
        },
        "top_k": {
          "type": "integer",
          "minimum": 1,
          "maximum": 20,
          "default": 8,
          "description": "상위 몇 개 청크를 반환할지."
        },
        "category": {
          "type": "string",
          "maxLength": 100,
          "description": "선택. 상위 폴더명 기반 카테고리 필터(예: 규정, 매뉴얼)."
        }
      }
    }
  }
}
```

> `default`는 JSON Schema Validator가 **자동 주입하지 않는다**. 핸들러 내부에서 `args.get("top_k", 8)`로 명시 주입한다.
>
> `query`의 `maxLength: 2000`는 사용자 요구(1MB 거부)를 만족한다. 1MB는 2000자를 훨씬 초과하므로 validator가 거절한다.

### 5.4 take_screenshot

```json
{
  "type": "function",
  "function": {
    "name": "take_screenshot",
    "description": "현재 화면을 캡처해 LLM의 비전 입력으로 전달합니다. continuous=true로 설정하면 interval_seconds 간격으로 연속 캡처를 시작합니다.",
    "parameters": {
      "$schema": "https://json-schema.org/draft/2020-12/schema",
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "continuous": {
          "type": "boolean",
          "default": false,
          "description": "true면 연속 캡처 모드 진입."
        },
        "interval_seconds": {
          "type": "number",
          "minimum": 1.0,
          "maximum": 60.0,
          "default": 5.0,
          "description": "연속 모드 캡처 주기(초). continuous=false일 때 무시됨."
        }
      }
    }
  }
}
```

`required` 없음(전부 선택). 단건 캡처 기본(`{}` 또는 `{"continuous": false}`).

---

## 6. dispatch() 상세 흐름 (의사코드)

> **구현은 Builder 몫.** 여기서는 결정 규칙을 명확히 한다.

```
async def dispatch(self, name: str, arguments: dict) -> ToolResult:

    # (1) 이름 화이트리스트
    if name not in LOCAL_TOOL_NAMES:
        return ToolResult(ok=False,
                          error=f"unknown_tool: {name}",
                          error_code="unknown_tool")

    # (2) arguments 타입
    if not isinstance(arguments, dict):
        return ToolResult(ok=False,
                          error=f"arguments must be dict, got {type(arguments).__name__}",
                          error_code="invalid_arguments")

    # (3) JSON Schema 검증 (미리 컴파일된 Validator 재사용)
    validator = self._validators[name]   # Draft202012Validator
    errors = sorted(validator.iter_errors(arguments), key=lambda e: e.absolute_path)
    if errors:
        first = errors[0]
        path = "/".join(str(p) for p in first.absolute_path) or "<root>"
        return ToolResult(ok=False,
                          error=f"invalid_arguments at {path}: {first.message}",
                          error_code="invalid_arguments")

    # (4) 핸들러 분기 및 서비스 존재 체크
    try:
        if name == "add_event":
            if self._calendar is None: return service_unavail("add_event")
            return await self._handle_add_event(arguments)

        elif name == "get_events":
            if self._calendar is None: return service_unavail("get_events")
            return await self._handle_get_events(arguments)

        elif name == "search_docs":
            if self._rag is None: return service_unavail("search_docs")
            return await self._handle_search_docs(arguments)

        elif name == "take_screenshot":
            # screenshot은 None 허용하지 않음(생성자에서 TypeError)
            return await self._handle_take_screenshot(arguments)

    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.exception("Tool handler raised: %s", name)
        return ToolResult(ok=False,
                          error=f"{type(e).__name__}: {e}",
                          error_code="handler_exception")
```

### 6.1 각 핸들러 payload 스키마

| 툴 | 성공 payload (ToolResult.payload) |
|---|---|
| add_event | `{"id": int, "title": str, "start": str(ISO), "duration_minutes": int, "description": str \| null}` |
| get_events | `{"count": int, "events": [{"id", "title", "start" ISO, "duration_minutes", "description"}, ...]}` |
| search_docs | `{"found": bool, "no_match_reason": str \| null, "hits": [{"doc_name", "page" \| null, "section" \| null, "chunk_id", "text", "score": float, "citation": str}, ...]}` |
| take_screenshot (단건) | `{"mode": "single", "image": "data:image/png;base64,..."}` |
| take_screenshot (연속 시작) | `{"mode": "continuous", "state": "started", "interval_seconds": float}` |
| take_screenshot (연속 중이었는데 continuous=true 재호출) | `{"mode": "continuous", "state": "already_running", "interval_seconds": float}` (ok=True, 이미 실행 중 정보를 전달. error_code는 None) |

### 6.2 핸들러별 세부 규칙

**`_handle_add_event`**
1. `start: str` → `datetime.fromisoformat(args["start"])`.
   - 타임존 없으면 `Asia/Seoul`(ZoneInfo)로 attach.
   - 파싱 실패 → `ValueError`로 상위가 잡아 `handler_exception`.
2. `calendar.add_event(title, start, duration_minutes, description)` 호출.
3. 반환된 `Event`를 payload로 직렬화. `datetime`은 `.isoformat()`.

**`_handle_get_events`**
1. `start`/`end` ISO 파싱(위와 동일).
2. `start > end` → `payload = {"count": 0, "events": []}`, `ok=True` 반환. (스키마로 막을 수 없는 교차 필드 케이스. LLM에게 "빈 결과"로 일관되게 응답.)
3. `calendar.get_events(start, end)` 반환 리스트를 직렬화.

**`_handle_search_docs`**
1. `top_k = args.get("top_k", 8)`.
2. `category = args.get("category")`.
3. `rag.retrieve(query, top_k, category)` 호출.
4. `RetrievalResult.hits`의 각 `SearchHit`을 (citation 문자열 포함) dict로 매핑.
   - citation 문자열은 `rag.format_citation(hit)` 호출.
5. `found=False`면 `no_match_reason="등록된 문서에서 답을 찾지 못했습니다"`를 포함.

**`_handle_take_screenshot`**
1. `continuous = args.get("continuous", False)`.
2. `interval = args.get("interval_seconds", 5.0)`.
3. `continuous=False`:
   - `data_url = await screenshot.capture_once()`.
   - `ToolResult(ok=True, payload={"mode":"single","image":data_url})`.
4. `continuous=True`:
   - `if screenshot.is_continuous_running`:
       - `ToolResult(ok=True, payload={"mode":"continuous","state":"already_running","interval_seconds":interval})`.
   - else:
       - `await screenshot.start_continuous(interval, on_frame=self._on_continuous_frame)`.
       - `ToolResult(ok=True, payload={"mode":"continuous","state":"started","interval_seconds":interval})`.

`_on_continuous_frame(data_url: str)`은 본 모듈 out-of-scope. **M_01 AppServiceContext**가 `ScreenshotService` 생성 시 별도 on_frame 콜백(프론트로 frame emit)을 주입한다. 본 모듈의 `_on_continuous_frame`은 기본 구현(log.debug)만 제공하며, `ScreenshotService.start_continuous(on_frame=...)`으로 주입 가능하도록 API 공개.

---

## 7. ScreenshotService 상세 설계

### 7.1 캡처 경로

- `mss.mss()` 인스턴스를 `__init__`에서 1회 생성, `aclose()`에서 `.close()`.
- primary monitor 좌표는 `self._sct.monitors[1]` (index 0은 모든 모니터 합). V1은 monitor 1 고정.
- 캡처 → `PIL.Image.frombytes("RGB", (w,h), sct_img.rgb)` → `BytesIO` PNG 인코딩(`compress_level=6`) → base64 → `"data:image/png;base64," + payload`.
- 해상도 축소 없음(M_05 스펙 "이미 base64 data URL로 채워져 있다는 전제"와 일치).

### 7.2 성능·메모리

- 1920×1080 풀 프레임 PNG 인코딩: 150~300 ms (i7-12700, 단일 스레드). R-06 스파이크 기준.
- 메모리: 프레임당 약 6 MB(압축 전 RGB 3바이트) + PNG 출력 0.5~2 MB. 참조 즉시 해제.
- 연속 모드 중 프레임 drop 방지 로직 없음 — `interval`이 캡처+인코딩 시간보다 짧으면 다음 틱이 뒤로 밀림(await 순차 실행).

### 7.3 연속 모드 수명주기

```
start_continuous(interval, on_frame):
    if self._task is not None and not self._task.done():
        raise ScreenshotCaptureError("continuous_already_running")

    if self._send_text:
        await self._send_text({"type":"privacy_warning", "text":"...", "interval_seconds": interval})

    self._stop_event = asyncio.Event()
    self._task = asyncio.create_task(self._loop(interval, on_frame))

_loop(interval, on_frame):
    try:
        while not self._stop_event.is_set():
            try:
                data_url = await self.capture_once()
                if on_frame:
                    await on_frame(data_url)
            except ScreenshotInitError:
                logger.error("Continuous capture aborted: display lost")
                break
            except ScreenshotCaptureError as e:
                logger.warning("Capture tick failed: %s", e)
            # cancellable wait
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval)
            except asyncio.TimeoutError:
                continue
    finally:
        logger.info("Continuous capture loop exited")

stop_continuous():
    if self._task is None: return
    self._stop_event.set()
    try:
        await asyncio.wait_for(self._task, timeout=5.0)
    except asyncio.TimeoutError:
        self._task.cancel()
        with contextlib.suppress(BaseException):
            await self._task
    self._task = None
    self._stop_event = None
```

### 7.4 privacy_warning 메시지 스키마

```json
{
  "type": "privacy_warning",
  "text": "연속 화면 공유를 시작합니다. 개인정보가 포함될 수 있으니 필요 시 '화면 공유 중지'라고 말씀해 주세요.",
  "interval_seconds": 5.0
}
```

M_01(WebSocketHandler)은 이 메시지 타입을 프론트로 그대로 passthrough한다(M_01 스펙에 메시지 타입 `privacy_warning` 등록 **변경 요청**).

---

## 8. ToolRouterAdapter 설계 (upstream 경계)

### 8.1 두 개의 경로가 필요한 이유

upstream `BasicMemoryAgent._openai_tool_interaction_loop`는 **내부에서 `self._tool_executor.execute_tools(tool_calls, "OpenAI")`를 호출**한다(basic_memory_agent.py L376/L514/L555 관찰). 즉 LLM이 방출한 `tool_calls` 전체를 한 번에 넘기고, upstream이 이를 iterate한다.

따라서 본 모듈은 두 레이어 어댑터를 제공한다:

1. **`ToolRouterAdapter.execute_tool(name, arguments) -> str`**
   — 사용자 요구 시그니처. 테스트와 프로젝트 내부 코드가 직접 호출할 수 있는 최소 표면.
2. **`CompositeToolExecutor` (`as_upstream_tool_executor()` 반환)**
   — upstream `ToolExecutor`와 동일한 `execute_tools(tool_calls, caller_mode) -> AsyncIterator[dict]` 시그니처를 구현. upstream 루프에 **drop-in 대체**로 주입 가능.

### 8.2 CompositeToolExecutor 디스패치 규칙

```
for call in tool_calls:
    name, tool_id, tool_input, is_error, result_content, parse_error
        = upstream_parse_tool_call(call)   # upstream.ToolExecutor.parse_tool_call 재사용

    if parse_error:
        # upstream과 완전히 동일한 parse_error 상태 업데이트 yield
        yield {"type":"tool_call_status", ..., "status":"error", ...}
        tool_results_for_llm.append(format_tool_result("OpenAI", ...))
        continue

    if name in ToolRouter.LOCAL_TOOL_NAMES:
        # 로컬 툴 처리
        yield running_status(tool_id, name, tool_input)
        result: ToolResult = await self._router.dispatch(name, tool_input or {})

        if name == "take_screenshot" and result.ok and result.payload.get("mode") == "single":
            # 이미지 스트리밍: upstream과 동일하게 content_items에 image item 포함
            yield completed_status_with_image(tool_id, name, result, num_images=1)
        else:
            yield completed_or_error_status(tool_id, name, result)

        tool_results_for_llm.append(
            openai_format(tool_id, json.dumps(payload_or_error))
        )

    else:
        # MCP 툴: fallback 위임 (async for로 passthrough)
        async for update in self._fallback.execute_tools([call], "OpenAI"):
            if update["type"] == "final_tool_results":
                tool_results_for_llm.extend(update["results"])
            else:
                yield update

yield {"type":"final_tool_results","results": tool_results_for_llm}
```

> **caller_mode 제한**: `"OpenAI"`만 지원. `"Claude"`/`"Prompt"`가 오면 `AgentProtocolError`를 raise(M_05 `api_not_support_tools` 경로와 일치).

### 8.3 JSON 직렬화 규칙

- `json.dumps(..., ensure_ascii=False, separators=(",", ":"))` 고정(공백 최소, 한글 유지).
- `datetime` → `.isoformat()` (핸들러에서 이미 처리).
- take_screenshot 단건 성공의 `image` 필드는 매우 길다(수십 KB ~ 수 MB). `execute_tool` 반환 문자열 크기를 로그에 찍을 때는 **길이만** 기록하고 내용은 생략(로그 PII 필터와 별개 규칙).

---

## 9. 에러 정책 표

| 상황 | 반응 | error_code | 예외 raise? | 로그 레벨 |
|---|---|---|---|---|
| `ToolRouter(screenshot=None)` | 즉시 실패 | — | `TypeError` | ERROR |
| `dispatch(name="rm_rf_root", ...)` | `unknown_tool` | `unknown_tool` | no | INFO |
| `dispatch(name, arguments=None)` | `invalid_arguments: not dict` | `invalid_arguments` | no | WARNING |
| `add_event({duration_minutes: -1})` | `invalid_arguments at duration_minutes: -1 is less than minimum 1` | `invalid_arguments` | no | INFO |
| `add_event({title: ""})` | `invalid_arguments at title` | `invalid_arguments` | no | INFO |
| `add_event({...})` but `calendar=None` | `service_unavailable: add_event` | `service_unavailable` | no | WARNING |
| `add_event({start:"내일 3시"})` | ISO 파싱 실패 → `ValueError` → `handler_exception` | `handler_exception` | no | ERROR |
| `add_event` SQLite write IOError | `handler_exception` | `handler_exception` | no | ERROR |
| `get_events({start:"2026-05-01", end:"2026-04-01"})` | `ok=True, payload={"count":0,"events":[]}` | — | no | INFO |
| `search_docs` top_k 미지정 | 기본값 8 적용, 정상 실행 | — | no | — |
| `search_docs` query 1MB | `invalid_arguments at query: too long` | `invalid_arguments` | no | INFO |
| `search_docs` but `rag=None` | `service_unavailable: search_docs` | `service_unavailable` | no | WARNING |
| `search_docs` LanceDB I/O 실패 | `handler_exception` | `handler_exception` | no | ERROR |
| `search_docs` 관련 문서 없음 | `ok=True, payload={"found":false,"hits":[], "no_match_reason":"..."}` | — | no | INFO |
| `take_screenshot` non-Windows | **생성자에서** `ScreenshotInitError` → M_01 기동 실패(ToolRouter 생성 단계 전파) | — | yes (init) | ERROR |
| `take_screenshot` 연속 모드 이미 실행 중에 `continuous=True` 재호출 | `ok=True, payload.state="already_running"` | — | no | INFO |
| `take_screenshot` interval_seconds=0.1 | `invalid_arguments at interval_seconds` | `invalid_arguments` | no | INFO |
| `take_screenshot` 런타임 캡처 실패 | `ok=False, error_code="screenshot_failed"` | `screenshot_failed` | no | ERROR |
| `dispatch` 중 `asyncio.CancelledError` | 상위 재전파. 연속 모드 시작 직후라면 `stop_continuous` try/finally. | — | yes | DEBUG |
| `execute_tool` 내부 예상 밖 예외 | `ok=False, error="adapter_exception: ..."`, JSON 반환 | `handler_exception` | no | ERROR |
| `CompositeToolExecutor` caller_mode != "OpenAI" | `AgentProtocolError` | — | yes | ERROR |

### 원칙

- **`ToolRouter`/`ToolRouterAdapter`의 공개 async 메서드는 예외를 raise하지 않는다**(CancelledError 제외). 모든 런타임 실패는 ToolResult 또는 JSON으로 변환.
- **초기화 실패는 부팅을 중단**한다(`ScreenshotInitError`, `TypeError`).
- **서비스 None은 초기화 실패가 아니다**. 해당 툴만 런타임에 `service_unavailable`. 부분 기능 동작 허용(개발 중 LanceDB 아직 미구성 등).

---

## 10. 성능·메모리 제약

| 항목 | 값 | 근거 |
|---|---|---|
| 본 모듈 RSS 기여 | ≤ 30 MB | `mss` + `Pillow` + `jsonschema` + 파이썬 오버헤드 |
| `dispatch` 자체 오버헤드 (스키마 검증 + 분기) | ≤ 5 ms (p99) | Draft2020-12 Validator 사전 컴파일 재사용 |
| `take_screenshot` 단건 지연 (1920×1080) | ≤ 300 ms (p95) | `mss` 캡처 + PIL PNG 인코딩(compress_level=6) |
| 연속 모드 최소 interval | 1.0 s | `interval_min` 기본값. 더 짧으면 캡처 backlog |
| 연속 모드 최대 interval | 60.0 s | `interval_max` 기본값 |
| base64 data URL 최대 크기 | ≤ 8 MB | 1920×1080 풀프레임 PNG 상한. LLM 컨텍스트 부담 방지를 위해 초과 시 로그 WARNING |
| `search_docs` → RAG 왕복(ToolRouter 경계) 오버헤드 | ≤ 10 ms(dispatch 내 직렬화 시간만) | 실제 검색 지연은 M_07 RagService 소관 |
| 동시 `dispatch` 호출 | 다중 허용 | `ToolRouter`는 상태 없음. 단, `ScreenshotService.start_continuous`는 단일 인스턴스당 1개만. |

---

## 11. 테스트 케이스

경로: `tests/tool_router/`. pytest + pytest-asyncio. `CalendarService`/`RagService`/mss는 전부 mock.

### 11.1 정상 케이스 (≥ 5)

**N-1. `add_event` 성공**
- mock `CalendarService.add_event`가 `Event(id=42, title="회의", start=datetime(2026,4,20,15,0,tzinfo=KST), duration_minutes=60, description=None, created_at=now)` 반환.
- 입력: `dispatch("add_event", {"title":"회의", "start":"2026-04-20T15:00:00+09:00", "duration_minutes":60})`.
- 검증: `ok=True`, `payload.id==42`, `payload.start=="2026-04-20T15:00:00+09:00"`, `payload.duration_minutes==60`. mock이 1회 호출.

**N-2. `get_events` 성공**
- mock이 Event 2건 반환.
- 입력: `dispatch("get_events", {"start":"2026-04-20T00:00:00+09:00","end":"2026-04-21T00:00:00+09:00"})`.
- 검증: `ok=True`, `payload.count==2`, `payload.events`가 길이 2 리스트.

**N-3. `search_docs` 성공 (인용 포함)**
- mock `RagService.retrieve`가 `RetrievalResult(hits=[SearchHit(chunk, score=0.72)], found=True, no_match_reason=None)` 반환.
- mock `RagService.format_citation` 반환값 `"`예산지침.pdf` 12페이지, '예산 승인 절차' 섹션"`.
- 입력: `dispatch("search_docs", {"query":"예산 승인 절차"})`.
- 검증: `ok=True`, `payload.found==True`, `payload.hits[0].citation`가 mock 문자열과 일치, `payload.hits[0].score==0.72`.

**N-4. `take_screenshot` 단건**
- mock `ScreenshotService.capture_once` 반환 `"data:image/png;base64,ABC..."`.
- 입력: `dispatch("take_screenshot", {})`.
- 검증: `ok=True`, `payload.mode=="single"`, `payload.image.startswith("data:image/png;base64,")`.

**N-5. `tool_specs()` 반환 4개 + 스키마 유효성**
- 입력: `router.tool_specs()`.
- 검증:
  1. 리스트 길이 4, 이름 집합 == `{"add_event","get_events","search_docs","take_screenshot"}`.
  2. 각 항목에 `"function"` 키 존재.
  3. 각 `function.parameters`가 `Draft202012Validator.check_schema`로 유효.
  4. 리스트는 호출마다 새 인스턴스(`router.tool_specs() is not router.tool_specs()`).

**N-6. `ToolRouterAdapter.execute_tool` JSON 포맷**
- 같은 입력으로 `adapter.execute_tool("get_events", {...})`.
- 검증: 반환 JSON 파싱 가능. `obj["ok"]==True`, `obj["payload"]["count"]`가 mock 결과와 일치.

**N-7. `take_screenshot` 연속 모드 시작**
- mock `ScreenshotService.is_continuous_running=False → True 전환`, `start_continuous`가 `send_text` 호출 검증 가능한 stub.
- 입력: `dispatch("take_screenshot", {"continuous": True, "interval_seconds": 5.0})`.
- 검증: `ok=True`, `payload.mode=="continuous"`, `payload.state=="started"`, mock send_text가 `privacy_warning` 이벤트로 1회 호출.

### 11.2 엣지 케이스 (≥ 5)

**E-1. `CalendarService=None` — add_event**
- router 생성 시 `calendar=None`, rag=Mock, screenshot=Mock.
- 입력: `dispatch("add_event", {valid args})`.
- 검증: `ok=False`, `error_code=="service_unavailable"`, `error.startswith("service_unavailable")`.

**E-2. `RagService=None` — search_docs**
- 동일 패턴. `ok=False`, `error_code=="service_unavailable"`.

**E-3. `search_docs` top_k 기본값 적용**
- mock RagService.retrieve를 `MagicMock(return_value=RetrievalResult(...))`로 두고 호출 인자를 캡처.
- 입력: `dispatch("search_docs", {"query":"q"})` (top_k 미지정).
- 검증: `rag.retrieve` 호출 인자에 `top_k=8`이 포함(명시 전달).

**E-4. `take_screenshot` continuous=True → privacy_warning 발행**
- N-7와 별도로, `send_text` 콜백 호출 횟수 및 페이로드 구조 정밀 검증. `type`, `text`, `interval_seconds` 3필드 모두 존재.

**E-5. `get_events` 날짜 역전 (start > end)**
- 입력: `dispatch("get_events", {"start":"2026-05-01T00:00:00+09:00","end":"2026-04-01T00:00:00+09:00"})`.
- 검증: `ok=True`, `payload.count==0`, `payload.events==[]`. mock CalendarService.get_events는 호출되지 **않는다**(핸들러 조기 반환).

**E-6. `add_event` description 생략**
- 입력: `{"title":"x","start":"2026-04-20T15:00:00+09:00","duration_minutes":30}`.
- 검증: `ok=True`. CalendarService.add_event 호출 인자 `description=None`.

**E-7. `search_docs` found=False (no match)**
- mock retrieve가 `RetrievalResult(hits=[], found=False, no_match_reason="등록된 문서에서 답을 찾지 못했습니다")`.
- 검증: `ok=True`, `payload.found==False`, `payload.no_match_reason==mock 문자열`, `payload.hits==[]`.

**E-8. `take_screenshot` 연속 모드 중복 시작**
- mock `is_continuous_running=True`.
- 입력: `dispatch("take_screenshot", {"continuous": True, "interval_seconds": 10.0})`.
- 검증: `ok=True`, `payload.state=="already_running"`. `start_continuous` mock은 호출되지 않음.

### 11.3 적대적 케이스 (≥ 3)

**A-1. `dispatch(name="rm_rf_root", ...)`**
- 입력: `dispatch("rm_rf_root", {"path":"/"})`.
- 검증: `ok=False`, `error_code=="unknown_tool"`, `error=="unknown_tool: rm_rf_root"`. 어떤 서비스도 호출되지 않음.

**A-2. `add_event` duration_minutes=-9999**
- 입력: `dispatch("add_event", {"title":"x","start":"2026-04-20T15:00:00+09:00","duration_minutes":-9999})`.
- 검증: `ok=False`, `error_code=="invalid_arguments"`, `error.contains("duration_minutes")`. CalendarService.add_event는 호출되지 않음.

**A-3. `search_docs` query 1MB 문자열**
- 입력: `dispatch("search_docs", {"query":"x"*1_048_576})`.
- 검증: `ok=False`, `error_code=="invalid_arguments"`, `error.contains("query")`. RagService.retrieve 호출 0회.

**A-4. `add_event` title이 정확히 200자 경계 / 201자**
- 200자 → 성공(ok=True). 201자 → invalid_arguments.
- boundary 정확성 확인.

**A-5. `dispatch` 핸들러 내부 무작위 예외**
- mock CalendarService.add_event가 `sqlite3.OperationalError("disk full")` raise.
- 검증: `ok=False`, `error_code=="handler_exception"`, `error.startswith("OperationalError:")`. 예외는 상위로 전파되지 않음. logger.exception 1회 호출(caplog).

**A-6. `take_screenshot` continuous=True, interval_seconds=0.5**
- 스키마 `minimum: 1.0` 위반.
- 검증: `ok=False`, `error_code=="invalid_arguments"`. `start_continuous` 호출 0회, `send_text` 호출 0회.

**A-7. `dispatch` 중 CancelledError 전파**
- handler가 `await asyncio.sleep(10)`에서 cancel되는 시나리오.
- 검증: `CancelledError`가 상위로 re-raise. `ScreenshotService.stop_continuous`가 (연속 모드 시작 직후 케이스에서) try/finally로 호출되어 누수 없음.

**A-8. `execute_tool` JSON 직렬화 내부 실패 (비정상 payload 객체)**
- 핸들러가 non-serializable 객체를 payload에 주입한 극단 케이스(예: datetime 객체를 isoformat 변환 누락).
- 검증: `execute_tool` 반환 JSON이 `{"ok":false,"error":"adapter_exception: ...","error_code":"handler_exception"}`. 예외 raise 없음.

---

## 12. Definition of Done

### 공통 (CLAUDE.md "산출물 체크리스트")

- [ ] 본 스펙 `specs/M_05b_ToolRouter_SPEC.md` 사용자 승인.
- [ ] `src/tool_router/` 구현 (`__init__.py`, `errors.py`, `types.py`, `router.py`, `screenshot.py`, `upstream_adapter.py`, `schemas/`(JSON Schema 상수 모듈)).
- [ ] `tests/tool_router/` 테스트: 본 스펙 N/E/A 전체 (정상 ≥5, 엣지 ≥5, 적대적 ≥3).
- [ ] `ruff format .`, `ruff check .`, `mypy src/tool_router/`, `pytest tests/tool_router/ -v` 모두 통과.
- [ ] `reviews/M_05b_ToolRouter_REVIEW.md` Critic PASS.
- [ ] `docs/MODULES.md`의 M_05b 상태가 ✅ DONE으로 갱신.

### M_05b 고유

- [ ] `ToolRouter.dispatch`는 **예외를 raise하지 않음**(CancelledError 제외). monkeypatch로 핸들러가 예외를 던지게 하고 ToolResult로 변환되는지 확인.
- [ ] 4개 툴 스키마가 `Draft202012Validator.check_schema`로 검증 통과.
- [ ] `tool_specs()`는 호출마다 새 리스트(얕은 복사)를 반환.
- [ ] `ScreenshotService`가 non-Windows 환경에서 `ScreenshotInitError`를 던짐 (단위 테스트는 `platform.system`을 monkeypatch).
- [ ] 연속 모드 시작 시 `send_text`로 `privacy_warning` 이벤트 1회 발행.
- [ ] 연속 모드 `stop_continuous`가 대기 태스크를 정상 종료 (누수 없음을 `pytest -W error::RuntimeWarning`으로 확인).
- [ ] `ToolRouterAdapter.execute_tool` 반환이 `ensure_ascii=False` UTF-8 JSON.
- [ ] `CompositeToolExecutor.execute_tools`가 upstream의 yield 프로토콜과 호환됨을 테스트(더미 upstream 시퀀스로 비교).
- [ ] `CompositeToolExecutor`가 `caller_mode != "OpenAI"`에서 `AgentProtocolError`를 raise.
- [ ] 본 모듈이 **upstream `ToolManager.tools` 사전을 수정하지 않음**을 테스트로 확인(로컬 툴이 MCP ToolManager에 등록되지 않는 계약).
- [ ] `upstream/Open-LLM-VTuber/src/open_llm_vtuber/**` 파일이 수정되지 않음 (git diff 확인).
- [ ] M_01 변경 요청 등록: WebSocket 메시지 타입 `privacy_warning` 패스스루 허용, `AppServiceContext`에서 `tool_router`/`tool_router_adapter` 조립.
- [ ] M_05 변경 요청 등록: `build_chat_agent(..., extra_tool_specs: list[ToolSpec] | None = None)` 파라미터 추가하여 `tool_specs()` 병합 배관. (M_05 스펙 §배선과 정합)

---

## 13. 의존성

### 13.1 Python 패키지

| 패키지 | 버전 핀 | 용도 | 상태 |
|---|---|---|---|
| `jsonschema` | `>=4.21,<5` | Draft 2020-12 Validator | **신규** — pyproject + bundle_deps.sh 추가 |
| `mss` | `>=9.0,<10` | Windows 화면 캡처 | **신규** — pyproject + bundle_deps.sh 추가 (Windows 휠) |
| `Pillow` | `>=10.2,<12` | mss RGB → PNG 인코딩 | upstream이 이미 요구 가능성 높음. pyproject 확인 후 추가 |
| `pytest` / `pytest-asyncio` | 기존 | 테스트 | 기존 |

### 13.2 런타임 전제

- Python 3.12+.
- Windows 10/11 (다른 OS에서는 `ScreenshotService` 초기화 실패 → **테스트 환경은 mock**).
- 이미 빌드된 CalendarService(M_09), RagService(M_07)는 M_05b 초기화 시점에 **선택적**. 없으면 부분 기능으로 기동.

### 13.3 모듈 의존

| 대상 | 관계 |
|---|---|
| M_05 LLMAgent | `tool_specs()`를 병합 소비. `CompositeToolExecutor`를 주입받아 `_openai_tool_interaction_loop`에 전달 |
| M_06 DocumentIngest | 간접(문서 등록 후 M_07이 검색 가능) |
| M_07 VectorSearch / RagService | `search_docs` 핸들러가 직접 호출 |
| M_09 CalendarService | `add_event`/`get_events` 핸들러가 직접 호출 |
| upstream `ToolManager` | 타입만 참조(본 모듈은 등록하지 않음). `CompositeToolExecutor`가 upstream `format_tool_result`·`parse_tool_call` 호출을 위해 사용 |
| upstream `ToolExecutor` | `CompositeToolExecutor`의 fallback으로 보유 (MCP 툴용) |
| M_01 AppCore | ToolRouter 조립 지점. WebSocket `privacy_warning` 메시지 패스스루 |

---

## 14. 디렉토리 구조

```
src/tool_router/
├── __init__.py              # 공개 심볼
├── errors.py                # ToolRouterError, ScreenshotInitError, ScreenshotCaptureError
├── types.py                 # ToolSpec, ToolResult, ToolErrorCode
├── schemas.py               # 4개 JSON Schema dict 상수 (add_event, get_events, search_docs, take_screenshot)
├── router.py                # ToolRouter + 4개 _handle_* 내부 메서드
├── screenshot.py            # ScreenshotService (mss + Pillow + continuous loop)
└── upstream_adapter.py      # ToolRouterAdapter, CompositeToolExecutor

tests/tool_router/
├── __init__.py
├── conftest.py              # mock CalendarService/RagService, fake mss 모듈, FakeScreenshotService
├── fakes.py                 # FakeCalendarService, FakeRagService
├── test_schemas.py          # N-5 (tool_specs 구조·유효성)
├── test_dispatch_normal.py  # N-1, N-2, N-3, N-4, N-7
├── test_dispatch_edge.py    # E-1 ~ E-8
├── test_dispatch_adversarial.py  # A-1 ~ A-8
├── test_screenshot.py       # ScreenshotService 단위(non-Windows error, continuous lifecycle)
├── test_adapter.py          # ToolRouterAdapter.execute_tool JSON 포맷, N-6
└── test_composite_executor.py  # CompositeToolExecutor와 upstream ToolExecutor 동작 동등성
```

---

## 15. 스펙 외 사항 (명시적 제외, 재확인)

본 모듈의 책임이 **아닌** 항목:

1. **tool 이름 문자열의 한국어 설명(description) 저작 및 튜닝** — 본 스펙에 최초 버전을 고정한다. 이후 프롬프트팀이 별도 CR로 개정.
2. **연속 스크린샷 프레임의 프론트 전달 경로** — M_01 WebSocketHandler가 `_on_continuous_frame` 콜백을 주입해 `continuous-capture-frame` 이벤트로 송신(M_01 CR).
3. **take_screenshot 결과 이미지의 BatchInput.images 주입** — ConversationOrchestrator(M_01)가 다음 LLM 턴의 `BatchInput` 구성 시 수행. 본 모듈은 data URL만 반환.
4. **"화면 공유 중지" 음성 명령 인식** — M_02 ASR + M_05 LLM이 담당. 본 모듈은 `stop_continuous()` API만 제공.
5. **MCP 툴의 등록·실행** — upstream `ToolManager`/`MCPClient` 소관. `CompositeToolExecutor`는 MCP 툴을 fallback에 단순 위임한다.
6. **tool arguments JSON 문자열 파싱** — upstream `ToolExecutor.parse_tool_call`이 이미 수행해 `dict`로 본 모듈에 도달.
7. **ToolResult payload의 LLM 프롬프트 포맷 설계** — LLM이 읽을 JSON 문자열 구조는 §8.3에 고정. 변경 시 M_05 스펙과 동기화 CR.
8. **Whisper·TTS·Avatar·Proactive 어떤 것도 본 모듈에서 건드리지 않는다**.
