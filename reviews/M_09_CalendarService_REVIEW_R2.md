# M_09 CalendarService — Critic 재검수 (R2)

## 판정: PASS

## 이전 라운드 MAJOR 해소 상태

| # | 이전 MAJOR | 수정 방식 | 실제 반영 위치 | 해소? |
|---|---|---|---|---|
| 1 | `tests/calendar_service/__init__.py` 생성 지시 정정 | 스펙 §13.1 체크박스 제거, §15 주석/§17 본문에 "생성하지 않는다" 명시, §7 `minutes` 제약 명문화 | `specs/M_09_CalendarService_SPEC.md:434-442`(체크박스 목록에서 `tests/calendar_service/__init__.py` 항목 삭제), `:525`(`# __init__.py 생성 금지 — CR-06 정책 일관`), `:559`("`tests/calendar_service/__init__.py`는 생성하지 않는다..."), `:266`(`events_due_within` `minutes` 제약 추가). 실 파일: `ls tests/calendar_service/__init__.py` → "No such file or directory" | ✅ |
| 2 | update/delete/events_due_within 에러 경로 3건 테스트 누락 | `TestErrorPaths` 3건 추가 | `tests/calendar_service/test_service.py:168-198` (`test_update_event_not_found_raises`, `test_delete_event_not_found_returns_false`, `test_events_due_within_nonpositive_raises`). 구현 보증: `src/calendar_service/service.py:405-407`(`EventNotFoundError(f"Event id={event_id} not found")`), `:474-479`(`rowcount > 0` False 반환), `:496-497`(`if not isinstance(minutes, int) or isinstance(minutes, bool) or minutes < 1: raise CalendarValidationError`) | ✅ |
| 3 | EXPLAIN QUERY PLAN 회귀 테스트 부재 | `TestIndexUsage` 1건 추가 | `tests/calendar_service/test_performance.py:30-59` (`test_get_events_uses_start_utc_index`). 별도 `sqlite3.connect(db_path)` 커넥션으로 구현 침범 회피. `"idx_events_start_utc" in plan_text` 부분 문자열 검증으로 SQLite 버전 차이에 robust. `@pytest.mark.slow` 미부착 → 기본 실행 포함 | ✅ |

## BLOCKER

없음.

## MAJOR (이번 라운드 신규)

없음.

## MINOR

### 이전 MINOR 7건 잔존 (CR-09 follow-up으로 기록)

- MINOR-1 잔존: `src/calendar_service/service.py:531` `except Exception as exc:  # noqa: BLE001` (close 내부 광범위 캐치).
- MINOR-2 잔존: `src/calendar_service/service.py:302` `id=event_id,  # type: ignore[arg-type]` (cursor.lastrowid None 미방어).
- MINOR-3 잔존: `src/calendar_service/service.py:330-331` `_validate_start(end)` 재사용으로 "start must be datetime" 오도 메시지.
- MINOR-4 잔존: `src/calendar_service/service.py:67-72` `_to_utc` 호출당 warning (get_events 호출 시 최대 2회).
- MINOR-5 잔존: emoji/4-byte UTF-8 title, 극단 datetime, `description=""` NULL 정규화 경계 테스트 공백.
- MINOR-6 잔존: `pyproject.toml:112-115` slow 마커 정의만, `addopts`에 `-m "not slow"` 없음.
- MINOR-7 잔존: `tests/app/test_service_context.py`의 `sys.modules` mock 패턴.

본 라운드 FAIL 사유로 삼지 않음(사용자 지시). CR-09로 일괄 처리 권고.

### 신규 MINOR 2건 (이번 라운드 도입)

- **NEW-MINOR-A**: `tests/calendar_service/test_performance.py:33-59` `test_get_events_uses_start_utc_index`는 **빈 DB**에서 EXPLAIN QUERY PLAN을 검증한다. 현 SQLite 3.x는 WHERE + 해당 컬럼 인덱스가 있으면 빈 테이블이어도 "SEARCH ... USING INDEX" 계획을 반환하므로 현 환경 PASS. 향후 SQLite이 "empty table short-circuit" 플랜을 도입하거나 ANALYZE 통계 기반 플래너 튜닝이 달라지면 플랜 텍스트가 바뀔 가능성 이론적으로 존재. 더 robust한 형태는 2~3건 `add_event` seed 후 EXPLAIN 실행. 현 테스트는 PASS이므로 MINOR.
- **NEW-MINOR-B**: `tests/calendar_service/test_service.py:181-187` `test_delete_event_not_found_returns_false`는 반환값(False)만 검증. "다른 행이 우연히 삭제되지 않음"을 확인하는 side-effect 검증은 없다. 예: 이벤트 1건 add → delete_event(999999) → 해당 이벤트가 여전히 `get_event(id)`로 조회되는지. 스펙 §10이 "반환값 False"만 계약하므로 규격 위반 아님.

