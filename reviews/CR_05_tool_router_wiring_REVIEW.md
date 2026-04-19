# CR-05 tool_router_wiring — Critic 검수 결과

## 판정: PASS (단, CR-03/CR-04 선행 의존 항목은 DoD 미완 상태로 명시)

## 후속 조치 기록 (MAJOR-3 수정 완료)

`_handle_start_continuous_capture`에 monitor_index/region WARN 누락 건 수정:
- `src/app/ws_handler.py:148-158` — 비기본값 시 WARN 로그 1회 추가
- `tests/app/test_ws_handler.py::TestContinuousCapture::test_start_monitor_index_region_ignored_with_warn` 신규 테스트 추가
- 검증: ruff/mypy PASS, `pytest tests/app/test_ws_handler.py` → **16 passed, 0 failed**

본 CR은 본문 L194-197에서 "CR-04 미승인 시 `build_chat_agent` 호출부만 보류하고 나머지는 선 진행 가능"으로 스코프 축소를 사전 인가했다. 해당 단서에 따라 "ScreenshotService/ToolRouter/ToolRouterAdapter 조립 + ws_handler 옵션 A 전환 + close() aclose 추가"는 요구 수준을 만족한다. 다만 DoD 체크리스트 중 `load_from_config → CompositeToolExecutor + extra_tool_specs` 항목은 **명시적 미완**이며, CR-03 머지 시 재검수 대상이다.

---

## BLOCKER
없음.

---

## MAJOR

1. **[MAJOR]** `src/app/service_context.py:107-126` — CR-05 DoD 5번 항목 "load_from_config가 CompositeToolExecutor를 self.tool_executor로 세팅하고 build_chat_agent(..., extra_tool_specs=tool_router.tool_specs()) 호출" 미이행.
   - 현재 `load_from_config`는 `await super().load_from_config(config)`만 호출하고, docstring에 TODO를 기재.
   - upstream `service_context.py:392`이 `AgentFactory.create_agent(..., tool_executor=self.tool_executor, ...)`로 `self.tool_executor`를 전달하므로, 본 재할당이 `super().load_from_config` **전에** 이루어져야 CompositeToolExecutor가 실제로 활성화된다. 현재 상태에서는 local tool call이 upstream MCP ToolExecutor로만 라우팅되어 M_05b 핸들러가 **런타임에 호출되지 않는다**.
   - CR-05 본문 L194-197의 "CR-04 미승인 시 보류"는 스코프 축소를 허용하지만, "CR-05 DoD 완료"를 선언하려면 CR-03/CR-04 이후 해당 코드 블록을 반드시 작성해야 함. 현재는 **기능적으로 tool_router가 조립은 되었으나 LLM tool_call 경로에 연결되지 않은 미결선 상태**.
   - 권고: CR-05 자체는 PASS하되, MILESTONES/MODULES에서 "AppCore DONE" 선언은 CR-03 머지까지 보류. `docs/MODULES.md`에 해당 의존 주석 추가 필요.

2. **[MAJOR]** `tests/app/test_service_context.py::TestCR05ToolRouterAssembly::test_n1_load_app_services_assembles_all_three` — 실제 계약 우회.
   - `mock_module.ScreenshotService = MagicMock(return_value=mock_screenshot)`, `mock_module.ToolRouter = MagicMock(return_value=mock_router)`로 생성자 호출만 목(mock)하고, 반환값을 그대로 AppServiceContext 필드에 꽂는지를 확인한다.
   - M_05b 스펙 §4.3 "screenshot=None 금지, TypeError"라는 **진짜 계약**은 실제 `ToolRouter` 클래스에 대해 검증되지 않는다 (mock이 TypeError를 던지지 않음).
   - 완화 요인: `tests/tool_router/test_dispatch_normal.py`, `test_screenshot.py`에서 진짜 `ToolRouter`/`ScreenshotService` 계약은 별도 검증됨. 따라서 이는 **단위 테스트의 적절한 경계**로 볼 수 있으나, N-1이 "조립 자체의 올바름"만 증명할 뿐 **실제 M_05b 계약 통과는 증명하지 않는다**는 점을 리뷰 기록에 남긴다.

