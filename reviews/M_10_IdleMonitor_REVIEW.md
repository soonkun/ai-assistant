# M_10 IdleMonitor Critic Review

Date: 2026-04-19
Verdict: **FAIL**

## Summary

M_10 IdleMonitor 모듈은 스펙의 공개 API·상태 기계·3계층 백엔드·D-1~D-12 결정 사항 거의 전부를 충실히 구현했고 ruff/mypy/pytest 51 pass / 2 skip에 커버리지 75%를 달성했다. 그러나 **두 건의 적대적(A-1, A-2) 테스트가 실제 폴백 체인을 우회한 "가짜 통과"이고**(FakeBackend 직접 주입 또는 `_select_backend` 자체를 `side_effect`로 교체), **AppConfig 배선에서 `active_gap_seconds`·`ProactiveConfig` 그룹화가 누락**(스펙 §13.1 "conf.yaml 필드 3개 신설" 위반)되어 `active_gap_seconds`가 사실상 기본값으로만 동작한다. R-10 회귀 방지 핵심 검증이 실제 코드 경로를 검증하지 못하고, 스펙이 명시적으로 DoD에 올린 배선 변경이 빠져 있으므로 Blocking으로 판정한다.

## Spec Alignment

### §4 공개 API
| 항목 | 위치 | 상태 |
|---|---|---|
| `IdleEvent = Literal["idle_rest", "overwork"]` | src/idle_monitor/types.py:9 | PASS |
| `IdleEventCallback` alias | types.py:12 | PASS |
| `__init__` kwargs(idle/overwork/active_gap/poll/clock/backend, cooldown·dnd **없음**) | service.py:31-70 | PASS (D-1 준수) |
| `start() -> None` (sync) | service.py:94 | PASS |
| `async def stop() -> None` | service.py:141 | PASS |
| `set_dnd(bool)` + TypeError | service.py:170-182 | PASS |
| `on_event(callback \| None)` | service.py:184-195 | PASS |
| `last_input_at()` | service.py:197-206 | PASS |
| `seconds_since_last_input()` | service.py:208-216 | PASS |
| `_tick(now=None)` 공개 | service.py:218-267 | PASS |
| `_IdleBackend` ABC | backends/base.py:14 | PASS |
| 에러 `IdleMonitorError` / `BackendInitError` | errors.py:7,11 | PASS |

### §5 알고리즘·백엔드
| 항목 | 위치 | 상태 |
|---|---|---|
| 3계층 백엔드(Pynput/Win32/Noop) | backends/{pynput,win32,noop}_backend.py | PASS |
| `_select_backend()` start() 시점 1회 결정 | backends/__init__.py:21-68 + service.py:115-131 | PASS |
| 비Windows → NoopBackend (`sys.platform != "win32"`) | backends/__init__.py:38 | PASS |
| pynput 실패 → Win32 폴백 (logger.warning) | __init__.py:43-54 | PASS (코드 경로 존재) |
| Win32 실패 → Noop (logger.error) | __init__.py:56-68 | PASS |
| `_tick` 상태 기계 active↔idle + overwork 1회/세션 | service.py:244-264 | PASS |
| active→idle 전이 시 `idle_rest` 1회 방출 | service.py:246-250 | PASS |
| 클록 역행 클램프 (D-10) | service.py:239, 216 | PASS |
| start 멱등성 (D-11) | service.py:105-107 | PASS |
| win32 wrap `& 0xFFFFFFFF` | win32_backend.py:76 | PASS |

