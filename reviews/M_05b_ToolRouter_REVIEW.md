# M_05b ToolRouter — Critic 검수 결과

## 판정: REJECT (1차)

BLOCKER 2건, MAJOR 4건, MINOR 8건.

---

## BLOCKER (수정 필수)

### BLOCKER-1: `CompositeToolExecutor.execute_tools`가 async generator가 아닌 coroutine function
- **파일**: `src/tool_router/upstream_adapter.py:140-150`
- upstream `execute_tools`는 async generator function. 호출 측은 `async for update in executor.execute_tools(...)` (await 없음). 구현체는 `async def` + `return self._execute_tools_impl(...)` → coroutine function → upstream 루프에 주입 시 `TypeError: 'coroutine' object is not an async iterator`.
- 테스트(`test_composite_executor.py`)가 `gen = await composite.execute_tools(...)`로 먼저 await해서 결함을 은폐함.
- **수정**: `execute_tools`를 진짜 async generator(`async def ... yield`)로 변경. 테스트도 `async for update in composite.execute_tools(...)` 패턴으로 수정.

### BLOCKER-2: 연속 모드 CancelledError 누수 방지 로직이 dead code
- **파일**: `src/tool_router/router.py:307-314`
- `started = False` → CancelledError 발생 → `if started:` → 항상 False → task 누수. 스펙 §4.3 "try/finally로 stop_continuous 호출" 위반.
- A-7 테스트도 연속 모드 시나리오를 검증하지 않음.
- **수정**: try/finally 구조로 교체. `ScreenshotService.start_continuous` 내부에도 create_task 이후 CancelledError 정리 블록 추가. A-7 테스트에 연속 모드 시나리오 추가.

---

## MAJOR

### MAJOR-1: `capture_once`가 동기 blocking I/O를 이벤트 루프에서 직접 실행
- **파일**: `src/tool_router/screenshot.py:67-98`
- `mss.grab`, PIL 인코딩, base64가 모두 blocking. 최대 300ms 이벤트 루프 차단.
- **수정**: `run_in_executor(None, self._capture_sync)`로 분리.

### MAJOR-2: `AgentProtocolError` import가 `src.agent` 전체를 eager-load
- **파일**: `src/tool_router/upstream_adapter.py:11`
- `from src.agent.errors import AgentProtocolError` → `src/agent/__init__.py` 전체 실행 → prompts 등 미설치 패키지로 ImportError 가능.
- **수정**: `AgentProtocolError`를 `src/tool_router/errors.py`에서 재-export하거나 `src/agent/errors.py` 단독 파일 직접 import.

### MAJOR-3: `_now_iso()`가 malformed ISO 8601 생성
- **파일**: `src/tool_router/upstream_adapter.py:24-25`
- `.isoformat() + "Z"` → `...+00:00Z` (타임존 중복).
- **수정**: `datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")` 또는 `+ "Z"` 제거.

### MAJOR-4: `interval_seconds` 미지정 + `continuous=True` 기본값 경로 미테스트
- `args.get("interval_seconds", 5.0)` 로직은 있으나 이 경로에 대한 테스트가 없음.
- **수정**: N-7-bis 테스트 추가 (interval_seconds 미지정 → 기본 5.0 사용 확인).

---

## MINOR

- MINOR-1: `parse_tool_call` 자체 구현 (스펙은 upstream 재사용 권고)
- MINOR-2: `capture_once`의 `ImportError`가 `ScreenshotCaptureError`로 변환됨 (InitError여야 함)
- MINOR-3: A-5 테스트에서 `logger.exception` 호출 횟수 검증 없음
- MINOR-4: `test_screenshot.py`의 `sys.modules` 오염 — `monkeypatch.setitem`으로 복원 필요
- MINOR-5: `tool_specs()` 얕은 사본 — dict 수정 방어 없음
- MINOR-6: Validator 재사용 검증 테스트 없음
- MINOR-7: privacy_warning 문자열 두 곳 하드코딩
- MINOR-8: `getattr(event, "description", None)` 타입 안전성 미흡

---

## 검증 실행 결과

- `ruff format --check`: PASS
- `ruff check`: PASS
- `mypy src/tool_router/`: PASS (0 errors)
- `pytest tests/tool_router/ -v`: 46 passed (단, BLOCKER-1/2 은폐로 품질 보증 불가)
- 외부 네트워크 호출: 없음 ✅
- upstream 파일 수정: 없음 ✅
- pyproject.toml 의존성 추가: ✅

---

## 2차 Critic 검수 결과

### 판정: REJECT

