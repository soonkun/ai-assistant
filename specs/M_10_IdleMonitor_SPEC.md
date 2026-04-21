# M_10 IdleMonitor — 스펙

> 분류: **NEW** — upstream `Open-LLM-VTuber/`에는 유휴 감지·휴식 권고 코드가 없다. `docs/ARCHITECTURE.md` §1(Windows API 블록)에서 NEW로 표시된 컴포넌트.
>
> 작성 근거: `REQUIREMENTS.md` §0/§5/§9/§10, `docs/MODULES.md` M_10(L350~L371)·M_11(L373~L397)·M_01(L44~L63), `docs/MILESTONES.md` M_10(L129~L137)·M_11(L139~L148), `docs/ARCHITECTURE.md` §1(L40~L50 ServiceContext 슬롯, L85~L95 Windows API 레이어, L158~L165 M_10 → ProactiveDispatcher), `docs/RISKS.md` R-10(pynput EDR 차단 시 GetLastInputInfo 폴백 필수), `specs/M_01_AppCore_SPEC.md` §서비스 컨텍스트(L196, L278 stop 순서), `specs/M_09_CalendarService_SPEC.md`(DI·sync 결정·테스트 스타일), `specs/M_08_AvatarState_SPEC.md`(결정 사항 표 + 초안 대비 표 스타일), `src/app/service_context.py:40,267~271`(idle_monitor 슬롯·stop 호출 경로).

---

## 1. 목적과 범위

### 1.1 목적

Windows 10/11 단일 사용자 PC에서 키보드·마우스 입력의 **유무**를 관찰해, 다음 두 가지 **상태 전이**를 비동기 콜백으로 방출하는 서비스 계층을 제공한다.

1. **`idle_rest`** — 마지막 입력 이후 `idle_threshold_min`(기본 45분)이 경과. REQUIREMENTS.md §5 "휴식 권고".
2. **`overwork`** — 연속 입력 상태(`active_gap_seconds` 이내 간격 유지)가 `overwork_threshold_min`(기본 2시간) 이상 지속. REQUIREMENTS.md §5 "이제 그만 일하라".

본 모듈은 **"상태 전이 감지기"**다. 메시지 문구 생성·WebSocket 송신·쿨다운·방해 금지 드롭·APScheduler 트리거는 **M_11 ProactiveDispatcher**의 책임이다(§6.3 D-1).

### 1.2 In-Scope

1. `IdleMonitor` 클래스 — `__init__` / `start` / `stop` / `set_dnd` / `on_event` / `last_input_at` / `seconds_since_last_input` / `_tick` 공개 메서드 8종.
2. `IdleEvent = Literal["idle_rest", "overwork"]` 타입 alias.
3. 두 백엔드 구현(§5.1):
   - **Primary** `PynputBackend` — `pynput.keyboard.Listener` + `pynput.mouse.Listener` 훅.
   - **Fallback** `Win32IdleBackend` — `ctypes`로 `user32.GetLastInputInfo()` 1초 폴링.
   - 공통 인터페이스 `_IdleBackend` (ABC).
4. 비Windows(`sys.platform != "win32"`) 환경용 **no-op 백엔드** `NoopBackend` — import는 성공, `start()`는 `logger.warning` 1회 + 아무 훅도 걸지 않음(§6.3 D-5).
5. `asyncio.Task` 기반 폴링 루프 — 1초(조정 가능, §6.3 D-4)마다 `_tick(now)` 호출.
6. 상태 기계(§5.2) — `IDLE` ↔ `ACTIVE` 두 상태만. 동일 전이에서 이벤트는 **1회만** 방출(§6.3 D-7).
7. 단일 콜백 슬롯 (§6.3 D-2) — `on_event(cb)`가 여러 번 호출되면 **덮어쓰기**.
8. `clock: Callable[[], datetime]` 주입 (§5.3) — 테스트에서 `_tick(fake_now)` 또는 monkeypatch로 시간 빨리감기.
9. `backend: _IdleBackend | None` 주입 (§5.3) — 테스트에서 pynput/pywin32 회피.
10. 단위 테스트(정상 ≥7, 엣지 ≥7, 적대적 ≥4; §12).
11. `pyproject.toml`에 `pynput` 추가 + `pywin32`를 Windows 전용 마커로 추가(§14), `scripts/bundle_deps.sh`에 wheel 수집 라인 추가(§14.3).
12. `src/app/service_context.py::load_app_services`에 `IdleMonitor(...)` 주입 1줄 + `close()` 경로 활용(`_call_stop` 이미 존재, §13).

### 1.3 Out-of-Scope (명시적 제외)

1. **쿨다운 적용**: 동일 이벤트(`idle_rest`/`overwork`)를 N분 내 재발행 금지 — **M_11 ProactiveDispatcher**의 책임(`cooldown_min=30` 파라미터). 근거: §6.3 D-1. 본 모듈은 "상태 전이 이벤트의 진실 공급원"만 제공한다.
2. **방해 금지(DND) 이벤트 드롭**: 본 스펙은 `set_dnd(enabled)`를 **제공**하되, DND가 `True`면 콜백 호출 자체를 **건너뛴다**(리소스 절약, §6.3 D-3). M_11도 자체 DND 플래그를 가질 수 있으나 **본 모듈의 drop이 선차단**(상위 층 중복 방지).
3. **WebSocket 송신 페이로드 생성**: M_11이 단일 WS 송신 타입 `ai-speak-signal`로 변환(상세: specs/M_11_ProactiveDispatcher_SPEC.md §7.3). 본 모듈은 `IdleEvent` Literal 문자열만 전달.
4. **APScheduler 연동 / 아침 브리핑 / 일정 10분 전 알림**: M_11의 책임(`docs/MILESTONES.md` L143~L146).
5. **로그인/잠금 화면 감지**: Windows 세션 락(`WTSSESSION_CHANGE`) 이벤트는 본 모듈에서 다루지 않는다. 화면 잠금 상태에서는 입력 이벤트가 자연스럽게 0건이 되어 `idle_rest`로 귀결되므로 별도 처리 불필요. 세션 상태 추적은 V2 검토.
6. **다중 사용자 분리**: REQUIREMENTS.md §10 "1인 1PC". 단일 프로세스 단일 인스턴스.
7. **Linux/macOS 전역 입력 훅**: REQUIREMENTS.md §0 Windows 전용. 비Windows는 no-op(§1.2 항목 4).
8. **EDR 예외 등록 자동화 / 사내 IT 협의 절차**: R-10 완화 방안 2번은 운영 절차(IT 부서 협의), 본 모듈 책임 아님.
9. **사용자별 임계값 UI**: `idle_threshold_min` / `overwork_threshold_min`은 생성자 인자로 고정. 설정 변경 UI는 M_12 범위 또는 V2.
10. **이벤트 메타데이터 확장**: 콜백 시그니처는 `Callable[[IdleEvent], Awaitable[None]]`로 Literal 문자열만 전달(§6.3 D-6). `duration_seconds`, `since` 등 부가 정보가 필요한 소비자(M_11)는 `last_input_at()`·`seconds_since_last_input()` 헬퍼를 **조회**해 얻는다.
11. **입력 내용(키 코드·마우스 좌표) 기록**: 본 모듈은 "입력이 있었는지"만 본다. 키 내용은 수집·저장·로깅하지 않는다(프라이버시 원칙).

---

## 2. 요구사항 연결

| REQUIREMENTS.md / 설계 문서 항목 | M_10 기여 |
|---|---|
| §0 Windows 10/11 전용 / 오프라인 | `pynput`(전역 훅) + `ctypes user32.GetLastInputInfo` 폴백. 외부 네트워크 호출 0건. |
| §5 "마우스·키보드 입력이 임계 시간(기본 45분) 없으면 가볍게 휴식 권고" | `idle_threshold_min=45` 기본값, 임계값 초과 시 `idle_rest` 콜백 1회. |
| §5 "연속 업무 임계 시간(기본 2시간)" | `overwork_threshold_min=120` 기본값 + `active_gap_seconds=60`으로 "연속" 정의. |
| §5 "메시지는 반복되지 않게 쿨다운 로직 적용" | 본 모듈은 동일 상태에 대해 전이당 1회만 방출(§6.3 D-7). 시간 기반 쿨다운은 M_11. |
| §5 "사용자가 방해 금지 모드 설정 가능" | `set_dnd(True/False)`. DND 활성 시 콜백 건너뜀(§6.3 D-3). |
| §9 외부 네트워크 호출 금지 | `pynput`·`pywin32`·`ctypes`·`asyncio` 모두 로컬. |
| §9 메모리 예산 | 훅 큐 + 단일 폴링 Task. 추가 메모리 < 5 MB(§11). |
| §10 다중 사용자 불가 | 단일 인스턴스 가정. |
| docs/RISKS.md R-10 (MEDIUM, OPEN) | **pynput 실패 시 `GetLastInputInfo` 폴백 필수 포함** — §5.1 Primary/Fallback 구조로 만족. |
| docs/ARCHITECTURE.md §3.4(프로액티브 흐름) | `IdleMonitor` → `ProactiveDispatcher.emit("idle_rest" / "overwork")` 경로 (§13.4). |
| docs/MILESTONES.md M_10 DoD 5항 | §13.2에 1:1 매핑. |