3. **[MAJOR]** `src/app/ws_handler.py:135-177` `_handle_start_continuous_capture`에 `monitor_index != 0` WARN 누락.
   - `_handle_screenshot_trigger`는 monitor_index/region 비기본값 시 WARN 1회를 기록하지만, `_handle_start_continuous_capture`는 `monitor_index`를 받아서 `ContinuousCaptureTask`에 그대로 저장하고 `_continuous_capture_loop`에 전달하는데, 실제 `capture_once()`는 monitor_index를 사용하지 않는다. 사용자가 `start-continuous-capture`에 `monitor_index=5`를 보내도 조용히 primary만 캡처된다.
   - CR-05 DoD 7번 "monitor_index/region 비기본값 입력 시 WARN 로그 1회"가 "_handle_screenshot_trigger" 경로만 명시했는지, 일반 원칙인지 스펙 문언이 모호. 본 Critic 의견: 연속 캡처도 동일한 사용자 혼선을 유발하므로 WARN 필요.
   - 권고: `_handle_start_continuous_capture`에도 동일 WARN 1회 기록 또는 CR-05 DoD 7번을 "screenshot-trigger 한정"으로 명시적으로 좁힌다.

---

## MINOR

1. **[MINOR]** `src/app/service_context.py:12-22` `TYPE_CHECKING` 블록에서 `from typing import Any as RagService` 등 `Any` 별칭이 M_05b 타입과 한 블록에 섞여 있다. 가독성상 M_07~M_11 자리표시자와 M_05b 실제 타입이 구분 안 됨. 주석은 있으나 실수로 `RagService = Any`가 실제 `RagService`를 덮어쓸 리스크는 없다(TYPE_CHECKING 전용). 스타일만 개선 여지.

2. **[MINOR]** `tests/app/test_service_context.py:63-75` — `importlib.util.spec_from_file_location("_tool_router_real", ...)`를 로드하려다가 `pass`로 끝낸다. 쓰지 않는 코드. 빌더가 시도하다 만 흔적으로 보임. 데드 코드 제거 필요.

3. **[MINOR]** `src/app/service_context.py:87` `# type: ignore[has-type]` — upstream `ServiceContext.__init__`의 `self.tts_engine: TTSInterface = None` 선언(upstream `service_context.py:52`)이 mypy에서 서브클래스 메서드 문맥에서 `has-type` 추론 실패를 일으키는 알려진 문제 회피. 정당한 사용 (mypy 에러가 실제 발생함을 확인). 다만 주석에 "upstream 상속 제약" 한 줄 남기는 편이 이해도에 좋다.

4. **[MINOR]** `tests/app/test_service_context.py:264-278` N-3 테스트는 `aclose` 호출만 검증하고 호출 **순서**는 `test_close_order_includes_screenshot`에서 따로 검증한다. 두 테스트가 독립이라 OK지만 후자 단일 테스트로 통합 가능.

5. **[MINOR]** `src/app/ws_handler.py:85` `monitor_index: int = data.get("monitor_index", 0) or 0` — `data.get("monitor_index", 0)`가 이미 기본 0을 반환하므로 `or 0`은 사족. 다만 `None` 명시 전달 시의 guard로 의도했다면 OK. 마찬가지 패턴이 L150에 반복.

6. **[MINOR]** `src/app/service_context.py:199` `await self.screenshot_service.aclose()`가 AttributeError(`aclose` 미구현)를 `Exception` 포괄 캐치로 삼킨다. M_05b `ScreenshotService`는 `aclose` 구현을 보장하지만, 미래에 다른 구현체가 주입될 경우 조용히 누수될 수 있다. MINOR.

---

## 스펙 vs 구현 매핑 검증