1차 BLOCKER 2건은 정상 수정되었으나, **1차 MAJOR-2가 그대로 방치**되어 있고, 수정 과정에서 **ruff format 위반**이 새로 들어갔다. 품질 게이트(CLAUDE.md "Validator는 구현 완료 판정 전에 ruff/mypy/pytest 모두 실행한다. 하나라도 실패하면 FAIL") 직접 위반.

---

### 1차 BLOCKER 수정 검증

- **BLOCKER-1** (execute_tools async generator): **✅ 수정 확인**
  - `inspect.isasyncgenfunction(CompositeToolExecutor.execute_tools) == True` (스크립트로 직접 검증)
  - `src/tool_router/upstream_adapter.py:140-151`에서 `async def ... yield update` 구조 확인
  - 모든 테스트(test_composite_executor.py L47/69/91/105/129/154)가 `async for item in composite.execute_tools(...)` 패턴 사용, `await composite.execute_tools`는 0건 (Grep 확인)
  - `test_execute_tools_is_async_generator_function` 검증 테스트 추가됨

- **BLOCKER-2** (연속 모드 CancelledError 누수 방지): **✅ 수정 확인**
  - `src/tool_router/router.py:307-314`에서 `try: await start_continuous(...) except asyncio.CancelledError: if is_continuous_running: await stop_continuous(); raise` 패턴 구현
  - A-7b 테스트(`test_a7b_continuous_cancelled_error_no_task_leak`)가 `CancelAfterStartScreenshot`으로 실제 시나리오 검증: `stop_continuous_calls >= 1`, `is_continuous_running == False` 복원 확인 (pytest PASS)

---

### 1차 MAJOR 수정 검증

- **MAJOR-1** (capture_once run_in_executor): **✅ 수정 확인**
  - `src/tool_router/screenshot.py:116-118`에서 `loop.run_in_executor(None, self._capture_sync)` 사용
  - `_capture_sync`가 동기 블로킹 처리(mss.grab, PIL 인코딩, base64) 담당
  - 미세 지적(MINOR-9): `asyncio.get_event_loop()`은 Python 3.12+에서 active loop 외부에서 호출 시 DeprecationWarning. 현재 `capture_once`는 항상 async context에서 호출되므로 실제 문제는 없으나 `asyncio.get_running_loop()`이 더 명확

- **MAJOR-2** (AgentProtocolError heavy import 회피): **❌ 수정되지 않음 — REJECT 사유**
  - `src/tool_router/upstream_adapter.py:11`은 여전히 `from agent.errors import AgentProtocolError`
  - 직접 실행 증거: venv의 `open_llm_vtuber`를 임시로 숨겼을 때 `import tool_router.upstream_adapter` 단독 실행이 다음과 같이 실패
    ```
    File "/mnt/c/projects/ai-assistant/src/agent/__init__.py", line 4, in <module>
        from .builder import build_chat_agent
    File "/mnt/c/projects/ai-assistant/src/agent/builder.py", line 6, in <module>
        from open_llm_vtuber.mcpp.tool_executor import ToolExecutor
    ModuleNotFoundError: No module named 'open_llm_vtuber'
    ```
  - 즉 tool_router를 import만 해도 `src/agent/__init__.py` → `builder.py` → upstream Open-LLM-VTuber 전체 트리가 강제 로드됨
  - 스펙 §13 "upstream ToolManager는 타입만 참조(본 모듈은 등록하지 않음)" 및 스펙 §9 "서비스 None은 초기화 실패가 아니다" 경계 설계 원칙 위반
  - 1차 리뷰가 명시적으로 제안한 수정책("`AgentProtocolError`를 `src/tool_router/errors.py`에서 재-export하거나 `src/agent/errors.py` 단독 파일 직접 import")이 전혀 적용되지 않음. Builder가 1차 Critic의 MAJOR 지적사항을 방치 → 재지적

- **MAJOR-3** (malformed ISO 8601 방지): **✅ 수정 확인**
  - `src/tool_router/upstream_adapter.py:25`: `datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")`
  - 직접 실행: `2026-04-18T16:10:35.856366Z` (`+00:00Z` 중복 없음)

- **MAJOR-4** (interval_seconds 미지정 기본값 테스트): **✅ 추가 확인**
  - `test_dispatch_normal.py::test_n8_take_screenshot_continuous_default_interval` 추가
  - `{"continuous": True}` (interval_seconds 미지정) → `interval_seconds=5.0`으로 start_continuous 호출, `payload.interval_seconds == 5.0` 검증 (PASS)

---

### 신규 BLOCKER / MAJOR

