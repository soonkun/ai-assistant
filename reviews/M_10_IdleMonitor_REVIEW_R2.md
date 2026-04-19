# M_10 IdleMonitor Critic Review — Round 2

Date: 2026-04-19
Verdict: **PASS**
Previous verdict: FAIL (reviews/M_10_IdleMonitor_REVIEW.md)

## Summary

Round 1 Blocking 3건(B1 A-1 우회, B2 A-2 우회, B3 AppConfig 배선 누락)이 모두
실제 코드에서 해소되었다. 구현·테스트·배선·YAML fixture·pyproject·bundle_deps·lint·mypy
·전체 테스트 스위트(556 passed / 6 skipped) 모두 일관되어 있고, mutation test로
회귀 검출 능력까지 확인했다. 스펙 §4~§16 전 영역을 앵커링 없이 다시 훑은 결과
신규 Blocking 없음. Non-blocking 관찰 사항만 아래에 기록한다.

---

## Previous Findings Re-verified

### B1 (A-1 우회 → 실제 폴백 체인 검증) — **해소**

`tests/idle_monitor/test_adversarial.py:22-68`

- `@pytest.mark.skipif(sys.platform != "win32")` **제거 확인**. Linux/WSL CI에서 실제 실행.
- `patch("idle_monitor.backends.sys") as mock_sys; mock_sys.platform = "win32"` 구조.
  `_select_backend()` 내부 `if sys.platform != "win32":` 참조가 **같은 `sys` 바인딩**이므로
  patch가 정확히 활성화된 시점에 분기 평가가 진행된다. 타이밍 버그 없음.
- `PynputBackend.start`에 `side_effect=BackendInitError("EDR blocked")` 주입 →
  `_select_backend` 내부의 `backend.start()` 호출이 실제로 예외를 던지고
  `logger.warning("pynput backend failed: ...")` 경로 실행.
- `Win32IdleBackend.start`에 `return_value=None` 주입 — `__init__`은 부작용 없이
  인스턴스만 생성되고 `.start()`가 patched이므로 ctypes.windll 접근 시도 없음.
  Linux에서도 `import ctypes.wintypes` 자체는 성공(`python3 -c 'import ctypes.wintypes'` 검증).
- 결과 단언: `isinstance(monitor._backend, Win32IdleBackend)` — 타입 체크 수행.
- loguru sink로 warning 메시지 수집 후 `"pynput" in msg` 포함 여부 확인.

**Mutation 검증**: `src/idle_monitor/backends/__init__.py`의 Win32 분기를
`raise BackendInitError(...)`로 치환하면 A-1 `AssertionError: Win32IdleBackend여야 하지만
NoopBackend`로 **실패**함을 실측 확인. 회귀 재현 능력 입증.

### B2 (A-2 우회 → 실제 강등 경로 검증) — **해소**

`tests/idle_monitor/test_adversarial.py:70-120`

- 이전의 `patch("idle_monitor.backends._select_backend", side_effect=lambda ...: _noop_after_error())`
  **완전 제거**. `_noop_after_error` 헬퍼도 제거됨(`tests/idle_monitor/` 검색 결과 0 히트).
- A-1과 동일한 `sys.platform` patch + `PynputBackend.start`/`Win32IdleBackend.start`
  양쪽에 `BackendInitError` 주입. 실제 `_select_backend`가 Pynput→Win32→Noop 강등 분기
  전체를 실행하고 `logger.error("both pynput and Win32 backends failed: ...")` 경로 1회 로그.
- 결과: `isinstance(monitor._backend, NoopBackend)` 단언 + error 로그 문자열 포함 확인 +
  `_tick()` 호출 후 crash 없음까지 검증.
- `IdleMonitor.start()` 호출이 **예외를 밖으로 내보내지 않는다**는 A-2 핵심 불변식도 검증됨.

### B3 (AppConfig `active_gap_seconds` 배선 + 상한 불일치) — **해소**

