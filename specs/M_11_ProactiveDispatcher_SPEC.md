# M_11 ProactiveDispatcher — 스펙

> 분류: **NEW** — upstream `Open-LLM-VTuber/`에는 프로액티브 스케줄러·쿨다운·DND 매니저가 없다(`ai-speak-signal` 수신 핸들러만 있고, 트리거 주체는 클라이언트). 본 모듈이 서버 내부 트리거 주체를 신설한다.
>
> 작성 근거:
> - `REQUIREMENTS.md` §4.2(10분 전 팝업+음성, 아침 브리핑), §5(휴식 권고, 쿨다운, DND), §9(외부 네트워크 금지), §10(단일 사용자).
> - `docs/ARCHITECTURE.md` L157~L176(프로액티브 발화 흐름), L165~L168(M_11 책임 = 스케줄 + 쿨다운 + DND), L170(`send_text({"type":"ai-speak-signal","text":<prompt>})` 포맷).
> - `docs/MODULES.md` L379~L403(M_11 초안 공개 API, 에러 정책, 의존).
> - `docs/MILESTONES.md` L139~L148(M_11 DoD 5항).
> - `specs/M_01_AppCore_SPEC.md` L332(`app.on_event("startup")` → `ctx.proactive_dispatcher.start()` 경로 예약), L385~L395·L914(upstream `ai-speak-signal` 수신 타입 유지).
> - `specs/M_09_CalendarService_SPEC.md` §4.2(`events_due_within(minutes) -> list[Event]` sync API).
> - `specs/M_10_IdleMonitor_SPEC.md` §6.3 D-1/D-2/D-3(쿨다운·DND 책임 경계, 콜백 단일 슬롯), §13.4(M_11 호출 계약).
> - `src/app/config.py`(`ProactiveConfig.cooldown_min` 기존재 L130~L135, `AppConfig.morning_briefing_time`·`dnd_enabled` 기존재 L151~L152).
> - `upstream/Open-LLM-VTuber/src/open_llm_vtuber/conversations/conversation_handler.py` L35~L64(`ai-speak-signal` 수신 경로가 서버에서 `proactive_speak_prompt`를 로드. `data.get("text")`는 **읽지 않음**).
> - `upstream/Open-LLM-VTuber/src/open_llm_vtuber/websocket_handler.py` L42, L91(`ai-speak-signal`이 수신 타입으로 `_handle_conversation_trigger`에 라우팅).

---

## 1. 목적과 범위

### 1.1 목적

프로액티브 발화(사용자가 요청하지 않았는데 AI가 먼저 말하는 경우)의 **단일 진입점**. 4종 토픽(`morning_briefing` / `event_reminder` / `idle_rest` / `overwork`)을 스케줄 또는 이벤트 트리거로 수집해, 쿨다운·DND 정책을 통과한 것만 upstream의 `ai-speak-signal` 프로액티브 경로로 **서버→클라이언트 방향** WebSocket 메시지로 주입한다.

### 1.2 In-Scope

1. `ProactiveDispatcher` 클래스 — `__init__` / `start` / `stop` / `emit` / `set_dnd` 5개 공개 메서드.
2. `ProactiveTopic = Literal["morning_briefing", "event_reminder", "idle_rest", "overwork"]` 타입.
3. APScheduler(`AsyncIOScheduler`) 기반 2개 잡:
   - Cron: 매일 `morning_time`(Asia/Seoul) → `_job_morning_briefing`.
   - Interval: `reminder_check_interval_seconds`(기본 60) → `_job_event_reminder`.
4. M_10 `IdleMonitor.on_event(self._on_idle_event)` 구독.
5. **토픽별 독립 쿨다운**(§6.3 D-3): 마지막 성공 emit 시각을 토픽별로 기록, 동일 토픽만 `cooldown_min`분 드롭.
6. DND 이중 체크 구조(§6.3 D-2): 본 모듈이 자체 `dnd_enabled`를 가지며, `set_dnd(...)` 호출 시 M_10에도 **동일값 전파**.
7. `event_reminder` 중복 방지: 이미 알림한 `(event_id, reminder_window_key)` 집합을 프로세스 메모리에 보관(§5.3).
8. 토픽별 한국어 고정 템플릿 메시지 합성(§7). LLM에게 자연어 생성을 맡기는 것은 upstream `proactive_speak_prompt` 경로의 책임으로 넘기고, 본 모듈은 upstream 페이로드의 `text` 필드에 "topic 코드 + 컨텍스트 문자열"을 실어 전송한다(§6.3 D-5).
9. 단위 테스트(정상 ≥7, 엣지 ≥7, 적대적 ≥4; §11).
10. `pyproject.toml`에 `APScheduler>=3.10,<4` 추가 + `scripts/bundle_deps.sh`에 wheel 수집 라인 추가(§13).
11. `src/app/service_context.py::load_app_services`에 `ProactiveDispatcher(...)` 주입 1블록 + FastAPI `startup` hook에서 `start()` 호출(§12).

### 1.3 Out-of-Scope (명시적 제외)

1. **자연어 프롬프트 최종 생성** — upstream `proactive_speak_prompt`(`characters/*.yaml`의 `tool_prompts` 항목) 또는 M_05 `GemmaChatAgent` 책임. 본 모듈은 topic 식별자와 컨텍스트 dict만 전달.
2. **프론트엔드 팝업 UI** — M_12 책임. REQUIREMENTS.md §4.2 "팝업"은 Electron 쪽 토스트·알림 창 구현.
3. **TTS 음성 합성** — M_04 `TTSEngine` + upstream 프로액티브 경로(`conversation_handler.handle_conversation_trigger`) 내 기존 파이프라인 재사용.
4. **아바타 표정 전환** — M_08 `AvatarState.push_event` 직접 호출은 본 모듈이 하지 않는다(§6.3 D-6 근거). 필요 시 `conversation_handler` 또는 M_05가 응답 스트림에 `[emotion:sleepy]` 등을 삽입.
5. **일정 자연어 파싱** — M_05 LLMAgent + M_05b ToolRouter.
6. **IdleMonitor 상태 기계** — M_10. 본 모듈은 M_10의 단일 콜백 슬롯 소비자.
7. **반복 일정(RRULE)** — M_09 §1.3 제외 항목과 일관.
8. **사용자 부재 장기 감지(예: 주말 장기 idle이면 morning_briefing 억제)** — V2 검토. V1은 매일 동일 트리거.
9. **프로액티브 발화 로깅·분석 대시보드** — V2. V1은 loguru 로그만.
10. **모바일 푸시 알림** — REQUIREMENTS.md §10 제외.

---

## 2. 요구사항 연결

| REQUIREMENTS.md / 설계 문서 | M_11 기여 |
|---|---|
| §0 완전 오프라인 / Windows 전용 | APScheduler는 순수 파이썬, 외부 네트워크 호출 0건. `send_text`는 M_01이 주입한 로컬 WebSocket send. |
| §4.2 "일정 도래 10분 전 팝업 + 음성 알림" | Interval(1분) → `calendar.events_due_within(reminder_lead_minutes=10)` → `emit("event_reminder", ...)`. |
| §4.2 "아침 첫 실행 시 오늘의 일정 브리핑" | Cron(매일 `morning_time=09:00`, Asia/Seoul) → `emit("morning_briefing", ...)`. "첫 실행"은 런타임 기동 후 최초 09:00 도래 시점으로 해석(§6.3 D-4). |
| §5 "임계 시간 없으면 휴식 권고" | M_10 `IdleMonitor`의 `idle_rest` 콜백 → `emit("idle_rest", ...)`. |
| §5 "2시간 넘으면 이제 그만 일하라" | M_10 `overwork` 콜백 → `emit("overwork", ...)`. |
| §5 "반복되지 않게 쿨다운" | 토픽별 `cooldown_min`(기본 30분) 드롭. |
| §5 "방해 금지 모드" | `set_dnd(True)` → 모든 토픽 drop + M_10에 전파. |
| §9 외부 네트워크 호출 금지 | `grep -r "requests\|httpx\|urllib\|fetch" src/proactive` = 0. APScheduler 트리거는 로컬 시계. |
| §9 메모리 예산 | 쿨다운 dict(토픽 4개 + 시각) + 중복 방지 set(§5.3)만 보관. 추가 메모리 < 1 MB. |
| docs/ARCHITECTURE.md L170 `send_text({"type":"ai-speak-signal","text":<prompt>})` | 송신 페이로드 포맷 준수(§7). |
| docs/MILESTONES.md L139~L148 M_11 DoD 5항 | §12에 1:1 매핑. |

---

## 3. upstream 재사용 분석

### 3.1 분류: **NEW** (REUSE 0건, EXTEND 0건, DROP 0건)

`rg -n "proactive_dispatcher\|ProactiveDispatcher\|APScheduler" upstream/Open-LLM-VTuber/` 히트 0건. upstream에는 "클라이언트가 서버에 `ai-speak-signal`을 보내면 서버가 `proactive_speak_prompt`를 로드해 대화를 트리거"하는 경로만 있을 뿐, **서버 자체가 스케줄에 따라 발화를 시작하는 주체**는 없다.

### 3.2 upstream `ai-speak-signal` 경로 재사용 방식