- **[MAJOR-NEW]** ruff format 위반 — DoD 품질 게이트 실패
  - 파일: `tests/tool_router/test_dispatch_adversarial.py:175-178`
  - BLOCKER-2 수정(A-7b 테스트 추가) 과정에서 inner class 정의 뒤에 extra blank line이 남음. ruff format --diff:
    ```
    @@ -175,7 +175,6 @@
                 # task가 생성된 후 CancelledError 발생 시뮬레이션
                 raise asyncio.CancelledError()

    -
         fake_ss = CancelAfterStartScreenshot(continuous_running=False)
    ```
  - CLAUDE.md "Validator는 구현 완료 판정 전에 위 네 가지를 모두 실행한다. 하나라도 실패하면 FAIL" 직접 위반
  - 수정: `ruff format .` 실행

- **[MINOR-NEW]** `asyncio.get_event_loop()` 사용 (screenshot.py:116, router.py:169/206/235)
  - Python 3.12+에서 active running loop 외부 호출 시 DeprecationWarning. 현재는 async context 내부에서만 호출되므로 동작하지만, 명확성을 위해 `asyncio.get_running_loop()` 권장.

- **[MINOR-NEW]** `CompositeToolExecutor._parse_tool_call`의 dict 경로(upstream_adapter.py:277)에서 `tool_id = call.get("id", "")`가 빈 문자열일 때 `parse_error=True`로 분기하나, 이후 `parse_error_{_now_iso()}` fallback id 생성 로직(L173)은 parse_error가 아닌 케이스에서 `tool_id=""`를 가진 local tool에는 적용되지 않는다. dict 경로에서 tool_id가 없을 때 `parse_error=True`가 보장되므로 실질적 문제는 없으나, 적대적 LLM이 `tool_id=""`인 tool_call dict를 방출해도 parse_error로 반려되는지 명시적 테스트 없음 (A-case 공백).

---

### 검증 실행 결과

- `ruff format --check src/tool_router tests/tool_router`: **FAIL** (1 file would be reformatted: tests/tool_router/test_dispatch_adversarial.py — extra blank line L175-178)
- `ruff check src/tool_router tests/tool_router`: PASS (All checks passed!)
- `mypy src/tool_router/`: PASS (Success: no issues found in 7 source files)
- `pytest tests/tool_router/ -v`: **49 passed, 0 failed** (6 pydantic warnings from upstream, 무관)
- 외부 네트워크 호출: 없음 (`src/tool_router`에 requests/httpx/aiohttp/urllib/http.client/fetch 0건 — Grep 확인)
- `git status upstream/`: clean (upstream 파일 수정 없음)

---

### 스펙 vs 구현 매핑 재검증 (주요 항목)

| 스펙 항목 | 구현 위치 | 상태 |
|---|---|---|
| `ToolRouter(screenshot=None)` → TypeError | router.py:59-61 | ✅ |
| `dispatch` 미지 툴 → unknown_tool | router.py:90-96 | ✅ |
| `dispatch` 비-dict args → invalid_arguments | router.py:99-108 | ✅ |
| JSON Schema 검증 사전 컴파일 + 재사용 | router.py:68-72 (`__init__`) | ✅ |
| CancelledError 재전파 + continuous 정리 | router.py:309-314, 144-145 | ✅ (A-7b PASS) |
| 모든 기타 예외 → ToolResult(ok=False) | router.py:146-152 | ✅ |
| `tool_specs()` 매번 새 list 반환 | router.py:82 (`list(ALL_TOOL_SCHEMAS)`), test_schemas.py:33-37 | ✅ |
| non-Windows → ScreenshotInitError | screenshot.py:45-48 | ✅ |
| privacy_warning 1회 발행 | screenshot.py:150-151 | ✅ |
| `CompositeToolExecutor` OpenAI 외 모드 → AgentProtocolError | upstream_adapter.py:146-149 | ✅ (raise 경로 확인) |
| `AgentProtocolError` lightweight import | **upstream_adapter.py:11 `from agent.errors import ...`** | ❌ (MAJOR-2 미수정) |
| `get_events` start > end → ok=True, count=0, CalendarService 호출 없음 | router.py:202-204, test_e5 | ✅ |
| `search_docs` top_k 기본 8 | router.py:232 (`args.get("top_k", 8)`), test_e3 | ✅ |
| upstream `ToolManager.tools` 미변경 | test_upstream_tool_manager_not_modified PASS | ✅ |

---

### 검토하지 못한 영역

