# M_09 CalendarService — 스펙

> 분류: **NEW** — upstream `Open-LLM-VTuber/`에는 대응 구현이 없다. SQLite 기반 일정 CRUD + 다가오는 이벤트 조회를 담당한다.
>
> 작성 근거: `REQUIREMENTS.md` §0/§4.1/§4.2/§9/§10, `docs/MODULES.md` L292~L320(M_09 초안), `docs/MILESTONES.md` L88~L96(DoD 고유 기준), `specs/M_05b_ToolRouter_SPEC.md`, `src/tool_router/router.py` L158~L227(호출 계약), `src/tool_router/schemas.py`(JSON Schema 경계값).

---

## 1. 목적과 범위

### 1.1 목적

사내 오프라인 AI 비서 "새싹이"의 일정 등록·조회·수정·삭제 스토어를 제공한다. 단일 SQLite 파일(`data/calendar.db`)을 유일한 영속 스토리지로 쓴다. 본 모듈은 **순수 데이터 계층**으로, 자연어 날짜 파싱·알림 송신·브리핑 문장 생성 등 **시간·문장 해석은 전혀 수행하지 않는다**.

### 1.2 In-Scope

1. `CalendarService` 클래스 — `add_event` / `get_events` / `get_event` / `update_event` / `delete_event` / `events_due_within` / `close` 7개 공개 메서드.
2. `Event` dataclass — `id`/`title`/`start`/`duration_minutes`/`description`/`created_at` 6필드. **frozen=True**.
3. SQLite 스키마 V1 DDL과 `PRAGMA user_version` 기반 단순 번호 비교 마이그레이션 훅.
4. tz-aware datetime 입출력 계약(§6).
5. `threading.RLock`을 이용한 스레드 안전 write/read 직렬화(§8).
6. `src/app/service_context.py` `load_app_services`의 `calendar_service` 주입 1줄 배선(§13 §13.6 "배선 범위 결정").
7. 단위 테스트(정상 ≥5, 엣지 ≥5, 적대적 ≥3) + 1만건 성능 smoke 테스트.

### 1.3 Out-of-Scope (명시적 제외)

1. **자연어 날짜 파싱** ("내일 오후 3시" 등). LLM(M_05) + tool_router(M_05b)가 ISO 8601 문자열로 변환 완료한 후 본 모듈에 도달한다. 실패 시 본 모듈은 `CalendarValidationError`.
2. **반복 일정(recurrence rules, RRULE, iCalendar RFC 5545)**. REQUIREMENTS.md에 없음. 향후 요구 시 `docs/CHANGE_REQUESTS.md` 경유.
3. **알림 실제 송신**. M_11 `ProactiveDispatcher`가 `events_due_within(10)`을 1분마다 폴링해 upstream `ai-speak-signal` 경로로 송신한다. 본 모듈은 "어떤 이벤트가 임박한가"만 반환.
4. **아침 브리핑 문장 생성**. M_11 + M_05 책임.
5. **캘린더 공유·외부 동기화(CalDAV, Google Calendar, Outlook)**. REQUIREMENTS.md §0 완전 오프라인으로 금지.
6. **다중 사용자 분리(멀티 테넌시)**. REQUIREMENTS.md §10 "다중 사용자 동시 접속 안 함".
7. **타임존 전환 UI / 설정 페이지**. `default_tz`는 생성자 인자로 고정.
8. **이벤트 첨부 파일·알림 채널 설정(이메일/SMS)**.
9. **Undo / soft delete / audit log**. `delete_event`는 하드 삭제.
10. **자동 DB 백업·복원**. 단일 파일이므로 운영은 외부 도구(Robocopy 등)에 위임.

---

## 2. 요구사항 연결

| REQUIREMENTS.md 항목 | M_09 기여 |
|---|---|
| §0 완전 오프라인 / Windows 10/11 | 표준 라이브러리 `sqlite3` 단일 파일 DB. 외부 네트워크 호출 0건, 추가 패키지 0건 |
| §4.1 일정 등록(함수 호출) | `add_event(title, start, duration_minutes, description)` → `Event` 반환. M_05b `add_event` 툴 핸들러가 `run_in_executor`로 호출 |
| §4.1 조회 | `get_events(start, end)` → `[start, end)` 반열린 구간, `start_utc ASC` 정렬 |
| §4.2 10분 전 알림 | `events_due_within(minutes=10)` → `[now_utc, now_utc+minutes]` 범위, 이미 지난 이벤트 제외. M_11 `ProactiveDispatcher`가 1분 간격 폴링 |
| §9 응답 지연 | 1만건 데이터에서 `get_events(1일 범위)` p95 ≤ 50ms. `idx_events_start_utc` 단일 B-Tree 인덱스로 달성 |
| §9 메모리 예산 | 단일 SQLite 커넥션 유지. 쿼리당 누적 메모리 ≤ 10 MB (1만건 전체 스캔 가정해도 row당 ≤ 1 KB × 1만 = 10 MB 상한) |
| §9 외부 네트워크 호출 금지 | 표준 라이브러리만 사용. import 레벨에서 네트워크 모듈 0 |
| §10 다중 사용자 불가 | 단일 커넥션 + `threading.RLock`으로 write 직렬화. 동시 접속 시나리오는 고려하지 않음 |

