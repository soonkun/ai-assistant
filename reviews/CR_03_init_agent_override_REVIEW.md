# CR-03 init_agent_override — Critic 검수 결과

검수자: fresh critic (builder와 분리된 세션)
검수일: 2026-04-19
대상 커밋: 작업 트리 (git status clean)
빌더 주장 검증 범위: `src/app/service_context.py`, `src/agent/upstream_adapter.py`, `tests/app/test_service_context.py`, `tests/agent/test_adapter.py`, `pyproject.toml`, `docs/CHANGE_REQUESTS.md` CR-03, `specs/M_01_AppCore_SPEC.md`, `specs/M_05_LLMAgent_SPEC.md`, `docs/MODULES.md`, `reviews/CR_05_tool_router_wiring_REVIEW.md` MAJOR-1.

---

## 판정: PASS (조건부)

조건: 아래 MAJOR-1·MAJOR-2의 테스트 실효성 보강 사항을 별도 follow-up CR로 추적 등록할 것. 코드 자체의 정합성과 DoD 14개 항목은 모두 충족되었으나, **CR-03의 "upstream AgentFactory가 호출 경로에서 제거된다"는 핵심 주장을 테스트가 기능적으로 증명하지 못한다**(E-2가 `load_from_config`를 거치지 않고 `init_agent`를 직접 호출한다). 리스크는 중간이며, Windows 실기 smoke에서 쉽게 드러나는 형태도 아니다. M_01 AppCore "DONE" 선언은 유지 가능하되, 리뷰 MAJOR-1 항목은 "해소 완료 + 테스트 보강 TODO"로 기록되어야 한다.

---

## BLOCKER
없음.

---

## MAJOR

1. **[MAJOR] `tests/app/test_service_context.py:655-683` E-2 테스트가 CR-03의 핵심 주장을 증명하지 못한다.**
   - E-2의 의도는 "upstream `AgentFactory.create_agent`가 호출 경로에서 제거됨"을 증명하는 것이며, CR-03 DoD 6번 및 M_01 SPEC L803 "upstream `AgentFactory.create_agent` 호출 횟수가 **0**임을 테스트(E-8)로 증명"의 유일한 근거 테스트다.
   - 실제 테스트 본문(L681)은 `await ctx.init_agent(MagicMock(), "페르소나")`로 **우리 오버라이드를 직접 호출**한다. `load_from_config`를 돌리지 않는다.
   - 우리 `init_agent` 오버라이드는 `AgentFactory`를 import도 하지 않으므로 직접 호출 경로에서는 `AgentFactory.create_agent.call_count == 0`이 **구조적으로 자명하다**(trivially true). `factory_mock.assert_not_called()`는 항상 통과한다.
   - 진짜 증명이 되려면 upstream `load_from_config`(upstream L249-L312)를 실제로 실행해 MRO가 우리 `init_agent`로 디스패치되는지, 그 결과 upstream의 `init_agent`(L364-405, AgentFactory 호출 지점)로 **떨어지지 않음**을 확인해야 한다.
   - 파일:라인: `tests/app/test_service_context.py:655-683`.
   - 권고 조치: E-2를 `ctx.load_from_config(<실제 upstream Config mock>)`로 유도. 최소한 upstream `_init_mcp_components`와 `init_live2d/init_asr/init_tts/init_vad/init_translate`를 모두 mock 처리한 후 `load_from_config`를 실행해, MRO 디스패치를 **실제로** 검증하는 통합 단위 테스트로 전환한다. 현재 상태의 E-2는 유지하되 명칭을 "직접 호출 경로 경유 시 AgentFactory 비참조"로 좁히고, 신규 테스트 E-2b를 추가해 load_from_config 경유 경로를 검증하는 것을 권장.

