# M_11 ProactiveDispatcher — MINOR Coverage Review

- 리뷰어: Critic (fresh)
- 대상: tests/proactive/test_minor_coverage.py (신규), src/proactive/dispatcher.py (비변경 전제)
- 판정: PASS
- 날짜: 2026-04-21

---

## 1. 독립 검증 결과

### 1.1 소스 불변 확인

```
$ git status --porcelain
?? specs/M_12_Frontend_SPEC.md
?? tests/proactive/test_minor_coverage.py
```

- `src/proactive/**`에 수정·추가 없음. 전제 충족.
- 추적되지 않는 M_12 스펙 파일은 본 리뷰 범위 외(테스트 파일 1건이 유일한 이번 변경).

### 1.2 pytest (전체 proactive)

```
tests/proactive/test_minor_coverage.py::TestStopIdleMonitorExceptionSwallowed::test_stop_swallows_on_event_none_exception PASSED
tests/proactive/test_minor_coverage.py::TestStopIdleMonitorExceptionSwallowed::test_stop_idempotent_after_exception PASSED
tests/proactive/test_minor_coverage.py::TestMinutesUntilTzNaive::test_tz_naive_treated_as_utc PASSED
tests/proactive/test_minor_coverage.py::TestMinutesUntilTzNaive::test_tz_naive_past_returns_zero PASSED
tests/proactive/test_minor_coverage.py::TestMinutesUntilTzNaive::test_tz_aware_and_naive_same_utc_moment_agree PASSED
tests/proactive/test_minor_coverage.py::TestMinutesUntilTzNaive::test_tz_naive_zero_delta_returns_zero PASSED
============================== 59 passed in 0.71s ==============================
```

- 기존 53건 + 신규 6건 = 총 59건 전부 PASS. 회귀 없음.

### 1.3 coverage

```
Name                          Stmts   Miss  Cover   Missing
src/proactive/dispatcher.py     200     16    92%   146-157, 322, 423-424, 436, 443-444, 446, 448
```

- **L200-L206(stop의 on_event try/except)**: missing 목록에서 **제거됨** → 커버 확인 (이전 R3: 202-203 miss).
- **L385-L392(_minutes_until tz-naive 가드)**: missing 목록에서 **제거됨** → 커버 확인 (이전 R3: 390 miss).
- 남은 miss는 이번 backlog와 무관(APScheduler import 실패 fallback 146-157, 빈 이벤트 early return 322, cleanup 예외 423-424, _parse_morning_time 비문자열/경계 분기 436·443-446·448).
- 모듈 단독 커버리지 92% ≥ 70%(§12.1 DoD) 여전히 만족.

### 1.4 ruff / mypy

```
$ ruff check tests/proactive/test_minor_coverage.py
All checks passed!

$ ruff format --check tests/proactive/test_minor_coverage.py
1 file already formatted

$ mypy tests/proactive/test_minor_coverage.py
Success: no issues found in 1 source file
```

- 전체 tests/proactive/ mypy 실행 시 13 errors 모두 기존 파일(test_dispatcher.py, test_cooldown_dnd.py) 유래의 pre-existing unused-ignore. 신규 파일 test_minor_coverage.py는 0 errors.
- `# type: ignore[misc]`(L30)는 단일 파일 mypy 실행에서는 실제로 필요한 억제(`FakeIdleMonitor`가 import 해석상 `Any`로 보일 때의 `subclass-of-Any` 경고)이며, 디렉터리 전체 실행에서도 "unused-ignore" 경고가 발생하지 않음을 확인.

---

## 2. 체크리스트 심사