---

## 3. upstream 재사용 분석

### 3.1 분류: **NEW** (REUSE 0건, EXTEND 0건, DROP 0건)

`rg -n "pynput|GetLastInputInfo|idle_monitor|IdleMonitor" upstream/Open-LLM-VTuber/` 실행 시 히트 0건. upstream은 음성 대화·TTS·VAD·LLM Agent 프레임워크로 유휴 감지 도메인을 포함하지 않는다.

### 3.2 ARCHITECTURE.md §1 Windows API 블록 근거

```
│ Windows API (M_10)         │
│  pynput: keyboard/mouse    │
│  mss: screenshot           │
│  pywin32: always-on-top    │
```

`pynput` 행이 본 모듈, `mss` 행은 M_05b(ScreenshotService), `pywin32` 행은 펫 모드 always-on-top(M_12) 용도다. M_10은 추가로 `pywin32`의 `GetLastInputInfo` 래퍼(또는 `ctypes` 직접 호출)를 폴백으로 사용한다(§5.1 Backend B).

---

## 4. 공개 API

### 4.1 타입 alias와 상수

```python
# src/idle_monitor/types.py
from typing import Literal
from collections.abc import Awaitable, Callable

IdleEvent = Literal["idle_rest", "overwork"]

IdleEventCallback = Callable[[IdleEvent], Awaitable[None]]
# 콜백 시그니처. IdleEvent Literal 외의 페이로드는 전달하지 않는다(§6.3 D-6).
```

### 4.2 `IdleMonitor` 클래스 시그니처

```python
# src/idle_monitor/service.py
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime

from .types import IdleEvent, IdleEventCallback
from .backends import _IdleBackend


class IdleMonitor:
    """Windows 유휴·과로 상태 전이 감지기.

    책임:
      - 키보드·마우스 입력 유무만 본다 (내용 미기록).
      - 1초 주기 `_tick`으로 상태 전이를 평가.
      - 전이 발생 시 `IdleEventCallback`을 `asyncio.create_task`로 호출(본체 블로킹 방지).

    비책임 (§1.3):
      - 시간 기반 쿨다운 (M_11).
      - WebSocket 송신 (M_11).
      - APScheduler 스케줄 (M_11).
    """

    def __init__(
        self,
        *,
        idle_threshold_min: int = 45,
        overwork_threshold_min: int = 120,
        active_gap_seconds: int = 60,
        poll_interval_seconds: float = 1.0,
        clock: Callable[[], datetime] = datetime.now,
        backend: _IdleBackend | None = None,
    ) -> None:
        """
        Args:
            idle_threshold_min: 무입력이 이 분수 이상 지속되면 `idle_rest` 방출.
                1 이상 1440 이하. 0/음수/1441+ → ValueError.
            overwork_threshold_min: 연속 활동이 이 분수 이상 지속되면 `overwork` 방출.
                1 이상 1440 이하. 범위 밖 → ValueError.
            active_gap_seconds: 연속 활동 판정 간격. 마지막 입력 이후 이 초 이하이면
                "계속 활동 중"으로 간주. 1 이상 3600 이하. 범위 밖 → ValueError.
            poll_interval_seconds: _tick 폴링 주기. 0.1 이상 10.0 이하.
                기본 1.0초. 테스트에서는 0.1로 낮춰 단위 테스트 가속 가능.
            clock: 현재 시각 공급자. 테스트에서 monkeypatch 대신 주입으로 고정.
                기본 `datetime.now`. tz-aware / naive 양쪽 수용하되 **일관성**은 호출자 책임
                (즉 clock이 naive이면 내부 연산도 naive로 수행). 기본 `datetime.now`는 naive.
            backend: `_IdleBackend` 인스턴스. None이면 `_select_backend()`가
                (Windows: Pynput → Win32 폴백 / 비Windows: Noop)을 자동 선택.

        Raises:
            ValueError: 위 파라미터 범위 위반.
        """
        ...

    def start(self) -> None:
        """백엔드 훅 초기화 + 폴링 Task 생성.

        - backend.start()가 `BackendInitError`를 던지면 Fallback 자동 전환(§5.4).
        - 이미 start된 상태에서 재호출 시 `logger.warning` 1회 + no-op (멱등).
        - 비Windows(Noop 백엔드)에서는 `logger.warning("IdleMonitor disabled on %s", sys.platform)`
          1회 로그 + 폴링 Task도 생성하지 않음(§6.3 D-5).
        - 이벤트 루프가 없는 상태(`asyncio.get_running_loop()` 실패)에서 호출하면
          `RuntimeError("IdleMonitor.start() must be called within a running event loop")`.
        """
        ...

    async def stop(self) -> None:
        """폴링 Task 취소 + 백엔드 훅 정리.

        동작:
          1. 폴링 Task에 `cancel()` 호출 + await (CancelledError swallow).
          2. backend.stop() 호출.
          3. _started 플래그 해제.
          4. 멱등 — 이미 stop되었거나 start되지 않은 상태에서도 예외 없음.
          5. 진행 중인 콜백 Task(들)은 기다리지 않는다 — fire-and-forget(§6.3 D-8).
        """
        ...

    def set_dnd(self, enabled: bool) -> None:
        """방해 금지 모드 토글.

        - True면 _tick에서 상태 전이가 감지되어도 콜백을 호출하지 않는다.
        - False로 복귀해도 이미 놓친 전이는 재방출하지 않는다(§6.3 D-3).
          다만 상태가 다시 전이되면(예: active→idle 재진입) 정상 방출된다.
        - 파라미터 타입 검증: bool 아니면 `TypeError`.
        """
        ...

    def on_event(self, callback: IdleEventCallback | None) -> None:
        """이벤트 콜백 등록. **덮어쓰기** (§6.3 D-2).

        - callback=None을 전달하면 콜백 제거.
        - 여러 번 호출 시 마지막 값만 유효.
        - 본 모듈은 단일 소비자(M_11 ProactiveDispatcher)를 전제로 설계.
        """
        ...

    def last_input_at(self) -> datetime:
        """마지막 입력 감지 시각 (clock() 기준 동일 tz/naive).

        - start() 이전에는 생성 시점의 clock() 값을 반환.
        - Win32 폴백에서는 `GetLastInputInfo`를 호출 시점에 조회해 환산한 값.
        """
        ...

    def seconds_since_last_input(self) -> float:
        """현재 시각과 `last_input_at()`의 차이(초, non-negative).

        - 클록 역행으로 음수가 계산되면 0.0으로 클램프(§6.3 D-10).
        """
        ...

    def _tick(self, now: datetime | None = None) -> None:
        """단위 테스트/단독 호출을 위한 **공개 가시 private** 메서드.

        Args:
            now: None이면 self._clock() 호출. 테스트에서는 명시적 datetime 주입.

        동작(§5.2 상세):
          1. now - last_input_at 계산.
          2. 현재 상태와 경과 시간으로 IDLE/ACTIVE 전이 판정.
          3. 전이 발생 + DND 비활성 + 콜백 존재 시 `asyncio.create_task(cb(event))`.
          4. 예외는 logger.error로 잡고 루프 생존(§10).

        호출 안전성: race 없음 (단일 이벤트 루프 단일 Task에서 호출되므로).
        """
        ...
```

### 4.3 `_IdleBackend` 내부 인터페이스 (ABC)

```python
# src/idle_monitor/backends/base.py
from abc import ABC, abstractmethod
from datetime import datetime


class BackendInitError(RuntimeError):
    """백엔드 초기화 실패 — 상위(IdleMonitor.start)가 폴백을 시도한다."""


class _IdleBackend(ABC):
    """IdleMonitor 내부 백엔드 인터페이스. 외부 모듈은 참조하지 않는다."""

    @abstractmethod
    def start(self) -> None:
        """훅/폴링 초기화. 실패 시 BackendInitError."""

    @abstractmethod
    def stop(self) -> None:
        """훅/폴링 정리. 멱등."""

    @abstractmethod
    def last_input_at(self, now: datetime) -> datetime:
        """마지막 입력 시각을 반환.
        - Pynput 백엔드: 내부 저장된 `self._last_input` (훅이 갱신).
        - Win32 백엔드: `GetLastInputInfo`의 tick count → `now - (현재 tick - last tick) ms` 환산.
        """
```

### 4.4 에러 클래스

```python
# src/idle_monitor/errors.py

class IdleMonitorError(Exception):
    """IdleMonitor 최상위 기본 예외."""


class BackendInitError(IdleMonitorError, RuntimeError):
    """백엔드 초기화 실패(훅 차단·DLL 부재 등)."""
    # backends/base.py에서 re-export. 상위는 폴백 시도 후 최종 실패면 no-op.
```