2. **[MAJOR] `tests/app/test_service_context.py:559-588` N-4 guard idempotency 테스트가 "실제 `load_from_config` 재호출" 시나리오를 검증하지 않는다.**
   - N-4는 `ctx.init_agent(agent_cfg, persona)` 후 수동으로 `ctx.character_config.persona_prompt = persona; ctx.character_config.agent_config = agent_cfg`를 설정한 다음 `init_agent`를 재호출한다.
   - 그러나 리뷰 요청 §A-5에 명시된 실제 걱정되는 시나리오는 **upstream `load_from_config`가 2회차에서 `_init_mcp_components`를 재실행해 `self.tool_executor`를 None/MCP로 리셋하는 상황**이다. 이 시점에 우리 init_agent가 가드로 early return하면 `self.tool_executor`에는 **composite 재주입이 일어나지 않는다**.
   - 1회차의 composite 참조는 `gemma_agent` 내부에 이미 캡처되어 있으므로 LLM tool_call은 여전히 composite로 흐르지만, `self.tool_executor` 슬롯을 외부(예: 모니터링/디버깅)에서 읽으면 MCP-only executor가 노출된다.
   - N-4는 이 갭을 덮지 못한다. `load_from_config`를 2회 실행하는 실제 테스트가 없으면 이 상태 drift는 조용히 숨겨진다.
   - 파일:라인: `tests/app/test_service_context.py:559-588`.
   - 권고 조치: N-4b를 추가해 `ctx.load_from_config(cfg)`를 두 번 호출(mock upstream Config로), `self.tool_executor`가 여전히 composite인지(또는 기대 상태가 MCP라면 그걸 명시) 확인. 현재 공개 계약(M_01 SPEC §공개 API)에 이 slot의 두 번째 load 후 상태가 명시되어 있지 않다 — 스펙 보강 필요.

3. **[MAJOR] `specs/M_01_AppCore_SPEC.md:801-807` DoD 체크박스가 중복·불일치한다.**
   - L801-805: CR-03 관련 DoD 5건이 모두 `[ ]` (unchecked).
   - L806-807: 같은 내용의 CR-03 DoD가 `[x] (CR-03 구현 완료)`로 재등장.
   - 이는 동일 DoD 항목을 두 번 기재하되 한 번은 체크, 한 번은 미체크한 상태다. 미래 독자(후임 개발자 또는 다음 Critic)가 "CR-03이 끝났는가"를 판단할 때 모순된 신호를 받는다.
   - CLAUDE.md "산출물 체크리스트 — 모든 DoD 체크박스 통과"가 DoD의 단일 진실 공급원을 요구하는데, 현재는 어느 쪽이 진실인지 불명확.
   - 파일:라인: `specs/M_01_AppCore_SPEC.md:801-807`.
   - 권고 조치: L801-805의 unchecked 항목을 제거하고 L806-807을 유지(또는 통합)하되, "CR-03 E-8 테스트(= E-2) 통과"가 빌더 주장대로 실제 통과했음을 파일:라인으로 명기. 혹은 L806-807을 삭제하고 L801-805를 `[x]`로 전환해도 동치.

---

## MINOR

1. **[MINOR] `src/app/service_context.py:130-137` 가드 조건에서 upstream L366의 `logger.info(f"Initializing Agent: {agent_config.conversation_agent_choice}")` 로그가 드롭됐다.**
   - 운영상 영향은 거의 없으나 upstream과의 행동 불일치이며, 별도 스펙 주석(§"upstream에서 drop한 side-effect 목록")이 누락됨. CR-03 본문 L80-133의 의사코드에도 이 로그 누락은 명시 안 됨.
   - 권고: L136의 `logger.info("AppServiceContext.init_agent: 동일 config — 재초기화 건너뜀")`이 있으니 신규 로그는 충분. 하지만 스펙(§공개 API `init_agent` docstring)에 "upstream `logger.info(Initializing Agent: ...)` 로그는 본 오버라이드에서 재현하지 않는다"를 1줄 명기.