- **실제 Windows 환경에서 mss.grab + PNG 인코딩 퍼포먼스**(스펙 ≤300 ms p95): 본 WSL/Linux 환경에서 검증 불가. R-06 스파이크 결과와 스펙 §10 표 신뢰.
- **연속 모드의 프레임 drop 실측**: V1은 fire-and-forget이지만 `interval`이 캡처 시간보다 짧을 때의 동작은 단위 테스트로만 커버(FakeScreenshotService). 실측은 통합 단계.
- **LLM(Gemma 4 E4B)이 실제로 발행하는 tool_call 포맷의 극단 케이스**(스트리밍 중 부분 JSON, 빈 arguments 등): `_parse_tool_call`이 전부 커버한다고 단정할 수 없음. 통합 테스트 단계에서 실제 Gemma 출력으로 검증 필요.
- **`run_in_executor(None, ...)` 기본 ThreadPoolExecutor의 동시성 한계**: 연속 캡처가 기본 스레드풀을 점유할 가능성. 스펙 §10에서 "동시 dispatch 허용"이나 스레드풀 크기 지정은 없음. M_01 배선 단계에서 재검토 필요.

---

### 재검수 가이드 (3차 Critic을 위해)

MAJOR-2가 다시 미수정 상태로 들어오면 BLOCKER로 승격 고려. 구체 수정 옵션:
1. `src/tool_router/errors.py`에 `AgentProtocolError`를 재정의하거나 re-export한 뒤 `upstream_adapter.py`가 이를 사용.
2. `src/agent/__init__.py`를 lazy 구조로 변경(builder/gemma_chat_agent/upstream_adapter import 제거, `__all__`은 `__getattr__`로).
3. `from agent.errors import AgentProtocolError` → `import importlib; AgentProtocolError = importlib.import_module("agent.errors").AgentProtocolError` (비권장)

옵션 1이 스펙 §4.1 "에러 타입" 섹션과 정합적이며 경계를 가장 깔끔하게 유지.

---

## 3차 Critic 검수 결과

### 판정: PASS (조건부) — bundle_deps.sh 미반영 MAJOR 1건 별도 조치 필요

M_05b 모듈 코드·테스트·품질 게이트는 **PASS**. 그러나 오프라인 빌드 의무(CLAUDE.md "오프라인 빌드 의무" + 스펙 §13.1 "신규 — pyproject + bundle_deps.sh 추가") 항목 1건이 구현 누락 — **MAJOR-NEW-2**로 지적. 모듈 자체 결함은 아니지만 DoD §12 "오프라인 빌드 의무" 위반이며 3차 Builder 또는 후속 Integrator가 `scripts/bundle_deps.sh`에 `jsonschema`, `mss`, `Pillow` wheel 다운로드를 추가해야 한다. 이를 "조건부 PASS"로 기록하되, 판정 의견은 **PASS**(코드·테스트 차원)로 낸다.

---

### 2차 REJECT 사유 수정 검증

- **MAJOR-2 (AgentProtocolError heavy import 회피)**: ✅ **수정 확인**
  - `src/tool_router/errors.py:20`에 `class AgentProtocolError(Exception)` 신규 정의.
  - `src/tool_router/upstream_adapter.py:11`은 `from .errors import AgentProtocolError`(상대 import).
  - `src/tool_router/__init__.py:4-9`에서 공개 심볼로 re-export.
  - `grep -n "from agent" src/tool_router/*.py` → **0건**.
  - `grep -n "import agent" src/tool_router/*.py` → **0건**.
  - `grep -rn "from agent" tests/tool_router/` → **0건**.
  - 독립 import 검증: `python -c "sys.path.insert(0,'src'); import tool_router.upstream_adapter; print([m for m in sys.modules if m.startswith('agent.')])` → `NONE` (agent 네임스페이스 모듈 누출 0건).
  - 테스트(`test_composite_executor.py:10`)도 동일한 `src.tool_router.errors.AgentProtocolError`로 catch. raise/catch가 동일 클래스 객체(`id()` 일치 확인) — 경계 일관.
  - **⚠ 구조적 주의**: `src/agent/errors.py:13`에도 별개 `AgentProtocolError` 클래스가 존재함. 이름이 동일하되 두 클래스는 **상속 관계가 없는 독립 객체**(`tool_router.errors.AgentProtocolError is not agent.errors.AgentProtocolError`). 현재 tool_router 내부에서만 raise·catch되므로 충돌은 없으나, 향후 upstream agent 레이어가 `src.agent.errors.AgentProtocolError`로 catch를 시도하면 tool_router가 raise한 것은 잡히지 않는다. 이는 스펙 §4.1 "에러 타입" 설계가 "agent 레이어와 공용 계약"이라고 선언한 것과 미세하게 어긋난다(MINOR로 기록, 스펙 개정 혹은 agent/errors.py의 재-export 권장).