---

## 3. upstream 재사용 분석

### 3.1 분류: **NEW** (REUSE 없음, DROP 없음)

upstream `Open-LLM-VTuber`는 음성 대화·TTS·VAD·LLM Agent·웹소켓에 특화된 프레임워크로, 일정(schedule/calendar/event) 관련 도메인 코드를 **포함하지 않는다**.

### 3.2 근거 증적

`grep -r "calendar\|Event " upstream/Open-LLM-VTuber/` 실행 결과(계획 단계 사전 조사, §1.3 Out-of-Scope와 연동):

- 히트: `upstream/Open-LLM-VTuber/uv.lock`, `upstream/Open-LLM-VTuber/requirements.txt` — 의존성 lock 파일의 무관 단어 매칭(`EventLoop`, `calendar` 등 파이썬 표준 패키지 이름 잔재). **도메인 코드 0건**.
- `src/open_llm_vtuber/` 하위에 `calendar*.py`, `schedule*.py`, `event_store*.py` 등 **0건**.
- 결론: REUSE 대상 없음. 본 모듈은 100% 신규 구현이다.

### 3.3 DROP

없음 — upstream에 대응물이 없으므로 "제거" 대상도 없다.

### 3.4 EXTEND

없음 — 본 모듈은 upstream 클래스를 상속·확장하지 않는다. `AppServiceContext`에 슬롯 주입만 한다(M_01 규약, §13 §13.6).

---

## 4. 공개 API

### 4.1 데이터 타입

```python
# src/calendar_service/service.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

_KST: ZoneInfo = ZoneInfo("Asia/Seoul")


@dataclass(frozen=True)
class Event:
    """단일 일정 레코드.

    - `start` / `created_at`은 **반드시 tz-aware**. 내부 저장은 UTC ISO 8601,
      반환 시 `CalendarService.default_tz` 기준으로 astimezone 후 전달.
    - frozen=True: 호출자 수정 방지. 수정은 반드시 `update_event` 경유.
    """

    id: int
    title: str
    start: datetime               # tz-aware
    duration_minutes: int
    description: str | None
    created_at: datetime          # tz-aware
```

### 4.2 CalendarService 메서드 시그니처 (전부 **동기**)

```python
class CalendarService:
    def __init__(
        self,
        db_path: str,
        *,
        default_tz: ZoneInfo = _KST,
    ) -> None: ...

    def add_event(
        self,
        title: str,
        start: datetime,
        duration_minutes: int,
        description: str | None = None,
    ) -> Event: ...

    def get_events(
        self,
        start: datetime,
        end: datetime,
    ) -> list[Event]: ...

    def get_event(self, event_id: int) -> Event | None: ...

    def update_event(self, event_id: int, **fields: Any) -> Event: ...

    def delete_event(self, event_id: int) -> bool: ...

    def events_due_within(self, minutes: int) -> list[Event]: ...

    def close(self) -> None: ...
```

### 4.3 sync API 확정 근거 (중요)

`docs/MODULES.md` L310~L317 초안은 `async def add_event / get_events / ...` 형태였으나, **본 스펙에서 sync로 확정**한다. 근거:

1. **호출자 계약**: `src/tool_router/router.py:158~227`의 `_handle_add_event` / `_handle_get_events`는 이미
   ```python
   await asyncio.get_running_loop().run_in_executor(
       None,
       lambda: self._calendar.add_event(...),
   )
   ```
   형태로 동기 함수를 executor에 밀어넣는다. 본 모듈이 `async`면 이중 await가 발생하거나 `run_in_executor` 경로가 깨진다.
2. **M_11 계약**: `ProactiveDispatcher`도 동일하게 `run_in_executor(None, lambda: calendar.events_due_within(10))` 패턴을 쓸 예정(MILESTONES M_11 기준 + 본 프로젝트 async 서비스 규약).
3. **SQLite 비동기 지원 부재**: 표준 `sqlite3` 모듈은 async API를 제공하지 않는다. `aiosqlite`는 추가 의존성이며 본 프로젝트 오프라인 번들 정책상 최소 의존성을 유지한다.
4. **I/O 특성**: 로컬 디스크 ≤ 10 MB DB 파일 단일 쿼리의 p95는 사실상 5~50ms. 블로킹 시간이 짧아 executor로 충분하며 async overhead를 추가할 실익이 없다.

