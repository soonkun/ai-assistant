# M_11 ProactiveDispatcher Critic Review — Round 2

Date: 2026-04-19
Verdict: **PASS**
Previous verdict: FAIL (reviews/M_11_ProactiveDispatcher_REVIEW.md)

## Summary

Fresh Round 2 검수 결과, R1의 Blocking 4건(B1~B4) + MAJOR 5건(M1~M5)이 모두 실질적으로 해소됐다. `ws_handler.py`의 D-13 라이프사이클 결함(super() 순서·handle_disconnect 미오버라이드) 양쪽 모두 올바른 순서·`is` 비교·finally 블록으로 재설계됐으며, R1에서 0건이던 라이프사이클 회귀 테스트가 4건(`TestActiveWsLifecycle.test_m5a~d`) 추가되었다. `tests/app/test_service_context.py::TestM11ProactiveDispatcherWiring`에 3건의 배선 회귀 테스트가 신규되었고, 이 중 앞 2건은 M_11 배선 블록 삭제 mutation을 실제로 탐지한다. `docs/MODULES.md §M_11` 공개 API 블록이 스펙 §15.1 신규 인자/`set_dnd` 메서드/payload 4키로 업데이트됐으며, DoD 요구대로 상태는 `🔲 TODO`를 유지했다. M1~M5 MAJOR 전건에 대응하는 신규 테스트 클래스 4개(`TestCleanupNotifiedReminders`, `TestCalendarExceptionSwallowed`, `TestConstructorValidation`, `TestEventReminderDedupFixed`)가 추가되어 테스트 수가 39→103건으로 늘었고, coverage도 85%→90%로 상승했다. APScheduler 설치 환경에서 전 103건 PASS, ruff/mypy(src/proactive/) 클린.

Blocking은 없다. 다만 mutation 관점에서 일부 비차단 결함이 관찰되므로 경미 결함에 기록한다.

## Previous Findings Re-verified

### B1 — `handle_new_connection` super() 순서 (CRITICAL R1 #1)

**실제 파일 확인: `src/app/ws_handler.py:61~72`**
```python
async def handle_new_connection(self, websocket: WebSocket, client_uid: str) -> None:
    await super().handle_new_connection(websocket, client_uid)
    self._app_ctx._active_ws = websocket
```

- super() 호출이 먼저, `_active_ws` 갱신이 뒤. 순서 반전 시 R1 버그가 재현된다.
- try/except로 예외를 삼키지 않음 — super()의 예외가 자연스럽게 전파되어 FastAPI handle_websocket_communication에서 처리.
- **Mutation 재현 테스트**: `test_m5b_active_ws_not_updated_on_super_exception`
  (`tests/app/test_ws_handler.py:516~536`)가 `WebSocketHandler.handle_new_connection`을 monkeypatch로 `side_effect=RuntimeError("connection init failed")`해 super()가 raise하는 상황을 재현한다. 원본 버그(super() 전 `_active_ws` 갱신)를 되돌리면 이 테스트가 FAIL한다. **B1 실질 해소 ✓**.

### B2 — `handle_disconnect` 오버라이드 + `_active_ws` 정리 (CRITICAL R1 #2)

**실제 파일 확인: `src/app/ws_handler.py:74~92`**
```python
async def handle_disconnect(self, client_uid: str) -> None:
    disconnecting_ws = getattr(self, "client_connections", {}).get(client_uid)
    async with self._tasks_lock:
        await self._cancel_continuous_task(client_uid)
    try:
        await super().handle_disconnect(client_uid)
    finally:
        if disconnecting_ws is not None and self._app_ctx._active_ws is disconnecting_ws:
            self._app_ctx._active_ws = None
```

- upstream `handle_disconnect` 시그니처(`client_uid: str`)와 일치(`upstream/.../websocket_handler.py:280`).
- `is` 식별자 비교 사용 — 다중 클라이언트에서 구 WS disconnect가 최신 `_active_ws`를 파괴하지 않음.
- super() 호출 후 finally 블록에서 정리 — upstream 부수 효과(client_connections/client_contexts pop, 대화 취소, context.close)가 모두 선행.
- **순서 우려**: super()가 먼저 client_connections에서 ws를 pop하므로, 본 오버라이드는 super() 호출 전에 `disconnecting_ws`를 미리 캡처한다(L82). 타당한 설계.
- **다중 클라이언트 회귀**: `test_m5d_second_client_disconnect_preserves_active_ws`(`tests/app/test_ws_handler.py:553~581`) — ws1→ws2 순서 연결, _active_ws=ws2 상태에서 ws1 disconnect. `is` 비교이므로 _active_ws는 ws2 유지. `==` 같은 값 비교였다면 MagicMock 특성상 모호해질 수 있으나, `is`는 명확히 통과. **B2 실질 해소 ✓**.