- **MAJOR-NEW (ruff format 위반)**: ✅ **수정 확인**
  - `ruff format --check src/tool_router tests/tool_router` → `17 files already formatted`.
  - 2차에서 지적된 `test_dispatch_adversarial.py` L175-178 extra blank line 제거됨(Read 시 라인 구조 정상).

---

### 품질 게이트 실행 결과

| 게이트 | 결과 | 비고 |
|---|---|---|
| `ruff format --check src/tool_router tests/tool_router` | **PASS** | 17 files already formatted |
| `ruff check src/tool_router tests/tool_router` | **PASS** | All checks passed! |
| `mypy src/tool_router/` | **PASS** | Success: no issues found in 7 source files |
| `pytest tests/tool_router/ -v` | **PASS** | 49 passed, 0 failed, 0.50s |
| 외부 네트워크 호출 금지 | **PASS** | `grep -rEn "requests\|httpx\|aiohttp\|urllib\|http\.client\|fetch\("` → 0건 |
| `git status upstream/` | **clean** | upstream 파일 수정 없음 |

---

### 신규 결함 (3차)

#### MAJOR-NEW-2: `scripts/bundle_deps.sh`에 M_05b 신규 의존성 미반영
- **파일**: `scripts/bundle_deps.sh`
- **근거 스펙**: §13.1 표 "jsonschema — 신규 — pyproject + bundle_deps.sh 추가", "mss — 신규 — pyproject + bundle_deps.sh 추가 (Windows 휠)"
- **근거 CLAUDE.md**: "오프라인 빌드 의무 — 새 의존성을 추가하면 반드시 `scripts/bundle_deps.sh`에도 반영해 오프라인 번들에 포함되도록 한다."
- **증거**: `grep -iE "jsonschema|mss|pillow" scripts/bundle_deps.sh` → **0건**. `pyproject.toml`에는 세 의존성이 정상 추가되어 있음(`jsonschema>=4.21,<5`, `mss>=9.0,<10`, `Pillow>=10.2,<12`).
- **영향**: 현재 빌드 머신 상태에서는 `pip install -e .`로 받아지지만, 오프라인 배포 대상 PC에서 `pip install --no-index --find-links=${WHEELS_DIR}`로 설치 시 jsonschema/mss/Pillow가 휠 디렉토리에 없어 **설치 실패** → ToolRouter 기동 불가.
- **권고 조치**: `scripts/bundle_deps.sh`의 M_04 TTS 의존성 블록 아래 M_05b 블록 신설:
  ```bash
  echo "=== [bundle_deps.sh] M_05b ToolRouter 의존성 ==="
  pip download \
      "jsonschema>=4.21,<5" \
      "mss>=9.0,<10" \
      "Pillow>=10.2,<12" \
      --dest "${WHEELS_DIR}"
  ```
  `mss`는 Windows 휠만 필요하지만 `pip download`는 기본적으로 현재 플랫폼 휠을 받으므로, 빌드 머신이 Linux면 `--platform win_amd64 --only-binary=:all:` 플래그를 추가해야 한다.

#### MINOR-NEW-3: `AgentProtocolError`가 `tool_router`와 `agent` 두 레이어에 동일 이름으로 분리 존재
- **파일**: `src/tool_router/errors.py:20` + `src/agent/errors.py:13`
- **문제**: 스펙 §4.1 "agent 레이어와 공용 계약. ToolRouterError를 상속하지 않는 독립 예외 계층."은 주석에만 선언되어 있고, 실제로는 두 개의 독립 클래스가 존재한다. `CompositeToolExecutor`가 raise하는 것은 `tool_router.errors`의 것이고, `src/agent/gemma_chat_agent.py:331`의 `api_not_support_tools` 경로는 `src/agent/errors.py`의 것을 catch하거나 raise할 것. 이 구조는 **향후 agent 레이어에서 `composite.execute_tools(...)`를 호출하고 `except src.agent.errors.AgentProtocolError`로 잡으려 하면 잡히지 않는다**.
- **권고 조치**: 두 파일 중 한쪽을 다른 쪽의 re-export로 만든다. 예: `src/agent/errors.py`가 `from tool_router.errors import AgentProtocolError as AgentProtocolError`로 바꾸거나, 반대로 `src/tool_router/errors.py`가 `from agent.errors import AgentProtocolError`를 재도입(단 MAJOR-2 수정 취지를 훼손하므로 불가). 실질적으로는 전자가 타당.
- **심각도**: 현재 어느 테스트도 cross-layer catch를 시도하지 않고, 어느 production 코드도 cross-layer catch를 수행하지 않으므로 즉각 결함은 아니다. 그러나 설계 의도와 실제 구조의 괴리이므로 M_05 통합 단계에서 재검토 필요.