2. **[MINOR] `src/app/service_context.py:140` `from agent.errors import AgentInitError`와 `tests/app/test_service_context.py:631,775` `from src.agent.errors import AgentInitError`는 서로 다른 모듈 객체를 생성한다.**
   - 검증: `python -c "import agent.errors as a; import src.agent.errors as b; print(a.AgentInitError is b.AgentInitError)"` → `False`.
   - 현재 테스트는 `build_chat_agent` mock의 side_effect로 AgentInitError를 던지고 `pytest.raises(AgentInitError)`로 받지만, **service_context 쪽의 `from agent.errors import ...` 경로는 `self.app_config is None` 분기(E-1에서 실행되지 않음)에서만 도달**하므로 duplicate class 문제가 우연히 숨겨져 있다.
   - 향후 "app_config is None" 경로를 타는 테스트를 작성하면 `pytest.raises(AgentInitError)`에서 두 클래스가 서로 다른 객체이므로 `except` 매칭 실패 가능성 존재.
   - 이는 프로젝트 전체의 `src.X` vs `X` 이중 import 경로 문제(mypy가 보고하는 `Source file found twice`)의 부분 증상. CR-03 범위 외지만 CR-03 테스트가 이 갭을 적극적으로 활용한다는 점을 기록.
   - 권고: `tests/app/test_service_context.py`의 모든 `from src.agent.errors import AgentInitError`를 `from agent.errors import AgentInitError`로 교체해 import 경로를 단일화. mypy 에러와도 무관하게 일관성 확보.

3. **[MINOR] `src/app/service_context.py:162` `self.tool_router.tool_specs()` 바로 앞에 `# type: ignore[union-attr]`가 있다.**
   - 로직상 `self.tool_router_adapter is not None`이 True일 때 `self.tool_router`도 함께 not-None인 것이 `load_app_services`의 조립 규약이지만, mypy는 그 불변식을 추론하지 못한다. 정당한 ignore.
   - 권고: `assert self.tool_router is not None, "tool_router_adapter is not None ⇒ tool_router is not None"` 한 줄을 추가하면 ignore를 제거 가능. 스타일 개선 제안.

4. **[MINOR] `tests/app/test_service_context.py:396-427` `_make_agent_sys_modules` 헬퍼가 3개 모듈(`agent.builder`, `agent.upstream_adapter`, `agent.errors`)을 동시에 mock하는데, 테스트마다 `agent.errors`를 처리하는 방식이 다르다.**
   - 대부분 `agent_init_error_cls=None`이고 이 경우 L421에서 `sys.modules.get("agent.errors", MagicMock())`로 기존 실모듈을 재사용한다. 그러나 A-2는 별도 `mock_errors = MagicMock(); mock_errors.AgentInitError = ...`를 직접 구성해 헬퍼를 우회한다. 일관성 부족.
   - 권고: 헬퍼에 `agent_init_error_cls` 기본값을 `AgentInitError` 실클래스로 바꾸면 모든 테스트가 동일 경로를 거친다.

5. **[MINOR] `tests/app/test_service_context.py:519-556` N-3 `CompositeToolExecutor._fallback` 검증의 범위가 좁다.**
   - 테스트는 `mock_adapter.as_upstream_tool_executor.side_effect=capture_as_upstream`로 호출 인자만 캡처해 `fallback is mcp_executor`를 확인한다.
   - "진짜" CompositeToolExecutor의 `_fallback` 속성을 검증하지는 않는다. 단위 경계상 허용되지만 CR-03 DoD 4번 "CompositeToolExecutor가 self.tool_executor에 주입되고 동일 참조가 build_chat_agent에 전달"의 후반부(= 동일 참조 전달)는 N-1 `ctx.tool_executor is mock_composite`와 N-3의 kwargs 캡처로 분산 검증된다. 단일 테스트로 종합적으로 묶는 편이 가독성 높음.

