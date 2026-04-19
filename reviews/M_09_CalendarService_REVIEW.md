# M_09 CalendarService — Critic 검수 결과

## 판정: PASS (조건부)

BLOCKER 0건, MAJOR 3건, MINOR 7건. M_09 재작업(패키지명 calendar→calendar_service) 및 CR-03 회귀 수정은 실효성 있게 해소되었고, 스펙 §13 DoD 24건 중 핵심 구현·성능·보안 관문은 모두 충족. 단, **§13.1 파일 체크박스 1건 미이행 (tests/calendar_service/__init__.py 부재)** 및 **§11.2 "EXPLAIN QUERY PLAN 회귀 테스트" 미구현**, **공개 API 7개 중 `delete_event`·`update_event`·`events_due_within(0)` 에러 경로 미커버**가 확인되어 "조건부"로 둔다. DoD 체크박스 정정과 최소 3건의 누락 테스트 추가 후 DONE 선언 가능.

---

## BLOCKER

없음 (프로덕션 shadowing smoke + 376 passed / 3 skipped + ruff·mypy PASS 확인).

---

## MAJOR

### MAJOR-1: DoD §13.1 "tests/calendar_service/__init__.py 빈 파일 명시 생성" 미이행
- **파일**: `tests/calendar_service/__init__.py` (존재하지 않음)
- **근거**: `specs/M_09_CalendarService_SPEC.md:438` — "`tests/calendar_service/__init__.py` — 빈 파일(명시적 생성, CR-06 테스트 수집 규약 고려)". 스펙 §15 디렉토리 구조에도 명시.
- 실제 tests/app, tests/asr, tests/vad, tests/tts, tests/agent, tests/tool_router 전부 `__init__.py`를 갖추고 있는 것과 비교해 일관성이 깨졌다.
- 현재 `addopts = "--import-mode=importlib"` 덕분에 pytest collection은 성공하나, 스펙이 요구한 CR-06 "테스트 패키지 shadowing 해결" 규약을 본 모듈만 이탈한 상태.
- **권고 조치**: `touch tests/calendar_service/__init__.py` 로 빈 파일 생성 후 DoD §13.1 체크박스 확인.

### MAJOR-2: `update_event` / `delete_event` / `events_due_within` 에러 경로가 테스트 0건
- **파일**: `tests/calendar_service/**` 전체
- **근거**:
  - 스펙 §1.2는 7개 공개 메서드 중 `update_event` / `delete_event` 를 포함. 스펙 §10 에러 정책 표는 `EventNotFoundError`(update 미존재), `delete_event` False 반환, `events_due_within(minutes<=0)` → `CalendarValidationError`를 명시.
  - `grep -rn "EventNotFoundError\|delete_event\|events_due_within.*0\|events_due_within.*-1" tests/calendar_service/` 결과: 0건(E5의 `update_event`는 start 필드 변경만 호출, EventNotFoundError 미검증).
  - `test_validation.py::TestAdversarialInputs` 에 `minutes=0 → CalendarValidationError` 테스트가 **없다**.
- 공개 API 3개의 주요 에러 경로가 전혀 고정되지 않음 → 추후 리팩토링 시 회귀가 발견되지 못할 위험.
- **권고 조치**: 최소 3건 추가.
  1. `test_update_event_not_found` — `update_event(event_id=99999, title="x")` → `EventNotFoundError`.
  2. `test_delete_event_returns_false_when_missing` — `delete_event(99999)` → `False`, 다른 이벤트 영향 없음 확인.
  3. `test_events_due_within_zero_raises` / `negative_raises` — `events_due_within(0)` / `events_due_within(-1)` → `CalendarValidationError`.

