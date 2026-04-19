# M_11 ProactiveDispatcher Critic Review

Date: 2026-04-19
Verdict: **FAIL**

## Summary

스펙 §4/§5/§6.3/§7/§8의 디스패처 본체(`src/proactive/`)는 대체로 충실하게 구현되었고 단위 테스트 39건이 전부 통과, 커버리지 85%, ruff/mypy 클린이다. 그러나 **D-13 WebSocket 라이프사이클 통합이 명백히 부서져 있다**: `AppWebSocketHandler.handle_new_connection`이 super() 실패 시 `_active_ws`를 오염된 상태로 남기고, `handle_disconnect`는 `_active_ws`를 전혀 정리하지 않아 끊긴 WebSocket이 영구 참조된다. 또한 스펙 §12.4의 "ProactiveDispatcher 주입 회귀 테스트 1건 추가" DoD가 미이행이고 (`tests/app/test_service_context.py`에 배선 테스트 없음), D-13 자체의 동작(handle_new_connection/handle_disconnect/_active_ws)을 검증하는 테스트가 존재하지 않는다. `docs/MODULES.md` §M_11 공개 API 블록은 초안 그대로이고 상태는 `🔲 TODO`. 이상 누수가 운영 중 무한 에러 로그를 유발하므로 본 모듈은 FAIL.

## Spec Alignment

### §4 공개 API

| 스펙 항목 | 구현 위치 | 상태 |
|---|---|---|
| `ProactiveTopic` Literal 4종 | `types.py:8` | 일치 |
| `TOPICS` frozenset | `types.py:17` — 타입이 `frozenset[str]` (스펙 원안은 `frozenset[ProactiveTopic]`) | 허용 가능(Literal 멤버 런타임은 str) |
| `__init__` 시그니처 (keyword-only + 11인자) | `dispatcher.py:46~60` | 일치 |
| `async start/stop/emit`, sync `set_dnd` | `dispatcher.py:134/186/208/260` | 일치 |
| `SendTextCallback` = `Callable[[dict[str,Any]], Awaitable[None]]` | `dispatcher.py:28` | 일치 |
| 파이썬 3.12 타입힌트 | `list/dict/X | None` 사용 | 일치 |

### §5 알고리즘

| 스펙 항목 | 구현 위치 | 상태 |
|---|---|---|
| 잡 2종 등록 (cron+interval, `max_instances=1`, `coalesce=True`) | `dispatcher.py:362~383` | 일치 |
| `misfire_grace_time=600` / `60` | `dispatcher.py:372,382` | 일치 |
| CronTrigger `timezone=self._timezone` | `dispatcher.py:367` | 일치(Asia/Seoul 기본값이 실제로 전달됨) |
| `_job_morning_briefing` → `get_events(today_start, today_end)` → `emit` | `dispatcher.py:278~304` | 일치 |
| `_job_event_reminder` → `events_due_within` → `emit` + `_notified_reminders` | `dispatcher.py:306~339` | 일치 |
| `_on_idle_event(topic)` — idle_rest/overwork | `dispatcher.py:341~348` | 일치 |
| `emit` 순서: enabled→topic check→DND→cooldown→compose→payload→send→update last | `dispatcher.py:208~258` | 일치 |
| `asyncio.Lock`으로 emit 원자성 보장(D-12) | `dispatcher.py:128, 228` | 일치 |
| `_cleanup_notified_reminders` (§5.3.1) | `dispatcher.py:394~426` | 구현됨, 그러나 **테스트 0건** — 청소 로직이 실제 작동하는지 회귀 없음 |

### §6.3 결정 사항