기동 실패를 상위(FastAPI lifespan)로 **올리지 않는다**. 모든 백엔드가 실패하면 `logger.error` 로깅 + `NoopBackend`로 강등하여 앱 기동은 계속(§10).

---

## 5. 알고리즘

### 5.1 백엔드 선택 전략

#### Backend A — `PynputBackend` (Primary, Windows)

- `pynput.keyboard.Listener(on_press=self._on_event)` + `pynput.mouse.Listener(on_move=self._on_event, on_click=self._on_event, on_scroll=self._on_event)`.
- 훅 핸들러는 **단일 필드 쓰기**만 수행: `self._last_input = now_provider()`. 키·마우스 내용 기록 없음.
- `start()`에서 두 Listener의 `.start()` 호출 후 `.wait()` 생략(non-blocking). Listener 스레드는 pynput이 내부 관리.
- EDR 차단 등으로 Listener가 `.start()` 직후 예외 또는 `.is_alive() == False` → `BackendInitError`.
- `stop()`: 두 Listener의 `.stop()` + `.join(timeout=1.0)`.

#### Backend B — `Win32IdleBackend` (Fallback, Windows, R-10 필수)

- `ctypes.windll.user32.GetLastInputInfo(LASTINPUTINFO)` 호출로 tick count 조회.
- `LASTINPUTINFO` 구조체:
  ```python
  import ctypes
  class LASTINPUTINFO(ctypes.Structure):
      _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
  ```
- `start()`: `ctypes.windll.user32.GetLastInputInfo`와 `ctypes.windll.kernel32.GetTickCount` 심볼 resolve. 실패 시 `BackendInitError`.
- `last_input_at(now)` 계산:
  ```
  current_tick = GetTickCount()    # uint ms, 49.7일마다 wrap
  last_tick = info.dwTime
  elapsed_ms = (current_tick - last_tick) & 0xFFFFFFFF   # wrap-safe
  last_input_at = now - timedelta(milliseconds=elapsed_ms)
  ```
- wrap 대응: `& 0xFFFFFFFF`로 unsigned 32bit subtraction. 49.7일 연속 PC 가동 시에도 정상.
- `stop()`: no-op (폴링 기반이므로 해제할 리소스 없음).

#### Backend C — `NoopBackend` (비Windows)

- `sys.platform != "win32"` 또는 기타 비호환 환경. 개발자(WSL/Linux)가 pytest를 돌릴 수 있어야 함(§13.5, §14.2).
- `start()`: `logger.warning("IdleMonitor disabled on non-Windows platform: %s", sys.platform)` 1회 + no-op.
- `stop()`: no-op.
- `last_input_at(now)`: **항상 `now` 반환** (무입력 간격 = 0). 결과적으로 `_tick`이 상태 전이를 **절대 감지하지 않는다**. 콜백도 호출되지 않음.

#### 선택 로직 `_select_backend()` (§5.4)

```
if sys.platform != "win32":
    return NoopBackend()
try:
    backend = PynputBackend(...)
    backend.start()          # 즉시 초기화 시도
    return backend
except BackendInitError as e1:
    logger.warning("pynput backend failed: %s; falling back to GetLastInputInfo", e1)
    try:
        backend = Win32IdleBackend(...)
        backend.start()
        return backend
    except BackendInitError as e2:
        logger.error("both pynput and Win32 backends failed: %s; IdleMonitor disabled", e2)
        return NoopBackend()
```

**중요**: 선택 로직은 `IdleMonitor.start()` 내부에서 **단 한 번** 실행된다. 생성자(`__init__`)가 호출된 시점에는 선택하지 않음 — 이벤트 루프 생성 전 임의 import 부작용을 피한다.

### 5.2 상태 기계와 `_tick`

상태 2개: `IDLE` / `ACTIVE`. 내부 필드 `self._state: Literal["idle", "active"]`.

초기 상태는 `ACTIVE` (start 직후 방금 기동한 사용자는 활동 중이라고 가정).

`_tick(now)` 의사코드:

```text
elapsed = (now - backend.last_input_at(now)).total_seconds()
# elapsed < 0 이면 clock skew — 0으로 클램프 (§6.3 D-10)

# --- 전이 판정 ---
if self._state == "active":
    # (1) active → idle 전이
    if elapsed >= idle_threshold_min * 60:
        transition_to("idle")
        emit("idle_rest")
    # (2) 연속 활동 판정: active 진입 시점부터 overwork 임계 경과?
    elif (now - self._active_since) >= timedelta(minutes=overwork_threshold_min):
        # active 상태 유지 중 overwork 발생: emit 1회, 그리고 overwork_emitted 플래그 설정
        if not self._overwork_emitted:
            emit("overwork")
            self._overwork_emitted = True
        # 상태는 active 유지 (overwork도 active의 연장선)
    else:
        pass   # 변화 없음
else:   # self._state == "idle"
    # idle 상태에서 입력이 발생하면 active 복귀
    if elapsed < active_gap_seconds:
        transition_to("active")
        # active 복귀 시 self._active_since = now, self._overwork_emitted = False
        # 이벤트는 emit 하지 않음 (idle→active는 UX상 조용한 복귀)
    else:
        pass
```

보조 필드:
- `self._active_since: datetime` — 가장 최근 `active` 진입 시각. `idle→active` 전이 또는 `start()`에서 갱신.
- `self._overwork_emitted: bool` — 이번 active 세션에서 `overwork` 이벤트를 이미 방출했는가. `active→idle` 또는 `idle→active` 전이 시 False로 리셋.

**핵심 불변식**:
- `overwork` 이벤트는 **하나의 active 세션당 최대 1회** (§6.3 D-7).
- `idle_rest` 이벤트는 **하나의 active→idle 전이당 1회** (§6.3 D-7). idle 유지 중 반복 방출 없음.
- 전이 없음 = 이벤트 없음.

### 5.3 시간 주입 (테스트 용이성)

- `clock: Callable[[], datetime]` 생성자 주입. 기본 `datetime.now`.
- `_tick(now=None)`의 `now` 파라미터로 직접 주입 가능(테스트에서 빠른 시간 전진).
- `PynputBackend`는 훅 핸들러에서 `self._clock()` 호출(주입된 같은 clock).
- `Win32IdleBackend`는 `GetTickCount()`가 시스템 시계 의존이므로 **주입 불가** → 테스트는 이 백엔드를 fake로 대체(§5.5).

### 5.4 자동 폴백 정책 (§6.3 D-9)

- **자동**: `_select_backend()`가 기본. `force_fallback=True` 같은 명시 옵션은 V1에서 **제공하지 않는다** (YAGNI; 필요 시 테스트에서 `backend=Win32IdleBackend(...)` 직접 주입).
- Primary 실패 이유(예외 메시지)는 `logger.warning`으로 1회만 기록. 반복 warn을 피하기 위해 start()에서 단 한 번 결정하고 이후 재시도하지 않는다.

### 5.5 Fake 백엔드 (테스트용)

```python
# tests/idle_monitor/fakes.py (테스트 전용, src/ 에 두지 않음)
class FakeBackend(_IdleBackend):
    def __init__(self, last: datetime):
        self.last = last
        self.start_called = 0
        self.stop_called = 0
        self.init_error: BackendInitError | None = None

    def start(self) -> None:
        self.start_called += 1
        if self.init_error is not None:
            raise self.init_error

    def stop(self) -> None:
        self.stop_called += 1

    def last_input_at(self, now: datetime) -> datetime:
        return self.last

    # 테스트 조작
    def simulate_input(self, at: datetime) -> None:
        self.last = at
```

---

## 6. 내부 구조와 결정 사항

### 6.1 파일 배치

```
src/idle_monitor/
├── __init__.py                    # IdleMonitor, IdleEvent, IdleEventCallback re-export
├── types.py                       # IdleEvent Literal, IdleEventCallback
├── errors.py                      # IdleMonitorError, BackendInitError
├── service.py                     # IdleMonitor 본체
└── backends/
    ├── __init__.py                # _select_backend, _IdleBackend re-export (내부용)
    ├── base.py                    # _IdleBackend ABC
    ├── pynput_backend.py          # PynputBackend (Windows Primary)
    ├── win32_backend.py           # Win32IdleBackend (Windows Fallback, R-10)
    └── noop_backend.py            # NoopBackend (비Windows 또는 양쪽 실패 시)

tests/idle_monitor/
# __init__.py 생성 금지 — CR-06 정책 (M_09 §17 선례)
├── conftest.py                    # fake backend, frozen clock fixtures
├── fakes.py                       # FakeBackend
├── test_service.py                # 정상 7건 + 엣지 일부
├── test_state_machine.py          # _tick 상태 전이 단위 테스트
├── test_backends.py               # PynputBackend/Win32Backend/NoopBackend import 스모크
│                                  # (실제 훅/ctypes는 mock)
└── test_adversarial.py            # A-1~A-4
```

### 6.2 내부 상태