### MAJOR-3: 스펙 §11.2 "EXPLAIN QUERY PLAN에 USING INDEX 포함 회귀 테스트" 미구현
- **파일**: `tests/calendar_service/**` (해당 테스트 없음)
- **근거**: `specs/M_09_CalendarService_SPEC.md:383` — "`EXPLAIN QUERY PLAN` 출력에 `USING INDEX idx_events_start_utc` 포함을 회귀 테스트로 확인". 이 테스트는 p95 ≤ 50 ms 성능 보장의 근거 지표다.
- 현재 성능 smoke(p95=0.04 ms)가 통과하지만, 미래 V2 마이그레이션에서 인덱스 drop/rename이 발생하면 p95는 서서히 저하되어도 임계 50 ms를 당장 넘지 않을 수 있다. EXPLAIN 회귀 테스트가 없으면 "인덱스 미사용"을 조기 검출할 수 없다.
- **권고 조치**:
  ```python
  def test_get_events_uses_index(svc):
      conn = svc._conn
      rows = conn.execute(
          "EXPLAIN QUERY PLAN SELECT * FROM events WHERE start_utc >= ? AND start_utc < ?",
          ("2026-04-01T00:00:00+00:00", "2026-04-02T00:00:00+00:00"),
      ).fetchall()
      plan = " ".join(str(r["detail"]) for r in rows)
      assert "idx_events_start_utc" in plan
  ```
  스펙에 명시된 관찰 가능 행동이므로 MAJOR로 승격.

---

## MINOR

- **MINOR-1**: `src/calendar_service/service.py:211` `except Exception as exc:` 광범위 캐치. 스펙 §10 표는 `CalendarInitError` 만 기재. `except CalendarInitError` 로 좁혀야 `AttributeError: app_config.paths` 같은 설정 버그가 silent fail로 숨지 않는다. (유사 패턴이 `ScreenshotInitError`에서는 좁혀져 있어 일관성도 깨짐.)
- **MINOR-2**: `src/calendar_service/service.py:302` `id=event_id,  # type: ignore[arg-type]` — `cursor.lastrowid`는 `int | None`이고, 런타임에 None이면 `Event.id=None`이 frozen dataclass로 봉인되어 버린다. `assert event_id is not None, "INSERT returned no rowid"` 로 방어하는 게 정석.
- **MINOR-3**: `src/calendar_service/service.py:330-331` `get_events(start, end)`에서 `end`가 datetime이 아닐 때 `_validate_start(end)` 가 "start must be datetime" 메시지를 낸다. 호출자가 어느 인자가 문제인지 모호. 전용 `_validate_datetime(dt, field_name)` 도입 권장.
- **MINOR-4**: `src/calendar_service/service.py:68-72` `_to_utc`가 naive 입력마다 `logger.warning` 발생. `get_events`에서 start/end 둘 다 naive면 2번 로깅. 스펙 §6.1 "호출당 1회" 해석이 "메서드 호출당 1회"라면 위반 가능. 메서드 레벨에서 1회로 합치거나 스펙에 명시 필요.
- **MINOR-5**: 경계/적대 테스트 누락 — emoji/4-byte UTF-8 title, 3000-01-01 / 1900-01-01 극단 datetime, `description=""` → NULL 정규화 검증(스펙 §7에 명시된 contract). 스펙 §12가 요구한 최소치(정상/엣지/적대 = 5/5/3)는 충족하나 실효성 관점에서 공백.
- **MINOR-6**: `pyproject.toml`에 slow 마커가 정의되어 있으나 `addopts`에 `-m "not slow"` 기본 제외가 없어, 성능 테스트가 기본 pytest 실행에서 1분 가까이 seed 후 실행된다(본 환경은 10k INSERT가 빠르지만 Windows 네이티브 환경에서는 WAL checkpoint로 지연 가능). 스펙 §12.1 test docstring이 "기본 pytest 실행에서는 제외"를 약속하나 설정은 이를 강제하지 않음.
- **MINOR-7**: `tests/app/test_service_context.py:244-251`의 M_09 회귀 테스트가 `sys.modules`에 `calendar_service`, `calendar_service.service`, `calendar_service.errors` 를 모두 `MagicMock`으로 덮어쓴다. 실제 `CalendarService`가 아닌 mock 클래스의 생성자 호출만 검증하므로, 본 테스트가 증명하는 건 "load_app_services가 `calendar_service.service.CalendarService` 심볼을 경로 인자로 1회 호출한다"뿐. DoD §13.6 요구("생성자 호출 확인")는 충족하나, 실제 DB 파일 경로 주입이 의도대로 동작하는지는 M_09 자체 conftest의 smoke에서만 확인됨. 통합 테스트 가치는 제한적.

---

## 스펙 vs 구현 매핑 (§13 DoD 전수)