- upstream L91 등록: `"ai-speak-signal": self._handle_conversation_trigger` — 수신 메시지 타입.
- upstream `conversation_handler.py` L35~L64: 수신 시 `context.system_config.tool_prompts["proactive_speak_prompt"]`를 로드해 user_input으로 사용.
- **gap**: upstream은 payload의 `text` 필드를 **읽지 않는다**. 본 스펙이 `text`를 실어 보내도 upstream 경로는 고정 프롬프트를 사용한다.

→ 본 스펙의 처리(§6.3 D-5):
1. **V1**: upstream 경로를 그대로 재사용. `text` 필드는 관측·디버그 용도로 보내되 upstream 처리에는 기여하지 않는다. "오늘 일정" / "10분 전 알림" / "휴식 권고" 구분은 `proactive_speak_prompt`를 토픽 무관 범용 템플릿으로 유지. 토픽별 세분화는 RISKS R-PROA-1(§14.5)로 등록.
2. **V2 (향후 CR)**: upstream `conversation_handler.handle_conversation_trigger`에 분기 추가해 `data.get("text")`와 `data.get("topic")`을 읽어 각 토픽별 프롬프트를 선택하도록 확장. **본 스펙 범위 외**.

### 3.3 upstream 파일 수정 없음 — CLAUDE.md 규칙 준수.

---

## 4. 공개 API

### 4.1 타입 alias

```python
# src/proactive/types.py
from typing import Literal

ProactiveTopic = Literal["morning_briefing", "event_reminder", "idle_rest", "overwork"]

# 토픽 상수 집합 (typo 검증용)
TOPICS: frozenset[ProactiveTopic] = frozenset(
    ["morning_briefing", "event_reminder", "idle_rest", "overwork"]
)
```

### 4.2 `ProactiveDispatcher` 클래스 시그니처

```python
# src/proactive/dispatcher.py
from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from apscheduler.schedulers.base import BaseScheduler
from zoneinfo import ZoneInfo

from calendar_service.service import CalendarService
from idle_monitor import IdleMonitor

from .types import ProactiveTopic


SendTextCallback = Callable[[dict[str, Any]], Awaitable[None]]
# M_08 AvatarState.push_event와 동일한 JSON-as-dict 시그니처.
# 호출자(M_01 AppCore)가 WebSocket 직렬화를 내부에서 수행한다고 약속한다.


class ProactiveDispatcher:
    """스케줄러 + 쿨다운 + DND를 통합 관리하는 프로액티브 발화 디스패처.

    책임:
      - APScheduler 잡 2종(cron: morning briefing, interval: event reminder)을 관리.
      - M_10 IdleMonitor의 단일 콜백 슬롯을 차지.
      - 토픽별 쿨다운(동일 토픽 N분 내 재발행 금지) + DND 드롭.
      - upstream `ai-speak-signal` 페이로드로 변환해 `send_text`에 전달.

    비책임 (§1.3):
      - 자연어 프롬프트 최종 생성 (upstream `proactive_speak_prompt`).
      - TTS / 아바타 표정 / 프론트 팝업.
    """

    def __init__(
        self,
        *,
        calendar: CalendarService,
        idle_monitor: IdleMonitor,
        send_text: SendTextCallback,
        morning_time: str = "09:00",
        timezone: ZoneInfo = ZoneInfo("Asia/Seoul"),
        reminder_lead_minutes: int = 10,
        reminder_check_interval_seconds: int = 60,
        cooldown_min: int = 30,
        dnd_enabled: bool = False,
        clock: Callable[[], datetime] = datetime.now,
        scheduler: BaseScheduler | None = None,
    ) -> None:
        """
        Args:
            calendar: M_09 CalendarService. sync API (`events_due_within`,
                `get_events`)를 `run_in_executor`로 호출(§5.2).
            idle_monitor: M_10 IdleMonitor. `on_event(self._on_idle_event)`로 구독(§5.4).
            send_text: upstream WebSocket `send_text` 콜러블. M_01 AppCore가 per-client
                ws 연결에 바인딩해 주입. 본 모듈은 dict를 넘기고 직렬화는 호출자 책임.
            morning_time: "HH:MM" 포맷. AppConfig.morning_briefing_time을 그대로 전달받는다.
                입력 검증 실패 시 ValueError (AppConfig.field_validator에서 선검증되므로
                정상 경로에서는 실패하지 않음).
            timezone: APScheduler cron 트리거의 기준 tz. 기본 Asia/Seoul.
            reminder_lead_minutes: event_reminder 리드 타임(분). 기본 10.
            reminder_check_interval_seconds: event reminder 폴링 간격(초). 기본 60.
                reminder_lead_minutes × 60 이하여야 함 — 그렇지 않으면
                임박 이벤트를 놓칠 수 있음 (§5.3 중복 방지 키 설계와 연동).
            cooldown_min: 토픽별 쿨다운(분). AppConfig.proactive.cooldown_min(기본 30)
                을 그대로 전달받는다.
            dnd_enabled: 초기 DND 상태. AppConfig.dnd_enabled 전달.
            clock: 현재 시각 공급자 (테스트 주입). 기본 `datetime.now`. tz-aware/naive
                일관성은 호출자 책임. reminder 잡 내부에서는 `datetime.now(timezone.utc)`를
                별도로 직접 호출(§5.3 근거).
            scheduler: APScheduler BaseScheduler 인스턴스 (테스트 주입). None이면
                `AsyncIOScheduler(timezone=timezone)` 기본 생성.

        Raises:
            ValueError:
                - morning_time 포맷 불량 (HH:MM 아님, 범위 밖).
                - reminder_lead_minutes <= 0 or > 1440.
                - reminder_check_interval_seconds <= 0 or > 3600.
                - cooldown_min <= 0 or > 1440.
            TypeError:
                - calendar / idle_monitor / send_text 타입 불량.
        """
        ...

    async def start(self) -> None:
        """APScheduler 기동 + IdleMonitor 콜백 구독 + 초기 상태 로깅.

        동작:
          1. 자체 APScheduler에 잡 2종 등록(morning cron, reminder interval).
          2. scheduler.start() 호출.
          3. idle_monitor.on_event(self._on_idle_event).
          4. self._started = True.

        멱등:
          - 이미 start된 상태에서 재호출 시 `logger.warning` 1회 + no-op.

        에러 처리:
          - APScheduler 초기화 실패 (scheduler.start() 예외) →
            `logger.error("APScheduler init failed: %s; proactive disabled", exc)` +
            self._enabled = False로 기동. **예외 전파 금지** (FastAPI lifespan 기동 중단
            방지, §10).
          - 이벤트 루프 없이 호출 시 APScheduler AsyncIOScheduler 자체가
            RuntimeError — 상위 문제로 위임.
        """
        ...

    async def stop(self) -> None:
        """APScheduler 종료 + IdleMonitor 콜백 해제.

        동작:
          1. scheduler.shutdown(wait=False) — 진행 중 잡을 기다리지 않음.
          2. idle_monitor.on_event(None) — 콜백 해제.
          3. self._started = False.

        멱등:
          - 이미 stop되었거나 start되지 않은 상태에서도 예외 없음.

        예외 처리:
          - scheduler.shutdown 예외 시 logger.warning + swallow (AppServiceContext.close가
            다른 서비스 정리를 계속해야 하므로).
        """
        ...

    async def emit(
        self,
        topic: ProactiveTopic,
        context: dict[str, Any] | None = None,
    ) -> bool:
        """토픽을 발송 요청.

        반환:
            True — send_text 호출 성공 + 쿨다운 기록 갱신됨.
            False — DND / 쿨다운 / send_text 예외로 드롭.

        동작 순서(§5.5):
          1. self._enabled == False → return False.
          2. topic이 TOPICS 밖 → ValueError 전파.
          3. DND ON → return False (`logger.debug`).
          4. 토픽별 쿨다운 체크 → 위반 시 return False (`logger.debug`).
          5. _compose_message(topic, context) → text 문자열.
          6. upstream 페이로드 dict 구성(§7).
          7. await send_text(payload).
             - 예외 발생 시 `logger.error` + return False (§10 근거).
          8. 쿨다운 기록 갱신: self._last_emitted_at[topic] = clock().
          9. return True.

        동시성:
          - 여러 소스(cron/interval/IdleMonitor)가 동시에 emit 호출할 수 있으므로
            self._emit_lock(asyncio.Lock)으로 2~8을 감싸 쿨다운 판정과 기록 갱신의
            원자성을 보장(§9.2).
        """
        ...

    def set_dnd(self, enabled: bool) -> None:
        """방해 금지 모드 토글.

        동작:
          1. bool 검증: 아니면 TypeError.
          2. self._dnd_enabled = enabled.
          3. self._idle_monitor.set_dnd(enabled) 전파 — M_10도 선차단해 콜백 Task
             생성 비용 절약(§6.3 D-2).
          4. logger.info("DND set to %s", enabled).

        반환: None (동기 메서드).

        주의:
          - M_10 IdleMonitor.set_dnd는 bool 아닐 시 TypeError (M_10 §9 표). 본 모듈도
            동일 계약을 전파.
          - DND 해제 시 "놓친 이벤트 재방출"은 하지 않음 (M_10 §6.3 D-3 일관).
        """
        ...
```

### 4.3 에러 클래스