```python
class IdleMonitor:
    # 파라미터
    _idle_threshold_min: int
    _overwork_threshold_min: int
    _active_gap_seconds: int
    _poll_interval_seconds: float
    _clock: Callable[[], datetime]

    # 런타임 상태
    _backend: _IdleBackend | None          # start() 전까지 None
    _state: Literal["idle", "active"]      # 초기 "active"
    _active_since: datetime                # 초기 clock() 값
    _overwork_emitted: bool                # active 세션당 1회
    _dnd_enabled: bool
    _callback: IdleEventCallback | None
    _task: asyncio.Task[None] | None       # 폴링 Task
    _started: bool                         # 멱등성 플래그
```

### 6.3 결정 사항

| ID | 결정 | 근거 |
|---|---|---|
| D-1 | **쿨다운·DND 책임 분리**: 본 모듈은 "상태 전이당 1회 이벤트" + `set_dnd` drop만 담당. **시간 기반 쿨다운**(예: 같은 이벤트 30분 재방출 금지)은 **M_11 전담**. | (a) `docs/MODULES.md` L373~L397에서 M_11이 "쿨다운" 책임임을 명시. `cooldown_min=30`은 M_11 `__init__` 파라미터. (b) "상태 전이"와 "시간 쿨다운"은 서로 다른 개념 — 본 모듈은 상태만, M_11은 송신 억제 정책. (c) 두 층에서 중복 적용은 누수 위험 없지만 테스트·디버깅 복잡도 증가. 단일 책임. (d) DND는 **두 층 중복**(본 모듈 + M_11 둘 다 `set_dnd`). 근거: 본 모듈에서 선차단하면 콜백 Task 생성 비용 절약, M_11은 upstream `ai-speak-signal` 송신 직전 최종 확인. 이중 방어는 허용(§1.3 In-Scope 2, `docs/ARCHITECTURE.md` L161~L163 일관). MODULES.md 초안의 `cooldown_min` 파라미터는 **본 스펙에서 제거**(§16.1). |
| D-2 | **`on_event` 단일 콜백 슬롯 (덮어쓰기)**. 리스트 누적 아님. | (a) M_11이 유일 소비자 (MODULES.md 그래프). (b) 멀티캐스트가 필요해지면 M_11 내부에서 fanout하는 것이 옳음 — 본 모듈이 브로드캐스트하면 콜백 예외 처리·순서 보장 책임이 부풀어 오른다. (c) 리스트 누적은 테스트 시 "이전 테스트의 콜백이 남아있는" 오염 버그를 유발. 덮어쓰기는 결정론적. |
| D-3 | **DND 활성 시 콜백 호출 자체를 건너뛴다** (상태 전이는 내부적으로 업데이트). | (a) 리소스 절약 + M_11의 중복 drop 로직 부담 감소. (b) 상태 전이는 여전히 내부 기록 → DND 해제 후 "다음 전이"부터 정상 방출. 즉 DND는 이벤트를 **미방출**하되 **내부 상태는 생생히 유지**. (c) "놓친 전이 재방출"은 하지 않는다 — UX 관점에서 "30분 전 idle_rest가 지금 도착"은 무의미. |
| D-4 | **폴링 주기 `poll_interval_seconds=1.0` 기본, 조정 가능**. | (a) 1초는 유휴 감지 UX에 충분(45분 스케일). (b) 테스트에서 0.1초로 낮춰 단위 테스트 가속. (c) `_tick`는 매우 가벼움 (dict lookup + datetime 산술) — 1초 폴링 CPU 부담 < 0.1%(§11). |
| D-5 | **비Windows 환경에서 `start()`는 `NoopBackend` + `logger.warning` 1회 + no-op**. 에러 안 던짐. | (a) 개발자(WSL/Linux) pytest 실행 환경 유지(§14.2). (b) import는 항상 성공해야 — `sys.platform` 분기를 `__init__`이 아닌 `_select_backend`에서 수행. (c) 런타임에 import 실패 시 앱 기동이 깨지면 모듈 독립성 훼손. |
| D-6 | **콜백 페이로드는 `IdleEvent` Literal 단일 인자**. `{"type": ..., "since": ..., "duration": ...}` 같은 dict 전달 없음. | (a) 소비자(M_11)는 `last_input_at()`/`seconds_since_last_input()` **조회**로 필요 정보를 얻는다(pull 모델). (b) 이벤트 페이로드에 시간 정보를 담으면 "이벤트 발생 시각 vs 콜백 실행 시각"의 clock skew 이슈가 생김. 조회 API는 항상 최신값을 반환하므로 일관성이 높다. (c) Literal은 mypy 타입 좁힘에 유리. |
| D-7 | **상태 전이당 이벤트 1회 불변식**. | (a) `idle_rest`: active→idle 전이 시 1회. idle 유지 중에는 재방출하지 않는다. (b) `overwork`: 하나의 active 세션(연속 활동 구간)당 1회. active→idle→active로 리셋되면 다시 방출 가능. (c) 시간 기반 "다시 방출" 욕구는 M_11이 쿨다운 만료 후 **소비자 쪽에서** 처리. (d) 본 모듈의 불변식은 단순·검증 가능. |
| D-8 | **콜백은 `asyncio.create_task`로 비동기 실행**. `_tick` 루프는 블로킹되지 않는다. | (a) 콜백이 느린 경우(M_11이 WebSocket 송신) `_tick`의 1초 간격이 무너지지 않음. (b) 콜백 예외는 Task 내부에서 swallow + `logger.warning` — 본 모듈 본체는 절대 죽지 않음(§10). (c) `stop()`은 Task들을 await하지 않고 루프만 취소 — fire-and-forget. 미완료 Task는 asyncio가 이벤트 루프 종료 시 경고 표시하지만 M_11 쪽에서 정리 책임. |
| D-9 | **Primary→Fallback 자동 전환**. `force_fallback=True` 옵션은 V1 제공 안 함. | (a) YAGNI — 필요 시 테스트/디버그에서 `backend=Win32IdleBackend(...)` 직접 주입으로 충분. (b) 프로덕션 코드 표면 축소 — 플래그가 많을수록 검증 곱셈. (c) Primary 실패 로그로 관찰 가능. |
| D-10 | **클럭 역행 방어**: `seconds_since_last_input()` 음수 시 0.0 클램프. `_tick`의 elapsed도 동일. | (a) 시스템 시계 수정(NTP 보정·수동 변경)으로 `now < last_input_at` 가능. (b) 음수 경과 시간은 상태 기계의 임계값 비교를 왜곡 — 0으로 가면 "방금 입력 있었음"으로 안전 해석. (c) 로그 경고 없이 조용히 클램프 — 시계 수정은 흔한 운영 이벤트. |
| D-11 | **start/stop 멱등성**: 중복 호출 안전. | (a) AppServiceContext 재기동 시나리오 대비. (b) close() 중복 호출(FastAPI lifespan 취소 경합) 방어. (c) 구현: `_started` bool 플래그. |
| D-12 | **이벤트 루프 바인딩**: `_task`는 `start()` 호출 시점의 실행 중인 이벤트 루프에 바인딩. `stop()`은 동일 루프에서 호출되어야 한다. | (a) AppServiceContext.load_app_services가 FastAPI lifespan 내부에서 호출되므로 단일 루프 가정 유효. (b) 다른 루프에서 `stop()` 호출 시 `RuntimeError` — 상위(FastAPI) 문제로 위임. |

### 6.4 로그 카테고리

- `logger.warning` — 백엔드 폴백, DND 상태 변경, 콜백 예외, 중복 start/stop.
- `logger.error` — 모든 백엔드 실패 + Noop 강등, `_tick` 내부 미처리 예외.
- `logger.debug` — `_tick` 상태 전이 세부 (개발 시만, INFO에 노이즈 올리지 않음).
- `logger.info` — start()/stop() 각 1회.

개인정보·입력 내용은 어떤 레벨에서도 기록하지 않는다.

---

## 7. 콜백 호출 정책

### 7.1 호출 컨텍스트

```python
# _tick 내부 (의사코드)
if transition_detected and not self._dnd_enabled and self._callback is not None:
    asyncio.create_task(self._safe_invoke_callback(event))

async def _safe_invoke_callback(self, event: IdleEvent) -> None:
    try:
        await self._callback(event)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.warning("idle callback raised: %s", exc, exc_info=True)
```

### 7.2 콜백 예외 처리

- `CancelledError`: 전파 (asyncio 규약).
- 기타 모든 예외: `logger.warning` + swallow. 본 모듈 본체는 계속 동작.
- 콜백 Task는 `stop()`에서 기다리지 않는다 (D-8).

### 7.3 콜백 순서

- `_tick`은 매 호출에서 최대 1개 이벤트만 방출 (상태 기계가 단일 전이만 탐지).
- 따라서 동시 콜백이 겹치는 경우는 **없다** — 1초 간격 폴링에서 직전 콜백이 아직 실행 중이어도 새 전이가 잡히지 않으면 새 Task 생성 없음.
- 이례적으로 `idle_rest` → `overwork` 사이 간격이 매우 짧은 시나리오는 상태 기계상 불가능 (idle 상태에서는 overwork 판정 경로가 없음).