### §6.3 결정 사항
| ID | 요구 | 상태 |
|---|---|---|
| D-1 쿨다운은 M_11 | grep `cooldown\|last_sent\|last_emit` on src/idle_monitor → 0 hit | PASS |
| D-2 단일 콜백 슬롯 + None 해제 | service.py:195 | PASS |
| D-3 DND drop (내부 state는 갱신) | service.py:273-279, tests N-4 | PASS |
| D-4 1초 폴링 기본 | service.py:37 | PASS |
| D-5 비Windows Noop + warning 1회 | backends/__init__.py:38-40, noop_backend.py:22-30 | PASS |
| D-6 콜백 Literal 단일 인자 | types.py:12, service.py:280 | PASS |
| D-7 전이당 1회 | service.py:244-264 + test_e1_*_no_duplicate | PASS |
| D-8 fire-and-forget `create_task` | service.py:280 | PASS |
| D-9 자동 폴백(R-10) | __init__.py + service.py:119-121 | PASS |
| D-10 클록 역행 클램프 | service.py:216, 239 | PASS |
| D-11 start/stop 멱등 | service.py:105, 150 | PASS |
| D-12 `_tick` 공개 + clock/backend DI | service.py:38-39, 218 | PASS |

### §9 에러 처리
| 상황 | 처리 | 상태 |
|---|---|---|
| `__init__` 범위 위반 → ValueError | service.py:59-70 | PASS |
| `set_dnd` 타입 검증 | service.py:179-180 | PASS |
| `on_event` 타입 검증 | service.py:193-194 | PASS |
| `start()` 루프 없을 때 RuntimeError | service.py:110-113 | PASS |
| 콜백 예외 swallow + warning | service.py:282-291 | PASS |
| `_tick` 내부 예외 logger.error | service.py:266-267 | PASS |
| backend.stop() 예외 swallow | service.py:162-165 | PASS |

### §10 테스트
| 카테고리 | 스펙 요구 | 실제 | 상태 |
|---|---|---|---|
| 정상 | N-1~N-7 (7건) | test_service.py TestNormalCases 7건 전부 | PASS |
| 엣지 | E-1~E-7 (7건) | E-1 3변형(state_machine), E-2/E-3(state_machine), E-4~E-7(test_service) | PASS |
| 적대적 | A-1~A-4 (4건) | 4건 존재하나 A-1/A-2 실질 우회 | **부분 FAIL** — 아래 Blocking 참조 |

## Findings

### Blocking

1. **[CRITICAL] `test_a1_pynput_init_error_falls_back_to_win32_mocked`가 실제 폴백 체인을 검증하지 않음** — tests/idle_monitor/test_adversarial.py:50-61
   - 해당 테스트는 `wire_monitor(IdleMonitor(...), mock_win32)`로 Win32 mock을 **직접 주입**한다. 실제로 `_select_backend()`가 PynputBackend의 `BackendInitError`를 잡아 Win32로 폴백하는 코드 경로는 실행되지 않는다.
   - `assert monitor._backend is mock_win32` 한 줄뿐으로 `isinstance`도 아니고, "폴백 메시지 logger.warning 1회"도 검증 안 함. 이는 스펙 §11.3 A-1의 "선택된 백엔드가 `Win32IdleBackend` 인스턴스. `logger.warning` 1회 (폴백 메시지 포함)" 요구를 충족하지 않는다.
   - Windows-only 원본 A-1(`test_a1_pynput_init_error_falls_back_to_win32`)은 `@pytest.mark.skipif(sys.platform != "win32")`로 Linux/WSL CI에서 **스킵**된다. 즉 R-10 회귀 방지 핵심 케이스가 프로젝트의 주 CI 환경에서 실행되지 않는다.
   - 권고 조치: `sys.platform`을 `"win32"`로 `patch`하고, `PynputBackend.start`에 `side_effect=BackendInitError(...)`를, `Win32IdleBackend.start`에 `return_value=None`을 `patch`한 뒤 `IdleMonitor.start()`를 호출해 `_select_backend`가 실제로 Win32로 폴백하는 것을 검증하라. 이미 동일 패턴이 `test_select_backend_pynput_fail_win32_fail_returns_noop`(test_backends.py:173)에 있으므로 그 방식을 A-1에도 적용하면 된다. 현재는 "A-1 변형 2건" 중 하나는 skip, 하나는 우회라 실질 커버 0.