### B3 — `TestM11ProactiveDispatcherWiring` 회귀 테스트 (CRITICAL R1 #3)

**실제 파일 확인: `tests/app/test_service_context.py:382~499`**

테스트 3건 존재:
1. `test_proactive_dispatcher_none_before_load_app_services` — __init__ 후 None 확인.
2. `test_proactive_dispatcher_injected_on_load_app_services` — `sys.modules["proactive"]` mock + `load_app_services` 호출 후 `ctx.proactive_dispatcher is mock_pd_instance` 검증. **Mutation 검증**: M_11 배선 블록(service_context.py L286~307)을 완전히 삭제하면 `ctx.proactive_dispatcher`가 None을 유지하고 assertion 실패 → FAIL. **검출 가능 ✓**.
3. `test_proactive_dispatcher_deps_wired` — `capture_init` side_effect로 kwargs를 포착해 `calendar is ctx.calendar_service`, `idle_monitor is ctx.idle_monitor` 객체 동일성 검증. **Mutation 검증**: 배선에서 calendar=None을 넣으면 assertion 실패 → FAIL. **검출 가능 ✓**.

**Pytest 실행 확인**: APScheduler 설치 환경에서 `pytest tests/app/test_service_context.py::TestM11ProactiveDispatcherWiring` 전 3건 PASS. M_10 R2의 openai 수집 실패 선례 패턴은 **재발하지 않았다**. 단, 본 venv에서 `openai/pysbd/langdetect/requests/websockets/APScheduler` 미설치 시 수집·실행 실패 — 이는 환경 이슈이지 구조 결함 아님(Builder/Validator 환경은 정상 추정). **B3 실질 해소 ✓**.

### B4 — `docs/MODULES.md` §M_11 API 블록 갱신 (CRITICAL R1 #4)

**실제 파일 확인: `docs/MODULES.md:379~415`**

- 상태: `🔲 TODO` **유지 확인** — DoD가 Critic PASS 후 `✅ DONE` 전환을 요구하므로 올바른 상태.
- 공개 API 블록이 스펙 §15.2 치환 문구와 **정확히 일치**: `timezone`, `reminder_check_interval_seconds`, `dnd_enabled`, `clock`, `scheduler` 5개 신규 인자 + `set_dnd(enabled: bool) -> None` 메서드 반영.
- Payload 4키 스키마(`{type, text, topic, context}`)가 L410 "비고" 영역에 명시.
- 쿨다운은 토픽별 독립/DND 이중 체크 서술 포함.
- ✅ DONE으로 **몰래 전환되지 않았다**(L382). **B4 실질 해소 ✓**.

### M1 — `_cleanup_notified_reminders` 회귀 테스트 (MAJOR R1 #1)

**`tests/proactive/test_dispatcher.py:378~437`에 3건 추가:**
- `test_m1a_expired_event_removed_after_ttl` — 과거 이벤트(start 1h ago + duration 30m) → 제거.
- `test_m1b_active_event_preserved_within_ttl` — 미래 이벤트 → 보존.
- `test_m1c_deleted_event_removed` — get_event None 반환 → 제거.

**Mutation 검증**: `_cleanup_notified_reminders`를 no-op으로 바꾸면 m1a/m1c가 FAIL(제거 안 됨). 정상 분기와 삭제 분기 양쪽 탐지 가능. **M1 실질 해소 ✓**.

주의: tz-naive 분기(dispatcher.py L419)는 여전히 미커버. 실무 영향은 적음(Calendar Event.start는 tz-aware 규약).

### M2 — calendar 예외 삼킴 테스트 (MAJOR R1 #2)

**`tests/proactive/test_dispatcher.py:445~483`에 2건 추가:**
- `test_m2a_morning_briefing_calendar_exception_swallowed` — BrokenCalendar가 get_events에서 RuntimeError. 예외 전파 없음 + send_text 미호출.
- `test_m2b_event_reminder_calendar_exception_swallowed` — events_due_within에서 RuntimeError. 동일.