```python
# src/proactive/errors.py

class ProactiveError(Exception):
    """ProactiveDispatcher 최상위 기본 예외."""


class ProactiveInitError(ProactiveError):
    """생성자 인자 검증 실패. ValueError를 이 타입으로 승격하지 않고 ValueError로 둔다."""
    # 실제 사용처 없음 — 본 스펙에서는 ValueError/TypeError만 사용.
    # 후속 확장 여지로 존재.
```

본 모듈은 **독자 에러 클래스를 거의 쓰지 않는다**. 근거: 생성자 검증은 표준 `ValueError`/`TypeError`, 런타임 실패는 로그 + 반환값(False)으로 표현해 호출자 트리에 자기 자신이 죽음을 전파하지 않는 self-healing 스타일(§10, M_10 §9와 일관).

---

## 5. 알고리즘

### 5.1 파일 배치

```
src/proactive/
├── __init__.py             # ProactiveDispatcher, ProactiveTopic, TOPICS re-export
├── types.py                # ProactiveTopic Literal, TOPICS frozenset
├── dispatcher.py           # ProactiveDispatcher 본체
├── messages.py             # _compose_message(topic, context) -> str
└── errors.py               # ProactiveError, ProactiveInitError (후속 확장용)

tests/proactive/
# __init__.py 생성 금지 — CR-06 정책 (M_09 §17, M_10 §6.1 선례)
├── conftest.py             # fake scheduler, fake calendar, fake idle_monitor, frozen clock
├── fakes.py                # FakeScheduler, FakeCalendar, FakeIdleMonitor
├── test_dispatcher.py      # N-1~N-7, E-1~E-7, A-1~A-4
├── test_schedule.py        # APScheduler 잡 등록·트리거 호출 (FakeScheduler 사용)
├── test_cooldown_dnd.py    # 쿨다운·DND 드롭 회귀 전용
└── test_messages.py        # _compose_message 출력 문자열 검증 (하드코딩 템플릿)
```

### 5.2 APScheduler 잡 등록 (`start()`)

```text
scheduler = AsyncIOScheduler(timezone=self._timezone)

# (A) morning briefing — Cron
hh, mm = parse(morning_time)   # "09:00" → 9, 0
scheduler.add_job(
    self._job_morning_briefing,
    trigger=CronTrigger(hour=hh, minute=mm, timezone=self._timezone),
    id="morning_briefing",
    max_instances=1,
    coalesce=True,             # 기동 중 여러 번 누락된 실행은 1회로 합침
    misfire_grace_time=600,    # 10분 지연 허용 (§6.3 D-4)
)

# (B) event reminder — Interval
scheduler.add_job(
    self._job_event_reminder,
    trigger=IntervalTrigger(seconds=reminder_check_interval_seconds),
    id="event_reminder",
    max_instances=1,
    coalesce=True,
    misfire_grace_time=60,
)

scheduler.start()
```

- 잡 함수는 **async def**. `AsyncIOScheduler`는 이벤트 루프 Task로 실행.
- `max_instances=1`: 이전 잡이 아직 실행 중이면 새 틱을 건너뛴다(겹치기 방지).
- `coalesce=True`: 백로그 누적 시 1회로 병합.

### 5.3 `_job_event_reminder()` — 10분 전 알림 로직

```text
async def _job_event_reminder(self) -> None:
    try:
        events = await run_in_executor(
            None,
            lambda: self._calendar.events_due_within(self._reminder_lead_minutes),
        )
    except Exception as exc:
        logger.error("events_due_within 실패: %s", exc)
        return

    for ev in events:
        key = (ev.id, self._reminder_window_key(ev))
        if key in self._notified_reminders:
            continue

        ok = await self.emit("event_reminder", {
            "event_id": ev.id,
            "title": ev.title,
            "start": ev.start.isoformat(),
            "minutes_until": self._minutes_until(ev.start),
        })
        if ok:
            self._notified_reminders.add(key)
```

**중복 방지 키 `_reminder_window_key(ev)`**:
- 사용자 PC가 1분 간격으로 폴링하면서 `events_due_within(10)`은 동일 이벤트를 여러 번 반환할 수 있다(이벤트 시작 10분 전부터 시작 시각까지).
- 키는 `ev.id`와 "이 알림이 어떤 reminder window에 속하는가"를 조합. V1은 단순화하여 **`ev.id` 단독**을 키로 사용하고, 이벤트가 시작 시각을 지나면 캐시에서 제거(§5.3.1).
- 이유: `minutes_until`이 9→8→...→0으로 줄어드는 동안 이미 한 번 emit했으면 재emit 안 함 → 사용자는 "10분 전" 알림을 1회만 받는다.
- V2 확장 여지: "5분 전 + 1분 전" 같은 2단계 알림이 필요하면 `(ev.id, lead_minute_bucket)` 키로 확장 가능.

#### 5.3.1 `_notified_reminders` 청소 (garbage collection)

- 매 `_job_event_reminder` 틱 **시작 시**:
  ```
  now = datetime.now(timezone.utc)
  self._notified_reminders = {
      key for key in self._notified_reminders
      if not self._is_event_past(key.event_id, now)
  }
  ```
- `_is_event_past(event_id, now)`: `calendar.get_event(event_id)`로 조회해 `start + duration < now`면 True. DB 접근 비용은 1만건 테이블에서도 < 1ms (M_09 §11 인덱스 근거).
- 단순 구현: `ev.id`를 키로 썼으므로 DB에서 해당 이벤트가 사라졌으면(`get_event` → None) 과거로 간주 → 캐시 제거.
- 메모리 상한: 하루 평균 수십 건 × 수명 하루 = 수십~수백 개. 1 MB 미만(§2).

### 5.4 `_on_idle_event(topic)` — M_10 콜백

```python
async def _on_idle_event(self, topic: IdleEvent) -> None:
    # IdleEvent = Literal["idle_rest", "overwork"] — M_10 types.py
    await self.emit(topic, context={})
```

- 본 모듈은 M_10의 단일 콜백 슬롯을 차지(M_10 §6.3 D-2).
- 콜백 예외 시 M_10이 `logger.warning` 후 본체 계속(M_10 §7.2). 본 모듈도 `emit` 내부에서 예외를 삼키므로 이중 보호.

### 5.5 `emit(topic, context)` 상세 의사코드

```python
async def emit(self, topic: ProactiveTopic, context: dict | None = None) -> bool:
    if not self._enabled:
        return False
    if topic not in TOPICS:
        raise ValueError(f"unknown topic: {topic!r}")

    async with self._emit_lock:
        if self._dnd_enabled:
            logger.debug("emit drop (dnd): topic=%s", topic)
            return False

        now = self._clock()
        last = self._last_emitted_at.get(topic)
        if last is not None and (now - last).total_seconds() < self._cooldown_min * 60:
            logger.debug("emit drop (cooldown): topic=%s, last=%s", topic, last)
            return False

        text = _compose_message(topic, context or {})
        payload = {
            "type": "ai-speak-signal",
            "text": text,
            "topic": topic,
            "context": context or {},
        }

        try:
            await self._send_text(payload)
        except Exception as exc:
            logger.error("send_text 실패: topic=%s, exc=%s", topic, exc)
            return False

        self._last_emitted_at[topic] = now
        logger.info("emit success: topic=%s", topic)
        return True
```

**단일 asyncio.Lock**:
- 여러 소스가 동시 emit → lock으로 직렬화.
- 쿨다운 판정과 기록 갱신 사이의 race 방지 (§9.2).
- 락 획득 대기는 < 10 ms 가정(emit 내부 작업이 가벼움: dict 생성 + WebSocket send).

---

## 6. 내부 구조와 결정 사항

### 6.1 내부 상태

```python
class ProactiveDispatcher:
    # 파라미터 (immutable after __init__)
    _calendar: CalendarService
    _idle_monitor: IdleMonitor
    _send_text: SendTextCallback
    _morning_time: str
    _timezone: ZoneInfo
    _reminder_lead_minutes: int
    _reminder_check_interval_seconds: int
    _cooldown_min: int
    _clock: Callable[[], datetime]

    # 런타임 상태
    _scheduler: BaseScheduler                           # AsyncIOScheduler 또는 주입값
    _dnd_enabled: bool                                  # set_dnd로 변경
    _enabled: bool                                      # start 실패 시 False
    _started: bool                                      # 멱등성 플래그
    _last_emitted_at: dict[ProactiveTopic, datetime]    # 토픽별 쿨다운 기록
    _notified_reminders: set[int]                       # event_reminder 중복 방지 (ev.id)
    _emit_lock: asyncio.Lock                            # emit 직렬화
```

### 6.2 로그 카테고리

- `logger.info` — `start()`/`stop()` 각 1회, emit 성공.
- `logger.warning` — 중복 start/stop, APScheduler 초기화 실패, DND 상태 변경.
- `logger.error` — APScheduler 기동 실패, send_text 예외, calendar 조회 실패.
- `logger.debug` — emit 드롭 사유(쿨다운/DND/enabled=False).

개인정보(일정 제목은 §14.3 참조 — V1에서는 제목을 WARN 로그에 그대로 남기되, M_01 `pii_mask` 필터가 휴대폰·이메일·주민번호만 마스킹).

### 6.3 결정 사항