→ 따라서 본 스펙 §16 "MODULES.md 갱신 필요"에서 초안의 `async` 표기를 동기로 정정한다.

### 4.4 에러 클래스 (errors.py)

```python
# src/calendar_service/errors.py

class CalendarError(Exception):
    """CalendarService 최상위 기본 예외."""


class CalendarInitError(CalendarError):
    """DB 파일 생성·스키마 초기화 실패(기동 실패)."""


class CalendarValidationError(CalendarError, ValueError):
    """입력 검증 실패(title 길이, duration 범위 등). ValueError 다중 상속으로
    호출자가 `except ValueError`로도 잡을 수 있다."""


class CalendarDBError(CalendarError):
    """sqlite3.OperationalError / IntegrityError wrap."""


class EventNotFoundError(CalendarError):
    """update_event에서 event_id 미존재. delete_event는 False 반환으로 처리."""
```

---

## 5. 데이터 모델 / SQLite 스키마 V1 (확정)

### 5.1 DDL

```sql
CREATE TABLE IF NOT EXISTS events (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  title             TEXT NOT NULL,
  start_utc         TEXT NOT NULL,        -- ISO 8601 UTC: YYYY-MM-DDTHH:MM:SS+00:00
  duration_minutes  INTEGER NOT NULL,
  description       TEXT,
  created_at_utc    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_start_utc ON events(start_utc);
```

### 5.2 직렬화 포맷 확정

- **저장**: Python `datetime`을 UTC로 변환 후 `dt.astimezone(timezone.utc).isoformat()` → `2026-04-19T12:34:56+00:00` 형태.
- **복원**: `datetime.fromisoformat(row_str)` → tz-aware UTC → `astimezone(default_tz)` → `Event.start` 필드 값.
- **정렬**: ISO 8601 문자열 사전식 정렬과 실제 시간 순서가 일치(UTC 고정). SQLite `ORDER BY start_utc ASC` 사용 가능.

### 5.3 왜 UTC 저장인가

1. 현재 대상은 Asia/Seoul(DST 없음)이지만, 추후 해외 지사 설치 시 재마이그레이션 불필요.
2. 문자열 lexicographic 정렬과 시간 정렬이 일치 → `ORDER BY start_utc` 인덱스 스캔만으로 정렬 완료.
3. tz-aware datetime의 isoformat은 `+00:00` 접미사를 포함해 혼동 여지가 없다.

### 5.4 PRAGMA user_version 기반 마이그레이션

- V1: `PRAGMA user_version = 1` 고정.
- 생성자 내 초기화 순서:
  1. `sqlite3.connect(db_path, check_same_thread=False, isolation_level=None)`  — autocommit 모드.
  2. `PRAGMA journal_mode = WAL`  (읽기/쓰기 동시성 향상).
  3. `PRAGMA synchronous = NORMAL`  (WAL 모드에서 안전하고 빠른 조합).
  4. `PRAGMA user_version` 조회 → 0이면 DDL 실행 후 `PRAGMA user_version = 1` 세팅.
  5. `PRAGMA user_version > 1`인 경우 `CalendarInitError("DB schema newer than supported")` — 다운그레이드 방지.
- **migrations.py**는 V1만 있는 현재 선택 파일이다. 상수만 정의하고 실제 V2 도입 시 추가(§15 참조).

### 5.5 필드 상세

| 컬럼 | 타입 | 제약 | 비고 |
|---|---|---|---|
| `id` | INTEGER | PK, AUTOINCREMENT | SQLite AUTOINCREMENT 보장 |
| `title` | TEXT | NOT NULL, 1~500자 | 애플리케이션 레벨 검증 |
| `start_utc` | TEXT | NOT NULL, ISO 8601 with tz | 인덱스 대상 |
| `duration_minutes` | INTEGER | NOT NULL, 1~1440 | 애플리케이션 레벨 검증 |
| `description` | TEXT | NULL 허용, 0~4000자 | NULL과 `""` 구분 유지(NULL이면 `Event.description=None`) |
| `created_at_utc` | TEXT | NOT NULL | 서버측(앱측) `datetime.now(timezone.utc)` |

---

## 6. 시간대(tz) 처리 규약

1. **입력 `start` / `end`가 tz-naive인 경우**: `default_tz`(기본 `Asia/Seoul`)로 가정하여 `start.replace(tzinfo=default_tz)` 후 UTC 변환. 첫 발생 시 `logger.warning("naive datetime received; assumed default_tz=%s", default_tz)`를 **호출당 1회** 출력(억제 카운터 불필요, 호출 빈도가 낮음).
2. **내부 저장**: 항상 UTC(`astimezone(timezone.utc).isoformat()`).
3. **반환**: `Event.start` / `Event.created_at`은 `astimezone(default_tz)` 적용 후 tz-aware로 반환. `.tzinfo`는 반드시 non-None.
4. **`events_due_within(minutes)`의 기준시**: `datetime.now(timezone.utc)`를 사용. `datetime.now()`(naive) 금지.
5. **범위 쿼리의 반열린 구간**: `start_utc >= :start AND start_utc < :end`로 구현. `end` 자체는 포함하지 않는다(MILESTONES L93 "`start <= e.start < end`"와 일치).