### §13.1 파일 생성 (9개)
| # | DoD 항목 | 구현/테스트 위치 | 상태 |
|---|---|---|---|
| 1 | `specs/M_09_CalendarService_SPEC.md` 사용자 승인 | specs/M_09_CalendarService_SPEC.md | ✅ |
| 2 | `src/calendar_service/__init__.py` — 심볼 re-export | src/calendar_service/__init__.py:1-23 | ✅ |
| 3 | `src/calendar_service/service.py` — CalendarService, Event | src/calendar_service/service.py:140-534 | ✅ |
| 4 | `src/calendar_service/errors.py` — 에러 5종 | src/calendar_service/errors.py:7-30 | ✅ |
| 5 | `src/calendar_service/migrations.py` — SCHEMA_V1_DDL + CURRENT_USER_VERSION | src/calendar_service/migrations.py:10-22 | ✅ |
| 6 | `tests/calendar_service/__init__.py` — 빈 파일 | (없음) | ❌ **MAJOR-1** |
| 7 | `tests/calendar_service/conftest.py` | tests/calendar_service/conftest.py:1-34 | ✅ |
| 8 | `tests/calendar_service/test_service.py` | tests/calendar_service/test_service.py:1-193 | ✅ |
| 9 | `tests/calendar_service/test_validation.py` | tests/calendar_service/test_validation.py:1-158 | ✅ |
| 9b| `tests/calendar_service/test_performance.py` | tests/calendar_service/test_performance.py:1-89 | ✅ |

### §13.2 테스트 개수·실행
| # | DoD 항목 | 위치 | 상태 |
|---|---|---|---|
| 10 | 정상 ≥ 5 | test_service.py::TestNormal N1~N5 | ✅ (5건) |
| 11 | 엣지 ≥ 5 | E1, E2, E5 + E3(4변형) + E4(4변형) → 11건 | ✅ |
| 12 | 적대적 ≥ 3 | A1, A3(6변형), A4, A2(perf) | ✅ (9건) |
| 13 | `pytest tests/calendar_service` PASS | 25 passed (perf 포함) | ✅ |
| 14 | 1만건 성능 smoke PASS (p95 ≤ 50 ms 로깅) | p95=0.04 ms 측정, logger 기록 | ✅ |

### §13.3 린트·타입·포맷
| # | DoD 항목 | 결과 | 상태 |
|---|---|---|---|
| 15 | ruff format 무변경 | "102 files already formatted" | ✅ |
| 16 | ruff check 위반 0 | "All checks passed!" | ✅ |
| 17 | mypy src/calendar_service 에러 0 | "Success: no issues found in 4 source files" | ✅ |

### §13.4 M_09 고유 DoD (MILESTONES L88~L96)
| # | DoD 항목 | 위치 | 상태 |
|---|---|---|---|
| 18 | tz-naive 시 Asia/Seoul 가정 | service.py:67-72 _to_utc, test_service.py:119 E1 | ✅ |
| 19 | `[start, end)` 반열린 구간 | service.py:347 `start_utc >= ? AND start_utc < ?`, test_e2 | ✅ |
| 20 | start ASC 정렬 | service.py:348 `ORDER BY start_utc ASC`, test_n2/e5 | ✅ |
| 21 | events_due_within 지난 이벤트 제외 | service.py:502 `now_utc` 기준, test_n3 | ✅ |
| 22 | DB 파일 자동 생성 + user_version 마이그 | service.py:169, 195-210 | ⚠ 자동 생성·user_version 비교 모두 **테스트 없음**. 코드는 있음. |
| 23 | 1만건 p95 ≤ 50 ms (수치 로깅) | test_performance.py:79, 측정 p95=0.04 ms | ✅ |

### §13.5 무결성
| # | DoD 항목 | 결과 | 상태 |
|---|---|---|---|
| 24 | upstream git diff 0 | `git status upstream/...`: clean | ✅ |
| 25 | pyproject 새 의존성 0 | 1bf2cad와의 diff: calendar 관련 추가 없음 | ✅ |
| 26 | 네트워크 호출 0 | grep requests/httpx/urllib/fetch: 0건 (fetchone/all만 일치) | ✅ |

### §13.6 배선
| # | DoD 항목 | 위치 | 상태 |
|---|---|---|---|
| 27 | service_context.py 주입 1줄 | service_context.py:205-213 | ✅ (단 `except Exception` MINOR-1) |
| 28 | 회귀 테스트 1건 | test_service_context.py:209-256 TestM09... | ✅ (MINOR-7 고려) |