| ID | 결정 | 근거 |
|---|---|---|
| **D-1** | **메시지 합성은 V1에서 하드코딩 한국어 템플릿**(`src/proactive/messages.py`), LLM 자연어 생성은 upstream `proactive_speak_prompt` 경로에 위임. | (a) 본 모듈의 `text` 필드는 upstream이 읽지 않음(§3.2) — 어차피 세밀한 문장은 upstream 프롬프트가 결정. 본 모듈이 LLM에 직접 쿼리하면 M_05 의존성이 양방향이 되어 순환. (b) 템플릿은 결정론적이어서 테스트 가능. (c) 토픽별 세분화된 프롬프트는 RISKS R-PROA-1로 등록(§14.5). |
| **D-2** | **DND는 M_10·M_11 이중 체크**. `set_dnd(bool)` 호출 시 본 모듈이 자체 상태 갱신 + M_10에도 전파. | (a) M_11이 APScheduler 경로(cron/interval)로 들어오는 토픽은 M_10과 무관 — M_10에만 두면 브리핑·알림 토픽의 DND 드롭이 누락. (b) `idle_rest`/`overwork` 토픽도 M_10의 선차단(§1.3)이 있으면 콜백 Task 생성 비용 절약, M_11의 최종 확인으로 페이로드 합성도 억제. (c) M_10 §6.3 D-3 "DND가 선차단"과 일관 — 본 모듈은 "최종 확정". |
| **D-3** | **쿨다운은 토픽별 독립**. 글로벌 단일 쿨다운이 아님. | (a) 초안(`docs/MODULES.md` L395)은 `cooldown_min=30`만 있고 스코프가 불분명. (b) 아침 브리핑(09:00) 직후 10분 내 일정 알림이 떠야 하는 케이스 — 글로벌 쿨다운이면 `event_reminder`가 드롭되어 REQUIREMENTS.md §4.2 위반. (c) `idle_rest`와 `event_reminder`는 의미가 달라 서로 간섭하면 안 됨. (d) 구현 비용은 dict[topic, datetime] 하나로 충분, 추가 복잡도 미미. |
| **D-4** | **Cron `misfire_grace_time=600`(10분)**, Interval `misfire_grace_time=60`(1분). Coalesce=True 공통. | (a) 기동이 09:00 이후에 일어났으면 **기동 후 10분 이내**에만 morning briefing을 쏜다 — "아침 첫 실행 시"(REQUIREMENTS.md §4.2)의 "첫 실행"을 "09:00 이후 10분 이내 기동"으로 해석. 그 이후 기동은 다음 날 09:00까지 대기. (b) 10분을 넘기면 "점심에 갑자기 아침 인사"가 되어 UX 이상. (c) Interval 1분 misfire는 실무적 여유. |
| **D-5** | **upstream 페이로드에 `text`·`topic`·`context` 필드를 싣는다**. upstream이 현재 `text`를 읽지 않아도 향후 확장 여지를 남긴다. | (a) ARCHITECTURE.md L170 명시 포맷. (b) 로그 관찰성 — WebSocket 로깅에서 "어떤 토픽이 언제 발송됐는지" 추적 가능. (c) 향후 `conversation_handler` 확장(§3.2 V2) 시 스키마 변경 없이 바로 활용. (d) upstream 기존 경로는 추가 키를 무시하므로 하위 호환 깨지지 않음. |
| **D-6** | **아바타 표정은 본 모듈이 건드리지 않는다**. `AvatarState.push_event` 직접 호출 금지. | (a) `overwork` 시 "sleepy" 표정 전환은 M_05 GemmaChatAgent가 응답 스트림에 `[emotion:sleepy]` 태그를 포함시키고 M_08이 정상 파이프라인으로 처리. (b) 본 모듈이 M_08에 직접 의존하면 결합도 상승 + 표정·음성 타이밍 동기화 책임이 분산. (c) M_08 §13 "호출자(M_05 또는 M_11)"는 "가능성"을 언급할 뿐, 본 스펙에서 M_11의 역할로 **확정하지 않는다**. |
| **D-7** | **send_text 예외는 삼키고 False 반환**. 상위에 전파하지 않는다. | (a) send_text는 WebSocket이 끊겼을 때 발생 가능 — 사용자가 클라이언트를 닫았거나 네트워크 일시 단절. APScheduler 잡에서 예외가 전파되면 잡이 drop되거나 스케줄러가 중단될 수 있음. (b) M_08 §8 `push_event`는 "전파"지만, 거기는 **대화 흐름의 일부**(사용자 입력 → LLM 응답)로 실패가 상위로 드러나야 의미가 있다. M_11은 **프로액티브**(사용자가 모르는 발화)이므로 실패를 조용히 삼키는 게 UX상 올바르다. (c) 다음 틱에 재시도되므로 영구 손실 아님. |
| **D-8** | **APScheduler 초기화 실패 시 앱 기동 계속**. `_enabled=False`로 강등. | (a) 프로액티브는 부가 기능 — AI 비서 본체(대화)가 살아야 함. (b) M_10 §10 "장애로 인해 AI 비서 본체를 다운시키지 않는다"와 동일 철학. (c) 로그 + 재시도 정책은 V2. V1은 로그만. |
| **D-9** | **scheduler·clock DI 지원**. 테스트에서 FakeScheduler·FakeClock 주입으로 시간·잡 트리거 제어. | (a) M_10 §5.3/§5.5 clock DI 선례. (b) APScheduler 실제 실행 없이 잡 함수를 직접 await해 단위 테스트 가능(§11 N-1~N-7). (c) freezegun 의존성 추가 회피(M_09 §12.4, M_10 §5.3 일관). |
| **D-10** | **event_reminder 중복 방지는 메모리 `set` + 과거 이벤트 garbage collection**. SQLite 플래그 컬럼 추가 금지. | (a) M_09 스키마 V1은 건들지 않는다(M_09 §1.3 "반복 일정 미지원"과 함께 "플래그 컬럼 추가도 V1 out"). (b) 프로세스 재시작 시 캐시가 리셋되면 이미 지난 10분 전 알림은 `events_due_within`이 더 이상 반환하지 않으므로(start 이후 이벤트만 반환) 중복 리스크 없음. (c) 기동 직후 5분 이내 이벤트가 있으면 알림이 한 번 더 뜰 가능성 있으나 UX 수용 가능 범위. (d) 영속성이 필요해지면 V2에서 `reminded_at` 컬럼 추가. |
| **D-11** | **topic 문자열을 M_10 IdleEvent와 공유 가능하도록 두 모듈 Literal이 동일 문자열("idle_rest"/"overwork")을 쓴다**. | (a) M_10 §4.1 `IdleEvent = Literal["idle_rest", "overwork"]`. (b) 본 모듈 `ProactiveTopic`이 이 둘을 포함 + `morning_briefing`, `event_reminder` 추가. (c) `_on_idle_event`에서 별도 매핑 없이 그대로 전달 → 실수 여지 감소. |
| **D-12** | **emit 락은 `asyncio.Lock` 단일**. 토픽별 락 분리 안 함. | (a) emit 내부는 매우 가볍고 호출 빈도 낮음(하루 수~수십 회). (b) 토픽별 락은 복잡도 증가 대비 실익 없음. (c) 쿨다운 판정과 기록 갱신의 원자성만 보장되면 충분. |

---

## 7. 송신 페이로드 스키마 (JSON)

`emit`이 `send_text`에 전달하는 dict:

```json
{
  "type": "ai-speak-signal",
  "text": "<토픽별 한국어 메시지, §7.2 템플릿>",
  "topic": "morning_briefing | event_reminder | idle_rest | overwork",
  "context": {
    "event_id": 42,
    "title": "팀 회의",
    "start": "2026-04-19T15:00:00+09:00",
    "minutes_until": 10,
    "events": [ {...}, ... ]
  }
}
```

### 7.1 필드 규약

| 키 | 타입 | 필수 | 의미 |
|---|---|---|---|
| `type` | str | ✅ | 고정 `"ai-speak-signal"` — upstream `websocket_handler.py` L91 라우팅 키와 일치. 다른 값 금지. |
| `text` | str | ✅ | 토픽별 한국어 템플릿 문자열. upstream 현재 경로는 읽지 않으나(§3.2) 로깅·V2 확장용. 빈 문자열 금지 (len ≥ 1). |
| `topic` | ProactiveTopic | ✅ | 4종 Literal. upstream 확장 시 분기 키. |
| `context` | dict | ✅ (빈 dict 허용) | 토픽별 부가 정보. §7.3 참조. |

**upstream 원본 필드(`"type": "ai-speak-signal"`)에 대한 하위 호환**: upstream L35는 `msg_type == "ai-speak-signal"` 조건만 본다 → 추가 키가 있어도 무시. 본 모듈의 payload는 upstream `_handle_conversation_trigger` → `handle_conversation_trigger`에 그대로 전달되어도 안전.

### 7.2 `_compose_message(topic, context) -> str` 템플릿 (messages.py)

**고정 한국어 템플릿 — V1 결정(D-1).**