| CR-05 DoD 항목 | 구현 위치 | 상태 |
|---|---|---|
| 1. `screenshot_service: ScreenshotService \| None` 타입 확정 | `service_context.py:22,45` | ✅ |
| 2. `tool_router`/`tool_router_adapter` 필드 신설 | `service_context.py:47-48` | ✅ |
| 3. `load_app_services`가 S→TR→Adapter 순 조립 | `service_context.py:139-166` | ✅ |
| 4. `ScreenshotInitError` 발생 시 세 필드 None + 앱 기동 계속 | `service_context.py:149-151, 163-166` | ✅ |
| 5. `load_from_config`가 CompositeToolExecutor+extra_tool_specs 배선 | `service_context.py:107-126` (TODO만) | ❌ (CR-03 의존, 본문 L194-197 단서로 허용) |
| 6. `close()`에서 `screenshot_service.aclose()` 호출 | `service_context.py:197-202` | ✅ |
| 7. `ws_handler`가 `capture_once()` 사용, base64 제거 | `ws_handler.py:118,236` (capture 호출 0건, base64 0건) | ✅ |
| 8. monitor_index/region 비기본값 WARN 1회 | `ws_handler.py:95-99` (_handle_screenshot_trigger만) | ⚠ (연속 캡처 경로 미적용 — MAJOR 3) |
| 9. N-1~N-3, E-1 테스트 통과 | `test_service_context.py::TestCR05ToolRouterAssembly` (5 tests PASSED) | ✅ |
| 10. 기존 `tests/app/test_ws_handler.py` 회귀 + N-4 | test_ws_handler 18 PASSED 포함 N-4 | ✅ |
| 11. `tests/tool_router/` 회귀 0건 | 49 PASSED | ✅ |
| 12. ruff format/check + mypy + pytest 전체 PASS | 전부 PASS | ✅ |
| 13. upstream 수정 없음 | `git status upstream/` clean | ✅ |
| 14. `specs/M_01_AppCore_SPEC.md` 갱신 | L190-233 필드/조립/close 순서 반영 | ✅ |

## 테스트 커버 검증

| CR-05 §필요 변경 5 테스트 | 구현된 테스트 | 상태 |
|---|---|---|
| N-1 3필드 not-None | `test_n1_load_app_services_assembles_all_three` | ✅ (단 mock 기반, MAJOR-2 참조) |
| N-2 tool_specs 길이 4 + 이름 | `test_n2_tool_specs_length_and_names` (real ToolRouter 사용) | ✅ |
| N-3 aclose 호출 | `test_n3_close_calls_screenshot_aclose` + `test_close_order_includes_screenshot` | ✅ |
| E-1 ScreenshotInitError 시 None 유지 | `test_e1_screenshot_init_error_sets_all_none` | ✅ |
| N-4 monitor_index/region WARN | `test_n4_monitor_index_region_ignored_with_warn` (loguru sink로 검증) | ✅ |
| 연속 캡처 WARN | (없음) | ❌ (MAJOR-3) |
| 기존 3회 실패 회귀 | `test_three_consecutive_failures_stops_loop` | ✅ |

## 빌더가 추가한 부수 변경 평가

- `service_context.py:87` `# type: ignore[has-type]` — **정당**. 제거 시 `mypy: Cannot determine type of "tts_engine" [has-type]` 실 발생 확인. upstream이 `self.tts_engine: TTSInterface = None`로 타입과 값이 모순되게 초기화하기 때문에 서브클래스 오버라이드 문맥에서 mypy 추론 실패. 정당한 ignore.
- `test_service_context.py`의 `patch.dict(sys.modules, {"tool_router": mock_module})` 패턴 — **정당**. `patch.dict`는 컨텍스트 종료 시 원복되어 다른 테스트 오염 없음. Linux(비-Windows)에서 `mss` 없이 `ScreenshotService.__init__`을 직접 실행하면 즉시 `ScreenshotInitError`가 발생하므로, `load_app_services`의 조립 로직을 독립 검증하려면 mock 주입이 불가피. 테스트 은폐가 아니라 단위 경계 설정.
- `test_n2_tool_specs_length_and_names`의 pytest.skip — **실제로는 Linux에서도 PASS**한다. `ToolRouter` 자체는 mss 없이도 import 가능하고, screenshot 생성자를 호출하지 않기 때문. 따라서 `try/except/pytest.skip`은 불필요한 방어 코드지만, 결과적으로 skip 없이 실행되어 검수 구멍 없음. MINOR로 분류도 안 할 수준.

