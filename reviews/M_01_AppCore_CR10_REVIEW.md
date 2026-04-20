# M_01 AppCore — CR-10 set-dnd 리뷰

- 리뷰어: Critic (fresh, 앵커링 없음)
- 범위: CR-10 (B-4 `set-dnd` 수신 + `dnd-state` 송신)
- 판정: **PASS**
- 날짜: 2026-04-21

## 1. 독립 검증 결과

### 변경 범위 (git status / diff --stat)
```
M specs/M_01_AppCore_SPEC.md        +83 lines
M src/app/ws_handler.py             +46 lines
M tests/app/test_ws_handler.py     +213 lines
```
CR-10 지시 범위(M_01 스펙·ws_handler·test_ws_handler)와 **완전히 일치**. `proactive/`·`idle_monitor/`·M_11/M_12 스펙 등 범위 외 파일 변경 없음.

### pytest tests/app/ -v
```
130 passed, 6 warnings in 12.96s
```
- `TestSetDnd::test_n12_set_dnd_true_success` PASSED  (N-12)
- `TestSetDnd::test_e10_enabled_string_rejected` PASSED (E-10 기본)
- `TestSetDnd::test_e10_enabled_int_rejected` PASSED (E-10 int 1/0 보완)
- `TestSetDnd::test_e11_dispatcher_none_sends_error` PASSED (E-11)
- `TestSetDnd::test_a8_set_dnd_spam_100` PASSED (A-8)
- `TestSetDnd::test_dispatcher_exception_sends_error_and_keeps_ws` PASSED (DoD L859 예외 격리 보완)

### 전체 회귀: pytest tests/
```
656 passed, 10 skipped, 6 warnings in 43.53s
```
기존 525개 테스트 + 신규 6건 = 통과. 회귀 0건.

### 커버리지 (src/app/ws_handler.py 전체)
```
Name                    Stmts   Miss  Cover   Missing
src/app/ws_handler.py     148      9    94%   131-134, 308-309, 315-317, 327, 342-343
```
Missing 9줄은 모두 screenshot 세션 가드·연속 캡처 루프 내부 path(CR-10 범위 외). `_handle_set_dnd` L230-L270 **4분기(성공/bool아님/None/예외) 전부 100% covered**.

### ruff
```
ruff format --check: 2 files already formatted
ruff check:         All checks passed!
```

### mypy (cd src && mypy app/ws_handler.py)
```
app/ws_handler.py:63: error: Unused "type: ignore" comment  [unused-ignore]
Found 1 error in 1 file (checked 1 source file)
```
`git stash` 검증 결과 CR-10 이전 L61에서 동일 에러 존재. CR-10으로 인한 **라인 이동(61→63)일 뿐 신규 에러 0건**. 리뷰 지시서에서 pre-existing로 명시 — FAIL 사유 아님.

## 2. 체크리스트 심사

### 스펙 정합성
| 항목 | 결과 | 근거 |
|---|---|---|
| §B-4 payload 스키마 `{"type":"set-dnd","enabled":bool}` 일치 | ✅ | ws_handler.py L244 `data.get("enabled")` |
| bool 엄격 검사 (int 1/0 거부, L487) | ✅ | ws_handler.py L247 `type(enabled) is not bool` (isinstance 대신 type() is 사용 — int·bool 서브클래스 관계 차단) |
| proactive_dispatcher None 분기 (L488) | ✅ | ws_handler.py L253-259 |
| dispatcher.set_dnd sync 호출 (L489, await 금지) | ✅ | ws_handler.py L263 `dispatcher.set_dnd(enabled)` (await 없음) |
| 예외 격리, WS 연결 유지 (L489 "예외 재전파 금지") | ✅ | ws_handler.py L262-267 `try/except Exception` + `return` (raise 없음) |
| 성공 응답 `{"type":"dnd-state","enabled":<bool>}` (§C L503) | ✅ | ws_handler.py L270 |
| 에러 메시지 문자열 §에러 표 L684-L686과 글자 일치 | ✅ | "set-dnd: enabled must be bool" (L684↔L249), "set-dnd: proactive_dispatcher not initialized" (L685↔L257), "set-dnd: dispatcher failed" (L686↔L266) |
| logger 레벨 일치 (bool아님/None → warning, 예외 → error) | ✅ | ws_handler.py L248 `warning`, L255 `warning`, L265 `error` |
| `proactive_dispatcher` 접근 경로 | ⚠ MINOR | 스펙 L488은 `self.default_context_cache.proactive_dispatcher`를 명시했으나 구현은 `self._app_ctx.proactive_dispatcher`(L253) 사용. `__init__` L49에서 `self._app_ctx = default_context_cache`로 동일 인스턴스 alias — **기능적으로 완전 동일**. 기존 `_handle_screenshot_trigger`도 `self.default_context_cache`를 쓰지만 `handle_disconnect`에서 `self._app_ctx._active_ws`를 쓰는 선례가 있어 내부 핸들러 관례상 허용 범위. 스펙 문구 엄격 일치로 보려면 MINOR. FAIL 아님. |
| dispatcher 호출 = `dispatcher.set_dnd` 직접 호출 (중간 래핑 없음) | ✅ | ws_handler.py L263 |