6. **[MINOR] `src/agent/upstream_adapter.py:88-94` `async def close()`의 docstring이 "CR-03"을 명시하지만 upstream guard의 **실행 조건**(`if self.agent_engine and hasattr(self.agent_engine, "close")`)을 본문에 재기술하지 않는다.**
   - 본 메서드의 **존재 이유**가 upstream guard 통과이므로 주석 1줄이 유지보수에 도움. 권고: docstring에 "upstream ServiceContext.close (`service_context.py:190-199`)의 hasattr 가드를 통과시키기 위한 배선"을 명시.

7. **[MINOR] `pyproject.toml:7-12` starlette/sse-starlette 핀 주석은 명확하나, `scripts/bundle_deps.sh` 반영 여부가 리뷰 범위에서 확인되지 않는다.**
   - starlette는 fastapi의 전이 의존성이라 `pip download fastapi==...`가 자동 포함하지만, **명시 핀을 추가했을 때** `pip download -r requirements.txt`가 별도 라인으로 처리하는지 번들 스크립트 실제 실행으로 검증 필요. CLAUDE.md "새 의존성 추가 시 bundle_deps.sh 반영"을 만족하려면 최소 주석("전이 의존성 보강 핀, 별도 bundle 작업 불요")을 bundle_deps.sh에 남기거나 실행 시험 결과를 남겨야 함.
   - 본 CR 범위 외의 환경 fix로 기술되어 있으나, bundle 증거가 없으면 오프라인 번들 시점에 다시 충돌 가능성.

---

## 스펙 vs 구현 매핑 검증

CR-03 DoD 14개 (docs/CHANGE_REQUESTS.md:261-282) 기준:

| # | DoD 항목 | 구현 위치 | 상태 | 근거 |
|---|---|---|---|---|
| 1 | `init_agent` 오버라이드 (스텝 1~7) | `src/app/service_context.py:115-194` | ✅ | 스텝 (1) 가드 L131-137, (2) app_config L142-146, (3) system_prompt L150, (4) mcp 확보 L153-154, (5) composite 분기 L157-172, (6) build_chat_agent L179-186, (7) 어댑터 L189, (8) config 동기화 L193-194. 스펙 §8단계를 모두 충족 |
| 2 | `load_from_config` TODO 블록 제거 | `src/app/service_context.py:107-113` | ✅ | L110-111에 "init_agent 오버라이드가 _init_mcp_components 직후에 디스패치되므로 build_chat_agent/CompositeToolExecutor 배선은 init_agent에서 완결됨 (CR-03)" 주석 존재. 본문은 `await super().load_from_config(config)` 1줄 |
| 3 | `BasicMemoryAgentAdapter.close()` 신규 | `src/agent/upstream_adapter.py:88-94` | ✅ | 동적 클래스 내부 메서드로 정의, `await self._agent.aclose()` 위임 |
| 4 | `CompositeToolExecutor` 주입 + build_chat_agent 전달 | `src/app/service_context.py:157-186` | ✅ | L161 `self.tool_executor = composite`, L183 `tool_executor=self.tool_executor` — 동일 참조가 build_chat_agent kwargs로 전달됨 (N-1, N-3 부분 검증) |
| 5 | `extra_tool_specs = self.tool_router.tool_specs()` 전달 | `src/app/service_context.py:162, 185` | ✅ | N-2가 `kwargs["extra_tool_specs"] == expected_specs`와 길이 4·이름 4종 확인 |
| 6 | upstream `AgentFactory.create_agent` 미호출 증명 (E-2) | `tests/app/test_service_context.py:655-683` | ⚠ | 테스트는 PASS하지만 **load_from_config를 거치지 않는 직접 호출**이라 trivially true (MAJOR-1). 구현 자체는 AgentFactory를 import조차 하지 않음 (src/app/service_context.py 전체에 `AgentFactory` grep 0건) |
| 7 | 재호출 idempotency (N-4) | `src/app/service_context.py:131-137` + `tests/app/test_service_context.py:559-588` | ⚠ | 구현은 OK, 테스트는 수동 상태 조작으로 검증 (MAJOR-2). build_chat_agent.call_count == 1 확인 |
| 8 | `build_chat_agent` 예외 전파 (E-1) | `src/app/service_context.py:179-186` (try/except 없음) + `tests/app/test_service_context.py:626-652` | ✅ | build_chat_agent의 예외를 잡는 try/except가 없음 — 자연 전파. 테스트가 `pytest.raises(AgentInitError)` 확인 |
| 9 | `tool_router_adapter is None` degraded 경로 (N-5) | `src/app/service_context.py:167-172` + `tests/app/test_service_context.py:591-619` | ✅ | extras=None, tool_executor 유지 — 테스트가 `ctx.tool_executor is original_executor` 확인 |
| 10 | N-1~N-5, E-1~E-3, A-1, A-2 총 10건 테스트 + adapter close 1건 | `tests/app/test_service_context.py:430-800`, `tests/agent/test_adapter.py:149-160` | ✅ | 10건 PASS + 1건 PASS 확인 (실행 결과 참조) |
| 11 | 회귀 0건 (tests/app, tests/agent, tests/tool_router) | 실행 결과 220 passed, 1 skipped | ✅ | skip은 CR-05 `test_n2_tool_specs_length_and_names` (별도 CR 분리 예정, 본 CR 무관) |
| 12 | ruff format/check + mypy + pytest PASS | — | ⚠ | ruff format PASS, ruff check PASS, pytest PASS. mypy는 **기존 `Source file found twice under different module names: "app.config" and "src.app.config"` 1건 유지**. CR-03 신규 mypy 에러 0건 확인. 이 에러는 빌더 주장대로 pythonpath 중복의 환경 문제 |
| 13 | upstream `Open-LLM-VTuber/**` git diff 없음 | `git status upstream/Open-LLM-VTuber/` | ✅ | nothing to commit, working tree clean |
| 14 | specs/M_01, specs/M_05, docs/MODULES.md, reviews/CR_05 MAJOR-1 cross-ref | 각 파일 | ⚠ | M_01 SPEC DoD 항목이 중복 기재됨(MAJOR-3). M_05 SPEC §배선 정책 L90-125는 B안으로 정정됨 (OK). MODULES.md L48는 CR-03 완료 주석 포함 (OK). CR_05 리뷰 cross-reference는 본 리뷰 문서에서 처리 |