### §13.7 문서 동기화
| # | DoD 항목 | 위치 | 상태 |
|---|---|---|---|
| 29 | MODULES.md M_09 ✅ DONE | docs/MODULES.md:295, 411 | ✅ |
| 30 | MODULES.md async→def 정정 | docs/MODULES.md:308-319 | ✅ |
| 31 | reviews/M_09_*.md Critic PASS 기록 | 본 파일 | ✅ (본 판정 적용 후) |

**§11.2 추가 요구 (DoD 표 외)**:
| EXPLAIN QUERY PLAN 회귀 테스트 | (없음) | ❌ **MAJOR-3** |

---

## 테스트 커버 검증 (실측 25건)

### 스펙 §12 매핑
| 스펙 케이스 | 구현 테스트 | 상태 |
|---|---|---|
| N1 add/get round-trip | test_n1_add_get_round_trip | ✅ |
| N2 get_events 범위 필터 | test_n2_get_events_range_filter | ✅ |
| N3 events_due_within 정확 매치 | test_n3_events_due_within_exact_match | ✅ (monkeypatch `_now_utc`) |
| N4 events_due_within 0건 | test_n4_events_due_within_empty | ✅ |
| N5 close 멱등 | test_n5_close_idempotent | ✅ |
| E1 tz-naive 입력 | test_e1_naive_datetime_assumed_kst | ✅ (값 일치 검증은 약함, MINOR) |
| E2 start==end | test_e2_start_equals_end_returns_empty | ✅ |
| E3 duration 경계 | test_e3_duration_{1,1440,0,1441}_* (4건) | ✅ |
| E4 title 길이 경계 | test_e4_title_{1,500,empty,501}_* (4건) | ✅ |
| E5 update 후 재정렬 | test_e5_update_start_reorders | ✅ |
| A1 SQL 인젝션 | test_a1_sql_injection_in_title | ✅ |
| A2 1만건 성능 | test_a2_get_events_p95 @slow, p95=0.04ms | ✅ |
| A3 적대적 입력 폭격 | test_a3_* (6건) | ✅ |
| A4 close 이후 사용 | test_a4_use_after_close | ✅ |

### 스펙 §10 에러 경로 매핑 (MAJOR-2)
| 에러 경로 | 테스트 | 상태 |
|---|---|---|
| EventNotFoundError (update) | — | ❌ |
| delete_event False 반환 | — | ❌ |
| events_due_within(minutes<=0) | — | ❌ |
| CalendarInitError (디렉토리/권한/user_version) | — | ❌ (코드만 있음) |
| DBError (close 이후 호출) | test_a4_use_after_close | ✅ |

---

## 빌더가 추가한 부수 변경 평가

### 1. conftest.py hack 제거 (M_09 재작업)
- 최상위 `conftest.py:1-126`에 이전 `calendar` 속성 복사 hack L113~L166 블록은 **남아있지 않다**. 대신 app/vad/asr/tts 각각에 대해 `importlib.util.spec_from_file_location` 으로 `sys.modules` 사전 등록(L68~L126) — 동일 패턴을 일관되게 4회 사용. `calendar_service`는 표준 lib와 이름이 다르므로 동일 hack 불필요. **적절.**

### 2. tests/calendar/ → tests/calendar_service/ 이동
- `tests/calendar/` 디렉토리 비존재 확인. 테스트 파일 모두 `tests/calendar_service/`에 존재. `from calendar_service.service import ...` 일관 사용. **적절.**