---

## 7. 입력 검증 규칙

`add_event` / `update_event` 양쪽에 동일하게 적용. 실패 시 `CalendarValidationError`.

| 필드 | 규칙 | 실패 메시지 예 |
|---|---|---|
| `title` | `str.strip()` 후 1~500자. 빈 문자열 / `None` / 공백만 → 실패 | `"title must be 1~500 chars after strip"` |
| `duration_minutes` | 정수 1~1440 (24시간). `float`/음수/0/1441+ → 실패 | `"duration_minutes must be 1~1440, got %r"` |
| `description` | `None` 또는 0~4000자. 초과 → 실패. 빈 문자열은 허용(NULL과 구분해 저장하지 않고 `""`는 NULL로 변환) | `"description must be 0~4000 chars"` |
| `start` | `datetime` 인스턴스여야 함. 문자열 전달 시 `CalendarValidationError("start must be datetime, got str")` | — |
| `events_due_within` `minutes` | 정수 1 이상. 0 또는 음수 → `CalendarValidationError("minutes must be >= 1")` | — |

**주의**: JSON Schema(M_05b `schemas.py`)가 `title` maxLength=200, `description` maxLength=2000으로 더 엄격한 상한을 걸고 있다. 본 모듈은 **애플리케이션 한계선**이 더 넓은 편인데, 이는 향후 UI 직접 입력(M_12 프론트엔드) 경로에서 더 긴 값을 허용할 여지를 둔다. JSON Schema가 먼저 차단하므로 정상 흐름에서는 200/2000을 초과해 본 모듈까지 도달하지 않는다. **JSON Schema 한계와 본 모듈 한계가 어긋나면 M_05b JSON Schema가 우선**이다.

### 7.1 중복 `(title, start)` 정책 확정

`docs/MODULES.md` L319 "중복 허용(새 id 부여) + 경고 로그"를 **본 스펙에서 재확인·확정**한다.

**결정: 중복 허용, 새 id 부여, `logger.warning` 1회.**

근거:
1. UX: "팀 회의"가 매주 수요일 오후 3시에 있다면 사용자가 수동으로 4주치를 등록하는 케이스 발생. 거부는 사용자 흐름 차단.
2. `update_event`로 인한 동일 `(title, start)` 발생 가능 — 거부 정책은 수정도 깨뜨림.
3. 중복 거부는 `UNIQUE(title, start_utc)` 인덱스 추가가 필요하나, V1 성능 예산에 영향. 소요가 불분명한 제약을 스키마에 박지 않는다.

경고 로그 포맷: `logger.warning("duplicate event: title=%r start=%s; creating new id", title, start_utc)`.

---

## 8. 동시성 / 스레드 안전성

### 8.1 커넥션 전략

- 단일 `sqlite3.Connection`을 생성자에서 오픈하고 프로세스 수명 동안 유지.
- `check_same_thread=False` — M_05b/M_11이 `asyncio.get_running_loop().run_in_executor(None, ...)`로 기본 executor(ThreadPoolExecutor, default workers) 스레드에서 호출하기 때문. 스레드 ID는 호출마다 달라질 수 있다.
- `isolation_level=None`(autocommit) — 명시적 트랜잭션이 필요한 경우 `conn.execute("BEGIN")` 사용. V1 모든 메서드는 단일 statement로 충족.

### 8.2 락

- `self._lock = threading.RLock()`.
- 모든 공개 메서드(add/get/update/delete/events_due_within)의 바디를 `with self._lock:`로 감싼다.
- 재진입 가능하도록 RLock 선택(`get_event`를 내부에서 `update_event`가 호출하는 경우 등).

### 8.3 Contention 예상

- 단일 사용자 전제(REQUIREMENTS.md §10). 일정 등록 빈도 < 1 op/분, 폴링 빈도 = 1/분 (M_11).
- 합산 부하 < 0.1 op/s → lock 대기 시간은 사실상 0. 병목 발생 가능성 없음.

### 8.4 트랜잭션 경계

- `add_event`: 단일 INSERT.
- `update_event`: 단일 UPDATE (존재 여부 선검사 SELECT 포함 — lock 범위 내에서 원자성 보장).
- `delete_event`: 단일 DELETE + `rowcount` 검사.
- `get_events` / `get_event` / `events_due_within`: 단일 SELECT.

---

## 9. close 라이프사이클

### 9.1 호출 지점