---

## 테스트 커버 검증

CR-03 본문 §테스트 계획 11건 기준:

| 테스트 | 구현 위치 | 실효성 평가 |
|---|---|---|
| N-1 정상 조립 | `test_n1_normal_assembly_with_tool_router` (L437-476) | ✅ `ctx.agent_engine is mock_bma_instance`, `ctx.tool_executor is mock_composite` 확인 |
| N-2 extra_tool_specs 전달 | `test_n2_extra_tool_specs_passed_to_build_chat_agent` (L478-516) | ✅ kwargs["extra_tool_specs"] 비교 + 길이 4 + 이름 집합 확인. 같은 tool_router 인스턴스의 `tool_specs.return_value`를 비교하므로 참조 정합성도 담보됨 |
| N-3 composite fallback 연결 | `test_n3_composite_fallback_is_mcp_executor` (L518-556) | ⚠ mock adapter의 `as_upstream_tool_executor` 호출 인자(`kwargs["fallback"]`)만 캡처. 진짜 CompositeToolExecutor의 `_fallback` 속성은 미검증(M_05b 책임). 단위 경계로는 허용 (MINOR-5) |
| N-4 guard idempotency | `test_n4_guard_idempotency` (L559-588) | ⚠ `build_chat_agent.call_count == 1`은 확인되나 load_from_config 재호출 시나리오는 미검증 (MAJOR-2) |
| N-5 degraded 모드 | `test_n5_degraded_mode_no_tool_router` (L591-619) | ✅ `kwargs["extra_tool_specs"] is None`과 `ctx.tool_executor is original_executor` 확인 |
| E-1 예외 전파 | `test_e1_build_chat_agent_exception_propagates` (L626-652) | ✅ `pytest.raises(AgentInitError)` 확인. MINOR-2의 duplicate class 갭은 이 경로에서는 문제되지 않음 (build_chat_agent mock이 직접 예외 던짐) |
| E-2 AgentFactory 미호출 | `test_e2_agent_factory_create_agent_not_called` (L654-683) | ❌ trivially true — load_from_config를 거치지 않음. CR-03의 핵심 주장(MRO 디스패치로 upstream factory 제거)을 기능적으로 증명하지 못함 (MAJOR-1) |
| E-3 재빌드 | `test_e3_rebuild_on_agent_config_change` (L685-713) | ✅ 다른 MagicMock 인스턴스라 `==` 비교가 False → 가드 통과 → call_count == 2. pydantic equality가 아니라 MagicMock identity라는 점에 의존하지만 CR-03 범위에서 유효 |
| A-1 프롬프트 인젝션 보존 | `test_a1_prompt_injection_preserved_as_is` (L719-746) | ✅ `injection in kwargs["system_prompt"]` 확인. sanitize 없음을 고정. 본 모듈이 sanitize 책임 아님을 명확히 함 |
| A-2 동시성 | `test_a2_concurrent_init_agent_no_crash` (L748-800) | ⚠ `call_count in (1, 2)` 허용. 실행 시 `asyncio.sleep(0)` 때문에 사실상 2회 build 되는 것이 관측됨. "결정론적 해석" 주장은 `assert ctx.agent_engine is not None`만으로 얕게 검증. flaky 가능성은 낮지만 "마지막 writer 승리" 정책을 강하게 고정하지는 않음 |
| adapter close 1건 | `test_adapter_close_delegates_to_agent_aclose` (test_adapter.py:149-160) | ✅ `mock_agent.aclose.assert_awaited_once()` — 심플하고 직접적인 위임 검증 |