```python
def _compose_message(topic: ProactiveTopic, context: dict[str, Any]) -> str:
    if topic == "morning_briefing":
        events = context.get("events") or []
        if not events:
            return "좋은 아침이에요! 오늘은 등록된 일정이 없어요."
        lines = [f"좋은 아침이에요! 오늘 일정은 {len(events)}개예요."]
        for ev in events[:5]:   # 최대 5개만 읽어주기
            start = ev.get("start_hhmm", "?")
            title = ev.get("title", "제목 없음")
            lines.append(f"- {start} {title}")
        if len(events) > 5:
            lines.append(f"(외 {len(events) - 5}개 더)")
        return "\n".join(lines)

    if topic == "event_reminder":
        title = context.get("title", "일정")
        minutes = context.get("minutes_until", 10)
        return f"{minutes}분 뒤 '{title}' 일정이 있어요."

    if topic == "idle_rest":
        return "오래 쉬지 않고 계셨네요. 잠깐 스트레칭은 어떠세요?"

    if topic == "overwork":
        return "2시간 넘게 집중하셨어요. 잠깐 눈을 감고 쉬어보세요."

    raise ValueError(f"unknown topic: {topic!r}")
```

- 테스트는 출력 문자열에 특정 키워드가 포함되는지 검증(§11 test_messages.py).
- 빈 events 리스트·키 누락 시에도 KeyError 없이 동작 — `.get` + 기본값.
- 문장 다양화(어휘 회전, 시간대 인사 변경)는 V2 범위.

### 7.3 토픽별 `context` 스키마

| 토픽 | 필수 키 | 예시 |
|---|---|---|
| `morning_briefing` | `events: list[dict]` (각 dict는 `start_hhmm`, `title` 포함) | `{"events": [{"start_hhmm": "15:00", "title": "팀 회의"}]}` |
| `event_reminder` | `event_id: int`, `title: str`, `start: str` (ISO), `minutes_until: int` | `{"event_id": 42, "title": "회의", "start": "2026-04-19T15:00:00+09:00", "minutes_until": 10}` |
| `idle_rest` | 없음 (빈 dict) | `{}` |
| `overwork` | 없음 (빈 dict) | `{}` |

---

## 8. 호출 경로 / 배선

### 8.1 전체 흐름 다이어그램

```
[기동]
FastAPI create_app
  └── AppServiceContext.load_app_services(app_config)
        └── ProactiveDispatcher(
              calendar=ctx.calendar_service,
              idle_monitor=ctx.idle_monitor,
              send_text=<per-client ws send>,   # §8.2 주의
              morning_time=app_config.morning_briefing_time,
              cooldown_min=app_config.proactive.cooldown_min,
              dnd_enabled=app_config.dnd_enabled,
            )
  └── app.on_event("startup")
        └── await ctx.proactive_dispatcher.start()
              ├── scheduler.add_job(morning_briefing, cron 09:00 KST)
              ├── scheduler.add_job(event_reminder, interval 60s)
              ├── scheduler.start()
              └── idle_monitor.on_event(self._on_idle_event)

[runtime 1 — 매일 09:00]
APScheduler
  └── _job_morning_briefing()
        ├── events = await run_in_executor(calendar.get_events(today_start, today_end))
        └── await emit("morning_briefing", {"events": [...]})
              └── await send_text({"type":"ai-speak-signal", "text": "…", "topic": "morning_briefing", "context": {...}})
                    └── upstream WebSocket 클라이언트 수신 → (클라이언트가 서버로 재송신 또는 서버 자체 loopback)
                          → upstream conversation_handler.handle_conversation_trigger("ai-speak-signal", ...)
                            → Agent → TTS → ws audio 재생

[runtime 2 — 1분마다]
APScheduler
  └── _job_event_reminder()
        ├── events = await run_in_executor(calendar.events_due_within(10))
        ├── for ev in events:
        │     └── if ev.id not in _notified_reminders:
        │           └── if await emit("event_reminder", {...}): _notified_reminders.add(ev.id)
        └── (past-event cache cleanup)

[runtime 3 — 유휴 감지]
IdleMonitor._tick
  └── asyncio.create_task(callback("idle_rest"))
        └── ProactiveDispatcher._on_idle_event("idle_rest")
              └── await emit("idle_rest", {})

[shutdown]
FastAPI lifespan.__aexit__
  └── AppServiceContext.close()
        └── _call_stop(self.proactive_dispatcher, "proactive_dispatcher")
              └── await proactive_dispatcher.stop()
                    ├── scheduler.shutdown(wait=False)
                    └── idle_monitor.on_event(None)
```

### 8.2 `send_text` 주입 전략 — **결정 사항(D-13)**

upstream WebSocket `send_text`는 **per-client**(연결당 다름). M_11은 서버 프로세스 수명 동안 1개 인스턴스이므로 "연결이 몇 개이든 그중 어느 소켓에 쓸 것인가" 문제가 있다.

**결정(D-13)**: 단일 사용자 전제(REQUIREMENTS.md §10) 하에 **"마지막으로 연결된 활성 WebSocket"**에 송신한다. M_01 AppCore가 per-client 연결을 관리하므로, 본 모듈이 직접 `send_text`를 저장하지 않고 **M_01이 제공하는 "현재 활성 클라이언트 dispatcher"** 콜러블을 주입받는다:

```python
# M_01 AppWebSocketHandler 측 (본 스펙 범위 외, 배선 계약만 정의)
async def _active_client_send_text(payload: dict[str, Any]) -> None:
    """client_connections의 가장 최근 연결 WebSocket.send_text(json.dumps(payload))."""
    if not self._client_connections:
        logger.debug("no active client; drop proactive payload")
        return
    ws = next(reversed(self._client_connections.values()))  # 최신 연결
    await ws.send_text(json.dumps(payload))
```

M_11은 이 콜러블을 생성자에서 받아 사용. 활성 연결이 0이면 `emit`은 False 반환(§5.5 step 7의 예외 경로와 동일). 이 `_active_client_send_text` 구현은 **M_01 범위**에서 마무리하며, 본 스펙은 **시그니처 계약(`Callable[[dict], Awaitable[None]]`)만 요구**한다.

**주의**: "활성 클라이언트 없음"은 `send_text` 콜러블이 조용히 반환(예외 없이)해도 되고, 예외를 던져도 된다. 본 모듈은 send_text 예외를 삼키므로(D-7) 어느 쪽이든 `emit` 동작이 손상되지 않는다.

### 8.3 `load_app_services` 배선 1블록

`src/app/service_context.py::load_app_services`에 다음 블록 추가(CalendarService·IdleMonitor 선례 이어서):

```python
# M-11: ProactiveDispatcher 초기화
if self.calendar_service is not None and self.idle_monitor is not None:
    try:
        from proactive import ProactiveDispatcher
        self.proactive_dispatcher = ProactiveDispatcher(
            calendar=self.calendar_service,
            idle_monitor=self.idle_monitor,
            send_text=<M_01 AppWebSocketHandler가 제공>,    # D-13
            morning_time=app_config.morning_briefing_time,
            cooldown_min=app_config.proactive.cooldown_min,
            dnd_enabled=app_config.dnd_enabled,
        )
        logger.info("M_11 ProactiveDispatcher initialized.")
    except Exception as exc:
        logger.warning(f"proactive_dispatcher 초기화 실패: {exc}")
        self.proactive_dispatcher = None
else:
    logger.warning("calendar_service 또는 idle_monitor가 None이므로 proactive_dispatcher 조립 건너뜀")
    self.proactive_dispatcher = None
```

`stop()` 호출 경로는 `src/app/service_context.py` L285~L289에 이미 존재(M_10 배선 완료 시 포함됨 확인, `_call_stop`).

### 8.4 `start()` 호출 지점

M_01 SPEC L332 "`app.on_event("startup")` → `ctx.proactive_dispatcher.start()`" 이미 예약. M_11 빌더는 M_01 `main.py`에서 해당 1줄 확인만 수행(추가 작성 있으면 기록).

```python
@app.on_event("startup")
async def _on_startup() -> None:
    if ctx.idle_monitor is not None:
        ctx.idle_monitor.start()
    if ctx.proactive_dispatcher is not None:
        await ctx.proactive_dispatcher.start()
```

---

## 9. 성능·메모리·동시성

### 9.1 성능

| 지표 | 요구 | 근거 |
|---|---|---|
| `emit` 단일 호출 지연 | ≤ 5 ms (median, send_text 제외) | dict 생성 + lock + rfc3339 format |
| `_job_event_reminder` 1틱 총 소요 | ≤ 100 ms @ 1만건 DB | M_09 §11 `events_due_within` p95 30ms + 중복 체크 O(n) |
| `_job_morning_briefing` 1회 | ≤ 200 ms | M_09 `get_events(1일)` p95 50ms + 메시지 합성 |
| `start()` 지연 | ≤ 500 ms | APScheduler AsyncIOScheduler.start() 벤치마크 |
| `stop()` 지연 | ≤ 100 ms | scheduler.shutdown(wait=False) |

### 9.2 동시성

- `emit`은 `asyncio.Lock`으로 직렬화.
- APScheduler 잡 함수는 `max_instances=1`로 self-overlap 방지.
- IdleMonitor 콜백 Task와 APScheduler Task가 동시 emit → lock 대기.
- `set_dnd`는 이벤트 루프 단일 스레드 가정 — bool 할당은 원자적이지만 emit 락 내부에서 읽으므로 안전.

### 9.3 메모리

| 항목 | 상한 |
|---|---|
| ProactiveDispatcher 인스턴스 | < 1 KB |
| `_last_emitted_at` dict (4 토픽) | < 1 KB |
| `_notified_reminders` set (일일 수십 건) | < 10 KB |
| APScheduler 내부 잡 큐 | < 100 KB |
| **합계** | **< 1 MB** |