---

## 검증 실행 결과

- `ruff format --check .`: **PASS** (94 files already formatted)
- `ruff check src/app src/tool_router tests/app tests/tool_router`: **PASS** (All checks passed)
- `mypy src/app/`: **PASS** (Success: no issues found in 10 source files)
- `pytest tests/app -v`: **PASS** (94 passed, 6 warnings — 모두 upstream pydantic deprecation, CR-05 무관)
- `pytest tests/tool_router -v`: **PASS** (49 passed)
- `git status upstream/`: clean (nothing to commit)

---

## CR-03 TODO 상태

CR-05 DoD 5번 "load_from_config가 CompositeToolExecutor를 self.tool_executor로 세팅하고 build_chat_agent(..., extra_tool_specs=tool_router.tool_specs()) 호출"은 **미완** 상태.

근거:
- `src/app/service_context.py:107-126` `load_from_config`는 본문에 TODO 주석만 남기고 `await super().load_from_config(config)`만 호출.
- upstream `service_context.py:382-394`의 `init_agent → AgentFactory.create_agent(tool_executor=self.tool_executor)`가 실제 ToolExecutor를 사용하므로, `self.tool_executor = composite` 재할당이 `super().load_from_config` **전에** 이루어져야 함.
- 현재 구현에서는 M_05b 로컬 핸들러(`add_event`/`get_events`/`search_docs`/`take_screenshot`)가 tool_router에 조립은 되었으나 **실제 LLM tool_call 경로에서 호출되지 않는다**.

허용 근거:
- CR-05 L194-197이 "CR-04 미승인 시 `build_chat_agent` 호출부만 보류하고 나머지는 선 진행 가능"을 명시.
- TODO 주석이 `service_context.py:112-124`에 명확히 남아있음 (파일/라인 확인).

판정:
- **CR-05 자체는 PASS**. 단, DoD 5번 체크박스는 **미체크 상태 유지**.
- CR-03(init_agent 가드 패턴) + CR-04(build_chat_agent extra_tool_specs) 머지 직후 **fresh critic 재검수 필수**.
- `docs/MODULES.md`에서 "M_01 AppCore DONE" 선언은 CR-03/04 이후로 보류해야 함. 현재 선언하면 CLAUDE.md §산출물 체크리스트 "DoD 전체 체크" 위반.

---

## 검토하지 못한 영역

- **Windows 실환경 통합 테스트**: 실제 `mss` + `ScreenshotService` + `ToolRouter` 조립 후 end-to-end 캡처 성공까지의 smoke test는 Linux WSL 환경에서 불가. M_05b `test_screenshot::test_screenshot_init_success_on_windows`가 `platform.system()` monkeypatch로 대체하지만, 실제 DXGI duplicator 경합은 Windows 실기에서만 검증 가능.
- **`_handle_screenshot_trigger` → `_handle_conversation_trigger` 재진입 경로**: data URL이 upstream `ImageSource.SCREEN` 처리 경로에서 올바르게 소비되는지 단위 테스트 없음. 통합 smoke(`test_create_app`)에서도 검증 안 됨.
- **`load_app_services`를 여러 번 호출할 때** 이전 `screenshot_service`가 `aclose` 없이 교체되어 mss 리소스 누수. 스펙상 1회 호출 전제이나 런타임 guard 없음.
- **`tests/tool_router/__init__.py`가 비어있어 pytest가 `tool_router`를 테스트 패키지로 인식할 수 있는 가능성**: conftest.py의 `sys.path.insert(0, src)`로 우선순위가 src 쪽에 있어 실제 충돌은 없으나, 테스트 컬렉션 환경에 따라 미래 회귀 가능성 존재. 별도 조사 권고.
- **CR-05 본문 L343-346에 기각된 "ws_handler continuous 루프를 tool_router.dispatch로 치환" 옵션**의 후속 CR 티켓이 실제로 `docs/CHANGE_REQUESTS.md`에 등록되어 있는지는 미확인.

다음 fresh critic이 CR-03/CR-04 머지 후 재검수할 때 위 영역을 우선 검토할 것.