---

## 빌더가 추가한 부수 변경 평가

- **`pyproject.toml:7-12` starlette/sse-starlette 핀**: 주석이 사유(fastapi 0.116 전이 충돌)와 해결책(`starlette<0.49`, `sse-starlette<3`)을 설명. mcp 1.27.0이 요구하는 `sse-starlette>=1.6.1`과도 양립. 정당한 환경 fix로 판단. 단 MINOR-7로 bundle_deps.sh 반영 증거 필요.
- **`docs/MODULES.md:48` M_01 상태 주석**: "CR-03(2026-04-19): ... 배선 완료" 문구 추가. `✅ DONE`은 유지. CR-05 리뷰 MAJOR-1이 요구한 cross-reference의 절반(`docs/MODULES.md`)은 충족.
- **`specs/M_01_AppCore_SPEC.md` 갱신**: L16 §목적/범위, L61 §EXTEND, L70 §DROP, L93-96, L214-287 §공개 API, L644 §에러 처리, L676 §동시성, L801-807 §DoD, L842, L857, L869, L885, L909, L911 반영. **DoD 중복 표기는 MAJOR-3**. 나머지는 B안 반영 OK.
- **`specs/M_05_LLMAgent_SPEC.md:86, 90-125`**: upstream `AgentFactory.create_agent`를 DROP 목록에 추가, §배선 정책을 CR-03 B안으로 완전 교체. 이전안 기각 이력도 보존. 스펙 표현이 명확하고 책임 분리("M_05는 build_chat_agent/Adapter만 제공, 오버라이드는 M_01 소유")도 명시 — 정합.
- **`src/agent/upstream_adapter.py:88-94` `close()` 메서드**: upstream guard (`hasattr(agent_engine, "close")`) 통과를 목적으로 추가. `await self._agent.aclose()` 위임 1줄 — 간결. 예외 전파 정책은 upstream close가 감싸지 않으므로 aclose에서 던진 예외는 ServiceContext.close가 삼키지 않고 전파 — 이 동작이 의도된 것인지(스펙 명시 없음)는 별도 확인 필요 (기존 L419-425 `aclose`가 자체 try/except로 경고 로그만 남기므로 실질적 누출은 거의 없음).