## 테스트 실효성 평가 (신규 4건)

| 테스트 | 주장 | 실효성 근거 |
|---|---|---|
| `TestErrorPaths::test_update_event_not_found_raises` | 존재하지 않는 id → `EventNotFoundError` | 실제 `EventNotFoundError` 타입 검증 + 메시지 내 "999999" 또는 "not found" OR 조건으로 포맷 변화에 탄력적. `service.py:405-407` 구현과 1:1 매핑. 실효성 있음. |
| `TestErrorPaths::test_delete_event_not_found_returns_false` | 999999 삭제 → False 반환, 예외 아님 | `assert result is False`로 타입·값 동시 검증(`0`과 False 혼동 방지). side-effect 미검증은 NEW-MINOR-B. 실효성 있음. |
| `TestErrorPaths::test_events_due_within_nonpositive_raises` | minutes=0, -5 → `CalendarValidationError` | 두 값 모두 동일 테스트 내에서 각기 `pytest.raises` 블록으로 격리 검증. `service.py:496-497` `minutes < 1` 분기를 양쪽 경계(0, 음수)로 트리거. bool 필터(`isinstance(minutes, bool)`)는 미검증 — 스펙이 요구하지 않으나 구현에 존재하는 방어. MINOR 수준 갭. 실효성 있음. |
| `TestIndexUsage::test_get_events_uses_start_utc_index` | `get_events` SQL이 `idx_events_start_utc` 인덱스 사용 | 별도 `sqlite3.connect(db_path)` 커넥션으로 `CalendarService._conn` private 미침범. EXPLAIN QUERY PLAN `detail` 문자열 전체 공백 join 후 부분 문자열 매칭 → "USING INDEX" / "USING COVERING INDEX" / 기타 SQLite 포맷 변형 모두 커버. 단 빈 DB에서 실행하는 것이 약점(NEW-MINOR-A). 실효성 있음. |

## 검증 실행 결과

- **프로덕션 shadowing smoke**: PASS — `loguru`가 표준 `calendar.day_abbr[0]='Mon'` 정상 접근, `calendar_service` 패키지 로드 후에도 shadowing 없음.
- **upstream clean**: YES — `git status upstream/Open-LLM-VTuber/` → `nothing to commit, working tree clean`.
- **ruff format --check .**: PASS — `102 files already formatted`.
- **ruff check src/calendar_service tests/calendar_service src/app**: PASS — `All checks passed!`.
- **mypy src/calendar_service**: PASS — `Success: no issues found in 4 source files`.
- **pytest tests/calendar_service -v**: **29 passed in 1.45s** (25 기존 + 4 신규).
- **pytest tests/calendar_service tests/app tests/agent tests/tool_router tests/vad tests/asr tests/tts -q**: **380 passed, 3 skipped, 0 failed** in 11.21s.
- **3 skipped 내역**:
  1. `tests/app/test_service_context.py` `TestCR05ToolRouterAssembly::test_n2_tool_specs_length_and_names` — "tool_router import 실패 (환경 문제)" (CR-06 환경 격리 허용).
  2. `tests/vad/test_slow.py` — "Requires real silero-vad package installed".
  3. `tests/vad/test_upstream_integrity.py` — "silero_vad is mocked or not installed".
  → 사용자 기준 "CR-06 1건 + silero_vad 2건"과 정확 일치.
- **pyproject.toml calendar_service 관련 의존성 추가 0건** 재확인.

## 최종 판정

**M_09 CalendarService는 이전 라운드 MAJOR 3건이 모두 실효성 있게 해소되었다. DONE 선언 가능.**

- 신규 MAJOR 0건, 신규 MINOR 2건(NEW-MINOR-A/B: 테스트 robustness 보완 여지).
- 이전 MINOR 7건은 모두 잔존하나 사용자 지시대로 FAIL 사유 아님. CR-09로 일괄 follow-up.
- 정적 검사(ruff format·check, mypy), 단위 380 passed / 3 skipped / 0 failed, upstream clean, pyproject에 calendar_service 의존성 추가 0건, 프로덕션 shadowing smoke PASS.

**한 줄 요약: PASS — M_09 CalendarService MAJOR 3건 완전 해소, 전체 380 passed / 3 skipped / 0 failed, 신규 MAJOR 0건, 신규 MINOR 2건(테스트 robustness)만 CR-09 follow-up 권고.**