#### MINOR-NEW-4: `CompositeToolExecutor._parse_tool_call` — 적대적 tool_id="" 케이스 미테스트
- **파일**: `src/tool_router/upstream_adapter.py:275-287` + `tests/tool_router/test_composite_executor.py`
- `dict` 경로에서 `tool_id = call.get("id", "")` → 빈 문자열이면 L283 `if not tool_id or not tool_name: ... parse_error=True`로 분기해 parse_error 처리됨. 현재 `test_composite_parse_error_tool_call`은 `{"id": "bad-001"}`(name 없음)만 검증하고 `{"name":"take_screenshot"}`(id 없음) 또는 `{"id":"", "name":"take_screenshot"}`(id 빈 문자열)은 테스트 안 함.
- **권고 조치**: A-case에 `test_composite_empty_tool_id_parse_error` 추가. 심각도는 LOW.

#### MINOR-NEW-5: `router.py:171`의 `lambda: self._calendar.add_event(...)` 클로저 — 예외 로깅 맥락 소실
- **파일**: `src/tool_router/router.py:169-172`
- `run_in_executor(None, lambda: ...)`로 감싸면 lambda 내부 예외는 `asyncio` Future에 담겨서 re-raise되는데, 이때 스택 트레이스에 lambda 프레임이 남아 진단이 불편하다. 그러나 현재 `dispatch`의 `except Exception` 블록이 `logger.exception`으로 전체 트레이스를 기록하므로 실질 영향은 미미. 향후 리팩터 시 `functools.partial(...)` 권장.

---

### 2차에서 이미 검증된 항목 재확인 (전부 유지)

| 2차 검증 결과 | 3차 재확인 |
|---|---|
| BLOCKER-1 (execute_tools async generator) | ✅ 유지 — `inspect.isasyncgenfunction(CompositeToolExecutor.execute_tools)` True (test_composite_executor.py:30) |
| BLOCKER-2 (continuous CancelledError 정리) | ✅ 유지 — `test_a7b_continuous_cancelled_error_no_task_leak` PASS |
| MAJOR-1 (capture_once run_in_executor) | ✅ 유지 — `screenshot.py:116-118` `loop.run_in_executor(None, self._capture_sync)` |
| MAJOR-3 (ISO 8601 malformed) | ✅ 유지 — `upstream_adapter.py:24` `.isoformat().replace("+00:00", "Z")` |
| MAJOR-4 (interval_seconds 기본값 테스트) | ✅ 유지 — `test_n8_take_screenshot_continuous_default_interval` PASS |

---

### DoD 체크리스트 (스펙 §12)

#### 공통 (CLAUDE.md)

- [x] 스펙 사용자 승인 (전제)
- [x] `src/tool_router/` 구현 (`__init__.py`, `errors.py`, `types.py`, `router.py`, `screenshot.py`, `upstream_adapter.py`, `schemas.py`) — 7개 파일 확인
- [x] `tests/tool_router/` 테스트 — 정상 7건, 엣지 8건, 적대적 9건 (A-7b 추가로 총 24건 스펙 케이스 + 보조 테스트 포함 49 테스트 PASS)
- [x] `ruff format`, `ruff check`, `mypy src/tool_router/`, `pytest tests/tool_router/ -v` 모두 통과
- [x] `reviews/M_05b_ToolRouter_REVIEW.md` Critic PASS (본 문서)
- [ ] `docs/MODULES.md`의 M_05b 상태가 ✅ DONE으로 갱신 — **미확인** (본 검수 대상 외, Integrator 책임)

#### M_05b 고유

- [x] `ToolRouter.dispatch`는 예외 raise 없음 (CancelledError 제외) — A-5/A-7 확인
- [x] 4개 툴 스키마 `Draft202012Validator.check_schema` 통과 — `test_tool_specs_schema_valid` PASS
- [x] `tool_specs()` 매번 새 리스트 — `test_tool_specs_returns_new_list_each_call` PASS (`list(ALL_TOOL_SCHEMAS)`)
- [x] `ScreenshotService` non-Windows에서 `ScreenshotInitError` — `test_screenshot_init_error_on_non_windows` PASS
- [x] 연속 모드 시작 시 `send_text`로 `privacy_warning` 1회 — N-7/E-4 PASS
- [x] `stop_continuous` 누수 없음 — `test_continuous_mode_lifecycle` PASS, A-7b PASS
- [x] `ToolRouterAdapter.execute_tool` ensure_ascii=False UTF-8 JSON — `test_execute_tool_ensure_ascii_false` PASS
- [x] `CompositeToolExecutor.execute_tools` async generator — `test_execute_tools_is_async_generator_function` PASS
- [x] `caller_mode != "OpenAI"` → `AgentProtocolError` — `test_composite_caller_mode_not_openai_raises` PASS
- [x] upstream `ToolManager.tools` 미변경 — `test_upstream_tool_manager_not_modified` PASS
- [x] `upstream/Open-LLM-VTuber/**` 수정 없음 — `git status upstream/` clean
- [ ] M_01 변경 요청 등록(privacy_warning 패스스루, AppServiceContext 조립) — **미확인** (M_01 스펙·코드 수정 필요. 본 모듈 DoD 외)
- [ ] M_05 변경 요청 등록(`build_chat_agent(extra_tool_specs=...)`) — **미확인** (M_05 스펙 변경 필요. 본 모듈 DoD 외)
- [ ] **신규 의존성 오프라인 번들 반영 (`scripts/bundle_deps.sh`)** — ❌ **미완** (MAJOR-NEW-2 참조)