---

## 10. 에러 처리 정책

| 상황 | 내부 처리 | 호출자 가시성 |
|---|---|---|
| `__init__` 파라미터 범위 위반 | ValueError/TypeError | 기동 실패 — `load_app_services`가 `logger.warning` + `proactive_dispatcher=None` |
| `start()` 이벤트 루프 없이 호출 | RuntimeError (AsyncIOScheduler 전파) | 호출자(FastAPI) 책임 |
| `start()` scheduler.start() 예외 | `logger.error` + `_enabled=False` + return (예외 전파 X) | 정상 — 기능만 비활성 |
| `start()` 중복 호출 | `logger.warning` + no-op | 정상 |
| `stop()` start 이전 호출 | no-op | 정상 |
| `stop()` scheduler.shutdown 예외 | `logger.warning` + swallow | 정상 |
| `emit` topic Literal 밖 | ValueError | 호출자(내부 코드) 버그 — 즉시 드러남 |
| `emit` DND drop | `logger.debug` + return False | 정상 |
| `emit` 쿨다운 drop | `logger.debug` + return False | 정상 |
| `emit` send_text 예외 | `logger.error` + return False (D-7) | 정상 (다음 틱 재시도) |
| `emit` `_enabled == False` | return False | 정상 |
| `_job_morning_briefing` 중 calendar.get_events 예외 | `logger.error` + 잡 종료 (APScheduler는 다음 실행 스케줄링) | 정상 |
| `_job_event_reminder` 중 calendar.events_due_within 예외 | `logger.error` + return | 정상 |
| IdleMonitor 콜백에서 예외 발생 | 본 모듈의 `_on_idle_event`는 emit 호출만; emit이 자체 예외 방어 | 정상 |
| `set_dnd` 인자 bool 아님 | TypeError | 호출자 책임 |
| `set_dnd` idle_monitor 전파 중 idle_monitor.set_dnd가 TypeError | 본 모듈에서도 TypeError 전파 (호출자 책임) | 호출자 책임 |
| 시스템 시계 역행 (`clock()`이 과거로) | `(now - last).total_seconds()` 음수 → 쿨다운 만료로 간주해 False 판정 실패 → emit 진행 | 부수 효과: 쿨다운이 일찍 풀릴 수 있음. 로그 없이 허용(M_10 D-10과 동일 철학). |

**원칙**:
- 생성자 검증은 fail-fast.
- 런타임 실패는 self-healing (로그 + False 반환).
- 프로액티브 기능 장애로 AI 비서 본체를 죽이지 않는다.

---

## 11. 테스트 케이스

pytest + pytest-asyncio. 합계 **정상 7 + 엣지 7 + 적대적 4 = 18건**.

### 11.1 정상 케이스 (Normal, N) — ≥7

**N-1. `emit("morning_briefing", {"events": [...]})` 성공**
- 준비: FakeSendText(AsyncMock), FakeCalendar, FakeIdleMonitor.
- `emit` 호출.
- 기대: `send_text`가 `{"type": "ai-speak-signal", "topic": "morning_briefing", ...}`로 1회 호출. `_last_emitted_at["morning_briefing"]` 기록.

**N-2. `emit("event_reminder", {...})` 성공 + 쿨다운 기록**
- `emit("event_reminder", {"event_id": 1, "title": "회의", "start": "...", "minutes_until": 10})`.
- 기대: send_text 1회 호출. context.title == "회의" 포함.

**N-3. IdleMonitor 콜백 → `idle_rest` emit**
- FakeIdleMonitor에 `on_event`로 등록된 콜백을 직접 호출 `await cb("idle_rest")`.
- 기대: send_text 1회 호출 (topic=idle_rest).

**N-4. IdleMonitor 콜백 → `overwork` emit**
- N-3와 동일 구조, topic="overwork".

**N-5. 쿨다운 만료 후 재emit 성공**
- `emit("idle_rest", {})` (t=0, OK) → clock.advance(31분) → `emit("idle_rest", {})` (성공).
- 기대: send_text 2회 호출.

**N-6. DND OFF 상태에서 정상 emit**
- 기본 `dnd_enabled=False`, `emit("idle_rest", {})` → True 반환.

**N-7. `start()`/`stop()` 정상 호출 (FakeScheduler 사용)**
- FakeScheduler 주입.
- `await dispatcher.start()`: FakeScheduler.add_job 2회 호출 (morning_briefing cron, event_reminder interval). FakeScheduler.start() 1회 호출. idle_monitor.on_event가 _on_idle_event로 바인딩.
- `await dispatcher.stop()`: FakeScheduler.shutdown 1회. idle_monitor.on_event(None).

### 11.2 엣지 케이스 (Edge, E) — ≥7

**E-1. 쿨다운 중 emit → False 반환**
- `emit("idle_rest", {})` (t=0) → True.
- clock.advance(29분 59초) → `emit("idle_rest", {})` → False. send_text 1회만(2회째 호출 없음).

**E-2. DND ON → 모든 토픽 drop**
- `set_dnd(True)`.
- `emit("morning_briefing", {...})` → False.
- `emit("event_reminder", {...})` → False.
- `emit("idle_rest", {})` → False.
- `emit("overwork", {})` → False.
- send_text 0회. `_last_emitted_at` 갱신 안 됨.

**E-3. 토픽별 쿨다운 독립 (D-3 회귀)**
- `emit("morning_briefing", {"events": []})` (t=0) → True.
- `emit("event_reminder", {...})` (t=0) → True. (서로 다른 토픽이므로 쿨다운 간섭 없음.)
- send_text 2회.

**E-4. `_job_morning_briefing` events 0건 — 브리핑 발송**
- FakeCalendar.get_events returns `[]`.
- `await dispatcher._job_morning_briefing()` 직접 호출.
- 기대: `emit("morning_briefing", {"events": []})` 호출. send_text에서 text="좋은 아침이에요! 오늘은 등록된 일정이 없어요." 포함.

**E-5. `_job_event_reminder` 중복 방지 (D-10 회귀)**
- FakeCalendar.events_due_within returns `[Event(id=1, ...)]` (2회 연속 호출해도 같은 이벤트).
- `await dispatcher._job_event_reminder()` 2회 호출.
- 기대: emit("event_reminder", ...) 1회만 호출. `_notified_reminders`에 1 포함.

**E-6. `start()` 중복 호출 멱등성**
- `await dispatcher.start()` 2회.
- 기대: 두 번째는 `logger.warning` + no-op. scheduler.add_job이 2회 호출되지 않음(총 2건만 — 잡 2종 × 1회).

**E-7. 잘못된 topic ValueError**
- `await dispatcher.emit("unknown_topic", {})` → ValueError.

### 11.3 적대적 케이스 (Adversarial, A) — ≥4

**A-1. APScheduler 초기화 실패 → 기능 비활성, 앱 기동 계속 (D-8 회귀)**
- FakeScheduler.start() 에 `side_effect=RuntimeError("scheduler broken")`.
- `await dispatcher.start()` → 예외 밖으로 나오지 않음. `_enabled == False`. 후속 `emit` 호출은 False 반환.

**A-2. `send_text` 예외 → False 반환, 본 모듈 생존 (D-7 회귀)**
- FakeSendText AsyncMock with `side_effect=ConnectionError("ws closed")`.
- `await dispatcher.emit("idle_rest", {})` → False.
- `_last_emitted_at["idle_rest"]`에 기록되지 않음 (쿨다운 미갱신 → 다음 틱 재시도 가능).
- 후속 `emit` 호출 정상 동작.

**A-3. 시계 역행 — 쿨다운 체크 왜곡**
- `emit("idle_rest", {})` (t=0) → True.
- clock = 과거로 역행 (t=-60분).
- `emit("idle_rest", {})` → True (쿨다운 판정이 음수 초로 간주되어 통과).
- 기대: 예외 없음. send_text 2회 호출. `logger.debug` 메시지 없음 (조용히 허용).

**A-4. 한 틱에 event 10개 — 모두 emit (쿨다운 간섭 확인)**
- FakeCalendar.events_due_within returns `[Event(id=i, ...) for i in range(10)]`.
- `_job_event_reminder` 1회.
- 기대: `event_reminder` emit 10회 호출 (각각 다른 event_id). **쿨다운은 토픽 기준**이므로 같은 틱 내에서는 다른 event_id여도 2번째부터 쿨다운에 막힌다 — `event_reminder` 토픽 기준 첫 1건만 성공. 나머지 9건은 False.
- 이 결과는 **§6.3 D-3의 trade-off**: 동일 토픽에서 한 틱에 여러 이벤트가 10분 안에 겹치면 첫 알림만 나간다. RISKS R-PROA-2(§14.5)로 등록.

### 11.4 테스트 지원 도구