### 3. VAD 테스트 5건 수정 (CR-03 회귀 해소)
- `tests/vad/test_factory.py:170-183` + `tests/vad/test_wiring.py:62/112/175/294`에 `app_config.paths.calendar_db_path = str(tmp_path/"test.db")` + `patch.dict(sys.modules, {"tool_router": _make_tool_router_mock()})` + `await ctx.load_app_services(app_config)` 추가.
- **계약 우회 위험 평가**:
  - VAD 테스트가 이제 load_app_services를 호출 → CalendarService/ScreenshotService/ToolRouter 초기화를 수반. 이는 CR-03 `init_agent` 오버라이드가 `app_config is None`일 때 `AgentInitError`를 raise하는 조건(`service_context.py:142-146`)을 만족시키기 위한 **필수** 전처리. VAD 단위 테스트가 "부분 통합 테스트"로 확장된 것은 사실이나, CR-03이 요구한 "load_app_services → load_from_config" 순서 계약을 테스트가 준수하는 것이므로 **계약 우회가 아니라 계약 준수**.
  - ScreenshotService는 `_FakeSSInitError` side_effect로 비-Windows 경로로 강제 → `tool_router=None` degraded 모드. 각 VAD 테스트는 init_vad 자체에 집중하고 init_agent는 `_noop_agent`로 완전 대체(`patch("app.service_context.AppServiceContext.init_agent", new=_noop_agent)`). MRO 관점에서 서브클래스 `init_agent`를 패치하는 것이 정합(upstream `ServiceContext.init_agent` 패치 시 AppServiceContext.init_agent가 먼저 호출되어 우회 불가).
  - ScreenshotService 실패 → ToolRouter 미조립 → init_agent가 tool_router_adapter=None 경로로 진입 → 정상 동작(`service_context.py:167-172`). 각 VAD 테스트는 이 경로를 **명시적으로 의도하고** `_noop_agent`로 실제 init_agent 실행 자체를 건너뛰므로 경로 커버 부담 없음.
  - **종합**: 적절한 회귀 수정. 테스트 의도 변질 없음.

### 4. MODULES.md / SPEC 편집
- MODULES.md M_09 블록: ✅ DONE 표기, `async def` → `def` 정정(L308-318), 의존성 `python-dateutil` 제거 후 `sqlite3, datetime, zoneinfo` 표기 — 스펙 §16 요구 모두 반영.
- SPEC §13.1 "builder가 재작업해 src/calendar_service/ 로 리네임"을 §17 "패키지명 결정 이력"에 기록 — 추적 가능성 확보.

---

## 검증 실행 결과

### 1. upstream 무결성
```
$ git status upstream/Open-LLM-VTuber/
On branch master
nothing to commit, working tree clean
```
→ **PASS** (수정 0건, DoD §13.5 24번).

### 2. ruff format --check .
```
102 files already formatted
```
→ **PASS**.

### 3. ruff check src/calendar_service tests/calendar_service src/app tests/app tests/agent tests/tool_router
```
All checks passed!
```
→ **PASS**.

### 4. mypy src/calendar_service
```
Success: no issues found in 4 source files
```
→ **PASS**.

### 5. mypy src/app (--explicit-package-bases)
```
src/app/service_context.py:101: error: Unused "type: ignore" comment  [unused-ignore]
src/app/service_context.py:115: error: Unused "type: ignore" comment  [unused-ignore]
src/app/service_context.py:132: error: Cannot determine type of "agent_engine"  [has-type]
src/app/service_context.py:154: error: Cannot determine type of "tool_executor"  [has-type]
Found 4 errors in 1 file (checked 10 source files)
```
→ 4건 모두 CR-03/CR-05 기존 이슈 (M_09 주입 블록 L205-213 관련 오류 없음). **M_09 신규 오류 0건**.

### 6. pytest tests/calendar_service (25건)
```
25 passed in 1.20s
```
→ **PASS** (perf 포함; p95=0.04 ms).

### 7. pytest tests/{calendar_service,app,agent,tool_router,vad,asr,tts} -q
```
376 passed, 3 skipped, 6 warnings in 13.00s
```
- 3 skipped 내역(`-rs` 실행 결과):
  - `tests/app/test_service_context.py:311` — `TestCR05ToolRouterAssembly::test_n2_tool_specs_length_and_names` (CR-06 환경 격리 이슈, 사용자 허용 목록).
  - `tests/vad/test_slow.py:40` — `Requires real silero-vad package installed` (환경 의존 allowed).
  - `tests/vad/test_upstream_integrity.py:175` — `silero_vad is mocked` (환경 의존 allowed).
- → 사용자 "3 skipped" 허용 기준과 일치.

### 8. 프로덕션 shadowing smoke (사용자 제공 스크립트)
```
2026-04-19 09:37:40.243 | INFO     | __main__:<module>:7 - startup smoke OK
calendar.day_abbr: Mon
calendar.timegm: 1767225600
```
→ **PASS** (calendar_service 패키지 로드 후에도 표준 `calendar` + loguru 정상).