**Mutation 검증**: except 블록을 `raise` 하는 버그로 바꾸면 두 테스트 모두 FAIL. **M2 실질 해소 ✓**.

### M3 — 생성자 검증 4분기 (MAJOR R1 #3)

**`tests/proactive/test_dispatcher.py:491~531`에 4건 추가:**
- `test_m3a`: send_text non-callable → TypeError (L84) ✓
- `test_m3b`: morning_time 포맷 불량 → ValueError (L87 _parse_morning_time) ✓
- `test_m3c`: reminder_lead_minutes=0 → ValueError (L90) ✓
- `test_m3d`: cooldown_min=0 → ValueError (L99) ✓

**부분 해소**: R1이 명시한 "생성자 검증 4분기 (84/91/95/100)"는 4개 줄을 가리켰다. L84/L91/L100은 커버됐으나 **L95 `reminder_check_interval_seconds` 범위 검증은 여전히 미커버**(coverage report에서도 L95 Missing). Builder 보고는 "4분기"라고 했으나 실제로는 3분기 + morning_time이다. 경미 결함에 기록(아래 Non-blocking #1). **M3 대부분 해소, 일부 간극 ⚠️**.

### M4 — `test_e5` dedup 재검증 (MAJOR R1 #4)

**`tests/proactive/test_dispatcher.py:539~582`에 신규 `TestEventReminderDedupFixed::test_m4_dedup_blocks_second_emit_after_cooldown` 추가:**

```python
clock = FakeClock(initial=datetime.now(tz.utc))
# ...
clock.advance(timedelta(minutes=1, seconds=1))  # cooldown(1분) + 1초
await dispatcher._job_event_reminder()  # 두 번째 틱
# send_text 호출 수가 여전히 1 — _notified_reminders 드롭 증명
```

**Mutation 검증**: `_notified_reminders` set을 제거하거나 `ev.id in self._notified_reminders` 체크를 `False`로 바꾸면, 쿨다운은 이미 통과했으므로 두 번째 emit이 성공해 send_text 호출 수=2. 테스트 assertion `second_call_count == first_call_count` 실패 → FAIL. **dedup 메커니즘 자체의 회귀가 실제로 잡힌다 ✓**.

기존 `test_e5_event_reminder_dedup`(L241~256)은 그대로 유지되어 쿨다운+dedup 이중 보호를 관찰하지만 dedup 전용은 M4 새 테스트가 맡는다. **M4 실질 해소 ✓**.

### M5 — `_active_ws` 라이프사이클 4건 (MAJOR R1 #5)

**`tests/app/test_ws_handler.py:470~581`에 `TestActiveWsLifecycle` 4건:**
- `test_m5a_active_ws_set_on_successful_connection` — happy path (B1 정방향) ✓
- `test_m5b_active_ws_not_updated_on_super_exception` — super 예외 시 갱신 안 됨 (B1 반례) ✓
- `test_m5c_active_ws_none_after_disconnect` — disconnect 후 None (B2 정방향) ✓
- `test_m5d_second_client_disconnect_preserves_active_ws` — is 비교 보존 (B2 반례) ✓

모든 테스트가 `AppWebSocketHandler` 실제 인스턴스를 사용하고 upstream 메서드만 `patch.object`로 mock. 라이프사이클 mutation 재현 능력 충분. **M5 실질 해소 ✓**.

## Spec Alignment

### §4 공개 API

| 스펙 항목 | 구현 위치 | 상태 |
|---|---|---|
| `ProactiveTopic` Literal 4종 | `src/proactive/types.py:8` | ✅ |
| `TOPICS` frozenset | `src/proactive/types.py:17` (타입은 `frozenset[str]`) | ⚠ 타입 정밀도 |
| `__init__` keyword-only 11인자 | `dispatcher.py:46~60` | ✅ |
| async `start/stop/emit`, sync `set_dnd` | `dispatcher.py:134/186/208/260` | ✅ |
| `SendTextCallback` = `Callable[[dict[str,Any]], Awaitable[None]]` | `dispatcher.py:28` | ✅ |
| 3.12 타입 힌트 (`list/dict/X \| None`) | 전체 일관 | ✅ |

### §5 알고리즘

| 항목 | 구현 위치 | 상태 |
|---|---|---|
| 잡 2종 등록 (cron+interval, max_instances=1, coalesce=True) | `dispatcher.py:354~383` | ✅ |
| misfire_grace_time 600/60 | `dispatcher.py:372,382` | ✅ |
| `_job_morning_briefing` → `get_events` → `emit` | `dispatcher.py:278~304` | ✅ |
| `_job_event_reminder` → `events_due_within` + `_notified_reminders` | `dispatcher.py:306~339` | ✅ |
| `_on_idle_event(topic)` — idle_rest/overwork | `dispatcher.py:341~348` | ✅ |
| `emit` 순서 (enabled→topic→DND→cooldown→compose→send→update) | `dispatcher.py:208~258` | ✅ |
| asyncio.Lock로 emit 원자성 (D-12) | `dispatcher.py:128, 228` | ✅ |
| `_cleanup_notified_reminders` (§5.3.1) | `dispatcher.py:394~426` | ✅ + 테스트 3건 |

### §6.3 결정 사항

| ID | 검증 | 상태 |
|---|---|---|
| D-1 하드코딩 템플릿, LLM 호출 없음 | `messages.py` 리터럴, LLM import 0건 | ✅ |
| D-2 DND 이중 (self + idle_monitor) | `dispatcher.py:268~272` | ✅ |
| D-3 토픽별 쿨다운 | `_last_emitted_at: dict[ProactiveTopic, datetime]` | ✅ |
| D-4 misfire_grace_time | cron 600, interval 60 | ✅ |
| D-5 payload 4키 | `dispatcher.py:243~248` | ✅ |
| D-7 send_text 예외 삼킴 + False | `dispatcher.py:250~254` | ✅ |
| D-8 APScheduler 실패 → `_enabled=False` | `dispatcher.py:150~157, 166~173` | ✅ |
| D-9 scheduler/clock DI | 생성자 주입 | ✅ |
| D-11 IdleEvent/ProactiveTopic 문자열 공유 | "idle_rest"/"overwork" 동일 | ✅ |
| D-12 단일 asyncio.Lock | `dispatcher.py:128, 228` | ✅ |
| **D-13** `AppWebSocketHandler._active_ws` + `_active_client_send_text` | `ws_handler.py:61~92`, `service_context.py:55~74` | ✅ (R1 대비 완전 재설계) |

### §7 송신 페이로드

- 4키 스키마 `{type, text, topic, context}` 정확 (dispatcher.py:243~248).
- upstream `conversation_handler.py:35~64` 직접 재확인: `msg_type == "ai-speak-signal"` 조건만, 추가 키는 무시 → 하위 호환 ✓.
- `_active_client_send_text`가 `json.dumps(payload)`로 WebSocket 직렬화 — D-13 §8.2 계약과 일치.

### §8 에러 처리

| 상황 | 구현 | 테스트 |
|---|---|---|
| `__init__` 파라미터 위반 (L84/91/95/100) | ValueError/TypeError | **M3a~d 4건** (L95 미커버) |
| `start()` scheduler.start 예외 | `_enabled=False` + return | A-1 |
| `stop()` shutdown 예외 | logger.warning + swallow | 미커버 (L197~198) |
| `emit` send_text 예외 | logger.error + False | A-2 |
| `_job_morning_briefing` calendar 예외 | logger.error + return | **M2a** |
| `_job_event_reminder` events_due_within 예외 | logger.error + return | **M2b** |
| IdleMonitor 콜백 unknown topic | logger.warning | 미커버 (L348) |

### §10 테스트 최소

| 카테고리 | 요구 | 구현 |
|---|---|---|
| 정상(N) | ≥7 | 7 (N-1~N-7) ✓ |
| 엣지(E) | ≥7 | 7 (E-1~E-7) ✓ |
| 적대(A) | ≥4 | 4 (A-1~A-4) ✓ |
| 추가(M) | (R1 후속) | 12 (M1×3, M2×2, M3×4, M4×1, M5×4(ws)) |
| 합계 | 18 | 103 테스트 PASS, coverage 90% |

### §12.4 배선 DoD

- [x] `load_app_services` 내 ProactiveDispatcher 주입 블록 (`service_context.py:286~307`).
- [x] `send_text` 콜러블 제공 (`_get_active_client_send_text`, `service_context.py:58~74`).
- [x] `TestM11ProactiveDispatcherWiring` 회귀 테스트 3건.
- [x] `AppWebSocketHandler`에 `handle_new_connection`/`handle_disconnect` 오버라이드(D-13 계약 완결).

### §12.5 문서 동기화

- [x] `docs/MODULES.md` §M_11 공개 API 블록 스펙 §15.2와 일치.
- [x] 상태 `🔲 TODO` 유지 (Critic PASS 이후 `✅ DONE` 전환이 DoD).
- [x] `docs/RISKS.md`에 R-PROA-1/2/3/4 등록(`docs/RISKS.md:142~169`).

### §13 의존성

- `pyproject.toml:43~44`에 `"APScheduler>=3.10,<4"` 추가 ✓.
- `scripts/bundle_deps.sh:146~151`에 APScheduler wheel 수집 라인 추가 ✓.
- 외부 네트워크 호출 `grep -rn "requests\|httpx\|urllib\|fetch(" src/proactive/` = 0 ✓.

## New Findings

### Blocking

없음. R1의 4건 Blocking 전건 실질 해소 + 회귀 방지 테스트 마련.

### Non-blocking (MAJOR)

없음. 이전 MAJOR 5건 모두 실질 해소.

### Non-blocking (MINOR)

1. **[MINOR] `reminder_check_interval_seconds` 생성자 검증 테스트 누락** (`src/proactive/dispatcher.py:94~98`).
   R1이 지적한 "생성자 검증 4분기 (L84/91/95/100)" 중 **L95(`reminder_check_interval_seconds` 범위)**가 여전히 미커버. M3a~d 4개 테스트는 L84/L87(morning_time)/L91/L100을 커버하되 L95는 누락. Builder 보고가 "4분기 모두 커버"라고 한 것은 사실과 다름 — 실제로는 "L84/L87/L91/L100"을 커버. Coverage report도 L95 Missing을 보여준다.
   권고: `test_m3e_reminder_check_interval_seconds_out_of_range_raises_valueerror` 1건 추가(예: `reminder_check_interval_seconds=0` 또는 `=3601` → ValueError).

2. **[MINOR] `test_proactive_dispatcher_none_when_calendar_or_idle_monitor_missing`이 vacuous** (`tests/app/test_service_context.py:485~499`).
   이 테스트는 `_make_ctx_raw()` 후 `ctx.proactive_dispatcher is None`만 확인하며 `load_app_services()`를 호출하지 **않는다**. `__init__`에서 이미 None으로 설정되기 때문에 이 assertion은 항상 참. 배선 분기(L303~307)에서 else 경로로 `proactive_dispatcher = "not_none"` 같은 mutation이 들어가도 이 테스트는 잡지 못한다.
   권고: `load_app_services(app_cfg)`를 호출한 뒤(단, `calendar_service=None`으로 강제해) `ctx.proactive_dispatcher is None`을 확인하는 형태로 재작성.

3. **[MINOR] `_get_active_client_send_text` late-binding 회귀 테스트 부재** (`src/app/service_context.py:58~74`).
   클로저 `ws = self._active_ws`가 호출 시점에 읽는 late-binding이 올바르게 구현됐으나, 연결 갱신 후 구 ws로 send되지 않음을 증명하는 단위 테스트가 없다. R1 MAJOR #4에서 지적된 그대로. 향후 누군가 early-binding으로 리팩토링해도 테스트 회귀로 잡히지 않는다.
   권고: `test_active_ws_late_binding` 1건 — `_get_active_client_send_text()`로 콜러블 획득 → `ctx._active_ws = ws1` 후 콜러블 호출(ws1.send_text 확인) → `ctx._active_ws = ws2` 갱신 → 같은 콜러블 재호출(ws2.send_text 호출됨을 확인).

4. **[MINOR] `TestM11ProactiveDispatcherWiring` send_text 바인딩 미검증** (`tests/app/test_service_context.py:477~479`).
   `"send_text" in captured_kwargs`로 키 존재만 확인하고 값 callable 여부는 검증 안 함. ProactiveDispatcher 생성자가 TypeError를 낼 것이므로 실제 결함은 런타임에 잡히나, 회귀 방어는 취약.
   권고: `assert callable(captured_kwargs["send_text"])` 한 줄 추가.

5. **[MINOR] `TOPICS: frozenset[str]`** (`src/proactive/types.py:17`)
   스펙 §4.1은 `frozenset[ProactiveTopic]`. 런타임 동일이나 타입 정밀도 손실.

6. **[MINOR] `stop()` shutdown 예외 / `_on_idle_event` unknown topic / `_minutes_until` tz-naive 분기 미커버** (coverage report `src/proactive/dispatcher.py` Missing L197~198, 202~203, 348, 390, 419).
   에러 처리 분기의 잔류 미커버. 각 1건씩 추가 가능.

7. **[MINOR] upstream의 `handle_disconnect` dead-code 활용** — 본 오버라이드는 `super().handle_disconnect` 호출 후 client_contexts에서 pop되기 전의 `client_connections[client_uid]`를 L82에서 미리 캡처한다. upstream 내부 구현이 바뀌어 L135(store_client_data)처럼 `client_connections` 채움이 지연되면 이 캡처가 None을 반환할 수 있다. upstream 의존성이지만 주석으로 명시해두면 좋다.

## Test Coverage Analysis

- **proactive 본체**: 90%(239/25). R1 85% 대비 +5%p.
- **미커버 Missing 라인** (dispatcher.py):
  - L95 — reminder_check_interval_seconds 검증 (MINOR #1).
  - L146~157 — 실제 AsyncIOScheduler import 경로 (integrator 범위로 위임, 스펙 §11.5).
  - L192 — stop() not started guard.
  - L197~198 — shutdown 예외.
  - L202~203 — on_event(None) 예외.
  - L322 — `if not events: return`.
  - L348 — _on_idle_event unknown topic.
  - L390, L419 — tz-naive 분기.
  - L423~424 — cleanup 내 exception.
  - L436, L443~444, L446, L448 — _parse_morning_time 세부 에러.
- **ws_handler.py `_active_ws` 라이프사이클**: 4분기(성공/실패/단일disconnect/다중) 모두 커버.
- **service_context.py M_11 배선**: 2경로(성공 주입/조건 누락) 중 1.5경로 커버 — Non-blocking MINOR #2.
- **전체**: 103건 PASS, FAIL 0건(APScheduler 설치 환경). ruff 통과, mypy(src/proactive) 통과.

## Previous Reviewer 재확인

R1 Critic의 판정이 정확했으며 모든 Blocking/MAJOR가 본 Round 2에서 실질 해소됨을 검증. R1이 놓친 mutation 취약점(vacuous 테스트, send_text 바인딩 미검증, late-binding 미검증)은 본 리뷰 MINOR #2~#4로 기록해 향후 개선 여지를 남김.

## 검토하지 못한 영역

1. **실제 `AsyncIOScheduler` 런타임 스모크** — 여전히 FakeScheduler 기반. 스펙 §11.5가 integrator 범위로 명시 위임. Integrator 테스트에서 cron/interval이 실제로 트리거되는지 확인 필요.
2. **FastAPI `startup` hook에서 `ctx.proactive_dispatcher.start()` 호출** — `src/app/main.py` 또는 서버 진입점을 본 리뷰에서는 확인하지 않음. `specs/M_01_AppCore_SPEC.md` L332 예약만 확인. 다음 Critic 또는 Integrator가 실제 코드 확인 필요.
3. **다중 연결 race** — 단위 테스트로 asyncio.gather로 동시 handle_new_connection 호출 시나리오는 미검증. 단일 사용자 전제(REQUIREMENTS §10)로 범위 외이지만 리스크 기록.
4. **upstream 미래 변경 대응** — upstream `WebSocketHandler.handle_disconnect` 시그니처가 바뀌면 본 오버라이드의 `client_uid: str` 가정이 깨진다. `tests/app/test_upstream_integrity.py`에 upstream baseline이 있는지 확인 권장.

## Recommendation

**PASS**. R1 Blocking 4건 + MAJOR 5건 모두 실질 해소, 신규 Blocking 0건, 스펙 §4~§13 전 섹션 충족, `docs/MODULES.md`·`docs/RISKS.md`·`pyproject.toml`·`scripts/bundle_deps.sh` 동기화 완료.

본 모듈은 **완료(DONE) 전환 준비 완료**. 최종 단계로 다음을 권고:
1. `docs/MODULES.md:382`의 상태를 `🔲 TODO` → `✅ DONE`으로 갱신 (CLAUDE.md 산출물 체크리스트 마지막 항목).
2. 상기 MINOR #1~#4 중 최소 #1(reminder_check_interval_seconds)과 #3(late-binding)은 후속 fast-follow PR로 추가 권장 — 필수는 아니지만 회귀 방어가 취약한 구간.
3. Integrator가 AsyncIOScheduler 실제 기동·cron 트리거 스모크 테스트 1건 추가 (스펙 §11.5).