`src/app/service_context.py:278~282`(AppServiceContext.close)이 `_call_close(self.calendar_service, "calendar_service")`로 호출한다. 본 모듈의 `close`는 **sync 함수**이며, `_call_close`는 sync/async 양쪽을 지원(sync는 직접 호출, async는 await). M_01 `_call_close` 패턴 확인.

### 9.2 동작

```text
1. self._lock 획득 (이미 진행 중인 연산 완료 대기).
2. self._conn이 None이 아니고 살아있으면:
   - conn.execute("PRAGMA wal_checkpoint(FULL)")  # WAL → DB 본체 반영
   - conn.close()
   - self._conn = None
3. 이미 close된 상태에서 재호출 시 no-op(멱등성).
4. 어떤 예외도 밖으로 던지지 않음 — logger.warning으로 삼키고 반환.
   (AppServiceContext.close는 개별 서비스 close 실패가 다른 정리를 막지 않도록 try/except로 감싸지만, 본 모듈도 방어적으로 처리)
```

### 9.3 close 이후 메서드 호출

`close()` 후 다른 메서드 호출 시 `CalendarDBError("calendar service is closed")` 발생. 다시 열려면 인스턴스를 새로 생성해야 한다(재활용 없음).

---

## 10. 에러 처리 정책

| 상황 | 내부 처리 | 호출자에게 노출 |
|---|---|---|
| `db_path` 디렉토리 없음 | `os.makedirs(dirname, exist_ok=True)` 자동 생성 | 생성 실패 시 `CalendarInitError`로 기동 실패 |
| `sqlite3.connect` 실패 (권한/디스크 등) | `CalendarInitError` wrap | 기동 실패 — `load_app_services`가 로그 경고 + `calendar_service=None` |
| `PRAGMA user_version > 1` (미래 DB) | `CalendarInitError("DB schema newer than supported")` | 기동 실패 |
| `sqlite3.OperationalError` (락 타임아웃, 디스크 풀 등) 런타임 | `CalendarDBError` wrap + `logger.exception` | 호출자에게 예외 — M_05b tool_router가 `ToolResult(ok=False, error="CalendarDBError: ...")` 변환 |
| `sqlite3.IntegrityError` | `CalendarDBError` wrap | 동일 |
| `title` 공백만 / 길이 초과 | `CalendarValidationError` | M_05b가 `ToolResult(ok=False, error="CalendarValidationError: title ...")` |
| `duration_minutes` 범위 밖 | `CalendarValidationError` | 동일 |
| `get_events`의 `start > end` | 빈 리스트 반환 (예외 아님) | 경계 완화. `src/tool_router/router.py:202~204`가 이미 선처리하지만 본 모듈 단독 호출 경로(M_11) 대비 방어 |
| `update_event(event_id, ...)` 미존재 | `EventNotFoundError` | M_05b는 현재 update 툴을 노출하지 않지만 내부 API로 제공 |
| `delete_event(event_id)` 미존재 | `False` 반환 (예외 아님) | M_05b도 현재 delete 툴을 노출하지 않지만 CLI/테스트 경로용 |
| `events_due_within(minutes <= 0)` | `CalendarValidationError("minutes must be >= 1")` | — |
| `close()` 이후 재호출 | `CalendarDBError("calendar service is closed")` | — |

---

## 11. 성능·메모리 요구

### 11.1 성능 목표

| 시나리오 | 목표 | 달성 전략 |
|---|---|---|
| `get_events(1일 범위)` @ 1만건 DB | p95 ≤ 50 ms | `idx_events_start_utc` B-Tree 범위 스캔 + 정렬 없이 인덱스 순회 |
| `add_event` | p95 ≤ 20 ms | 단일 INSERT, WAL 모드 |
| `events_due_within(10)` @ 1만건 DB | p95 ≤ 30 ms | 동일 인덱스, 10분 범위는 극도로 좁음 |
| `close()` | ≤ 50 ms | WAL checkpoint 포함 |

### 11.2 쿼리 형태

```sql
-- get_events
SELECT id, title, start_utc, duration_minutes, description, created_at_utc
FROM events
WHERE start_utc >= :start AND start_utc < :end
ORDER BY start_utc ASC;

-- events_due_within
SELECT id, title, start_utc, duration_minutes, description, created_at_utc
FROM events
WHERE start_utc >= :now_utc AND start_utc <= :upper_utc
ORDER BY start_utc ASC;
```

`EXPLAIN QUERY PLAN` 출력에 `USING INDEX idx_events_start_utc` 포함을 회귀 테스트로 확인.

### 11.3 메모리

- 커넥션 1개 + row factory(`sqlite3.Row`) 사용. 쿼리 결과는 `fetchall()`로 일시 전체 로드.
- 1만건 반환 시 row당 ≤ 1 KB × 1만 = **≤ 10 MB** (상한). 일반 1일 범위는 수십 건 — 수 KB.
- 스트리밍(`cursor.__iter__`) 도입은 V1 불필요. V2에서 `limit/offset` 페이지네이션과 함께 재검토.