### 9. 패키지명 오염 검증
```
$ grep -rn "^from calendar " src/ tests/   # 0 hits
$ grep -rn "^import calendar$\|^import calendar " src/ tests/   # 0 hits
$ grep -n "calendar" conftest.py   # 0 hits (복원성 확인)
```
→ **PASS**. 루트 `conftest.py`에 M_09 hack 잔재 없음.

---

## CR-03 회귀 해소 여부

**결론: 회귀 해소됨, 테스트 의도 변질 없음.**

- 근거:
  1. CR-03 `init_agent` 오버라이드(`src/app/service_context.py:115-195`)가 `app_config is None`일 때 `AgentInitError`를 raise하는 contract는 여전히 유효.
  2. VAD 테스트 5건은 이를 준수하기 위해 `AppConfig()` + `paths.calendar_db_path` 세팅 + `load_app_services(app_config)` 선행 호출로 CR-03 contract를 존중한다.
  3. 각 테스트는 `patch("app.service_context.AppServiceContext.init_agent", new=_noop_agent)` 로 서브클래스 메서드를 직접 교체 → upstream `ServiceContext.init_agent` 패치만으로는 MRO상 AppServiceContext 구현이 먼저 호출되어 우회 불가하기에 **서브클래스 패치가 정합**(CR-03 MRO 디스패치 리뷰와 일치).
  4. ScreenshotService의 비-Windows 실패는 `tool_router=None` degraded 경로로 빠지고, 각 테스트는 `_noop_agent`로 init_agent 실행을 완전 대체하므로 degraded 경로의 build_chat_agent 호출 부담 없음. VAD 단위 테스트의 목적은 VAD 래핑이지 Agent 조립이 아니므로 범위 일탈 없음.
- 종합: 5건 수정은 회귀를 해소하는 최소 침습 패치. 더 우아한 해법(예: `load_app_services`를 mock 처리)도 가능하나 현재 구현이 CR-03 contract를 우회하지 않으므로 수용 가능.

---

## 검토하지 못한 영역

- **Windows 환경 실측**: 본 검토는 Linux WSL에서 수행. Windows 네이티브(FastAPI + loguru)에서의 `calendar` 표준 lib 동시 import 검증은 smoke script 모의로만 가능. 실제 배포 검증은 Validator/Integrator 단계 필수.
- **CR-03 이외 init_agent 패치 경로**: VAD 테스트가 AppServiceContext.init_agent를 mock하지만, 다른 경로(ASR·TTS 테스트)에서 동일 문제가 재발하는지는 본 리뷰 범위 밖(사용자 제공 스코프는 VAD 5건).
- **SQLite WAL 파일 정합성 (crash-safe)**: `close()` 가 `PRAGMA wal_checkpoint(FULL)`을 수행하나, SIGKILL로 강제 종료될 때 WAL 복구 테스트는 없음. 스펙 §9가 요구하지 않으므로 범위 외.
- **cursor.lastrowid None 경로**: INSERT 후 None 반환 시나리오는 rowid table에서 발생하지 않지만, 방어 코드 부재는 MINOR-2로 기재.
- **ServiceContext.close → _call_close → calendar_service.close 실제 라이프사이클**: 현재 tests/app/test_service_context.py::TestAppServiceContextClose::test_close_calls_all_services가 mock으로 5단계 순서를 검증. 실제 CalendarService.close() 호출 후 DB 파일 검증(체크포인트)은 없음.

---

## 최종 의견 (요약)

M_09 CalendarService 구현·성능·shadowing 복구·CR-03 회귀 수정은 실효성 있게 완료. 핵심 계약(UTC 저장·KST 반환·반열린 구간·p95≤50ms·threading RLock·close 멱등)은 코드와 테스트로 모두 확인됨. 그러나 **`tests/calendar_service/__init__.py` 미생성(MAJOR-1)**, **update/delete/events_due_within 에러 경로 테스트 0건(MAJOR-2)**, **EXPLAIN QUERY PLAN 회귀 테스트 부재(MAJOR-3)** 3건이 스펙 §13/§11 DoD에 명시된 항목이므로 조건부 PASS. 위 3건을 최소 보완 후 DONE 선언 권장. MAJOR 3건이 해소되지 않은 채 다음 모듈로 이행 시, 본 리뷰가 예측한 회귀 감지 공백이 향후 비용으로 누적될 위험이 있다.

**한 줄 요약 판정: PASS (조건부) — DoD §13.1 누락 1건 + 누락 테스트 3종 보완 필요.**