---

## 8. 송신 페이로드 규약

본 모듈은 **WebSocket을 직접 호출하지 않는다**. 콜백을 통해 `IdleEvent` Literal 문자열만 전달.

M_11이 수신 후 어떻게 `ai-speak-signal`로 변환하는지는 M_11 SPEC의 책임이다(단일 WS 송신 타입, specs/M_11_ProactiveDispatcher_SPEC.md §7.3). 참고(§13.4 호출 경로):

```
IdleMonitor._tick
  └── asyncio.create_task(callback("idle_rest"))
        │  (callback == ProactiveDispatcher._handle_idle_event, M_11)
        └── ProactiveDispatcher.emit("idle_rest", context={...})
              └── (쿨다운/DND 최종 확인) → send_text({"type":"ai-speak-signal","text":<휴식 권고 프롬프트>})
```

본 모듈이 보장하는 계약:
- 콜백 인자는 정확히 `"idle_rest"` 또는 `"overwork"` 중 하나.
- 콜백은 await 가능한 coroutine을 반환해야 함.
- 콜백 예외는 swallow — 본 모듈은 "계속 감지".

---

## 9. 에러 처리 정책

| 상황 | 내부 처리 | 호출자 가시성 |
|---|---|---|
| `__init__` 파라미터 범위 위반 (idle_threshold_min<=0, overwork_threshold_min>1440 등) | `ValueError` | 기동 실패 — load_app_services가 logger.warning + `idle_monitor=None` 처리 |
| `set_dnd` 인자가 bool 아님 | `TypeError("set_dnd expects bool")` | 호출자 책임 |
| `on_event` 인자가 callable도 None도 아님 | `TypeError("callback must be callable or None")` | 호출자 책임 |
| `start()` 중복 호출 | `logger.warning("IdleMonitor.start() called twice; ignoring")` + no-op | 정상 |
| `stop()` start 이전 호출 | no-op (`self._started is False`) | 정상 |
| `stop()` 중복 호출 | no-op | 정상 |
| `start()` 이벤트 루프 없이 호출 | `RuntimeError("must be called within a running event loop")` | 호출자 (FastAPI lifespan) 책임 |
| Pynput 백엔드 `start()` 실패 (`BackendInitError`) | Win32 폴백 자동 시도 + logger.warning 1회 | 정상 (폴백 경로) |
| Win32 백엔드 `start()` 실패 | NoopBackend 강등 + logger.error 1회 | 정상 (기능만 비활성) |
| 비Windows 환경 `start()` | NoopBackend + logger.warning 1회 | 정상 |
| `_tick` 내부 예외 (백엔드 호출 실패 등) | try/except로 감싸 logger.error + 다음 틱 계속 | 정상 (루프 생존) |
| 콜백 예외 | logger.warning + swallow | 정상 |
| 클록 역행 (`now < last_input_at`) | elapsed=0.0 클램프 | 정상 (조용히) |
| 비동기 Task 취소 (FastAPI 종료) | CancelledError 전파, 백엔드 stop() 호출 | 정상 |

**원칙**:
- 생성자 검증 실패는 fail-fast (`ValueError`).
- 런타임 실패는 가능한 한 self-healing (폴백, Noop 강등, 예외 swallow).
- 본 모듈 본체는 "휴식 권고"라는 부가 기능이며, 장애로 인해 **AI 비서 본체(대화)를 다운시키지 않는다**.

---

## 10. 성능·메모리·동시성

### 10.1 성능

| 지표 | 요구 | 근거·계측 |
|---|---|---|
| `_tick` 단일 호출 지연 | ≤ 1 ms (median) | 상수시간 datetime 산술 + state machine dispatch |
| 폴링 CPU 점유 (1초 주기) | < 0.1% | _tick 1ms × 1Hz = 0.1% 상한 |
| Pynput 훅 콜백 오버헤드 | < 0.01 ms/event | 단일 필드 쓰기 (datetime 할당) |
| Win32 GetLastInputInfo 1회 호출 | < 0.1 ms | kernel32 시스템 콜 |
| `start()` 지연 | < 100 ms | pynput Listener.start() 내부 스레드 생성 |
| `stop()` 지연 | < 200 ms | Listener.join(timeout=1.0) 실제로는 즉시 반환 |

### 10.2 메모리

| 항목 | 상한 | 근거 |
|---|---|---|
| IdleMonitor 인스턴스 오버헤드 | < 1 KB | 파라미터 + 상태 변수 수십 개 |
| Pynput Listener 스레드 2개 | < 4 MB | 각 스레드 스택 + 훅 큐 |
| Win32 백엔드 | < 100 KB | ctypes struct 1개 |
| **총 추가 메모리** | **< 5 MB** | §1.2 요구와 일치 |

### 10.3 동시성

- `_tick` 폴링 Task는 단일 이벤트 루프에서 순차 실행 → race 없음.
- Pynput 훅 콜백은 **별도 스레드**(Listener가 생성)에서 실행 — `self._last_input = ...` 단일 필드 쓰기만 수행, CPython GIL 하에서 원자적. 읽기도 원자적. **락 불필요**(§6.3 D-12 불변식: 단일 필드, 쓰기 1곳, 읽기 1곳).
- `set_dnd`는 이벤트 루프 스레드에서 호출 가정 (FastAPI 핸들러). 다른 스레드에서 호출해도 bool 할당은 원자적.
- `on_event`는 start 전 1회 호출 권장. 런타임 재등록도 원자적 할당.

**전역 lock 사용 없음**. CPython GIL + 단순 원자적 연산 조합으로 충분.

---

## 11. 테스트 케이스

파일 배치는 §6.1. pytest + pytest-asyncio. 합계 **정상 7 + 엣지 7 + 적대적 4 = 18건**(CLAUDE.md 하한: 정상 ≥5, 엣지 ≥5, 적대적 ≥3 충족).

### 11.1 정상 케이스 (Normal, N) — ≥7

**N-1. active→idle 전이 시 `idle_rest` 1회 방출**
- 준비: `FakeBackend(last=t0)`, clock=`fake_clock(t0)`, `idle_threshold_min=1`, callback=AsyncMock.
- `start()` 호출.
- `_tick(t0 + 61초)` 직접 호출.
- 기대: callback이 `"idle_rest"` 1회 호출. `state == "idle"`.

**N-2. overwork 전이 1회 방출 + active 세션 유지**
- 준비: `FakeBackend(last=t)`가 계속 갱신 (`simulate_input` 매 틱). `overwork_threshold_min=2` (2분), `active_gap_seconds=60`.
- `start()` 후 t0, t0+30s, t0+60s, ..., t0+121s 까지 fake input. 각 시점에서 `_tick`.
- 기대: `overwork` 이벤트 정확히 1회 (t0+120s 경계 근처). `state == "active"` 유지.

**N-3. idle→active 복귀 — 이벤트 미방출 (조용한 복귀)**
- 준비: N-1 이후 상태가 idle.
- `fake_backend.simulate_input(t0 + 120s)` + `_tick(t0 + 121s)`.
- 기대: callback 재호출 없음 (idle→active는 UX상 조용). `state == "active"`. `_overwork_emitted == False` (active 세션 리셋).

**N-4. DND 활성 시 전이 발생해도 콜백 호출 안 됨**
- 준비: FakeBackend, `set_dnd(True)`.
- `_tick(t0 + 61s)` → idle 전이 조건.
- 기대: callback 호출 0회. 내부 `state == "idle"`은 갱신됨 (D-3 근거).

**N-5. `on_event` 덮어쓰기 — 최신 콜백만 호출 (D-2 회귀 방지)**
- 준비: `cb_a = AsyncMock(); cb_b = AsyncMock()`. `on_event(cb_a)` 후 `on_event(cb_b)`.
- 전이 발생.
- 기대: `cb_a` 0회, `cb_b` 1회.

**N-6. `last_input_at()` / `seconds_since_last_input()` 조회**
- 준비: FakeBackend(last=t0), clock=fake(t0 + 30s).
- `last_input_at()` → t0.
- `seconds_since_last_input()` → 30.0 (±0.1 허용).

**N-7. `_tick` 공개 호출로 단위 테스트 가능 (시간 빨리감기)**
- 준비: clock=mutable wrapper, callback=AsyncMock.
- `clock.advance(46 min)` + `_tick()` (now=None → self._clock()).
- 기대: `idle_rest` 1회.

### 11.2 엣지 케이스 (Edge, E) — ≥7

**E-1. 임계값 정확 경계**
- `idle_threshold_min=45`, elapsed=45*60 - 1s → idle_rest 미방출.
- elapsed=45*60 → idle_rest 방출 (inclusive).
- elapsed=45*60 + 1s → 방출 (한 번만 — 중복 없음, D-7 회귀).

**E-2. 콜백 None — 이벤트 발생해도 크래시 없음**
- `on_event(None)` 명시 해제 (또는 처음부터 미등록).
- `_tick` 실행 → state 전이는 기록, `create_task` 호출 없음.
- 기대: 예외 없음.