- `src/app/config.py:106-135`에 `ProactiveConfig` 신설. 4개 필드:
  `idle_threshold_min` (default=45, `ge=1, le=1440`),
  `overwork_threshold_min` (default=120, `ge=1, le=1440`),
  `active_gap_seconds` (default=60, `ge=1, le=3600`),
  `cooldown_min` (default=30, `ge=1, le=1440`).
  스펙 §4.2 상한(idle/overwork 1~1440, active_gap 1~3600)과 완전 일치.
  `IdleMonitor.__init__`의 유효 범위와도 일치(상한 불일치 해소).
- `AppConfig.proactive = Field(default_factory=ProactiveConfig)` (L150).
  구 평면 필드(`AppConfig.idle_threshold_min` 등)는 **완전 제거** 확인
  (`grep "app_config\.idle_threshold\|\.proactive_cooldown_min"` → src 히트 0).
- `src/app/service_context.py:252-261`에서 `IdleMonitor(...)`에 3개 파라미터
  (`idle_threshold_min`, `overwork_threshold_min`, `active_gap_seconds`)를 모두 주입.
- YAML fixture 3종(`conf.valid.yaml`, `conf.invalid_url.yaml`, `conf.missing_app.yaml`)
  모두 `proactive:` 블록으로 이관. `conf.missing_app.yaml`은 부분 필드(idle_threshold_min=10)만
  두고 나머지 기본값 사용 → `test_e1_missing_app_fields_use_defaults` 통과.
- 배선 회귀 테스트 `test_idle_monitor_active_gap_seconds_wired`는
  `active_gap_seconds=120`(기본값 60과 다름)으로 설정해 실제 배선 여부 판정.

**Mutation 검증**: `service_context.py`의 `active_gap_seconds=...` 한 줄을 제거하면
`test_idle_monitor_active_gap_seconds_wired`가 `assert 60 == 120` 실패 — 배선 라인 삭제
회귀를 정확히 검출함을 실측 확인.

---

## Spec Alignment

### §4 공개 API
모든 시그니처·타입 힌트·생성자 kwargs 6종(idle/overwork/active_gap/poll/clock/backend)
정확히 일치. `_tick(now=None)` public-visible private 메서드 포함.

### §5 알고리즘
- 3계층 백엔드(`pynput_backend.py`, `win32_backend.py`, `noop_backend.py`) 존재.
- `_select_backend()` 순서: `sys.platform != "win32"` → Noop / Pynput try → `BackendInitError` catch →
  Win32 try → `BackendInitError` catch → Noop + logger.error. 스펙 §5.1 슈도코드와 완전 일치.
- `_tick` 상태 기계: `elapsed = max(0.0, (now - last).total_seconds())`로 클록 역행 클램프(D-10).
- active→idle 전이 시 `_overwork_emitted=False` 리셋, `idle_rest` emit. overwork 판정은
  `(now - _active_since) >= overwork_threshold_sec` 조건으로 `_overwork_emitted` 플래그 1회만.

### §6.3 결정 사항
D-1(쿨다운은 M_11) / D-2(단일 콜백 슬롯) / D-3(DND drop) / D-4(1초 폴링) /
D-5(비Win Noop+warn) / D-6(Literal 단일 인자) / D-7(전이당 1회) / D-8(create_task) /
D-9(자동 폴백) / D-10(클록 역행 클램프) / D-11(start/stop 멱등) / D-12(_tick 공개+DI) —
전부 코드·테스트에서 확인.

### §9 에러 처리
파라미터 범위 위반 → ValueError / set_dnd·on_event TypeError / start RuntimeError
(이벤트 루프 부재) / 콜백 예외 swallow+warning / `_tick` 내부 예외 error+루프 생존 /
backend.stop 예외 swallow. 전부 일치.

### §10 동시성
- `_tick` 폴링 Task는 단일 이벤트 루프 순차 실행.
- 콜백은 `asyncio.create_task(self._safe_invoke_callback(event))` fire-and-forget.
- Pynput 훅 스레드는 단일 필드 쓰기(`self._last_input = clock()`) — CPython GIL 하 원자적.
  락 없이도 안전.