---

## 12. 테스트 케이스

파일 배치는 §15 참조. 각 케이스는 번호·입력·기대 결과를 번호매김. 합계 **정상 5 + 엣지 5 + 적대적 4 = 14건**.

### 12.1 정상 (Normal, N)

1. **N1 add/get round-trip**: `add_event("회의", 2026-04-20T15:00+09:00, 60, "기획")` → 반환 `Event.id >= 1`. 이후 `get_event(id)`가 동일 필드(tz-aware 포함)로 반환.
2. **N2 get_events 범위 필터**: 9/1, 9/15, 9/30 세 건 등록 → `get_events(9/10, 9/20)` → 9/15 단 1건, 정렬 start ASC.
3. **N3 events_due_within 정확 매치**: `now+5min` 이벤트 1건 + `now+20min` 이벤트 1건 → `events_due_within(10)` → 앞 1건만 반환.
4. **N4 events_due_within 0건**: 모든 이벤트가 `now+30min` 이후 → `events_due_within(10)` → `[]`.
5. **N5 close 멱등**: `close()` 두 번 호출해도 예외 없음. 두 번째는 no-op.

### 12.2 엣지 (Edge, E)

1. **E1 tz-naive 입력**: `add_event("회의", datetime(2026,4,20,15,0), 60)` → 반환 `event.start.tzinfo == Asia/Seoul` (UTC+9). 경고 로그 1회 출력 확인.
2. **E2 `start == end` 경계**: `get_events(t, t)` → 빈 리스트(`start < end` 아님 → 반열린 구간에서 공집합).
3. **E3 duration 경계**: `duration=1`, `duration=1440` 둘 다 성공. `0`과 `1441`은 `CalendarValidationError`.
4. **E4 title 길이 경계**: 1자("A")·500자 성공. 빈 문자열("")과 501자는 실패.
5. **E5 update로 start 변경 후 재정렬**: 3건 등록(A=9/10, B=9/15, C=9/20) → B를 9/25로 update → `get_events(9/1, 9/30)` 결과 [A, C, B] 순서.

### 12.3 적대적 (Adversarial, A)

1. **A1 SQL 인젝션 시도**: `add_event("'; DROP TABLE events; --", ...)` 성공 후 `get_events`가 여전히 기존 테이블에서 데이터 반환(prepared statement로 안전). 인젝션 title도 그대로 저장되어 있음.
2. **A2 대규모 데이터 성능 smoke** (`@pytest.mark.slow`): 1만건 seed(3년치, 랜덤 분산) 후 `get_events(하루 범위)` 50회 반복. p95 ≤ 50 ms. pytest log에 실제 측정치 기록.
3. **A3 적대적 입력 폭격**: `duration=0`, `duration=-1`, `duration=10**9`, `title=None`, `title="   "`(공백만), `description="x"*5000` 전부 `CalendarValidationError`. DB에 커밋된 행이 없음.
4. **A4 close 이후 사용**: `close()` 후 `add_event(...)` 호출 → `CalendarDBError("calendar service is closed")`. DB 파일에 신규 행 없음.

### 12.4 공통 픽스처

- `conftest.py`: `tmp_path`로 `db_path=tmp_path/"calendar.db"` 픽스처.
- 시간 고정: `freezegun` 의존성 추가 금지(오프라인 번들 최소화). 대신 **monkeypatch** + `datetime` wrapper 함수(`_now_utc()`)를 모듈 내부에 두고 테스트에서 `monkeypatch.setattr` 사용.

---

## 13. Definition of Done

공통 DoD(CLAUDE.md "산출물 체크리스트") + M_09 고유(MILESTONES L88~L96) + 본 스펙 추가분.

### 13.1 파일 생성

- [ ] `specs/M_09_CalendarService_SPEC.md` (본 파일, 사용자 승인 완료).
- [ ] `src/calendar_service/__init__.py` — `CalendarService`, `Event`, 에러 5종 re-export.
- [ ] `src/calendar_service/service.py` — `CalendarService`, `Event`.
- [ ] `src/calendar_service/errors.py` — 에러 5종.
- [ ] `src/calendar_service/migrations.py` — `SCHEMA_V1_DDL` 상수 + `CURRENT_USER_VERSION = 1`. V1만이면 함수 없이 상수만.
- [ ] `tests/calendar_service/conftest.py` — `db_path` 픽스처, `now_utc_override` 픽스처.
- [ ] `tests/calendar_service/test_service.py` — CRUD + `events_due_within`.
- [ ] `tests/calendar_service/test_validation.py` — 입력 검증.
- [ ] `tests/calendar_service/test_performance.py` — `@pytest.mark.slow` 1만건 seed.

### 13.2 테스트