**E-3. 콜백이 예외를 던져도 루프 생존**
- `cb = AsyncMock(side_effect=RuntimeError("boom"))`.
- 전이 발생 → cb 호출 → RuntimeError → logger.warning.
- 후속 `_tick` 정상 동작 (state 기계 변경 없이 계속).

**E-4. start 미호출 상태에서 stop — no-op**
- `await monitor.stop()` (start 없이).
- 기대: 예외 없음. `_task is None`.

**E-5. stop 중복 호출 — no-op**
- `start()` → `await stop()` → `await stop()`.
- 기대: 두 번째 stop도 예외 없음. backend.stop() 1회만 호출 (멱등).

**E-6. 클록 역행**
- `last_input_at = t0 + 10s`, `now = t0`.
- `seconds_since_last_input()` → 0.0 (음수 클램프, D-10).
- `_tick(t0)` → state 전이 없음 (elapsed=0 < 임계값).

**E-7. 백엔드 없이 `_tick` 직접 호출 (init 검증)**
- FakeBackend 미주입, `backend=None` 기본 + 비Windows 환경 가정.
- `_select_backend()`가 Noop 반환.
- `_tick` 호출 — NoopBackend.last_input_at(now) == now → elapsed=0 → 전이 없음.
- 기대: 예외 없음, callback 호출 없음.

### 11.3 적대적 케이스 (Adversarial, A) — ≥4

**A-1. Pynput `BackendInitError` → Win32 자동 폴백 (R-10 회귀 방지)**
- 준비: `PynputBackend.start()`을 `side_effect=BackendInitError("EDR blocked")`로 monkeypatch. `Win32IdleBackend.start()`는 no-op mock.
- `IdleMonitor.start()` 호출.
- 기대: 선택된 백엔드가 `Win32IdleBackend` 인스턴스. `logger.warning` 1회 (polback 메시지 포함).

**A-2. Pynput + Win32 둘 다 실패 → Noop 강등 + 경고만, 앱 기동 계속**
- 두 백엔드 모두 `BackendInitError` mock.
- `IdleMonitor.start()`.
- 기대: 선택된 백엔드가 `NoopBackend`. `logger.error` 1회. 예외 밖으로 나오지 않음. `_tick` 호출해도 crash 없음.

**A-3. 매우 긴 대기 (24시간) 시뮬레이션 — overflow 없음**
- FakeBackend last=t0, clock.advance(24h). `_tick()`.
- 기대: `idle_rest` 1회. 내부 timedelta 연산 정상. `_overwork_emitted` 미발동 (idle 상태이므로).

**A-4. `_tick` 1초 미만 간격 폭격 (1000회/초 스트레스)**
- 상태 변화 없이 `for _ in range(1000): _tick(t_fixed)` 반복.
- 기대: callback 0회 (전이 없음). 시간 복잡도 O(1000). 총 소요 < 50 ms (§10.1 근거). 메모리 누수 없음 (`gc.collect` 후 Task 0개).

### 11.4 테스트 지원 도구

- `pytest-asyncio` `@pytest.mark.asyncio` 사용.
- Fake 클럭: `class FakeClock: def __init__(self, t0): self._t = t0; def __call__(self): return self._t; def advance(self, delta): self._t += delta`.
- Pynput/Win32 mock: `unittest.mock.patch("idle_monitor.backends.pynput_backend.PynputBackend")`.
- 로깅 캡처: `caplog` fixture.
- 타임아웃: 각 테스트 `@pytest.mark.timeout(5)` (Task 누수 방지).

### 11.5 실제 Windows 환경 스모크 (CI 선택)

본 스펙 테스트 12.1~12.3은 **전부 FakeBackend 기반**이므로 Linux/WSL에서도 통과해야 한다. 실제 pynput/Win32 경로 검증은 **통합 테스트**(integrator 에이전트) 단계에서 Windows VM으로 수행 — M_10 단위 테스트 DoD에 포함하지 않음.

---

## 12. Definition of Done

### 12.1 공통 (CLAUDE.md "산출물 체크리스트")

- [ ] `specs/M_10_IdleMonitor_SPEC.md` (본 문서) 사용자 승인.
- [ ] `src/idle_monitor/` 하위 파일(§6.1) 구현.
- [ ] `tests/idle_monitor/test_*.py`: 정상 ≥7, 엣지 ≥7, 적대적 ≥4 (본 스펙 기준 18건).
- [ ] `ruff format .`, `ruff check .`, `mypy src/`, `pytest tests/idle_monitor/ -v` 모두 통과.
- [ ] 테스트 커버리지 ≥ 70% (본 모듈 파일 한정).
- [ ] `reviews/M_10_IdleMonitor_REVIEW.md`에 Critic PASS 기록.
- [ ] `docs/MODULES.md` M_10 행 상태가 `✅ DONE`으로 갱신 + 초안 대비 차이(§16) 반영.

### 12.2 M_10 고유 DoD (docs/MILESTONES.md L129~L137 기준)

- [ ] `start()` 후 45분 무입력 가정(가상 시계 주입) → `idle_rest` 콜백 1회 호출 (N-1).
- [ ] 이어서 추가 시간 경과해도 쿨다운 없이 동일 idle 상태에서 **추가 호출 없음** (D-7, E-1).
  - 주: MILESTONES는 "쿨다운으로 추가 호출 없음"이라 표기. 본 스펙에서는 "상태 전이 1회 불변식"으로 해석 (D-1 근거 — 시간 기반 쿨다운은 M_11).
- [ ] 2시간 연속 입력 → `overwork` 콜백 1회 호출 (N-2).
- [ ] `set_dnd(True)` 후 모든 이벤트 drop. 해제 후 다음 조건 달성 시 다시 방출 (N-4 + idle→active→idle 시나리오).
- [ ] 훅 초기화 실패 시 예외를 삼키고 서비스는 no-op로 기동 (A-2).

### 12.3 백엔드 커버리지

- [ ] `PynputBackend` import + 생성자 테스트 (훅 실제 생성은 mock).
- [ ] `Win32IdleBackend` import + LASTINPUTINFO 구조체 정의 검증.
- [ ] `NoopBackend` — 비Windows 경로 강제(`sys.platform` monkeypatch) 테스트.
- [ ] `_select_backend()` 의 3분기(pynput 성공 / pynput 실패 → win32 성공 / 둘 다 실패) 모두 A-1/A-2 + 정상 경로로 커버.
- [ ] **R-10 필수 요건**: pynput → Win32 자동 폴백 경로가 테스트에서 실측 검증됨 (A-1).

### 12.4 무결성

- [ ] upstream `Open-LLM-VTuber/**` git diff 빈 상태.
- [ ] 새 의존성 정확히 2종 (`pynput`, `pywin32`) — `pyproject.toml` 추가 + `scripts/bundle_deps.sh` 갱신.
- [ ] `pywin32`는 `sys_platform == "win32"` 환경 마커로 선언 (§14.2 근거).
- [ ] 네트워크 호출 0건 (`grep -r "requests\|httpx\|urllib\|fetch" src/idle_monitor` → 0).

### 12.5 배선 범위 결정

- [ ] `src/app/service_context.py::load_app_services` 내 `IdleMonitor(...)` 주입 1줄 추가 + try/except (logger.warning + `idle_monitor=None` 폴백). **M_10 범위에 포함** — 근거: M_11이 `idle_monitor` 필드를 구독하도록 의존하며(§13.4), 배선 없이는 M_11 회귀 발생.
- [ ] `tests/app/test_service_context.py`에 IdleMonitor 주입 회귀 테스트 1건 추가 (실제 훅은 `unittest.mock.patch`로 차단).
- [ ] FastAPI lifespan에서 `idle_monitor.start()`가 `app.on_event("startup")` 또는 M_01의 기존 startup hook에서 호출되도록 1줄 추가. stop은 `AppServiceContext.close()`가 이미 `_call_stop(self.idle_monitor, "idle_monitor")`을 호출하므로 **추가 작업 없음**(`src/app/service_context.py:267~271` 확인).

### 12.6 문서 동기화

- [ ] `docs/MODULES.md` M_10 블록 갱신: 상태 `🔲 TODO` → `✅ DONE`, 공개 API에 `last_input_at`/`seconds_since_last_input`/`_tick`/`active_gap_seconds`/`poll_interval_seconds` 추가, `cooldown_min`/`dnd_enabled` **제거**(§16.1).
- [ ] `docs/RISKS.md` R-10 상태: OPEN → **MITIGATING** (폴백 구현 완료 후).

---

## 13. 배선 범위 결정 (AppServiceContext 연결)

### 13.1 생성자 주입 (load_app_services)

`src/app/service_context.py::load_app_services` 기존 구조(CalendarService 선례 참조, 208~214 라인)와 동일 패턴:

```python
# 기존: self.calendar_service = CalendarService(...)
# 신규 (M_10 추가):
try:
    from idle_monitor import IdleMonitor
    self.idle_monitor = IdleMonitor(
        idle_threshold_min=app_config.proactive.idle_threshold_min,   # conf.yaml
        overwork_threshold_min=app_config.proactive.overwork_threshold_min,
        active_gap_seconds=app_config.proactive.active_gap_seconds,
    )
except Exception as exc:
    logger.warning(f"idle_monitor 초기화 실패: {exc}")
    self.idle_monitor = None
```

**conf.yaml 필드**: M_01 SPEC L134의 `proactive_cooldown_min`은 M_11용이며 본 모듈과 무관. 본 모듈용 conf 필드는 새로 3개 추가 필요:
- `proactive.idle_threshold_min` (기본 45)
- `proactive.overwork_threshold_min` (기본 120)
- `proactive.active_gap_seconds` (기본 60)

이들 필드는 M_01 `AppConfig.proactive` 섹션에 추가. M_10 builder가 `src/app/config.py`(또는 동등 파일)에 3줄 추가 — M_01이 이미 `proactive_cooldown_min`을 가지고 있으므로 `ProactiveConfig` 구조체 확장 1회로 처리.

### 13.2 `start()` 호출 지점

FastAPI lifespan의 startup hook. M_01 SPEC L332 "app.on_event('startup') → ctx.idle_monitor.start(), ctx.proactive_dispatcher.start()" 예약 경로 활용:

```python
# src/app/main.py 또는 동등 위치 (M_01 범위)
@app.on_event("startup")
async def _on_startup() -> None:
    if ctx.idle_monitor is not None:
        ctx.idle_monitor.start()
    # M_11 ProactiveDispatcher는 M_11 단계에서 추가
```

### 13.3 `stop()` 호출 지점

`src/app/service_context.py::close()`의 267~271번 라인은 이미 다음 코드를 포함:

```python
if self.idle_monitor is not None:
    try:
        await _call_stop(self.idle_monitor, "idle_monitor")
    except Exception as exc:
        logger.error(f"idle_monitor.stop() 실패: {exc}")
```

`_call_stop`이 sync/async 양쪽을 지원(`src/app/service_context.py:305~311`)하므로 본 모듈의 `async def stop`도 정상 await된다. **추가 수정 없음**.

### 13.4 M_11 ProactiveDispatcher 호출 계약

M_11 builder가 본 모듈을 소비하는 경로(본 스펙은 M_11 구현을 하지 않으나 계약만 고정):

```python
# M_11 SPEC 착수 시 구현할 부분 (본 모듈 범위 외, 참고용 의사코드)
class ProactiveDispatcher:
    def __init__(self, *, idle_monitor: IdleMonitor, ...):
        self._idle_monitor = idle_monitor
        idle_monitor.on_event(self._handle_idle_event)

    async def _handle_idle_event(self, event: IdleEvent) -> None:
        # 쿨다운 + DND 최종 확인 후 ai-speak-signal 송신
        await self.emit(event, context={})
```

**본 모듈이 보장하는 것**:
- `on_event(callback)`은 단일 덮어쓰기 — M_11이 생성자에서 한 번 호출.
- 콜백은 Literal 문자열만 수신 — M_11이 context dict를 별도 구성.
- 콜백 예외 시 본 모듈 본체는 죽지 않음.
- `last_input_at()`/`seconds_since_last_input()`로 M_11이 부가 정보 조회 가능.

### 13.5 호출 경로 다이어그램

```
[startup]
FastAPI app.on_event("startup")
  └── AppServiceContext.idle_monitor.start()
        └── _select_backend() → PynputBackend (Win11 정상) 또는 Win32IdleBackend (pynput 차단 시)
              └── backend.start()  (Listener 스레드 or ctypes resolve)
        └── asyncio.create_task(self._poll_loop())   # 폴링 Task

[runtime - 사용자 키 입력]
PynputBackend Listener 스레드
  └── _on_event(key) → self._last_input = clock()

[runtime - 1초 주기]
_poll_loop()
  └── while not stopped: _tick(self._clock()); await asyncio.sleep(poll_interval)

_tick()
  └── elapsed = (now - backend.last_input_at(now)).total_seconds()
  └── 상태 전이 판정
  └── if transition and not dnd and callback:
        └── asyncio.create_task(_safe_invoke_callback(event))
              └── await ProactiveDispatcher._handle_idle_event("idle_rest")  # M_11
                    └── (쿨다운/DND 최종 확인) → ws send_text(ai-speak-signal)

[shutdown]
FastAPI lifespan.__aexit__
  └── AppServiceContext.close()
        └── _call_stop(self.idle_monitor, "idle_monitor")
              └── await idle_monitor.stop()
                    ├── self._task.cancel()
                    └── backend.stop()  (Listener.stop + join)
```

---

## 14. 의존성

### 14.1 신규 Python 패키지

| 패키지 | 버전 제약 | 용도 | 환경 마커 |
|---|---|---|---|
| `pynput` | `>=1.7,<2` | Windows 전역 키보드·마우스 훅 (Primary 백엔드) | **없음** (WSL/Linux에서도 import만 가능해야 하므로 `sys_platform` 제한하지 않음. Linux에서도 pynput은 import 가능하나 실제 Listener는 X11 DISPLAY 필요 — 본 모듈은 비Windows에서 NoopBackend로 분기하므로 pynput 코드 경로 자체 미실행) |
| `pywin32` | `>=306` | Windows 전용. `GetLastInputInfo` 직접 호출은 `ctypes`로도 가능하나 pywin32가 이미 M_12(펫 모드 always-on-top)에서 필요 — **공유**. 본 모듈은 `ctypes` 접근을 기본으로 하고 pywin32 의존은 M_12와 공유 명분으로 추가. | `sys_platform == "win32"` |

`pyproject.toml` 추가 (CR-05/06 dependencies 블록 확장):

```toml
# 기존 dependencies 블록 말미에 추가:
"pynput>=1.7,<2",
"pywin32>=306; sys_platform == 'win32'",
```

### 14.2 비Windows(WSL/Linux) 환경에서의 처리

- `pynput` — `pip install` 자체는 성공. Linux에서 import는 가능하나 X11 `DISPLAY` 미설정 시 Listener.start() 실패. 본 모듈은 **import는 허용, Listener 실행은 NoopBackend 분기로 회피** (§5.1, §6.3 D-5).
- `pywin32` — `sys_platform == "win32"` 마커로 **Windows에서만 설치**. Linux에서는 `import win32api` 등이 ImportError. 본 모듈은 Win32IdleBackend의 import를 `sys.platform` 검사 뒤로 지연(`__init__` 내부가 아닌 첫 사용 시).
- 테스트 전략: WSL CI에서 `sys.platform = 'linux'` 경로가 NoopBackend로 귀결되는 테스트 (E-7).
- 실제 Windows 경로 검증은 integrator 에이전트가 Windows VM에서 실행 (§11.5).

### 14.3 `scripts/bundle_deps.sh` 갱신

`=== [bundle_deps.sh] M_10 IdleMonitor 의존성 ===` 블록 추가:

```bash
pip download \
    "pynput>=1.7,<2" \
    --dest "${WHEELS_DIR}"

# pywin32는 Windows 전용. 빌드 머신이 Windows라면 아래, Linux라면 --platform 지정 필요.
pip download \
    "pywin32>=306" \
    --platform win_amd64 \
    --python-version 3.12 \
    --only-binary=:all: \
    --dest "${WHEELS_DIR}"
```

### 14.4 표준 라이브러리

- `asyncio` — Task 관리.
- `datetime` / `timedelta` — 시간 산술.
- `ctypes` — Win32 GetLastInputInfo 호출 (pywin32 미설치 환경에서도 fallback 경로 제공 가능성 확보).
- `logging` (또는 loguru) — M_01 표준 로거.
- `typing` — Literal, Callable, Awaitable.
- `sys` — platform 검사.
- `abc` — `_IdleBackend` ABC.

---

## 15. 성능·리소스 검증

| 항목 | 검증 방법 | 기준 |
|---|---|---|
| 1초 주기 폴링 CPU | 1분간 `psutil.Process().cpu_percent()` 측정 (integrator 단계, Windows VM) | < 0.1% |
| 메모리 추가 상주 | start 전/후 RSS diff 측정 | < 5 MB |
| `_tick` 1000회 호출 총 소요 | 단위 테스트 A-4 | < 50 ms |
| 훅 콜백 latency | pynput Listener 내부 큐 크기 모니터 (Windows VM) | 상시 < 100 events/sec |

단위 테스트는 `pytest-benchmark` 의존성 추가하지 않고 `time.perf_counter` 수기 측정(freezegun 금지 선례와 일관).

---

## 16. docs/MODULES.md 초안과의 일치·수정 사항

`docs/MODULES.md` L350~L371의 M_10 초안과 본 스펙의 차이. 본 스펙 승인 후 `docs/MODULES.md`를 아래와 같이 갱신 (M_07/M_08/M_09 선례 동일 패턴).

### 16.1 변경 요약 표