| ID | 검증 | 상태 |
|---|---|---|
| D-1 하드코딩 템플릿, LLM 호출 없음 | `messages.py`에 4 토픽 문자열 리터럴. LLM import 0건 | 일치 |
| D-2 DND 이중 (self + idle_monitor) | `dispatcher.py:260~272` | 일치 |
| D-3 토픽별 쿨다운 | `_last_emitted_at: dict[ProactiveTopic, datetime]` | 일치 |
| D-4 misfire_grace_time | cron 600, interval 60 | 일치 |
| D-5 payload 4키 (`type`, `text`, `topic`, `context`) | `dispatcher.py:243~248` | 일치 |
| D-7 send_text 예외 삼킴 + False | `dispatcher.py:250~254` | 일치 |
| D-8 APScheduler 실패 시 `_enabled=False` | `dispatcher.py:150~157, 166~173` | 일치 |
| D-9 scheduler/clock DI | 생성자 주입 | 일치 |
| D-11 IdleEvent/ProactiveTopic 문자열 공유 | 양쪽 Literal이 "idle_rest"/"overwork" 동일 | 일치 |
| D-12 단일 asyncio.Lock | `dispatcher.py:128, 228` | 일치 |
| D-13 `AppWebSocketHandler._active_client_send_text` | `service_context.py:58~74`, `ws_handler.py:61~64` | **BROKEN** — 상세는 다음 섹션 |

### §7 송신 페이로드

- 4키 스키마 `{type, text, topic, context}` 정확히 실려 나감(`dispatcher.py:243~248`).
- upstream `conversation_handler.py:35~64` 직접 확인: `msg_type == "ai-speak-signal"` 조건만 검사하고 `data.get("text")`는 읽지 않음 — 추가 키 `text/topic/context`는 무시되므로 **하위 호환 OK**. 스펙이 리스크로 기재한 R-PROA-1은 정확하다.
- 한 가지 경미한 우려: payload `text` 필드 값이 한국어 템플릿인데 upstream이 읽지 않고 고정 프롬프트를 사용하므로 V1 UX는 upstream 프롬프트 로직 의존. **스펙 내 리스크로 명시됨**.

### §8 에러 처리

| 상황 | 구현 | 상태 |
|---|---|---|
| `__init__` 파라미터 위반 | `ValueError`/`TypeError` 전파 | 일치, **테스트 없음** (미커버 라인 84/91/95/100) |
| `start()` scheduler.start 예외 | `_enabled=False` + return (예외 전파 X) | 일치, 테스트 A-1 커버 |
| `stop()` shutdown 예외 | logger.warning + swallow | 일치, 테스트 없음(197~198 미커버) |
| `emit` send_text 예외 | logger.error + False | 일치, 테스트 A-2 커버 |
| `_job_morning_briefing` calendar 예외 | logger.error + return | 구현됨(292~294), **테스트 없음** |
| `_job_event_reminder` events_due_within 예외 | logger.error + return | 구현됨(317~319), **테스트 없음** |
| IdleMonitor 콜백 unknown topic | logger.warning | 구현됨(348), **테스트 없음** |

### §10 테스트 목록