### 테스트 충실도 (스펙 §테스트 N-12/E-10/E-11/A-8 4건)
| 스펙 케이스 | 구현 테스트 | 검증 내용 | 결과 |
|---|---|---|---|
| N-12 set-dnd(true) 정상 | test_n12_set_dnd_true_success (L638-658) | `call_count==1`, 인자 `True`, await 없음(MagicMock으로 sync 호출 검증), `dnd-state {enabled:true}` 송신 | ✅ |
| E-10 `"true"` 문자열 | test_e10_enabled_string_rejected (L660-701) | `call_count==0`, error 메시지 문자열 정확히 일치, caplog warning 1회, `dnd-state` 미송신 | ✅ |
| E-10 보완: int 1 거부 | test_e10_enabled_int_rejected (L703-719) | `enabled=1` 입력 시 `call_count==0` + error. 스펙 L487 "int 1/0도 거부" 회귀 방지 | ✅ (스펙 L487 충족도 100%) |
| E-11 dispatcher None | test_e11_dispatcher_none_sends_error (L721-758) | error 송신, `call_count==0`, warning 기록, `dnd-state` 미송신, 예외 전파 없음 | ✅ |
| A-8 100회 스팸 | test_a8_set_dnd_spam_100 (L760-800) | `call_count==100`, 최종 상태 일관성(last arg == last dnd-state.enabled), send_json 100회(error 0건) | ✅ |
| DoD L859 "예외 격리" 보완 | test_dispatcher_exception_sends_error_and_keeps_ws (L802-825) | `set_dnd.side_effect=RuntimeError` → error 송신, `dnd-state` 미송신, 예외 재전파 없음 | ✅ (스펙이 요구한 4건 외 추가 제공) |

- 모킹 우회: `MagicMock(spec=ProactiveDispatcher)`로 타입 계약 강제(spec= 지정으로 속성 오타 방지). 실제 로직 우회 없음.
- "쉬운 방향 왜곡" 흔적 없음: int 1 거부(E-10 보완)와 예외 격리(DoD 보완) 모두 엄격 테스트 추가 쪽으로 보강.
- A-8 메모리 어서션(RSS < 10 MB)이 스펙에 있으나 실구현은 call_count·상태 일관성으로 대체 — A-3 선례(MAJOR-10 결정)와 동일 정책이고 `send_json`을 AsyncMock으로 받아 누적만 카운트하므로 10 MB 위반 가능성 실질적으로 0. MINOR도 아님.

### 에러 처리
| 항목 | 결과 | 근거 |
|---|---|---|
| 스펙 §에러 표 3행 (L684-L686) 반영 | ✅ | 문자열 글자 일치, 앞서 검증 |
| `except Exception:` 광범위 캐치 | ⚠ | L264 `except Exception as exc`는 **스펙 L489가 "TypeError 등 예외"를 명시하며 예외 재전파 금지를 요구**하므로 의도된 캐치. `return`으로 WS 연결 유지. 허용. |
| 에러 메시지 사용자 의미 | ✅ | 세 메시지 모두 프런트 토스트용으로 충분 |