- [ ] 정상 ≥ 5, 엣지 ≥ 5, 적대적 ≥ 3 (본 스펙 §12 기준 14건 이상).
- [ ] `pytest tests/calendar_service` PASS.
- [ ] `pytest tests/calendar_service -m slow` 1만건 성능 테스트 PASS (p95 ≤ 50 ms 로깅).

### 13.3 린트·타입·포맷

- [ ] `ruff format src/calendar_service tests/calendar_service` 무변경.
- [ ] `ruff check src/calendar_service tests/calendar_service` 위반 0.
- [ ] `mypy src/calendar_service` 에러 0.

### 13.4 M_09 고유 DoD (MILESTONES L88~L96)

- [ ] `add_event(title, start, duration_minutes)`가 tz-naive 시 Asia/Seoul 가정.
- [ ] `get_events(start, end)`가 `start <= e.start < end` 반열린 구간.
- [ ] 정렬 `start ASC`.
- [ ] `events_due_within(10)`이 이미 지난 이벤트 제외.
- [ ] SQLite 파일 없을 때 자동 생성, `PRAGMA user_version` 기반 번호 비교 마이그레이션.
- [ ] 1만건 데이터에서 `get_events(1일 범위)` 50 ms 이하 (smoke 로그에 수치 기록).

### 13.5 무결성

- [ ] upstream `Open-LLM-VTuber/**` git diff 빈 상태 (수정 0건).
- [ ] 새 외부 의존성 0건. `pyproject.toml`에 추가 항목 없음.
- [ ] 네트워크 호출 0건 (`grep -r "requests\|httpx\|urllib\|fetch" src/calendar_service` → 0).

### 13.6 배선 범위 결정 (본 범위 포함)

- [ ] `src/app/service_context.py`의 `load_app_services`에 `CalendarService(db_path=app_config.data_dir/"calendar.db")` 주입 1줄 추가. 실패 시 `logger.warning` + `self.calendar_service = None`. **본 M_09 범위에 포함**한다(별도 CR로 분리하지 않는다) — 근거: ToolRouter 조립이 `calendar=self.calendar_service`를 요구하며(`service_context.py:225`), 배선 없이는 M_05b tool_router의 `add_event/get_events`가 작동 불가. 1줄 배선을 별도 CR로 분리하면 M_09 완료 판정 직후 ToolRouter 회귀를 일으킬 수 있다.
- [ ] `tests/app/test_service_context.py`에 CalendarService 주입 회귀 테스트 1건 추가. 실제 DB 생성은 하지 않고 `unittest.mock.patch("app.service_context.CalendarService")`로 생성자 호출 확인.

### 13.7 문서 동기화

- [ ] `docs/MODULES.md` M_09 블록의 상태를 `🔲 TODO` → `✅ DONE`.
- [ ] `docs/MODULES.md` M_09 공개 API 표기의 `async def` → `def` 정정 (§16 근거).
- [ ] `reviews/M_09_CalendarService_REVIEW.md`에 Critic PASS 기록.

---

## 14. 의존성

### 14.1 표준 라이브러리만

- `sqlite3` — 파일 DB.
- `datetime`, `timezone` — 시각 처리.
- `zoneinfo.ZoneInfo` (Python 3.9+) — Asia/Seoul. Windows에는 `tzdata` 휠이 필요할 수 있으나 본 프로젝트는 이미 `zoneinfo` 경로를 사용 중(`src/tool_router/router.py:11`). 추가 설치 없음.
- `threading.RLock` — 스레드 직렬화.
- `logging` — 표준 로거.
- `os`, `pathlib.Path` — 디렉토리 생성.
- `dataclasses` — `Event` frozen dataclass.
- `typing.Any` — `update_event` 키워드 인자.

### 14.2 의존성 추가 금지

- `python-dateutil` — MODULES.md L320 초안 언급이 있으나 **본 스펙은 불필요**로 확정. 자연어 파싱은 M_05 책임이고, 본 모듈은 tz-aware `datetime` 객체만 수용하므로 `zoneinfo` + `datetime`으로 충분.
- `aiosqlite` — §4.3 근거로 sync API 채택, 불필요.
- `freezegun` — §12.4 근거로 monkeypatch로 대체.
- `SQLAlchemy` / `peewee` — 본 모듈 복잡도에 비해 과잉.

### 14.3 테스트 의존성

- `pytest` (이미 있음).
- `pytest-cov` (이미 있음).
- 신규 의존성 0건.

---

## 15. 디렉토리 구조