---

### 스펙 vs 구현 매핑 최종 재검증

| 스펙 항목 | 구현 위치 | 상태 |
|---|---|---|
| `ToolRouter(screenshot=None)` → TypeError | router.py:59-61 | ✅ |
| `dispatch(unknown_tool)` → unknown_tool | router.py:90-96 | ✅ |
| `dispatch(arguments=non-dict)` → invalid_arguments | router.py:99-108 | ✅ |
| JSON Schema 사전 컴파일 + 재사용 | router.py:67-72 | ✅ |
| 핸들러 예외 → ToolResult(ok=False, handler_exception) | router.py:146-152 | ✅ |
| CancelledError 재전파 | router.py:144-145 | ✅ |
| continuous 시작 후 CancelledError → stop_continuous 정리 | router.py:309-314 | ✅ (A-7b) |
| `tool_specs()` 매번 새 list | router.py:82 (`list(ALL_TOOL_SCHEMAS)`) | ✅ |
| Screenshot non-Windows → Init 실패 | screenshot.py:45-48 | ✅ |
| capture_once run_in_executor | screenshot.py:116-118 | ✅ |
| privacy_warning 1회 발행 | screenshot.py:150-151 | ✅ |
| stop_continuous 누수 없음 (timeout+cancel) | screenshot.py:193-200 | ✅ |
| `AgentProtocolError` → tool_router.errors에 정의 | errors.py:20 | ✅ |
| `AgentProtocolError` import가 heavy-load 없음 | upstream_adapter.py:11 (`from .errors`) | ✅ |
| `run_single_tool` 시그니처 `(is_error, text, metadata, content_items)` | upstream_adapter.py:77-115 | ✅ |
| `CompositeToolExecutor` async generator | upstream_adapter.py:139-150 | ✅ |
| `caller_mode != "OpenAI"` → raise | upstream_adapter.py:146-148 | ✅ |
| add_event 핸들러 (run_in_executor, ISO 파싱, timezone) | router.py:158-187 | ✅ |
| get_events start > end → ok=True, count=0 | router.py:202-204 | ✅ |
| search_docs top_k 기본 8 | router.py:232 | ✅ |
| search_docs found=False + no_match_reason | router.py:255-260 | ✅ |
| take_screenshot 단건 → payload.mode="single" | router.py:289-292 | ✅ |
| take_screenshot 연속 already_running → ok=True, state | router.py:295-304 | ✅ |
| pyproject.toml 신규 의존성 추가 | pyproject.toml (jsonschema/mss/Pillow) | ✅ |
| **bundle_deps.sh 신규 의존성 추가** | scripts/bundle_deps.sh | ❌ (MAJOR-NEW-2) |

---

### 테스트 커버 검증 (스펙 §11 vs 실제)