| 스펙 케이스 | 구현 | 상태 |
|---|---|---|
| N-1 morning_briefing emit | `test_dispatcher.py::test_n1_emit_morning_briefing_success` | 있음 |
| N-2 event_reminder emit | `test_n2_emit_event_reminder_success` | 있음 |
| N-3 idle_rest callback | `test_n3_idle_rest_callback` | 있음 |
| N-4 overwork callback | `test_n4_overwork_callback` | 있음 |
| N-5 쿨다운 만료 재emit | `test_n5_cooldown_expires_resend` | 있음 |
| N-6 DND OFF 정상 emit | `test_n6_emit_with_dnd_off` | 있음 |
| N-7 start/stop 정상 | `test_n7_start_stop_normal` | 있음 |
| E-1 쿨다운 내 drop | `test_e1_cooldown_blocks_resend` | 있음 |
| E-2 DND 모든 토픽 drop | `test_e2_dnd_blocks_all_topics` | 있음 |
| E-3 토픽별 쿨다운 독립 | `test_e3_topic_cooldown_independent` | 있음 |
| E-4 morning 0건 emit | `test_e4_job_morning_no_events` | 있음 |
| E-5 event_reminder 중복방지 | `test_e5_event_reminder_dedup` | **부분적** — dedup 회귀가 약함(아래 Finding MAJOR #3) |
| E-6 start 중복 멱등 | `test_e6_start_idempotent` | 있음 |
| E-7 unknown topic ValueError | `test_e7_invalid_topic_raises` | 있음 |
| A-1 APScheduler 초기화 실패 | `test_a1_apscheduler_init_failure` | 있음 |
| A-2 send_text 예외 삼킴 | `test_a2_send_text_exception_swallowed` | 있음 |
| A-3 시계 역행 | `test_a3_clock_regression` | 있음 |
| A-4 한 틱에 10개 이벤트 | `test_a4_ten_events_same_tick` | 있음 |

정상 7 + 엣지 7 + 적대적 4 = 18건 스펙 충족. `tests/proactive/` 전체 39건 (보조 테스트 포함) 모두 PASS, coverage 85%(dispatcher.py 82%).

## D-13 Integration (적대적)

### handle_new_connection 오버라이드 (`ws_handler.py:61~64`)

```python
async def handle_new_connection(self, websocket: WebSocket, client_uid: str) -> None:
    self._app_ctx._active_ws = websocket
    await super().handle_new_connection(websocket, client_uid)
```

**결함 #1 (CRITICAL)**: super() 실패 시 _active_ws 오염.
upstream 원본(`upstream/.../websocket_handler.py:100~133`)은 초기화 실패 시 `_cleanup_failed_connection`을 호출하고 **예외를 재전파**한다. 오버라이드는 super() 이전에 `_active_ws`를 교체하므로, super()가 실패해도 `_active_ws`에 실패한 웹소켓이 남는다. `_cleanup_failed_connection`은 `client_connections` dict만 비우고 `_active_ws`는 손대지 않는다. 이후 cron이 트리거되면 `_active_ws.send_text(...)`가 오류를 낸다.

**결함 #2 (CRITICAL)**: handle_disconnect가 _active_ws를 정리하지 않는다.
`ws_handler.py:66~73`의 `handle_disconnect` 오버라이드는 `_continuous_tasks`만 취소하고 super()를 호출한 뒤 리턴한다. `_active_ws`를 None으로 되돌리지 않으므로, 클라이언트가 끊어진 이후에도 이미 종료된 WebSocket 객체가 계속 참조된다. APScheduler cron/interval이 돌면서 `ws.send_text(json.dumps(payload))`를 호출하면 FastAPI/Starlette의 `WebSocketDisconnect`(또는 더 나쁜 `RuntimeError: Cannot call "send" once a close message has been sent`)가 매 틱마다 발생한다. ProactiveDispatcher의 D-7이 예외를 삼키지만, 스펙 D-13이 명시한 "no active client; drop proactive payload" DEBUG 경로가 아니라 `send_text 실패: ...` ERROR 경로로 떨어진다. 이는 **D-13의 "연결 없으면 drop" 정책 위반이자 로그 노이즈**다.

**결함 #3 (MAJOR)**: _active_ws 라이프사이클 테스트 전무.
`tests/app/test_ws_handler.py`에 `handle_new_connection` 오버라이드나 `_active_ws` 갱신을 검증하는 테스트가 하나도 없다(`grep _active_ws tests/app/` = 0건). D-13 계약은 배선만 있고 회귀 방지망이 없어 상기 두 결함이 영구히 숨을 수 있다.

**결함 #4 (MAJOR)**: late-binding은 올바르지만 테스트로 확인되지 않음.
`_get_active_client_send_text`는 클로저로 `self._active_ws`를 호출 시점에 읽으므로(`service_context.py:67~72`) 연결 갱신 후 구 ws에 쏘지 않는다 — 이 점은 맞게 구현되었다. 그러나 이 late-binding 동작을 재현하는 단위 테스트가 없어 리팩토링 시 회귀 위험.

## Findings

### Blocking

1. **[CRITICAL] `ws_handler.py:61~64`** — `handle_new_connection`이 super() 이전에 `_active_ws`를 덮어쓴다. super()가 예외를 내면 `_active_ws`가 실패한 소켓으로 오염되며, upstream의 `_cleanup_failed_connection`은 `_active_ws`를 복구하지 않는다.  
   스펙 근거: §8.2 D-13 "활성 연결이 0이면 emit은 False 반환". 실패한 소켓은 '활성'이 아니므로 반드시 초기화되어야 함.  
   권고: `await super().handle_new_connection(...)`을 먼저 호출해 성공 시에만 `_active_ws`를 갱신하거나, try/except로 실패 시 `_active_ws`를 원상 복구.

2. **[CRITICAL] `ws_handler.py:66~73`** — `handle_disconnect`가 `_active_ws`를 None으로 재설정하지 않는다.  
   스펙 근거: §8.2 D-13 "활성 연결이 0이면 `send_text` 콜러블이 조용히 반환(DEBUG)". 끊긴 ws에 계속 send가 가면 "DEBUG drop"이 아니라 "ERROR send_text 실패"가 반복 발생 — D-13 정책 위반.  
   권고: disconnect 시 `if self._app_ctx._active_ws is websocket_being_disconnected: self._app_ctx._active_ws = None`. 또는 `client_uid`로 현재 저장된 ws 매칭. 다중 연결 상황에서는 "가장 최근" 추적이 깨지므로 `client_connections` dict를 역참조해 재선정.

3. **[CRITICAL] DoD §12.4 미이행 — ProactiveDispatcher 배선 회귀 테스트 없음**  
   스펙 근거: §12.4 "`tests/app/test_service_context.py`에 ProactiveDispatcher 주입 회귀 테스트 1건 추가 (`unittest.mock.patch('proactive.ProactiveDispatcher')`)". `grep ProactiveDispatcher tests/app/` 결과 배선 회귀 테스트 0건(기존 참조는 모두 close() 순서 테스트의 MagicMock 세팅). 이 DoD 항목은 Builder가 명시적 체크 항목을 건너뛴 것.  
   권고: `test_service_context.py`에 (a) `load_app_services` 후 `ctx.proactive_dispatcher is not None` 검증, (b) `ProactiveDispatcher.__init__` mock 패치로 `send_text=_get_active_client_send_text()`, `morning_time=app_config.morning_briefing_time`, `cooldown_min=app_config.proactive.cooldown_min`, `dnd_enabled=app_config.dnd_enabled` 인자가 실제로 전달되는지 검증, (c) calendar 또는 idle_monitor가 None이면 `proactive_dispatcher=None` 검증.

4. **[CRITICAL] DoD §12.5 미이행 — `docs/MODULES.md` M_11 블록 미갱신**  
   `docs/MODULES.md:382`가 여전히 `🔲 TODO`, `docs/MODULES.md:389~401`의 공개 API가 초안 상태 그대로(스펙 §15.1의 신규 인자 `timezone`/`reminder_check_interval_seconds`/`dnd_enabled`/`clock`/`scheduler`와 `set_dnd` 메서드, payload 4키 결정 반영 안 됨). DoD는 **Critic PASS 기록 이전에 갱신**을 요구하지 않고 "M_11을 완료 선언하려면"의 일부이므로, Critic PASS를 받기 전 현상은 정상이다 — 그러나 본 리뷰는 FAIL이므로 PASS 이후 정리 항목이 아닌 **후속 작업 리스트에 반드시 포함**.  
   권고: Critic 재검수 또는 후속 작업 시 §15.2 치환 문구를 적용, 상태를 `✅ DONE`으로 갱신.

### Non-blocking (MAJOR)

1. **[MAJOR] `_cleanup_notified_reminders` 회귀 테스트 전무** (`dispatcher.py:394~426`, coverage 0%).  
   스펙 §5.3.1과 §6.3 D-10의 "메모리 누수 방지" 근거가 실제로 작동하는지 검증되지 않음. 장기 실행 시 이벤트 ID가 영구 누적될 위험. 특히 `ev_start.tzinfo is None`일 때 UTC 가정 분기, `ev is None`(DB 삭제) 분기가 테스트 없음.  
   권고: 3건 추가 — (a) 과거가 된 이벤트가 제거되는지, (b) `get_event` → None인 이벤트가 제거되는지, (c) tz-naive start가 UTC로 해석되는지.

2. **[MAJOR] `_job_event_reminder` / `_job_morning_briefing`의 calendar 예외 경로 테스트 없음** (라인 292~294, 317~319).  
   스펙 §10 "calendar 조회 실패 시 topic drop + logger.error" 분기가 실제로 예외 삼킴으로 구현됐는지 미검증. FakeCalendar에 side_effect를 주입해 1건씩 추가하면 즉시 검증 가능.

3. **[MAJOR] 생성자 검증 분기 테스트 없음** (84/91/95/100).  
   스펙 §4.2 "Raises ValueError: morning_time 포맷 불량, reminder_lead_minutes/cooldown_min 범위 위반 / TypeError: send_text 타입 불량" 4종 모두 적대적 테스트로 보호되지 않음. 가장 방어적 코드인 fail-fast 게이트가 회귀 없이 노출돼 있음.

4. **[MAJOR] `test_e5_event_reminder_dedup` 회귀가 약하다** (`test_dispatcher.py:241~256`).  
   `cooldown_min=1`로 설정했는데 두 번째 `_job_event_reminder` 호출이 1분 뒤가 아니라 동일 시각(clock advance 없음)이라 쿨다운으로 drop된다. 이는 **"dedup(`_notified_reminders`)이 작동한다"가 아니라 "쿨다운이 작동한다"를 증명**할 뿐이다. 스펙 D-10 "reminder 중복 방지는 메모리 set"을 증명하려면 clock.advance(cooldown 이상) 후 같은 이벤트로 두 번째 틱 → `_notified_reminders`에 의해 drop되는지 확인해야 한다. 현재 테스트로는 `_notified_reminders` 메커니즘 자체가 제거돼도 테스트가 통과한다.

5. **[MAJOR] D-13 "마지막 연결" 뉘앙스 검증 부재**  
   스펙 §8.2 "마지막으로 연결된 활성 WebSocket". 현재 구현은 단일 값 덮어쓰기이므로 기술적으로 "마지막"이나, 다중 연결/재연결 시나리오에서 `_active_ws` 추적이 올바른지 확인하는 테스트가 없다. `handle_new_connection` 두 번 호출 후 `_active_ws`가 두 번째 ws를 가리키는지, disconnect 시점에 마지막 연결이 아니면 `_active_ws`를 건드리지 말아야 하는지 등 라이프사이클 시나리오 테스트 필요.

### Non-blocking (MINOR)

1. **[MINOR] `TOPICS: frozenset[str]`** (`types.py:17`)  
   스펙 §4.1은 `frozenset[ProactiveTopic]`인데 구현은 `frozenset[str]`. Literal은 런타임에 str이므로 기능상 동일하나 정밀도 손실. 타입힌트 주석 통일 권장.

2. **[MINOR] `emit` 로그 메시지에 % 스타일 포맷 사용** (`dispatcher.py:152, 168, 180, 253, 257`)  
   loguru는 f-string 또는 `logger.info("... {}", x)` 기반 스타일을 권장. `logger.error("send_text 실패: topic=%s, exc=%s", topic, exc)` 같은 `%s` 스타일은 loguru에서도 동작하지만, 본 프로젝트 다른 모듈은 f-string을 쓴다(M_10 선례). 일관성 경미 이슈.

3. **[MINOR] 스펙 §5.5 pseudocode와 §10 시계 역행 정책 내부 충돌**  
   §5.5는 `< cooldown_min * 60`만 검사(음수도 `<`이므로 drop), §10은 시계 역행 시 emit 허용을 명시. 구현은 §10을 택했다(237~240). 스펙 자체의 모순으로 구현 자체는 문제 없으나 스펙 다듬기 권장.

4. **[MINOR] stop 경로의 일부 브랜치 미커버** (라인 192, 197~198, 202~203)  
   멱등 no-op, shutdown 예외 처리, `on_event(None)` 예외 처리 세 분기 모두 회귀 테스트 없음. N-7이 성공 경로만 커버.

5. **[MINOR] APScheduler 실제 import 경로 커버 부재** (라인 146~157)  
   `scheduler=None` 기본값 경로에서 실제 `AsyncIOScheduler`를 import하는 분기를 타는 테스트가 없다. 본 스펙 §11.5가 integrator 범위로 명시적으로 위임했으므로 결함은 아니나, 최소 1건의 AsyncIOScheduler import smoke test는 가치가 있음.

6. **[MINOR] `_parse_morning_time`이 dispatcher.py 하단에 module-level 함수로 존재**  
   스펙 §5.1 파일 배치엔 `messages.py`와 `dispatcher.py`만 있고 `_parse_morning_time`은 dispatcher.py에 있는 것이 자연스러우나, `__init__.py`의 `__all__`에 노출되지 않으며 모듈 외부 사용처도 없어 OK.

## Test Coverage Analysis

- 전체 커버리지: 85% (dispatcher.py 82%, messages.py 100%, types.py 100%, errors.py 100%, __init__.py 100%) — 70% 기준 통과.
- **그러나 미커버 라인은 전부 에러 처리·적대적 분기**다:
  - 생성자 검증 4분기 (84, 91, 95, 100)
  - scheduler.start 내부 생성 경로 (146~157)
  - stop() 예외 처리 (197~198, 202~203)
  - calendar 예외 삼킴 (292~294, 317~319)
  - _on_idle_event unknown topic (348)
  - _minutes_until tz-naive 분기 (390)
  - _cleanup_notified_reminders 전체 (415, 419, 422~424) — §5.3.1 메모리 누수 방지 회귀 0건
  - _parse_morning_time 범위·파싱 에러 분기 (436, 439, 443~444, 446, 448)
- 커버리지 숫자는 통과하지만 **보호해야 할 경로가 보호되지 않는 테스트 디자인**.
- `test_e5_event_reminder_dedup`는 dedup이 아닌 cooldown을 증명 — Finding MAJOR #4.

## 검토하지 못한 영역

1. **실제 `AsyncIOScheduler` 런타임** — 단위 테스트 전부 FakeScheduler 기반이라 `AsyncIOScheduler.add_job` 시그니처·`CronTrigger` 생성자·`IntervalTrigger` 생성자의 실제 호환성은 확인 못함. 스펙 §11.5가 integrator 범위로 명시 위임했으므로 본 리뷰 책임 외.
2. **`upstream` 프로액티브 수신 경로의 end-to-end** — `ai-speak-signal` → `handle_conversation_trigger` → `proactive_speak_prompt` → TTS 음성 출력까지의 전체 연쇄. upstream 코드 읽기만 수행했고 통합 테스트는 돌리지 않음.
3. **FastAPI `@app.on_event("startup")`에서 `ctx.proactive_dispatcher.start()` 호출 여부** — DoD §12.4 항목 3. `src/app/` 내 main 모듈 또는 startup hook을 grep으로 확인하지 못함. 다음 Critic이 확인 필요.
4. **다중 클라이언트 동시 연결/해제 race** — asyncio 단일 루프라 일반적으로 안전하지만 `_active_ws` 경쟁을 단위 테스트로 재현하지 않음. 본 스펙 §9.2 "단일 사용자" 전제로 범위 외이나 리스크 기록.
5. **APScheduler cron `morning_time="25:00"` 같은 부적격 입력** — `_parse_morning_time`에서 거르므로 APScheduler까지 도달하지 않지만, AppConfig validator 경로와 본 모듈 validator의 중복/공백 재확인 필요.

## Recommendation

**FAIL**. 다음 사항을 처리한 후 fresh Critic 재검수.

1. (CRITICAL) `ws_handler.handle_new_connection`의 `_active_ws` 갱신을 super() 성공 후로 이동 + 실패 시 원상 복구.
2. (CRITICAL) `ws_handler.handle_disconnect`에서 `_active_ws`가 끊기는 websocket을 가리키면 None으로 재설정 (또는 남은 활성 연결 중 최신으로 재선정).
3. (CRITICAL) `tests/app/test_service_context.py`에 `ProactiveDispatcher` 주입 회귀 테스트 1건 이상 추가 (DoD §12.4).
4. (CRITICAL) `tests/app/test_ws_handler.py`에 `_active_ws` 라이프사이클 테스트 3건 추가: (a) handle_new_connection 성공 시 `_active_ws=ws`, (b) super() 실패 시 `_active_ws`가 오염되지 않음, (c) handle_disconnect 후 `_active_ws is None`.
5. (MAJOR) `_cleanup_notified_reminders` 회귀 테스트 3건, calendar 예외 삼킴 2건, 생성자 검증 4건 추가.
6. (MAJOR) `test_e5_event_reminder_dedup`를 clock.advance(cooldown+1분) 구조로 리팩토링해 dedup 메커니즘 자체를 검증.
7. (DoD) `docs/MODULES.md` §M_11 블록을 스펙 §15.2 치환 문구로 교체하고 상태 `✅ DONE`.

본 모듈의 핵심 로직(dispatcher.py, messages.py)은 견고하다 — FAIL 사유는 전적으로 D-13 통합 지점의 라이프사이클 누수와 배선 회귀 테스트 부재다.
