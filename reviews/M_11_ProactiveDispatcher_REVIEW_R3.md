# M_11 ProactiveDispatcher Critic Review — Round 3 (Fast-Follow 재검수)

Date: 2026-04-19
Verdict: **PASS**
Previous verdict: PASS (reviews/M_11_ProactiveDispatcher_REVIEW_R2.md)

## Summary

R2에서 PASS 판정받은 상태에서 MINOR 6건(#1~#6)에 대한 fast-follow 변경분을
fresh session으로 mutation 관점에서 재검증. 대상 변경은 **커밋되지 않은
작업 트리 상태**(`git status`: dispatcher.py / types.py / test_dispatcher.py /
test_service_context.py 4개 modified)이며, 주장된 4개 변경이 모두 실제로
존재함을 `git diff`로 대조 확인했다.

- `src/proactive/types.py`: `TOPICS: frozenset[str]` → `frozenset[ProactiveTopic]` 전환 ✓
- `src/proactive/dispatcher.py:346`: `# type: ignore[arg-type]` 주석 1줄 제거 ✓ (로직 변경 없음)
- `tests/proactive/test_dispatcher.py`: 신규 `TestConstructorValidationExtra` 1건 +
  `TestErrorBranches` 3건 (총 +4건) ✓
- `tests/app/test_service_context.py`: `TestM11ProactiveDispatcherWiring::test_proactive_dispatcher_none_when_calendar_or_idle_monitor_missing` parametrize 2분기 재작성 + `test_proactive_dispatcher_deps_wired`에 `assert callable(...)` 1줄 추가 + `TestActiveClientSendTextLateBinding` 신규 ✓

Fast-follow 대상 10개 테스트 전건 PASS(파이썬 3.12 + APScheduler 설치 venv).
`pytest tests/proactive/ tests/app/` 전체 177건 PASS. `ruff check` 통과.
`mypy src/proactive/` **Success: no issues found in 5 source files** — `# type: ignore` 제거가 타입 회귀를 만들지 않음.

mutation 검증을 **실제 코드 수정·테스트 실행·복원** 방식으로 수행했고
(아래 #2, #3, #6a, #6b, #6c 실증), 주장된 mutation 탐지 능력을 전부 확인.

MINOR #6의 잔여 미커버 분기(`stop()`의 `on_event(None)` 예외 L202-203,
`_minutes_until` tz-naive L390)와 R2에서 포착 못한 `set_dnd` TypeError 분기
L269가 coverage missing으로 남지만, 모두 non-blocking이며 차기 fast-follow
대상으로 기록한다.

## MINOR 재검증 결과

### MINOR #1 — `reminder_check_interval_seconds` 경계 검증 → ✓ 해소

**검증**: `tests/proactive/test_dispatcher.py:593~613`의 `test_m3e`는 하한(`=0`)과
상한(`=3601`) 양쪽을 독립 `pytest.raises(ValueError, match="reminder_check_interval_seconds")`
컨텍스트로 분리 검증. 두 경계 모두 커버.

**Coverage 실증**: fast-follow 적용 후 `src/proactive/dispatcher.py` missing 라인에
L94-98이 **더 이상 나타나지 않음**(R2 리포트의 L95 Missing 제거됨).

**Mutation 탐지**: L94 조건 블록(`if not (1 <= reminder_check_interval_seconds <= 3601):`)을
삭제하면 `ProactiveDispatcher(... reminder_check_interval_seconds=0)` 호출이
ValueError 없이 통과 → `pytest.raises` FAIL. ✓

### MINOR #2 — 배선 분기 mutation 탐지 → ✓ 해소 (실증)

**검증**: `tests/app/test_service_context.py:486~551`의 parametrize 2분기.
- `calendar_missing`: `sys.modules["calendar_service.service"].CalendarService = MagicMock(side_effect=RuntimeError("DB 없음"))` 주입 → `service_context.py:233`의 `CalendarService(...)` 호출이 RuntimeError → L235 `except`가 `self.calendar_service = None` 설정. 이후 L287 `if calendar_service is not None and ...`가 False → `proactive_dispatcher = None`.
- `idle_monitor_missing`: `patch("app.service_context.IdleMonitor", side_effect=RuntimeError("pynput 없음"))` → L276의 `IdleMonitor(...)`가 RuntimeError → L282 `except`가 `self.idle_monitor = None`. 이후 L287 조건 False → `proactive_dispatcher = None`.

**Mutation 탐지 실증**:
1. `and` → `or` mutation 적용 → 두 parametrize 케이스 모두 FAIL 실증.
   ```
   FAILED ...test_proactive_dispatcher_none_when_calendar_or_idle_monitor_missing[calendar_missing]
   FAILED ...test_proactive_dispatcher_none_when_calendar_or_idle_monitor_missing[idle_monitor_missing]
   ```
2. 배선 블록 `if ... :` → `if True:` mutation 적용 → 두 parametrize 케이스 모두 FAIL 실증.

양쪽 분기가 **독립적으로** mutation을 탐지한다는 R2의 요구를 완전 충족.

**경미 관찰**: `idle_monitor_missing` 케이스에서 `calendar_service`는 실제로 정상 생성되어 SQLite 파일이 test 작업 디렉토리에 남을 수 있다. 기존 `TestM10IdleMonitorWiring`/`TestM09CalendarServiceWiring`도 같은 패턴이며 CI가 이미 허용하는 동작이므로 별도 결함은 아님.

### MINOR #3 — `_get_active_client_send_text` late-binding 회귀 → ✓ 해소 (실증)

**검증**: `tests/app/test_service_context.py:554~597`의 `test_active_ws_late_binding`은 5단계(ws1 세팅 → ws1.send_text 1회 호출 → ws2 교체 → ws2.send_text 호출/ws1 count 변화 없음 → None 설정 시 어느 쪽도 호출 안 됨)를 모두 검증.

**Mutation 탐지 실증**: 콜러블 외부에서 `ws_captured = self._active_ws`로 early-binding 캡처하는 mutation 적용 → FAIL 실증.
```
FAILED tests/app/test_service_context.py::TestActiveClientSendTextLateBinding::test_active_ws_late_binding
```

### MINOR #4 — `send_text` callable assertion → ✓ 해소

**검증**: `tests/app/test_service_context.py:480`에 `assert callable(captured_kwargs["send_text"]), "send_text가 callable이 아님"` 1줄 추가. git diff로 존재 확인.

**Mutation 탐지 논리**: `service_context.py:294`의 `send_text=self._get_active_client_send_text()`를 `send_text=None`으로 바꾸면 `captured_kwargs["send_text"] = None` → `callable(None) == False` → assertion FAIL. 실제로 ProactiveDispatcher 생성자의 L83~84 `if not callable(send_text): raise TypeError`가 우선 발동해 `ProactiveDispatcher()`가 TypeError 전파되고 `load_app_services`의 L300 `except Exception` 캐치로 `proactive_dispatcher = None`이 되어 다른 assertion(`ctx.proactive_dispatcher is mock_pd_instance`)이 먼저 깨지지만, callable 체크가 이중 방어선으로 추가된 점이 회귀 안정성을 향상.

### MINOR #5 — `TOPICS: frozenset[ProactiveTopic]` + `# type: ignore` 제거 → ✓ 해소

**검증 1**: `src/proactive/types.py:17`가 `frozenset[ProactiveTopic]`로 정밀화. 런타임 값은 동일(4개 문자열 Literal).

**검증 2**: `src/proactive/dispatcher.py:346`에서 `await self.emit(topic, context={})`의 `# type: ignore[arg-type]` 제거 확인(`grep "type:\s*ignore" src/proactive/dispatcher.py` → 0건). 제거가 타당한 이유: L345 `if topic in TOPICS:`에서 `TOPICS`가 이제 `frozenset[ProactiveTopic]`이므로 narrowing으로 `topic`이 `ProactiveTopic`으로 좁혀져 emit의 첫 인자 타입이 맞음.

**Mypy 실증**: `python -m mypy src/proactive/` → **Success: no issues found in 5 source files**.

**Validator "pre-existing" 주장 재검증**:
- Validator가 보고한 `src/app/ws_route.py: Source file found twice` 에러는 재현 안 됨.
- 대신 `mypy src/` 전체 실행 시 `src/vector_search/types.py: Source file found twice under different module names: "app.config" and "src.app.config"` 에러 발견 — 이는 M_07 VectorSearch의 MYPYPATH 구성 이슈이며 M_11과 무관.
- `git log --oneline -5 src/app/ws_route.py` 결과: 마지막 변경은 `e59046a feat(M_01): AppCore`. M_11 fast-follow와 완전히 무관.
- 결론: validator의 파일 경로 보고는 부정확했으나("ws_route.py"가 아닌 "vector_search/types.py"), **M_11 fast-follow와 무관한 pre-existing 이슈**라는 결론은 정확. MINOR #5는 문제 없이 해소.

### MINOR #6 — 에러 처리 분기 미커버 → ⚠️ 부분 해소 (3/5)

R2 리포트의 L197-198, L202-203, L348, L390, L419 중 3개 분기만 커버:

| 분기 | 라인 | fast-follow 테스트 | 상태 |
|---|---|---|---|
| scheduler.shutdown 예외 | L197-198 | `test_stop_shutdown_exception_swallowed` | ✓ (mutation 실증) |
| idle_monitor.on_event(None) 예외 | L202-203 | (없음) | ⚠️ 여전히 미커버 |
| _on_idle_event unknown topic | L348 | `test_on_idle_event_unknown_topic_warns` | ✓ (mutation 실증) |
| _minutes_until tz-naive | L390 | (없음) | ⚠️ 여전히 미커버 |
| _cleanup tz-naive ev_start | L418-419 | `test_cleanup_handles_tz_naive_start` | ✓ (mutation 실증) |

**Mutation 실증 #6a (shutdown 예외)**: `dispatcher.py:198`의 `logger.warning(...)`을 `raise exc`로 바꾸면 `await dispatcher.stop()`이 RuntimeError 전파 → 테스트 FAIL.
```
FAILED tests/proactive/test_dispatcher.py::TestErrorBranches::test_stop_shutdown_exception_swallowed
```
Builder의 "loguru는 caplog에 안 잡혀서 부수 효과로 검증"이라는 설계는 정확. `_started is False` + `idle_monitor._callback is None` 두 assertion이 shutdown 예외 후에도 L200~205가 계속 실행됨을 검증 — mutation이 `raise exc`였다면 이후 라인이 실행 안 되어 `idle_monitor._callback is None` assertion FAIL. ✓

**Mutation 실증 #6b (unknown topic)**: `dispatcher.py:345`의 `if topic in TOPICS:`를 `if True:`로 바꾸면 `emit("bogus_topic", {})` → emit 내부 L225-226의 `raise ValueError(f"unknown topic...")` 발동 → 테스트 FAIL.
```
FAILED tests/proactive/test_dispatcher.py::TestErrorBranches::test_on_idle_event_unknown_topic_warns
```
테스트는 `send_text.assert_not_called()` 와 `dispatcher._enabled is True`를 모두 확인. ✓

**Mutation 실증 #6c (tz-naive cleanup)**: `dispatcher.py:418`의 `if ev_start.tzinfo is None:`를 `if False:`로 바꾸면 tz-naive가 유지되고 L421 `ev_start + duration_td < now_utc` 비교에서 TypeError(aware vs naive) 발생 → L423 `except`가 catch해 `logger.debug`만 남기고 **`to_remove` 추가 안 함** → assertion `77 not in _notified_reminders` FAIL.
```
FAILED tests/proactive/test_dispatcher.py::TestErrorBranches::test_cleanup_handles_tz_naive_start
```
테스트 설계가 정확한 분기를 타고 있음을 실증. ✓

**미해소 잔여 2건**:
- **L202-203 (`on_event(None)` 예외 삼킴)**: coverage missing 여전. fast-follow가 `_bad_on_event(None) → RuntimeError`를 세팅하는 시나리오를 추가하지 않음. 회귀 방어 누락.
- **L390 (`_minutes_until` tz-naive 분기)**: coverage missing 여전. `_minutes_until`에 tz-naive start를 전달하는 단위 테스트 부재. `_cleanup`의 tz-naive 분기(L418-419)는 커버됐으나 `_minutes_until`의 것은 미커버.

`test_cleanup_handles_tz_naive_start` 테스트 docstring에 "25시간 전"이라는 잘못된 주석이 있음(실제로는 2000-01-01이므로 26년 전). 테스트 동작엔 영향 없음, 주석 품질만 경미 결함.

## New Findings (fast-follow 변경에서 새로 발견)

### Blocking
없음.

### MAJOR
없음.

### MINOR

1. **[MINOR] R2 MINOR #6의 L202-203 / L390 2건 미해소**
   Fast-follow가 R2 MINOR #6의 5개 분기 중 3개만 해소하고, `stop()`의 `idle_monitor.on_event(None)` 예외 삼킴(L202-203)과 `_minutes_until`의 tz-naive 분기(L390)는 여전히 coverage missing. Builder 보고에서 "MINOR #6a/b/c"로 3건 추가했다고 분명히 명시했으므로 고의 범위 제한이지만, R2가 `coverage missing` 항목을 5건 나열한 만큼 2건은 다음 fast-follow 라운드로 이관 필요.
   권고: 
   - `test_stop_on_event_none_exception_swallowed` 1건 (idle_monitor.on_event가 RuntimeError 발생 시에도 `_started=False`로 정리됨).
   - `test_minutes_until_tz_naive_start` 1건 (`dispatcher._minutes_until(datetime(2026, 1, 1))`처럼 tz-naive 직접 주입해 UTC fallback 커버).

2. **[MINOR] `set_dnd` TypeError 분기 L269 미커버**
   R2에서 언급되지 않았으나 `src/proactive/dispatcher.py:268-269`의 `if not isinstance(enabled, bool): raise TypeError(...)` 분기도 coverage missing. fast-follow 전후 동일하게 Missing. 생성자 검증 4분기(M3a~e)와 짝을 이루는 공개 API 가드이므로 테스트 1건 권장.
   권고: `test_set_dnd_non_bool_raises_typeerror` — `dispatcher.set_dnd("yes")` → `pytest.raises(TypeError)`.

3. **[MINOR] `test_cleanup_handles_tz_naive_start` docstring 주석 부정확**
   `tests/proactive/test_dispatcher.py:668~672` docstring에 "25시간 전 (tzinfo=None) — 어느 시간대에서도 '과거'"라고 적혀 있으나 실제 `datetime(2000, 1, 1, 0, 0, 0)`은 약 **26년 전**. 테스트 동작에는 문제 없고 assertion도 정확하지만, 차기 유지보수자가 오해할 수 있다. docstring 정정 권장.

4. **[MINOR] `test_cleanup_handles_tz_naive_start`의 fallback 분기 의존성**
   MINOR #6c mutation 분석 중 발견: tz-naive 분기(L418-419)를 우회한 mutation이 `if False:` 이면 L421에서 TypeError → L423 `except`로 catch되어 `to_remove`에 추가 안 됨. 테스트가 FAIL하는 이유는 `77 not in _notified_reminders` assertion 깨짐 때문. 이는 의도한 mutation 탐지 경로이지만, 테스트가 **tz-naive 분기의 정상 동작(UTC 간주)**을 검증하는 게 아니라 **해당 분기가 없으면 TypeError가 발생해 cleanup 실패**라는 간접 증거로 검증한다. 더 강한 회귀 방어를 원한다면 L419 분기 실행이 UTC 치환을 **정확히 하는지**(예: naive 00:30이 UTC 00:30으로 치환됨)를 직접 비교하는 테스트가 바람직하나, 현 테스트도 최소 요건은 충족.

5. **[MINOR] type hint 경미**
   `src/proactive/dispatcher.py:113`의 `self._timezone: _ZoneInfo = timezone if timezone is not None else _ZoneInfo("Asia/Seoul")`는 TYPE_CHECKING 블록의 `ZoneInfo`와 런타임 `_ZoneInfo`가 별칭이지만 형식적으로 서로 다른 symbol이라 mypy가 관대하게 통과시킨 것. 이번 fast-follow와 무관한 기존 코드지만, 차기 리팩토링 시 통일 권장.

## mypy 이슈 판정: "M_11과 무관한 pre-existing"

**결론: 유효하나 validator의 파일 경로 보고는 부정확**.

- `mypy src/proactive/` 단독 실행: **PASS (5 files clean)** — fast-follow가 mypy 회귀를 만들지 않음.
- `mypy src/` 전체 실행: `src/vector_search/types.py: Source file found twice under different module names: "app.config" and "src.app.config"` — 이는 M_07 VectorSearch의 패키지 설정 이슈로 추정. `src/app/ws_route.py`와 무관.
- `git log --oneline -5 src/app/ws_route.py` → 마지막 변경 `e59046a feat(M_01)`. M_11 b4437f9 commit보다 이전.
- validator의 "pre-existing"이라는 결론 자체는 유효(M_11 fast-follow는 mypy 회귀 0건). 다만 validator가 **다른 파일(ws_route.py vs vector_search/types.py)을 보고**했다는 점은 validator 파이프라인의 사소한 부정확성으로 기록.

## Recommendation

**PASS**. 다음을 근거로 한다:

1. R2 MINOR #1, #2, #3, #4, #5 (5건)는 **완전 해소**. 그중 #2/#3/#5/#6 일부는 mutation 테스트를 실제로 코드 수정·복원 방식으로 돌려 탐지 능력 실증.
2. R2 MINOR #6 (5분기 중 3분기 해소). 잔여 2분기는 비차단.
3. 전 177건 테스트 PASS, ruff clean, mypy(src/proactive) clean.
4. coverage 90% → 92% 상승.

`docs/MODULES.md:382`의 상태는 이미 `✅ DONE`이므로 갱신 불필요.

**차기 fast-follow PR 권고 (선택)**:
- New Findings MINOR #1 (L202-203, L390 커버)
- New Findings MINOR #2 (set_dnd TypeError 커버)
- New Findings MINOR #3 (docstring 주석 정정)

**커밋 권고**: 현재 fast-follow 4개 파일이 작업 트리 modified 상태로 남아 있음(`git status`). 검수 통과했으므로 `fix(M_11): ...` 형태로 커밋 필요.

## 검토하지 못한 영역

1. **실제 AsyncIOScheduler 런타임** — 여전히 FakeScheduler 기반. R2와 동일하게 integrator 범위.
2. **FastAPI startup hook의 `proactive_dispatcher.start()` 호출** — `main.py` 또는 `server.py` 진입점 미확인. R2에서도 다음 Critic/Integrator로 위임된 영역.
3. **mypy 전체 pass** — `mypy src/` 실행 시 vector_search/types.py에서 duplicate module name 에러. M_11 범위는 아니지만 M_07 리뷰어 또는 플랫폼 이슈 해결 필요.