```
src/calendar_service/
├── __init__.py          # from .service import CalendarService, Event
│                        # from .errors import (CalendarError, CalendarInitError,
│                        #                      CalendarValidationError,
│                        #                      CalendarDBError, EventNotFoundError)
├── service.py           # CalendarService, Event, _KST, _now_utc()
├── errors.py            # 에러 5종
└── migrations.py        # SCHEMA_V1_DDL, CURRENT_USER_VERSION=1

tests/calendar_service/
# `__init__.py` 생성 금지 — CR-06 정책(tests/tool_router shadowing 해결) 일관
├── conftest.py          # db_path fixture, now_utc_override fixture
├── test_service.py      # N1~N5, E1/E2/E5, A4
├── test_validation.py   # E3, E4, A1, A3
└── test_performance.py  # A2 @pytest.mark.slow
```

### 15.1 이름 충돌 주의

`src/calendar_service/`는 Python 표준 라이브러리 `calendar`와 패키지 이름이 충돌한다. 해결책:

- `src/` 아래는 프로젝트 루트 `sys.path`에 이미 `pyproject.toml` + `[tool.pytest.ini_options] pythonpath=["src"]` 설정으로 들어가 있다(기존 `src/tool_router` 등 패턴 확인).
- 표준 `calendar` 모듈을 쓰지 않으므로 실제 충돌은 발생하지 않는다. 다만 `from calendar import HTMLCalendar` 같은 임포트는 본 패키지를 먼저 찾게 된다 → 본 프로젝트에서 표준 `calendar`를 사용하지 않는 원칙을 유지.
- Critic이 의심할 경우 `tests/calendar_service/test_service.py` 맨 위에서 `import calendar_service as _project_calendar_package` 해서 충돌 없음을 회귀 확인 가능.

---

## 16. MODULES.md 갱신 필요 사항

본 스펙이 확정되면 M_09 builder가 `docs/MODULES.md` L292~L320을 다음과 같이 정정하여 **함께 커밋한다**(DoD §13.7 체크박스).

1. 상태: `🔲 TODO` → `✅ DONE`.
2. 공개 API의 `async def add_event` → `def add_event`. 마찬가지로 `get_events`, `get_event`, `update_event`, `delete_event`, `events_due_within` 모두 `def`로 정정.
3. 근거 각주 추가: "호출자(M_05b/M_11)가 `run_in_executor`로 sync 함수를 기대하며, SQLite 표준 라이브러리는 async를 지원하지 않으므로 sync API로 확정 (specs/M_09_CalendarService_SPEC.md §4.3)".
4. 의존 표기의 `python-dateutil`을 제거. `표준 sqlite3, datetime, zoneinfo`로 교체.
5. 중복 정책 표기를 "중복 허용(새 id 부여) + 경고 로그" 그대로 유지(본 스펙 §7.1에서 재확인).

---

## 17. 패키지명 결정 이력

패키지명 `calendar_service` 채택 근거: 표준 라이브러리 `calendar`(loguru 내부 `_datetime.py`가 `from calendar import day_abbr, day_name` 의존)와의 충돌 회피.
B안(`src/calendar/`) 기각 — conftest.py의 속성 복사 hack이 pytest 환경에서만 동작하며 프로덕션 FastAPI 기동 시 `ImportError` 유발. 기각 상세는 M_09 BLOCKER 수정 커밋 로그 참조.

`tests/calendar_service/__init__.py`는 생성하지 않는다. 이유: CR-06이 `tests/tool_router/__init__.py`가 유발하는 패키지 shadowing을 해결하기 위해 `tests/*/__init__.py` 전면 삭제 정책을 채택했으며 M_09도 동일 정책을 따른다.

---

## 18. 스펙 외 사항 (명시적 제외)

본 모듈의 책임이 **아닌** 것:

1. **자연어 날짜/시간 파싱** — M_05 LLMAgent + M_05b ToolRouter의 책임. ISO 8601 문자열로 도달해야 한다.
2. **반복 일정 / RRULE / iCalendar 파싱** — V1 범위 외. 향후 요구 시 CHANGE_REQUEST.
3. **알림 실제 송신** — M_11 ProactiveDispatcher.
4. **아침 브리핑 문장 생성** — M_11 + M_05.
5. **캘린더 공유 / 외부 동기화** — REQUIREMENTS.md §0 오프라인으로 영구 금지.
6. **사용자/권한 분리** — REQUIREMENTS.md §10 단일 사용자.
7. **타임존 전환 UI** — `default_tz`는 생성자 고정.
8. **이벤트 첨부파일, URL, 참석자 목록** — V1 범위 외.
9. **soft delete / audit log / undo** — V1은 하드 삭제.
10. **DB 백업·복원 자동화** — 운영 도구에 위임(Robocopy 등).
11. **`conf.yaml` 기반 설정 로딩** — `db_path`는 `AppServiceContext.load_app_services`가 `app_config.data_dir / "calendar.db"`로 주입. 본 모듈 자체는 YAML을 모른다.
12. **로거 이름과 포맷 표준화** — M_01이 정의한 프로젝트 로거를 `logging.getLogger(__name__)`로 가져다 쓸 뿐.

---