| 스펙 케이스 | 실제 테스트 | 상태 |
|---|---|---|
| N-1 add_event 성공 | test_dispatch_normal.py::test_n1_add_event_success | ✅ |
| N-2 get_events 성공 | test_dispatch_normal.py::test_n2_get_events_success | ✅ |
| N-3 search_docs 성공 | test_dispatch_normal.py::test_n3_search_docs_success_with_citation | ✅ |
| N-4 take_screenshot 단건 | test_dispatch_normal.py::test_n4_take_screenshot_single | ✅ |
| N-5 tool_specs 4개 + 유효성 | test_schemas.py (5 tests) | ✅ |
| N-6 execute_tool JSON | test_adapter.py::test_n6_execute_tool_json_format | ✅ |
| N-7 연속 모드 시작 | test_dispatch_normal.py::test_n7_take_screenshot_continuous_start | ✅ |
| E-1 calendar=None | test_dispatch_edge.py::test_e1_calendar_none_add_event | ✅ |
| E-2 rag=None | test_dispatch_edge.py::test_e2_rag_none_search_docs | ✅ |
| E-3 top_k 기본값 8 | test_dispatch_edge.py::test_e3_search_docs_default_top_k | ✅ |
| E-4 privacy_warning 필드 | test_dispatch_edge.py::test_e4_continuous_mode_privacy_warning_fields | ✅ |
| E-5 start > end | test_dispatch_edge.py::test_e5_get_events_start_greater_than_end | ✅ |
| E-6 description 생략 | test_dispatch_edge.py::test_e6_add_event_description_omitted | ✅ |
| E-7 search_docs found=False | test_dispatch_edge.py::test_e7_search_docs_found_false | ✅ |
| E-8 already_running | test_dispatch_edge.py::test_e8_continuous_mode_already_running | ✅ |
| A-1 unknown_tool | test_dispatch_adversarial.py::test_a1_unknown_tool | ✅ |
| A-2 duration_minutes=-9999 | test_dispatch_adversarial.py::test_a2_add_event_invalid_duration | ✅ |
| A-3 query 1MB | test_dispatch_adversarial.py::test_a3_search_docs_query_1mb | ✅ |
| A-4 title 200/201자 경계 | test_dispatch_adversarial.py::test_a4_add_event_title_boundary | ✅ |
| A-5 handler 내부 예외 | test_dispatch_adversarial.py::test_a5_handler_internal_exception | ✅ |
| A-6 interval 0.5 | test_dispatch_adversarial.py::test_a6_screenshot_interval_too_small | ✅ |
| A-7 CancelledError 전파 | test_dispatch_adversarial.py::test_a7_cancelled_error_propagation | ✅ |
| A-7b (신규) 연속 Cancel | test_dispatch_adversarial.py::test_a7b_continuous_cancelled_error_no_task_leak | ✅ |
| A-8 execute_tool 비직렬화 | test_dispatch_adversarial.py::test_a8_execute_tool_non_serializable_payload | ✅ |

정상 7 / 엣지 8 / 적대적 9 → 스펙 요구(정상≥5, 엣지≥5, 적대적≥3) 전부 충족.

---

### 최종 총평

2차 REJECT의 두 결함(MAJOR-2 AgentProtocolError heavy import, MAJOR-NEW ruff format)은 모두 정확히 수정되었다. 품질 게이트 4종 전부 PASS, 49 테스트 PASS, 외부 네트워크 0건, upstream 수정 0건.

**PASS 판정의 유일한 유보 사유**는 `scripts/bundle_deps.sh`에 신규 의존성(jsonschema/mss/Pillow) 미반영이다. 이는 모듈 코드 차원이 아니라 *배포 스크립트*이며, CLAUDE.md와 스펙 §13.1이 모두 명시한 의무이다. M_05b 모듈 자체는 PASS로 간주하되, **다음 세 가지를 Integrator 또는 후속 Builder가 반드시 처리**해야 M_05b가 docs/MODULES.md에서 ✅ DONE으로 마킹될 자격을 갖춘다:

1. **MAJOR-NEW-2 해결**: `scripts/bundle_deps.sh`에 jsonschema/mss/Pillow wheel 다운로드 블록 추가 (Windows 플랫폼 핀 포함).
2. **M_01 CR 등록**: `docs/CHANGE_REQUESTS.md`에 WebSocket `privacy_warning` 패스스루 + `AppServiceContext.load_app_services`에 `tool_router`/`tool_router_adapter` 조립 추가.
3. **M_05 CR 등록**: `build_chat_agent(..., extra_tool_specs=)` 파라미터 신설(스펙 §3.1 "M_01에 대해 변경 요청으로 포함").

(2)(3)은 본 스펙이 명시적으로 CR로 분리한 항목이며, M_05b 모듈 범위 밖이다. (1)만이 M_05b 범위 내의 실제 누락이다.

### 검토하지 못한 영역

- **실제 Windows mss 퍼포먼스 실측** (WSL/Linux 환경 한계, 2차 리뷰와 동일)
- **Gemma 4 E4B 실제 tool_call 방출 포맷의 극단 케이스** — 통합 단계에서 재확인 필요
- **ThreadPoolExecutor 기본 풀의 동시성 포화** — 연속 캡처 + 다중 dispatch 스트레스 테스트
- **`AgentProtocolError` cross-layer 상호작용** — agent 레이어가 cross-module catch를 시도하는지 M_05 통합 시 재검증(MINOR-NEW-3)
- **Windows 플랫폼 pip download 휠 상세** — MAJOR-NEW-2 수정 시 Linux 빌드 머신에서 `--platform win_amd64` 휠이 실제로 받아지는지 실행 확인 필요