---

## 검증 실행 결과

- `git status upstream/Open-LLM-VTuber/`: **clean** (nothing to commit)
- `ruff format --check .`: **PASS** (94 files already formatted)
- `ruff check src/app src/agent tests/app tests/agent tests/tool_router`: **PASS** (All checks passed!)
- `mypy src/app src/agent`: **⚠ 기존 1건 존속**
  - 출력: `src/app/config.py: error: Source file found twice under different module names: "app.config" and "src.app.config"`
  - 판단: 환경 문제(pyproject.toml `pythonpath = [".", "src", ...]`에서 src와 루트가 모두 sys.path에 있어 `app`과 `src.app`이 같은 파일을 두 이름으로 참조). CR-03 신규 mypy 에러 0건. 빌더 주장 일치.
- `pytest tests/app tests/agent tests/tool_router -v`: **220 passed, 1 skipped, 6 warnings**
  - 1 skipped: `tests/app/test_service_context.py::TestCR05ToolRouterAssembly::test_n2_tool_specs_length_and_names` (이유: `tool_router import 실패 (환경 문제)`). **CR-03과 무관한 CR-05 테스트이며, 리뷰 지시에 따라 판정에 반영하지 않음.** 다음 critic이 별도 CR에서 추적.
  - 6 warnings: 모두 upstream pydantic deprecation. CR-03과 무관.
- `pytest tests/app/test_service_context.py::TestCR03InitAgentOverride -v`: **10 passed** (N-1, N-2, N-3, N-4, N-5, E-1, E-2, E-3, A-1, A-2 전부)
- `pytest tests/agent/test_adapter.py -v -k close`: **1 passed, 6 deselected** (`test_adapter_close_delegates_to_agent_aclose` PASS)

---

## CR-05 리뷰 MAJOR-1 해소 확인

CR-05 리뷰(`reviews/CR_05_tool_router_wiring_REVIEW.md:23-27`)의 MAJOR-1은 "load_from_config가 CompositeToolExecutor를 self.tool_executor로 세팅하고 build_chat_agent(..., extra_tool_specs=tool_router.tool_specs()) 호출" 미이행을 지적했다.

- **해소 여부**: **YES (경로 이전 후 해소)**.
- **근거**:
  - `src/app/service_context.py:157-162` — `composite = self.tool_router_adapter.as_upstream_tool_executor(fallback=mcp_tool_executor)`, `self.tool_executor = composite`, `extra_specs = self.tool_router.tool_specs()`.
  - `src/app/service_context.py:179-186` — `await build_chat_agent(..., tool_executor=self.tool_executor, extra_tool_specs=extra_specs)`.
  - CR-05 본문 L194-197에서 이미 "CR-04 미승인 시 build_chat_agent 호출부만 보류하고 나머지는 선 진행 가능"을 사전 인가했고, CR-03에서 load_from_config가 아니라 **init_agent 오버라이드**로 배선 경로가 이전됨(CR-05 DoD 5번의 위치 조건은 완화됨, CR-03 §필요 변경 2 주석 참조).
- **단**: CR-05 MAJOR-1이 요구한 `load_from_config` **직접** 재정의 방식은 채택되지 않았다(B안 기각 이력 참조). 실제 재정의 위치는 `init_agent`이나, 전체 LLM tool_call 경로가 composite로 흐르는 최종 목표는 동등하게 달성됨.
- **M_01 AppCore DONE 선언 가능 여부**: **가능**. 단 MAJOR-1·MAJOR-2의 테스트 보강 + MAJOR-3의 DoD 중복 정리를 follow-up TODO로 등록할 것. 현 상태로도 기능·빌드·테스트 관점에서는 PASS.

---