### §13.1 배선
`service_context.py:252-261` — 스펙 §13.1 슈도코드와 1:1 매핑.
`try/except Exception → idle_monitor=None` 패턴도 준수.

### §16.1 conf.yaml 3개 필드
스펙은 `idle_threshold_min`/`overwork_threshold_min`/`active_gap_seconds` 3개만 요구.
구현은 `cooldown_min`까지 총 4개 추가. **이는 스펙-범위 위반이 아니다** —
M_10 스펙 §13.1 본문에 "M_01이 이미 `proactive_cooldown_min`을 가지고 있으므로
`ProactiveConfig` 구조체 확장 1회로 처리"라고 명시. M_01 스펙 L134의 기존 필드
`proactive_cooldown_min`을 `ProactiveConfig.cooldown_min`으로 리네이밍·이관한 것이므로
범위 내. M_01 AppConfig 구 평면 필드에 의존하는 기존 코드가 없음(`grep` 0 hit)이라
리팩터가 깨뜨리는 호출자 없음.

---

## Test Coverage Analysis

- 정상 N-1~N-7 (7건), 엣지 E-1 3변형 + E-2~E-7 (9건), 적대 A-1~A-4 (4건) — 스펙 §11 요구 충족.
- 배선 테스트 4건(`test_idle_monitor_none_before_load_app_services`,
  `test_idle_monitor_injected_on_load_app_services`, `test_idle_monitor_start_called_in_event_loop`,
  `test_idle_monitor_active_gap_seconds_wired`) — before/after 분리 검증으로 배선 라인
  삭제 회귀를 검출 가능.
- 전체 스위트: `pytest tests/ -q` → **556 passed, 6 skipped**. Linux/WSL CI에서
  A-1/A-2 실행(skipped 아님). 이전 R1에서 경고했던 "`openai` 부재로 test_service_context.py
  collection 실패" 현상도 해소 — `tests/app/test_service_context.py` 30건 전부 PASS.
- Mutation test(Critic 직접 실측): Win32 분기 제거 → A-1 FAIL / active_gap_seconds 배선 제거 →
  `test_idle_monitor_active_gap_seconds_wired` FAIL. 두 테스트 모두 실제 회귀 재현 가능.

---

## Non-blocking

1. **[MINOR] A-1/A-2 로그 단언이 `any(...)` 패턴 — 정확한 1회 카운트 아님**
   `test_adversarial.py:64-66, 111-113`. 스펙 §11.3은 "logger.warning 1회" / "logger.error 1회"를
   요구하나, 현재 구현은 "'pynput'/'Win32'/'both' 포함 메시지가 최소 1건" 수준.
   중복 로그가 찍혀도 통과함. 현재 `_select_backend`는 단일 분기 경로이므로
   실제로 한 번만 찍히고, 이는 코드 리뷰로 충분히 확인되므로 Blocking 아님.
   권고(선택): `assert sum("pynput" in msg for msg in warning_messages) == 1`로 강화.

2. **[MINOR] `NoopBackend._warned` 클래스 변수 섀도잉** — R1에서 이미 지적.
   클래스 속성으로 선언 후 인스턴스에서 `self._warned = True` 할당 시 인스턴스 속성
   섀도잉. 의도된 "인스턴스당 1회"는 동작하지만 클래스 수준 공유로 오해할 여지.
   권고: `__init__`에 명시 또는 모듈 레벨 플래그로 전환. 기능 영향 없음.

3. **[MINOR] `ProactiveConfig`에 `extra="forbid"` 미설정**
   `src/app/config.py:106-135`. 구 평면 키(`idle_threshold_min` 등)를 YAML 최상위에
   직접 기입한 사용자가 있으면 pydantic 기본 "ignore" 정책에 의해 조용히 무시됨.
   마이그레이션 오탐지. 권고: `model_config = {"extra": "forbid"}` 추가 또는
   README 마이그레이션 노트. Breaking change 경보 관점에서 고려.