- `pytest-asyncio` `@pytest.mark.asyncio`.
- **FakeScheduler**: `add_job / start / shutdown`만 가진 최소 Mock. `add_job`으로 받은 함수를 `trigger_job(name)`으로 직접 호출 가능하게 해 APScheduler 트리거를 시뮬레이션.
- **FakeCalendar**: `events_due_within(minutes)` / `get_events(start, end)` / `get_event(id)` 세 메서드만 mock. 미리 설정된 list 반환.
- **FakeIdleMonitor**: `on_event(cb)`만 기록. `set_dnd(bool)` no-op. 테스트에서 `trigger_idle_event("idle_rest")`로 콜백 직접 호출.
- **FakeClock**: `class FakeClock: _t; __call__; advance(delta)` (M_10 §5.5와 동일).
- **FakeSendText**: `AsyncMock()` — 호출 인자 기록.
- 타임아웃: 각 테스트 `@pytest.mark.timeout(5)`.

### 11.5 실제 APScheduler 실행 스모크 (integrator 범위)

단위 테스트 전부 FakeScheduler 기반. 실제 `AsyncIOScheduler`가 cron/interval 트리거를 발화하는지는 **integrator 에이전트가 통합 테스트**(Windows VM 또는 Linux CI에서 scheduler.start() 후 짧은 시간 대기 방식)로 수행 — M_11 단위 테스트 DoD에 포함하지 않는다.

---

## 12. Definition of Done

### 12.1 공통 (CLAUDE.md "산출물 체크리스트")

- [ ] `specs/M_11_ProactiveDispatcher_SPEC.md` (본 문서) 사용자 승인.
- [ ] `src/proactive/` 하위 파일(§5.1) 구현.
- [ ] `tests/proactive/` 테스트 파일: 정상 ≥7, 엣지 ≥7, 적대적 ≥4 (본 스펙 기준 18건).
- [ ] `ruff format .`, `ruff check .`, `mypy src/`, `pytest tests/proactive/ -v` 모두 통과.
- [ ] 테스트 커버리지 ≥ 70% (본 모듈 한정).
- [ ] `reviews/M_11_ProactiveDispatcher_REVIEW.md`에 Critic PASS 기록.
- [ ] `docs/MODULES.md` M_11 행 상태가 `✅ DONE`으로 갱신 + 초안 대비 차이(§15) 반영.

### 12.2 M_11 고유 DoD (docs/MILESTONES.md L139~L148 기준)

- [ ] 매일 09:00 KST cron 트리거로 `morning_briefing` 1회 발송(단위 테스트에서는 `_job_morning_briefing` 직접 호출로 검증).
- [ ] 1분 간격 interval 트리거로 `events_due_within(10)` 호출 → 결과 이벤트별 `event_reminder` 발송 + 중복 방지.
- [ ] IdleMonitor 콜백 수신 시 `idle_rest`/`overwork` 토픽으로 emit.
- [ ] 토픽별 쿨다운 (기본 30분) 적용 — 동일 토픽 재emit 드롭.
- [ ] DND ON 시 모든 토픽 drop + M_10에 전파.
- [ ] APScheduler 초기화 실패 시 `_enabled=False`로 강등, 앱 기동 계속.

### 12.3 무결성

- [ ] upstream `Open-LLM-VTuber/**` git diff 빈 상태.
- [ ] 새 의존성 정확히 1종 (`APScheduler>=3.10,<4`) — `pyproject.toml` 추가 + `scripts/bundle_deps.sh` 갱신.
- [ ] 네트워크 호출 0건: `grep -r "requests\|httpx\|urllib\|fetch(" src/proactive` → 0.

### 12.4 배선 범위 결정

- [ ] `src/app/service_context.py::load_app_services` 내 `ProactiveDispatcher(...)` 주입 블록 추가(§8.3).
- [ ] `send_text` 콜러블 제공 루트: M_01 `AppWebSocketHandler`에 `_active_client_send_text` 메서드 추가 (§8.2 D-13). **본 스펙은 M_01에 1~5줄 추가를 요구**하며, M_11 builder가 해당 수정을 동반 커밋한다. M_01 SPEC 수정 필요 여부는 §14.5 RISKS R-PROA-3로 등록.
- [ ] FastAPI `@app.on_event("startup")` 에 `ctx.proactive_dispatcher.start()` 1줄 추가 확인 (M_01 SPEC L332 기존재 — 실제 코드 반영 여부를 M_11 builder가 확인·추가).
- [ ] `tests/app/test_service_context.py`에 ProactiveDispatcher 주입 회귀 테스트 1건 추가 (`unittest.mock.patch("proactive.ProactiveDispatcher")`).

### 12.5 문서 동기화

- [ ] `docs/MODULES.md` M_11 블록 상태 `🔲 TODO` → `✅ DONE`, 초안 대비 변경 사항(§15)을 공개 API 블록에 반영:
  - `__init__`에 `timezone`, `reminder_check_interval_seconds`, `dnd_enabled`, `clock`, `scheduler` 인자 추가.
  - `set_dnd(enabled: bool) -> None` 메서드 추가.
- [ ] `docs/RISKS.md`에 R-PROA-1/R-PROA-2/R-PROA-3 추가 (§14.5).

---

## 13. 의존성

### 13.1 신규 Python 패키지

| 패키지 | 버전 제약 | 용도 | 환경 마커 |
|---|---|---|---|
| `APScheduler` | `>=3.10,<4` | AsyncIOScheduler, CronTrigger, IntervalTrigger | 없음 (모든 플랫폼 공통) |

**선택 근거**:
- **APScheduler vs aiocron**: APScheduler가 stdlib 수준 성숙도(10년+ 유지보수), Cron + Interval을 **동일 API**로 제공, AsyncIOScheduler가 asyncio 이벤트 루프와 자연스럽게 통합.
- **APScheduler vs 자체 asyncio.sleep 루프**: DST·윤초·프로세스 슬립 복원 처리가 APScheduler에 이미 구현되어 있어 재발명 낭비.
- 외부 네트워크 호출 없음(`grep -r 'http' apscheduler/` = 0). 오프라인 번들 정책 §0 통과.

### 13.2 `pyproject.toml` 추가

```toml
# 기존 dependencies 블록 말미에 추가:
"APScheduler>=3.10,<4",
```

### 13.3 `scripts/bundle_deps.sh` 갱신

`=== [bundle_deps.sh] M_11 ProactiveDispatcher 의존성 ===` 블록 추가:

```bash
pip download \
    "APScheduler>=3.10,<4" \
    --dest "${WHEELS_DIR}"
```

APScheduler는 `tzlocal`, `pytz_deprecation_shim` 등 경미한 트랜지티브 의존성을 가진다. `pip download`가 자동으로 해결하므로 명시 열거 불필요.

### 13.4 표준 라이브러리

- `asyncio` — Lock, Task, create_task, get_running_loop.
- `datetime` / `timedelta` / `timezone` — 시각 산술.
- `zoneinfo.ZoneInfo` — Asia/Seoul tz.
- `typing` — Literal, Callable, Awaitable, Any.
- `logging` (loguru) — M_01 표준 로거.

---

## 14. 스펙 외 사항 (명시적 제외, 오해 방지용) + RISKS

### 14.1 범위 외 기능

본 모듈의 책임이 **아닌** 항목:

1. **토픽별 세밀한 LLM 프롬프트 라우팅** — upstream `conversation_handler.py` 확장 필요 (§3.2 V2). V1은 `proactive_speak_prompt` 단일 템플릿 재사용.
2. **아바타 표정 전환** (§6.3 D-6). M_05/M_08 책임.
3. **프론트 토스트·팝업 UI** — M_12 + upstream frontend 책임.
4. **반복 일정(RRULE) 알림** — M_09 §1.3 제외와 일관.
5. **메시지 톤 다양화 / 어휘 회전** — V2.
6. **프로액티브 발화 이력 SQLite 저장** — V2.
7. **다중 사용자 / 각 사용자별 개별 쿨다운** — REQUIREMENTS.md §10 단일 사용자.
8. **사용자 부재 장기 감지에 의한 브리핑 억제** — V2 (§1.3 항목 8).
9. **모바일 알림 / 이메일 연동** — REQUIREMENTS.md §10.
10. **reminder_lead_minutes의 동적 변경** — 생성자 고정.
11. **APScheduler 잡 pause/resume UI** — V1 미포함. DND만으로 제어.

### 14.2 "나중에 결정" 금지

본 스펙에서 **결정하지 않은 사항은 없다**. 모호한 지점은 §14.5 RISKS에 명시적으로 등록.

### 14.3 개인정보 취급

- event_reminder emit 시 payload `context.title`에 사용자가 입력한 일정 제목이 그대로 들어간다. 제목에 개인정보(이름·연락처)가 포함될 수 있음.
- 방어: M_01 `pii_mask`(`specs/M_01_AppCore_SPEC.md` §로깅)가 log record에 휴대폰·이메일·주민번호 패턴만 마스킹 — 일반 이름은 미처리.
- WebSocket 페이로드는 localhost 전송이므로 네트워크 노출 없음.
- 로그 레벨 INFO에서 `logger.info("emit success: topic=%s", topic)`만 — title은 DEBUG 레벨에서만. DEBUG는 기본 비활성.
- 추가 마스킹은 V2.

### 14.4 로그 노이즈 억제

- `_job_event_reminder`가 1분마다 돌면서 "0건" 결과에서도 `logger.debug`를 뱉지 않도록 — 결과 len==0 시 로그 생략.
- emit 드롭(DND/쿨다운)은 DEBUG — 운영 로그(INFO)에 노이즈 없음.

### 14.5 RISKS (docs/RISKS.md에 등록 필요)