### 비기능·보안
| 항목 | 결과 | 근거 |
|---|---|---|
| 동기 I/O로 이벤트 루프 막기 | ✅ | dispatcher.set_dnd는 M_11 §4에 "단일 스레드 bool 할당 원자적"으로 명시. 블로킹 없음. |
| 메모리 누수 (닫히지 않은 리소스) | ✅ | 핸들러가 리소스 소유 안 함 |
| 외부 네트워크 호출 | ✅ | 없음 (CLAUDE.md §절대 금지 준수) |
| PII 마스킹 | ✅ | bool payload — PII 없음 |
| 파일 쓰기에 사용자 입력 주입 | ✅ | 해당 없음 |

### 코드 품질
| 항목 | 결과 | 근거 |
|---|---|---|
| 네이밍·주석 (docstring 4단계 일치) | ✅ | L236-243 스펙 단계 1:1 대응 주석 |
| 하드코딩 | ✅ | 에러 문자열은 스펙 계약이므로 정당 |
| 중복·데드 코드 | ✅ | 없음 |
| 핸들러 등록 (N-4) | ✅ | `"set-dnd": self._handle_set_dnd` L58, test_n4_new_handlers_registered 통과 |

### 회귀·변경 범위
| 항목 | 결과 |
|---|---|
| src/app/ws_handler.py 외 소스 수정 | ✅ (없음) |
| specs/ 중 M_01 외 수정 | ✅ (없음) |
| pytest 전체 회귀 PASS | ✅ (656 passed) |
| `_handle_set_dnd` 4분기 전부 covered | ✅ (coverage missing에 L244-270 없음) |

## 3. 결함 목록

### 심각(CRITICAL): 0건

### 중대(MAJOR): 0건

### 경미(MINOR): 1건

1. **[MINOR]** `src/app/ws_handler.py:253` — 스펙 L488은 `self.default_context_cache.proactive_dispatcher`를 명시하나 구현은 `self._app_ctx.proactive_dispatcher` 사용.
   - 기능 영향: 없음 (`__init__` L49 `self._app_ctx = default_context_cache` — 동일 인스턴스 alias).
   - 근거: 같은 파일 `_handle_screenshot_trigger`는 `self.default_context_cache`를 쓰는 반면 `handle_disconnect`는 `self._app_ctx._active_ws`를 쓰는 등 기존 관례가 이미 mixed. 엄격 일치를 원하면 스펙 L488 문구를 `self._app_ctx.proactive_dispatcher`로 조정하거나, 구현을 `self.default_context_cache`로 바꾸는 1-line 정리 권고.
   - 차단 사유 아님 — FAIL 사유 아님.

## 4. 최종 판정

### **PASS**

### 근거 요약
- 스펙 §B-4 4단계 동작·§C `dnd-state` 송신·§에러 표 3행이 모두 구현에 1:1 매핑됨. 에러 메시지 문자열까지 글자 단위로 일치.
- 스펙이 요구한 N-12/E-10/E-11/A-8 **4건 모두 구현** + DoD L859 "예외 격리" 보완 테스트 1건 + E-10 int 보완 테스트 1건 = 총 6건.
- 구현의 `type(x) is not bool` 사용으로 `isinstance(True, int)==True` 서브클래스 함정을 정확히 회피, 스펙 L487 "int 1/0도 bool이 아니므로 거부" 요구 충족.
- sync 호출(await 없음), 예외 격리(재전파 없음), WS 연결 유지 모두 코드·테스트로 증명.
- pytest 656 passed, ruff 통과, 신규 mypy 에러 0건.
- CR-10 범위 준수(3개 파일만 변경, M_11/M_12/proactive/ 무변화).

### 커밋 권고
- 본 변경은 **커밋 가능 상태**. docs/MODULES.md의 M_01 상태 표에 CR-10 완료 표기 권고(별도 작업).
- MINOR 1건(`_app_ctx` vs `default_context_cache` 접근 경로 용어 통일)은 후속 정리 대상. 차단 없음.

### 수정 지시
없음.