2. **[CRITICAL] `test_a2_both_backends_fail_noop_degraded`도 실제 체인을 우회** — tests/idle_monitor/test_adversarial.py:64-83, 131-136
   - `patch("idle_monitor.backends._select_backend", side_effect=lambda _clock: _noop_after_error())`로 `_select_backend` 함수 **자체를 치환**한다. `_noop_after_error()`는 `logger.error("... test simulation ...")` 로그를 찍고 `NoopBackend()`를 반환하는 테스트 헬퍼다. 즉 실제 `_select_backend`가 Pynput→Win32→Noop로 강등하는 분기 로직은 실행되지 않는다.
   - 사실상 "NoopBackend가 할당되면 `_tick`이 crash 없다"만 확인할 뿐이며, 스펙 §11.3 A-2가 요구하는 "pynput+Win32 둘 다 `BackendInitError` → Noop 강등 + logger.error 1회 + 예외 밖으로 나오지 않음"을 end-to-end 검증하지 않는다.
   - 참고: `test_select_backend_pynput_fail_win32_fail_returns_noop`(test_backends.py:173-196)가 `_select_backend` 자체의 실제 분기를 검증하므로 그 테스트는 OK. 그러나 스펙이 A-2로 요구한 것은 `IdleMonitor.start()` 진입부터 Noop 강등까지의 **전 경로**이므로 A-2 테스트도 동일 스타일로 재작성해야 한다.
   - 권고 조치: `sys.platform="win32"` + `PynputBackend.start/Win32IdleBackend.start` 두 개를 `side_effect=BackendInitError(...)`로 patch한 뒤 `IdleMonitor().start()` 호출 → `assert isinstance(monitor._backend, NoopBackend)` + `caplog`에서 `logger.error` 1건 검증.

3. **[MAJOR → BLOCKING] AppConfig 배선 누락 — `active_gap_seconds` 파라미터가 전달되지 않음** — src/app/service_context.py:251-260, src/app/config.py:118-120
   - 스펙 §13.1은 AppConfig에 `proactive.idle_threshold_min` / `proactive.overwork_threshold_min` / `proactive.active_gap_seconds` **3개 필드**를 신설하고 `IdleMonitor` 생성자에 전부 주입하도록 명시한다(§16.1 "conf.yaml 필드 3개 신설").
   - 구현은 `AppConfig`에 `idle_threshold_min` / `overwork_threshold_min`만 평면 필드로 존재하며(`ProactiveConfig` 그룹 미생성), **`active_gap_seconds`는 아예 필드가 없음**. `service_context.py:253-256`은 두 개만 전달하고 `active_gap_seconds`를 넘기지 않아 IdleMonitor는 하드코딩된 기본값 60초로만 동작한다.
   - DoD 12.5 "`src/app/service_context.py::load_app_services` 내 `IdleMonitor(...)` 주입 1줄 추가" 및 §16.1 "conf.yaml 필드 3개 추가"를 명시적으로 위반. 향후 M_11에서 "연속 활동 간격"을 운영 시 조정하려 해도 conf로 노출되지 않아 불가능하다.
   - 추가로 `AppConfig.idle_threshold_min`은 `le=600`인데 `IdleMonitor.__init__`은 `le=1440` → 스펙 §4.2 "1~1440"과도 맞지 않고, `AppConfig`가 더 strict한 상한으로 가로막는 inconsistency.
   - 권고 조치:
     (a) `src/app/config.py`에 `ProactiveConfig(BaseModel)` 신설 (`idle_threshold_min=45`, `overwork_threshold_min=120`, `active_gap_seconds=60`, 기존 `proactive_cooldown_min`도 이리로 이동 권장) — 또는 최소한 `active_gap_seconds` 필드를 AppConfig에 평면 추가.
     (b) `AppConfig.idle_threshold_min`의 `le` 상한을 1440으로 맞추거나 IdleMonitor 쪽을 600으로 하향(스펙 §4.2는 1440이므로 AppConfig 쪽을 올리는 것이 옳음).
     (c) `service_context.py`가 `active_gap_seconds`를 포함해 3개를 전부 `IdleMonitor(...)`에 주입.