4. **[MINOR] `docs/MODULES.md` M_10 상태가 여전히 `🔲 TODO`** — DoD §12.6은
   Critic PASS 후 갱신이므로 이 리뷰(PASS)가 트리거. Builder는 후속 작업으로 갱신하면 됨.
   Blocking 아님(선후 관계).

5. **[MINOR] `docs/RISKS.md` R-10 상태 `OPEN`** — DoD §12.6에 따라 PASS 후
   `MITIGATING`으로 갱신 예정. 선후 관계이므로 본 리뷰에서 Blocking 아님.

6. **[MINOR] `tests/idle_monitor/fakes.py`가 conftest에서 re-export**
   R1 지적 그대로 유지. `from tests.idle_monitor.conftest import FakeBackend, FakeClock`.
   스펙 §5.5는 `fakes.py`가 원본, conftest가 import하는 구조를 제시했으나 현재는 반대.
   실제 실행 에러 없으나 선례 일관성 측면. 기능 영향 없음.

7. **[MINOR] `Win32IdleBackend.start()` 광범위 `except Exception:`**
   `src/idle_monitor/backends/win32_backend.py:51`. ctypes.windll 접근 실패 상황
   커버용이지만 `AttributeError, OSError`로 좁힐 수 있음. 보안 영향 없음.

8. **[MINOR] `pywin32` 의존성이 본 모듈에서 실사용되지 않음** — R1 지적과 동일.
   스펙 §14.1의 M_12 공유 명분이므로 위반은 아님. M_12 구현 시 실사용 확인 필요.

---

## Project Rule Compliance

- 외부 네트워크 호출: `grep -rn "httpx|requests|urllib|fetch|aiohttp" src/idle_monitor` 0건. PASS.
- 새 의존성: `pynput>=1.7,<2` + `pywin32>=306; sys_platform == "win32"` — pyproject.toml L41-42
  / bundle_deps.sh L127-142에 정확히 반영. Windows 마커·wheel 다운로드 옵션 명시. PASS.
- mypy: `mypy src/idle_monitor` → "Success: no issues found in 9 source files". PASS.
  (참고: `mypy src/`는 기존 프로젝트 구조 이슈로 "app.config vs src.app.config" 중복 경고가
  뜨나 M_10 신규 코드와 무관.)
- ruff: `ruff check` → "All checks passed!" PASS.
- upstream/ 무결성: idle_monitor는 NEW 모듈로 upstream 수정 없음.

---

## 검토하지 못한 영역 (다음 Critic·integrator가 이어서)

- 실제 Windows VM에서 pynput Listener `.is_alive()` 재차단 시나리오 — integrator 단계.
- pywin32가 M_12(always-on-top)에서 실제로 쓰이는지 — M_12 builder가 확인.
- `_poll_loop`이 cancel된 직후 `_tick`가 `create_task`를 호출한 잔존 Task의
  이벤트 루프 종료 경계 처리 — integrator가 장시간 실행 로그로 확인.
- Windows EDR 환경의 실제 차단 재현 — integrator(사내 IT 협의).

---

## Recommendation

**PASS**. Round 1 Blocking 3건 모두 실제 코드·테스트에서 해소되었고,
mutation test로 회귀 검출 능력까지 입증되었다. 스펙 §4~§16 전면 재검증 결과
신규 Blocking 없음. Non-blocking 8건은 모두 기능 영향 없는 정리·문서 수준.

후속 작업(후순위):
1. `docs/MODULES.md` M_10 블록 `🔲 TODO → ✅ DONE` 갱신 + API 표 수정 (DoD §12.6).
2. `docs/RISKS.md` R-10 `OPEN → MITIGATING` (DoD §12.6).
3. (선택) Non-blocking #1, #3 보강.

M_10 구현은 M_11 ProactiveDispatcher 착수를 막을 이유가 없다.