## 검토하지 못한 영역

1. **Windows 실기 smoke**: WSL 환경에서 `mss` + 실 `ScreenshotService` + 실 `ToolRouter` + 실 `build_chat_agent`(Ollama 서버 필요) 경로의 end-to-end 기동은 검증 불가. 특히 `init_agent`가 실제 `load_from_config` 흐름에서 MRO로 디스패치되는지는 **본 Critic이 직접 확인하지 못했다**(MAJOR-1). Windows Ollama 환경에서 기동해 `self.agent_engine`이 `BasicMemoryAgentAdapter`이고 `self.tool_executor`가 CompositeToolExecutor 인스턴스인지 smoke 필요.
2. **`handle_config_switch` 경로**: upstream L472-559가 런타임에 `load_from_config`를 재호출한다. 재호출 시 CR-03 가드와 `_init_mcp_components` 재실행의 상호작용이 테스트에 부재. 리뷰 요청 §A-3에서 "self.app_config은 여전히 not None이어야 정상"이라 언급했는데, handle_config_switch 경로는 load_app_services를 다시 부르지 않으므로 app_config는 보존됨을 코드 읽기로 확인했으나 테스트 부재.
3. **`tests/tool_router/__init__.py`가 pytest collect 시 `tool_router` 이름을 shadowing하는 문제**: CR-03 본체와 무관하나, `test_n2_tool_specs_length_and_names` skip의 근본 원인. 본 리뷰 지시에 따라 판정 반영하지 않음. 다음 critic 또는 별도 CR(예: CR-06)에서 추적 필요.
4. **`BasicMemoryAgentAdapter.close()`의 예외 처리**: upstream close가 `if self.agent_engine and hasattr(...):` 이후 try/except 없이 `await self.agent_engine.close()`를 호출한다. 우리 `close()`가 예외를 던지면 upstream close의 남은 경로(현재는 없음)와 상위 정리 루틴에 영향을 줄 수 있다. 본 Critic은 GemmaChatAgent.aclose가 자체 try/except를 갖는다는 점을 확인하고 영향 없음으로 판단했으나, 제3의 가짜 agent 구현체가 `aclose`를 예외로 던지면 close 체인 전파가 일어날 수 있음. MINOR 이하로 분류.
5. **`scripts/bundle_deps.sh`에 starlette/sse-starlette 관련 변경 필요 여부**: 본 Critic이 해당 스크립트 실제 실행/검토 안 함. MINOR-7 참조.
6. **`src.agent.errors` vs `agent.errors` duplicate class 가능성**: 현재는 실제 경로에서 문제되지 않지만, mypy 에러와 테스트 import 경로 비일관성의 부분 증거. MINOR-2 참조.

다음 fresh critic이 "CR-03 테스트 실효성 보강 CR"을 리뷰할 때 위 1·2·4를 우선 검토할 것.

---

## 최종 의견

구현 코드(`src/app/service_context.py`, `src/agent/upstream_adapter.py`)는 스펙과 CR-03 본문의 스텝 1~8을 빠짐없이 반영했고 정합성 측면에서 결함이 없다. 14개 DoD 중 실질 검증 가능한 12개는 ✅, 나머지 2개(#6 E-2, #14 스펙 중복)는 ⚠ 수준이며 "조건부 PASS"로 M_01 DONE 선언은 유지 가능하다. 그러나 **E-2가 CR-03의 핵심 주장을 기능적으로 검증하지 못한다**는 MAJOR-1은 Windows 실기 smoke 또는 `load_from_config` 통합 단위 테스트 추가로 반드시 후속 보완할 것. CR-05 리뷰 MAJOR-1은 "배선 경로 이전" 형태로 해소됐다.

**판정 한 줄 요약: PASS (조건부) — 코드·DoD·테스트는 계약을 충족하나, E-2·N-4의 테스트 실효성과 M_01 SPEC DoD 중복 표기 3건을 follow-up CR로 보강할 것.**