### Non-blocking

1. **[MAJOR] A-1 Windows-only 실측 케이스가 Linux CI에서 skip** — tests/idle_monitor/test_adversarial.py:23
   - 현재 주 CI 환경(WSL/Linux)에서 R-10 폴백 경로 실측 검증이 0건이다. Blocking #1 해결과 같이 다뤄야 한다.

2. **[MAJOR] `NoopBackend._warned`를 클래스 변수로 선언 후 인스턴스에서 쓰기** — src/idle_monitor/backends/noop_backend.py:22, 24-30
   - `_warned: bool = False`는 클래스 속성. 첫 `start()`에서 `self._warned = True`로 인스턴스 속성으로 섀도잉되므로 원래 의도대로 "인스턴스당 1회"는 동작한다. 다만 다른 인스턴스의 상태를 공유하지 않아 테스트가 `NoopBackend()` 여러 번 생성하면 매번 warning이 찍힌다. 스펙 §6.3 D-5의 "1회"가 **프로세스 생애당 1회**인지 **인스턴스당 1회**인지 모호한데, 현재 구현은 후자. 클래스 변수 표기와 실제 의미가 불일치하는 것 자체가 미묘한 버그 모양새다.
   - 권고: `__init__`에 `self._warned = False`를 명시적으로 쓰거나, 진짜 프로세스 1회면 모듈-레벨 플래그(`_WARNED_ONCE = False`)를 쓰라.

3. **[MINOR] `tests/idle_monitor/fakes.py`가 `tests.idle_monitor.conftest`를 import** — fakes.py:7
   - `from tests.idle_monitor.conftest import FakeBackend, FakeClock` 형태인데, conftest는 pytest의 fixture 파일이다. 일반적으로 conftest를 다른 테스트 파일이 직접 import하는 것은 안티패턴(테스트 실행 경로가 아닌 곳에서는 ImportError). 지금은 실사용이 없으니 실패하지 않으나, 의도대로라면 `FakeBackend`/`FakeClock`을 `fakes.py`에 정의하고 conftest가 `fakes.py`에서 import해야 한다(스펙 §5.5도 `tests/idle_monitor/fakes.py`를 원본으로 지목).

4. **[MINOR] `docs/RISKS.md` R-10 상태 미갱신** — docs/RISKS.md:113
   - 스펙 §12.6이 Critic PASS 후 R-10을 `OPEN → MITIGATING`으로 갱신하도록 지시. 현재 OPEN. 단, 이 갱신은 "Critic PASS 후" 단계 작업이므로 지금은 FAIL 사유로 쓰지는 않는다.

5. **[MINOR] `Win32IdleBackend.start()`에서 `except Exception:` 광범위 캐치** — src/idle_monitor/backends/win32_backend.py:51
   - `getattr(ctypes, "windll")` 실패 경로 커버용이지만 너무 넓다. `AttributeError` 등으로 좁힐 수 있다.

6. **[MINOR] `pywin32` 의존성이 본 모듈에서 실사용되지 않음** — src/idle_monitor/backends/win32_backend.py 전체가 `ctypes`만 사용
   - 스펙 §14.1이 "M_12와 공유 명분으로 추가"라고 명시하므로 위반은 아니나, 본 모듈만 놓고 보면 의존성이 불필요. M_12가 실제로 pywin32를 쓰는지 재확인 필요.

7. **[MINOR] `test_e7_noop_backend_tick_no_crash`는 `@pytest.mark.asyncio`지만 state 전이 없어 `create_task` 미호출** — 사실상 sync 테스트와 동일. 문제는 아님, 관찰.

## Test Coverage Analysis