| # | 항목 | 판정 | 근거 |
|---|---|---|---|
| 1 | L200-L203 실제 실행 | OK | coverage missing 목록에서 제거 + `BrokenOnEventIdleMonitor(raise_on=None)`이 `on_event(None)`에서만 RuntimeError를 던져 try/except 분기 실행(test L88-99). |
| 2 | L385-L392 실제 실행 | OK | `_minutes_until`에 `(now_utc + 30min).replace(tzinfo=None)`을 주입해 `start.tzinfo is None` 가드 진입(test L126-138). |
| 3 | tz-naive 테스트 flakiness | OK | `assert 28 <= minutes <= 30` — `datetime.now(timezone.utc)`는 테스트 호출과 내부 호출 사이 드리프트 ≪ 60s 보장. 과거/영점/aware-비교 케이스는 `max(0, ...)` 또는 ±1 tolerance로 경계 안전. |
| 4 | BrokenOnEventIdleMonitor 시그니처 | OK | `on_event(self, callback: Any) -> None` — `FakeIdleMonitor.on_event`, `ProactiveDispatcher._idle_monitor.on_event(None)`·`on_event(self._on_idle_event)` 모두와 호환. |
| 5 | on_event 호출 횟수 검증 | OK | start에서 1회(raise 없음 — callback is not None), stop에서 1회(raise — callback is None)로 count=2 assertion 정확. |
| 6 | `_started` 접근(화이트박스) | ALLOW | 기존 test_dispatcher.py:636·642·648·664에서 이미 `_started`/`_callback` 직접 접근하는 화이트박스 패턴 사용 중. 일관. |
| 7 | stop 멱등성 검증 | OK | 2차 stop()은 `if not self._started: return`로 조기반환(L191-192) → on_event 재호출 없음 → count 유지(==2). 검증 맞음. |
| 8 | N/E/A 네이밍 규약 충돌 | ACCEPTABLE | 별도 파일·서술형 클래스명. 모듈 docstring이 MINOR backlog 커버리지 명시로 근거 충분. test_dispatcher.py 내 `TestErrorBranches`와 역할·이름이 겹치지 않음. |
| 9 | `# type: ignore[misc]` 정당성 | OK | 검증: 제거 시 `Class cannot subclass "FakeIdleMonitor" (has type "Any")`. 억제 필요. typing.cast·Protocol은 subclass 용도로 부적절. |
| 10 | 스펙 외 거동 가정 | OK | "예외 삼킴 후 dispatcher 재사용 가능"이라는 과잉 주장 없음. 단지 stop 완료(_started=False)와 멱등 재호출만 검증 — 스펙 §5(멱등 stop) 범위 내. |
| 11 | CancelledError 케이스 | N/A | 스펙 §10은 `except Exception`으로만 삼키도록 명시 → `BaseException`/`CancelledError` 전파가 의도된 동작. 이번 backlog는 "기존 except 분기 커버"가 목적이므로 별도 적대 케이스 불요. |
| 12 | 테스트 격리성 | OK | 각 테스트가 `_make_dispatcher` 로컬 헬퍼로 독립 인스턴스 생성. 모듈 스코프 상태 없음. |
| 13 | 소스 침해 여부 | OK | `git status`에 `src/proactive/**` 변경 없음. |
| 14 | 기존 스타일(import, format) | OK | `from __future__ import annotations`, `ruff format` 통과, conftest/fakes 재사용. |
| 15 | 네트워크 호출 | NONE | 외부 호출 없음 — CLAUDE.md §절대금지 위반 아님. |

### 스펙 vs 테스트 매핑

| 스펙/backlog 항목 | 테스트 | 상태 |
|---|---|---|
| dispatcher.py L202-203 coverage (MODULES.md L384) | test_stop_swallows_on_event_none_exception | OK |
| 위 분기의 멱등 재호출 | test_stop_idempotent_after_exception | OK |
| dispatcher.py L390 tz-naive 분기 coverage (MODULES.md L385) | test_tz_naive_treated_as_utc | OK |
| tz-naive + 과거 경계 | test_tz_naive_past_returns_zero | OK |
| tz-naive + aware 등가성 | test_tz_aware_and_naive_same_utc_moment_agree | OK |
| tz-naive + 영점 | test_tz_naive_zero_delta_returns_zero | OK |

---

## 3. 결함 목록

### CRITICAL
없음.

### MAJOR
없음.

### MINOR
1. **[MINOR]** `# type: ignore[misc]` (L30) 의 근거 주석이 없어 후속 정리 시 "unused-ignore"로 오인될 수 있음. 디렉터리 전체 mypy 모드에서는 사실상 무효 억제처럼 보이지만, 단일 파일 mypy에서는 필요. 짧은 근거 주석(e.g. "single-file mypy sees FakeIdleMonitor as Any via ignore_missing_imports") 1줄이 있었다면 완전했음. 스펙/규약 위반은 아님.
2. **[MINOR]** `@pytest.mark.timeout(5)` 누락(§11.4 권고). 단, 기존 test_dispatcher.py 전 테스트가 이미 동일하게 누락 → 일관성 유지이며 이 PR 범위 외 문제.

두 항목 모두 회귀 위험 없음. FAIL 사유 아님.

---

## 4. 최종 판정

**PASS.**

- 타겟 분기 2종(L200-L203, L385-L392) 모두 실행·커버 확인.
- 소스 불변, 회귀 0건, lint/format/mypy 청정.
- MINOR 2건은 기록 목적이며 차단 사유 아님.

### 후속 조치(지시)

- `docs/MODULES.md` L383-L385의 "잔여 MINOR (backlog)" 블록(3줄: L383 헤더 + L384·L385 두 bullet)을 제거하고, 상태 행(L382)에 "R4 MINOR backlog 해소 2026-04-21" 한 줄을 추가하라. 편집 주체는 본 Critic이 아니며, M_11 오너가 별도 커밋으로 처리한다.