| 항목 | 초안 | 본 스펙 | 수정 근거 |
|---|---|---|---|
| `cooldown_min: int = 30` 파라미터 | `__init__`에 존재 | **제거** | §6.3 D-1 — 시간 기반 쿨다운은 M_11 전담. M_10은 상태 전이당 1회 불변식만 제공. |
| `dnd_enabled: bool = False` 파라미터 | `__init__`에 존재 | **제거** (생성자 인자 없음; `set_dnd(False)`가 기본 상태) | D-1 연장 — M_10은 `set_dnd()` 메서드만 제공. 생성 시 DND는 항상 False로 시작. conf.yaml에 초기 DND 설정은 없음 (REQUIREMENTS.md §5 "사용자가 설정 가능" — 런타임 토글). |
| `active_gap_seconds: int = 60` 파라미터 | **없음** | **추가** | §5.2 근거 — "연속 활동" 정의가 없으면 overwork 판정이 애매. 명시적 파라미터화. |
| `poll_interval_seconds: float = 1.0` 파라미터 | **없음** | **추가** | §6.3 D-4 — 테스트에서 0.1로 낮춰 단위 테스트 가속. |
| `clock: Callable[[], datetime]` | **없음** | **추가** | 테스트 용이성. freezegun 의존성 추가 회피(선례 동일). |
| `backend: _IdleBackend \| None` | **없음** | **추가** (내부용, 타입은 비공개) | 테스트 용이성. DI로 pynput/pywin32 회피. |
| `start()` | `def start() -> None` | `def start() -> None` (유지) + Noop 분기 명시 | 변경 없음 |
| `stop()` | `def stop() -> None` | `async def stop() -> None` | `_call_stop`이 sync/async 모두 수용. async로 선언해 폴링 Task `cancel + await` 자연스러움. |
| `on_event(callback)` | `Callable[[IdleEvent], Awaitable[None]]` | `IdleEventCallback \| None` (None 전달 가능) | 콜백 해제 경로 필요. |
| `last_input_at()` | **없음** | **추가** (public) | M_11이 부가 정보 조회용(§6.3 D-6). |
| `seconds_since_last_input()` | **없음** | **추가** (public) | 동일 근거. |
| `_tick(now)` | **없음** | **추가** (public-visible private) | 단위 테스트·시간 빨리감기. M_07 `RagService.retrieve` sync 선례와 유사한 "테스트 용이성 우선" 결정. |
| 폴백 전략 | "로그 경고, 서비스 no-op" | **Win32 자동 폴백** + 둘 다 실패 시 Noop 강등 | R-10 **필수 포함 사항**. 초안보다 강화. |
| 의존성 | `pynput, asyncio` | `pynput, pywin32 (win32 only), asyncio, ctypes` | R-10 폴백 구현에 필요. |

### 16.2 M_10 블록 치환 문구 (MODULES.md 반영용)

```markdown
### M_10 IdleMonitor (Windows 유휴 감지)

- **분류**: NEW
- **상태**: ✅ DONE  (← 🔲 TODO)
- **목적**: 마우스·키보드 입력 이벤트를 관찰해 유휴(`idle_rest`)·과로(`overwork`) 상태 전이를 방출.
  시간 기반 쿨다운과 WebSocket 송신은 M_11 책임(specs/M_10 §6.3 D-1).
- **공개 API**
  ```python
  IdleEvent = Literal["idle_rest", "overwork"]
  IdleEventCallback = Callable[[IdleEvent], Awaitable[None]]

  class IdleMonitor:
      def __init__(self, *,
                   idle_threshold_min: int = 45,
                   overwork_threshold_min: int = 120,
                   active_gap_seconds: int = 60,
                   poll_interval_seconds: float = 1.0,
                   clock: Callable[[], datetime] = datetime.now,
                   backend: _IdleBackend | None = None) -> None: ...
      def start(self) -> None: ...
      async def stop(self) -> None: ...
      def set_dnd(self, enabled: bool) -> None: ...
      def on_event(self, callback: IdleEventCallback | None) -> None: ...
      def last_input_at(self) -> datetime: ...
      def seconds_since_last_input(self) -> float: ...
      def _tick(self, now: datetime | None = None) -> None: ...   # public-visible private
  ```
- **에러**: pynput 훅 실패 → Win32 `GetLastInputInfo` 자동 폴백 (R-10 필수 요건). 둘 다 실패 시
  NoopBackend로 강등 + logger.error, 서비스 자체는 no-op로 계속 기동(기능 비활성).
- **의존**: `pynput`, `pywin32` (Windows only, `sys_platform == "win32"` 마커), `asyncio`, `ctypes`.
- **비고**: `cooldown_min`/`dnd_enabled` 생성자 인자는 **M_11로 이동** (specs/M_10 §16.1).
  `active_gap_seconds`, `poll_interval_seconds`, `clock`, `backend` 신설 (§6.3 D-4, §5.3).
```

---

## 17. 스펙 외 사항 (명시적 제외, 오해 방지용)

본 모듈의 책임이 **아닌** 항목. Critic은 아래 항목을 M_10 결함으로 간주하지 않는다.

1. **시간 기반 쿨다운 정책**: "동일 이벤트 30분 내 재방출 금지" — M_11 (docs/MODULES.md L389, specs/M_11).
2. **WebSocket 송신 / `ai-speak-signal` 페이로드 생성** — M_11.
3. **APScheduler 크론 트리거 / 아침 09:00 브리핑 / 일정 10분 전 알림** — M_11.
4. **화면 잠금·세션 상태 추적** — V2 검토. V1에서는 잠금 상태 = 무입력 상태로 귀결.
5. **EDR 예외 등록·IT 부서 협의** — 운영 절차, RISKS R-10 완화 방안 2번은 본 모듈 책임 아님.
6. **conf.yaml 파싱** — M_01 `AppConfig.proactive` 섹션. 본 모듈은 **kwargs만 받는다**.
7. **한국어 휴식 권고 메시지 문구 / TTS 프롬프트** — M_05(시스템 프롬프트) / M_11(프로액티브 토픽 프롬프트 템플릿).
8. **아바타 감정 전환**: `overwork` 이벤트 시 "sleepy" 표정으로 전환하는 로직은 M_11이 `avatar_state.push_event`를 추가 호출(`docs/ARCHITECTURE.md` §3.4 근거). 본 모듈은 아바타 상태를 건드리지 않는다.
9. **사용자 설정 GUI / DND 토글 버튼** — M_12 프론트엔드 + M_01 WebSocket 메시지 타입 (현재 M_01 SPEC에 `dnd-toggle` 타입이 없다면 M_11/M_12 단계에서 CR로 추가).
10. **다중 콜백 / 콜백 리스트** — 단일 슬롯 덮어쓰기 (§6.3 D-2).
11. **이벤트 메타데이터 확장**: since/duration/context dict 전달 — 콜백은 Literal 문자열만 (§6.3 D-6). 소비자가 헬퍼로 pull.
12. **테스트용 `force_fallback` 플래그** — YAGNI (§6.3 D-9). 테스트는 `backend=Win32IdleBackend(...)` 직접 주입으로 대체.
13. **pynput Listener 스레드 정상성 모니터링**: Listener가 도중에 죽는 경우 재시작 — V1 범위 밖. `stop()` + 재`start()` 수동 경로만 제공.
14. **다른 운영체제 지원** (Linux `evdev`, macOS Accessibility API): REQUIREMENTS.md §0 Windows 전용. NoopBackend로 비Windows는 기능 비활성.

---

## 18. 부록 — upstream·소스 증적

본 스펙 작성 중 참조한 경로:

- `upstream/Open-LLM-VTuber/src/open_llm_vtuber/**` — `rg "idle|GetLastInputInfo|pynput"` 히트 0건. 본 모듈은 100% 신규.
- `src/app/service_context.py:40` — `self.idle_monitor: "IdleMonitor | None" = None` 슬롯 기존재.
- `src/app/service_context.py:267~271` — `_call_stop(self.idle_monitor, "idle_monitor")` 호출 경로 기존재.
- `src/app/service_context.py:305~311` — `_call_stop` 헬퍼가 sync/async 양쪽 stop 수용.
- `docs/ARCHITECTURE.md` §1 Windows API 블록 — pynput·pywin32 사용 계획 근거.
- `docs/RISKS.md` R-10 — pynput 폴백 필수 요건.
- `docs/MILESTONES.md` L129~L137 — DoD 5항.
- `specs/M_01_AppCore_SPEC.md` L134 `proactive_cooldown_min` — M_11 책임임을 확인(본 모듈 인자 아님).
- `specs/M_01_AppCore_SPEC.md` L332 — FastAPI startup hook에서 `ctx.idle_monitor.start()` 호출 계획 기존재.
- Windows API `GetLastInputInfo`: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getlastinputinfo (외부 참조 — 코드 런타임에 접근하지 않음).

본 스펙이 **upstream 파일을 수정하지 않는다**는 CLAUDE.md 규칙을 준수.

---