- 정상 7 / 엣지 7 / 적대적 4 총 18건 요구 → 파일 상 18건 존재(중복 변형 포함 시 51 items 전체 pass/skip).
- 커버리지: `src/idle_monitor/` 전체 75% (`pynput_backend.py` 43%, `win32_backend.py` 50% — 둘 다 Windows 전용 런타임 분기라 Linux에서는 불가피). 핵심 분기(폴백 체인)가 `test_select_backend_pynput_fail_win32_fail_returns_noop`로 실측 커버되므로 플랫폼 제약은 문제 아님.
- `_tick` 상태 기계 분기는 state_machine 테스트로 완전 커버. 경계값 E-1은 3가지 변형으로 회귀 방지 수준이 뛰어남.
- FakeBackend 테스트가 Pynput/Win32 경로를 우회하는지 확인: test_state_machine, test_callbacks, test_service 모두 `wire_monitor(IdleMonitor(...), FakeBackend)` 또는 `backend=fake_backend` 방식으로 pynput/Win32 import를 실제로 발동하지 않음. 좋음.
- 회귀 방지의 약한 고리: A-1/A-2 적대적 케이스가 실제 체인을 우회(위 Blocking #1, #2). R-10 자동 폴백이 "구현은 되어 있는데 실측 테스트가 없는" 상태.
- `tests/app/test_service_context.py::TestM10IdleMonitorWiring`는 `isinstance(ctx.idle_monitor, IdleMonitor)`만 단언(246, 278라인). M_08 R2에서 경고한 "배선 라인 삭제 시에도 pass하는 은폐"에 해당하지 않으려면, 테스트가 "load_app_services 전후 변화"를 검증해야 하는데 `test_idle_monitor_none_before_load_app_services` + `test_idle_monitor_injected_on_load_app_services` 두 개로 before/after를 분리 검증하고 있어 배선 라인 제거 시 실패한다. 이건 OK.

## 검토하지 못한 영역

- 실제 Windows VM 상의 pynput `.start()` 동작(EDR 차단·listener `is_alive()` 회귀) — integrator 단계 책임.
- `scripts/bundle_deps.sh`를 실제로 돌려서 wheel이 다운로드되는지 — 이 단계의 범위 아님.
- `pywin32`가 M_12에서 실제 사용되는지(스펙 §14.1의 공유 명분의 정당성).
- 장시간 실행(6시간+) 시 pynput Listener 스레드 누수/메모리 증가 — integrator 단계.
- `_tick` 내부에서 `asyncio.create_task`를 호출하는데, `_poll_loop`를 cancel한 직후 이벤트 루프 종료 경계에서 dangling Task가 어떻게 처리되는지 — 스펙 D-8이 "fire-and-forget, asyncio가 종료 시 경고"라고 허용하긴 하나 실측 없음.

## Recommendation

**FAIL**. 다음 3건이 먼저 고쳐져야 한다:
1. Blocking #1 — A-1 적대적 테스트를 `sys.platform` patch + `PynputBackend/Win32IdleBackend.start` side_effect 방식으로 재작성해 실제 폴백 체인을 end-to-end 검증.
2. Blocking #2 — A-2 적대적 테스트를 동일 방식으로 재작성(양쪽 BackendInitError → Noop + caplog의 logger.error 확인). `_noop_after_error` 헬퍼는 제거.
3. Blocking #3 — `AppConfig`에 `active_gap_seconds`(및 가급적 `ProactiveConfig` 그룹) 신설 + `idle_threshold_min le`를 1440으로 정렬 + `service_context.py`가 3개 파라미터 모두 전달. 배선 회귀 테스트(`TestM10IdleMonitorWiring`)에 `active_gap_seconds` 값이 실제로 IdleMonitor 내부(`monitor._active_gap_seconds`)에 전달됐는지 확인하는 단언 추가.

위 3건 수정 후 fresh critic이 재검수해야 한다. 재검수 시 `reviews/M_10_IdleMonitor_REVIEW_R2.md`로 분리하고 본 리뷰의 결함 항목에 한정하지 말고 스펙 전체를 다시 훑어야 한다(앵커링 방지).