| ID | 제목 | 심각도 | 상태 | 완화 방안 |
|---|---|---|---|---|
| **R-PROA-1** | upstream `proactive_speak_prompt`가 토픽 무관 단일 템플릿 — morning_briefing·event_reminder·idle_rest·overwork의 어조가 구분되지 않음 | MEDIUM | OPEN | V2에서 `conversation_handler.py`에 `data.get("topic")` 분기 추가. 본 스펙은 payload에 topic 필드를 실어 호환 준비. |
| **R-PROA-2** | 한 틱에 10분 이내 이벤트가 여러 건 있으면 첫 건만 알림 — 토픽 단위 쿨다운이 "동일 토픽 첫 1건"만 통과시킴 (§11 A-4) | LOW | OPEN | V1은 허용(실무상 드뭄). V2에서 `event_reminder` 토픽에 한해 `(topic, event_id)` 쿨다운 키 확장. |
| **R-PROA-3** | M_01 `AppWebSocketHandler`에 `_active_client_send_text` 메서드가 현재 없음 — M_11 builder가 M_01 코드에 수~5줄 추가 필요(§8.2 D-13) | LOW | OPEN | M_11 builder 커밋에 M_01 수정 포함. M_01 SPEC 본문에도 `AppWebSocketHandler.send_to_active_client` 메서드 계약 추가 필요 여부는 Critic 판단. |
| **R-PROA-4** | `start()` 시점에 활성 WebSocket이 없으면 scheduler는 돌지만 `emit`이 항상 False를 반환 — 기동 직후 몇 분간 브리핑이 누락될 수 있음 | LOW | OPEN | misfire_grace_time=600로 완화. 그 이상 지연 시 다음 날 대기 허용. |

---

## 15. docs/MODULES.md 초안과의 일치·수정 사항

`docs/MODULES.md` L379~L403의 M_11 초안과 본 스펙의 차이. 본 스펙 승인 후 `docs/MODULES.md`를 아래와 같이 갱신 (M_10 §16 선례 동일 패턴).

### 15.1 변경 요약 표

| 항목 | 초안 | 본 스펙 | 수정 근거 |
|---|---|---|---|
| `cooldown_min: int = 30` (단일, 스코프 불명) | 있음 | 유지하되 **토픽별 독립 쿨다운**으로 해석 명시 (§6.3 D-3) | REQUIREMENTS.md §4.2 "아침 브리핑 직후 10분 전 알림" 흐름이 글로벌 쿨다운이면 드롭됨. |
| `timezone: ZoneInfo` | 없음 | **추가** (기본 Asia/Seoul) | APScheduler CronTrigger에 필수. 해외 지사 설치 대비. |
| `reminder_check_interval_seconds: int = 60` | 없음 | **추가** | 단위 테스트에서 빠른 폴링(10초)으로 검증 가능. |
| `dnd_enabled: bool = False` | 없음 | **추가** (AppConfig.dnd_enabled 초기값 전달) | REQUIREMENTS.md §5 "사용자가 설정 가능" — 런타임 토글 + 초기값. |
| `clock: Callable[[], datetime]` | 없음 | **추가** | 테스트 용이성 (M_10 §5.3 선례). freezegun 의존성 회피. |
| `scheduler: BaseScheduler \| None` | 없음 | **추가** (내부용 DI) | 테스트 용이성 — FakeScheduler로 APScheduler 실행 회피. |
| `set_dnd(enabled: bool) -> None` | 없음 | **추가** (공개 메서드) | REQUIREMENTS.md §5 + M_10 §6.3 D-2 이중 체크 구조. |
| `start()` sync | `async def start()` | 유지 (`async`) | scheduler.start()는 sync지만 async로 통일해 호출 스타일 일관. |
| `stop()` sync | `async def stop()` | 유지 (`async`) | AppServiceContext._call_stop이 양쪽 수용. |
| `emit` 페이로드 필드 | 명시 없음 | **`{type, text, topic, context}` 4키 확정** (§7) | ARCHITECTURE.md L170 + upstream 하위 호환. |
| 의존성 | `APScheduler, M_09, M_10` | 동일 + 버전 제약 `>=3.10,<4` 명시 | 1차 릴리스 기준. |
| 에러 정책 | "스케줄러 초기화 실패 → 로그 경고 + 기능 OFF" | 동일 + `_enabled=False` 플래그 + send_text 예외 삼킴 (D-7, D-8) | M_10 §10 철학 일관. |

### 15.2 M_11 블록 치환 문구 (MODULES.md 반영용)

```markdown
### M_11 ProactiveDispatcher (스케줄러 + 쿨다운 + DND)

- **분류**: NEW
- **상태**: ✅ DONE  (← 🔲 TODO)
- **목적**: APScheduler cron(매일 09:00 KST) + interval(1분) 잡과 M_10 IdleMonitor 콜백을
  받아 토픽별 쿨다운·DND 정책을 적용한 뒤 upstream `ai-speak-signal` 경로로 WebSocket 발화 지시 발송.
- **공개 API**
  ```python
  ProactiveTopic = Literal["morning_briefing", "event_reminder", "idle_rest", "overwork"]
  SendTextCallback = Callable[[dict[str, Any]], Awaitable[None]]

  class ProactiveDispatcher:
      def __init__(self, *,
                   calendar: CalendarService,
                   idle_monitor: IdleMonitor,
                   send_text: SendTextCallback,
                   morning_time: str = "09:00",
                   timezone: ZoneInfo = ZoneInfo("Asia/Seoul"),
                   reminder_lead_minutes: int = 10,
                   reminder_check_interval_seconds: int = 60,
                   cooldown_min: int = 30,
                   dnd_enabled: bool = False,
                   clock: Callable[[], datetime] = datetime.now,
                   scheduler: BaseScheduler | None = None) -> None: ...
      async def start(self) -> None: ...
      async def stop(self) -> None: ...
      async def emit(self, topic: ProactiveTopic,
                     context: dict[str, Any] | None = None) -> bool: ...
      def set_dnd(self, enabled: bool) -> None: ...
  ```
- **에러**: APScheduler 초기화 실패 → `_enabled=False` 강등 + logger.error, 앱 기동 계속.
  send_text 예외 → logger.error + return False (다음 틱 재시도).
- **의존**: `APScheduler>=3.10,<4`, M_09 CalendarService, M_10 IdleMonitor.
- **비고**: 쿨다운은 토픽별 독립. DND는 M_10/M_11 이중 체크(본 모듈이 M_10에 전파).
  send_text 콜러블은 M_01 `AppWebSocketHandler`가 `_active_client_send_text`로 제공 (§8.2 D-13).
```

---

## 16. 부록 — upstream·소스 증적

본 스펙 작성 중 참조한 경로:

- `upstream/Open-LLM-VTuber/src/open_llm_vtuber/conversations/conversation_handler.py` L35~L64 — `ai-speak-signal` 수신 시 `proactive_speak_prompt` 로드 경로.
- `upstream/Open-LLM-VTuber/src/open_llm_vtuber/websocket_handler.py` L42, L91 — `ai-speak-signal`이 수신 타입으로 등록됨 (M_11이 **클라이언트→서버 방향**으로 페이로드를 주입).
- `src/app/service_context.py:40~44` — `idle_monitor`, `avatar_state`, `proactive_dispatcher` 슬롯 기존재.
- `src/app/service_context.py:251~261` — M_10 IdleMonitor 배선 선례.
- `src/app/service_context.py:285~289` — `_call_stop(self.proactive_dispatcher, "proactive_dispatcher")` 호출 경로 기존재.
- `src/app/config.py:106~135` — `ProactiveConfig` 3필드 + `cooldown_min` 기존재.
- `src/app/config.py:151~152` — `AppConfig.morning_briefing_time`, `dnd_enabled` 기존재.
- `src/app/config.py:156~182` — `morning_briefing_time` HH:MM validator 기존재.
- `specs/M_01_AppCore_SPEC.md` L332 — FastAPI startup hook에 `ctx.proactive_dispatcher.start()` 호출 계획 기존재.
- `specs/M_01_AppCore_SPEC.md` L914 — upstream `ai-speak-signal` 경로 재사용 계약 명시.
- `specs/M_09_CalendarService_SPEC.md` §4.2 — `events_due_within(minutes) -> list[Event]` sync API + `get_events(start, end)` 반열린 구간.
- `specs/M_10_IdleMonitor_SPEC.md` §6.3 D-1/D-2/D-3 — 쿨다운·DND 책임 경계, 콜백 단일 슬롯, DND 이중 체크.
- `specs/M_10_IdleMonitor_SPEC.md` §13.4 — M_11 호출 계약 예시 의사코드.
- `specs/M_08_AvatarState_SPEC.md` §7 — `send_text`가 dict를 받는 콜러블 시그니처 선례.
- `docs/ARCHITECTURE.md` L157~L176 — 프로액티브 흐름 다이어그램.
- `docs/MILESTONES.md` L139~L148 — M_11 DoD 5항.
- APScheduler 공식 문서(외부): https://apscheduler.readthedocs.io/ — 코드 런타임에 접근하지 않음, 설계 근거만.

본 스펙이 **upstream 파일을 수정하지 않는다**는 CLAUDE.md 규칙을 준수. M_01 배선은 본 프로젝트 파일(`src/app/*.py`) 수정 범위.

---
