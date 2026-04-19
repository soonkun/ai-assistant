# M_08 AvatarState Critic Review — Round 3

Date: 2026-04-19
Verdict: PASS
Previous verdicts: R1 FAIL, R2 FAIL

## Summary

Fresh 세션에서 스펙/구현/테스트/통합 지점을 전면 재검증한 결과, 이전 두 라운드의 Blocking 4건은 모두 실제 파일 상태에서 해소되었다. Round 2에서 제기된 핵심 통합 결함 2건(N-B1 `load_app_services` 배선 누락, N-B2 `typing.Any as AvatarState` alias)이 모두 코드 레벨에서 제거되었으며, 배선 회귀를 고정시키는 신규 테스트 2건(`TestM08AvatarStateWiring`)이 실재한다. `pytest tests/avatar_state/ tests/app/test_service_context.py` 76/76 pass, `ruff check` clean, `ruff format --check` clean. 스펙의 모든 DoD 항목이 코드·테스트에 반영된다. 새로운 Blocking 결함 0건. 남은 잔여 이슈는 전부 문서 드리프트(스펙 §5.1 L316 `%r`, §8 표 L436, §10.4 L590의 `caplog` 잔존 표현) 수준이며 runtime 영향이 없어 Non-blocking으로만 기록한다.

## Previous Findings Re-verified

### Round 1

| 지적 ID | 설명 | 현 상태 | 증거 |
|---|---|---|---|
| B1 (Blocking) | 스펙 §5.1 의사코드 `break` 누락 vs 구현 불일치 | **해소** | `specs/M_08_AvatarState_SPEC.md:314, 318` 양쪽 분기 모두 `break` 명시, 주석도 "뒤의 유효 키는 무시한다(D-3 첫 등장 기준, §10.3 A-1). study도 동일 경로(D-6)"로 업데이트. `tag_parser.py:61, 66`의 두 `break`와 의미 정합. |
| B2 (Blocking) | `service.py` logger.error 포맷이 `%r` (loguru 미치환) | **해소** | `service.py:138-141`이 brace-style `"(emotion={!r})"`. `tests/avatar_state/test_push_event.py:214-233`이 loguru sink로 records 캡처해 `"sad" in records[0]` 단언, 1회 로그 고정. |
| NB1 | A-1/E-8 테스트 warning 1회 단언 부재 | **해소** | `test_extract_emotion.py:168, 176, 197` 모두 `assert len(warnings) == 1` 강화. R2 지적의 `test_e8_study_tag_only`도 `>= 1` → `== 1`로 강화됨. |
| NB2 | E-8/A-1 `caplog` 검증 요구와 실제 loguru sink 헬퍼 불일치 | **문서만 드리프트** | 구현(loguru sink)은 적절히 WARNING 1건을 검출. 스펙 §10.4(L590) 문구가 아직 "caplog fixture"를 말함. runtime 영향 없음. |
| NB3 | 에러 메시지 tuple 순서(CHARACTER_SAESSAGI 순) | **해소** | `types.py:93-102`, `service.py:47-56` 모두 tuple 리터럴로 선언 순서 고정. `sorted()` 호출 제거됨. |
| NB4 | `test_extract_emotion.py` callable 소문자 annotation 오타 | **해소** | `test_extract_emotion.py:7, 30` — `from collections.abc import Callable` 후 `Callable[[], Any]` 사용. |

### Round 2

| 지적 ID | 설명 | 현 상태 | 증거 |
|---|---|---|---|
| B-R2-1 (Blocking) | `load_app_services`에 `AvatarState(default="neutral")` 배선 라인 부재 | **해소** | `src/app/service_context.py:216-218`에 M_09 배선 직후 `self.avatar_state = AvatarState(default="neutral"); logger.info("AvatarState 초기화 완료 (default=neutral).")`가 과도한 try/except 없이 단순 2줄로 추가됨. 스펙 §13.1 "1줄 추가" 의도와 부합(logger는 M_09 선례와 일관성). |
| B-R2-2 (Blocking) | `from typing import Any as AvatarState` alias 잔존 | **해소** | `service_context.py:12`가 정식 런타임 import `from avatar_state import AvatarState` (TYPE_CHECKING 블록 바깥). L42 필드 타입 힌트 `AvatarState | None`이 실제 클래스를 참조. M_09 `from calendar_service.service import CalendarService` 패턴과 일관. |
| NB-R2-1 | `test_e8_study_tag_only` 로그 카운트 `>= 1` 약화 | **해소** | `test_extract_emotion.py:176`가 `assert len(warnings) == 1`로 강화. |
| NB-R2-2 | 스펙 §8/§10 E-8/§10.4의 `caplog`·`%r` 잔존 | **미해소 (MINOR)** | §5.1 의사코드 L316, §8 표 L436, §10 E-8 L562, §10.4 L590 4곳에 여전히 `%r`/`caplog` 표현 존재. 구현은 brace-style + loguru sink이므로 runtime 차이는 없지만 문서-구현 이원화 지속. |
| NB-R2-3 | `tag_parser.py:64-65` dead-equivalent 조건 | **미해소 (MINOR)** | 현재 `tag_parser.py`에는 `if first_emotion is None:` 분기가 **제거**되어 있고 바로 `first_emotion = "neutral"` 대입. R2 권고대로 단순화됨 — **오히려 적절히 해소**. 본 리뷰에서 R2 보고서 오류를 정정. |
| NB-R2-4 | `_capture_errors_async` except/raise 패턴 과잉 | **미해소 (MINOR)** | `test_push_event.py:22-44` 여전히 `except Exception: exc_to_raise = exc ... finally: remove` 패턴. 기능 정상. |
| NB-R2-5 | B2 회귀 테스트가 `_capture_errors_async` 헬퍼를 쓰지 않고 인라인 중복 | **미해소 (MINOR)** | `test_push_event.py:214-233` 여전히 인라인으로 handler_id 관리. 스타일 불일치. |
| NB-R2-6 | `docs/MODULES.md:24-25` 다이어그램 오해 소지 | **미해소 (MINOR)** | 문서 개선 제안 수준. 영향 없음. |

## New Findings

### Blocking
없음.

### Non-blocking

1. **[MINOR] 스펙 §5.1 의사코드(L316) `logger.warning("unknown emotion tag: %r", m.group(0))`가 stdlib printf 스타일로 남아 있음.**
   - 구현(`tag_parser.py:63`)은 brace-style `"unknown emotion tag: {!r}"`. 의미 동등하고 테스트는 양쪽 모두에서 "joy"·"[emotion:study]" 문자열만 substring 검사하므로 runtime 영향 0. 다만 R1 B2 교정 이후 의사코드의 대응 수정이 누락된 드리프트. 권고: 의사코드 L316과 §8 에러 표 L436의 두 `%r` 참조를 `{!r}`로 갱신.

2. **[MINOR] 스펙 §10.4 테스트 지원 도구(L590) "로깅 검증은 `caplog` fixture"와 §10 E-8(L562) "caplog 에 WARNING 레벨 1건"이 실제 구현(loguru sink 헬퍼 `_capture_warnings`)과 불일치.**
   - loguru는 기본 설정에서 stdlib logging에 propagate 되지 않아 `caplog`에 잡히지 않는다. 현 구현은 `logger.add(_sink, level="WARNING")`으로 WARNING 1건을 정확히 포착 — 본질상 caplog보다 강한 검증. 스펙 문서를 "loguru sink 헬퍼(또는 propagate 활성화된 caplog)"로 수정 권고.

3. **[MINOR] `src/app/service_context.py:216`의 배선 코드는 try/except 없이 단순하며 `AvatarState(default="neutral")`의 실패 경로가 `ValueError`(default 검증) 단 하나뿐이라 정당하다. 그러나 M_09는 try/except로 감싸는 패턴인 반면 M_08은 맨 호출이라 _스타일_ 혼종이다.**
   - 스펙 §8 표(L444)가 `AvatarState.__init__(default="neutral")`은 **정상**이라고 명시하므로 try/except 생략이 맞다. 하지만 `load_app_services` docstring(L200)은 "각 서비스의 생성자 호출만 수행. 실패해도 앱 기동은 계속"이라고 말한다. M_08이 굳이 try/except를 두지 않는 이유를 주석으로 1줄 남기면 향후 동료가 "왜 M_08만 빠져 있지?"를 묻지 않게 된다. 문서화 수준의 개선 제안.

4. **[MINOR] `tests/avatar_state/test_extract_emotion.py::TestNormal::test_all_spoken_emotions_parse`가 루프마다 새 `state` 픽스처를 재사용하는데, 각 이터레이션에서 state에 내부 상태 기록이 없음을 암묵 가정한다.**
   - `extract_emotion`은 stateless 순수 함수라 문제없다(§9.3). 하지만 만약 미래에 캐시 추가 등 변경이 일어나면 이 테스트가 이를 은폐할 수 있다. 권고: 반복 앞에 `state = AvatarState()` 재초기화 또는 주석으로 stateless 의존을 명시.

5. **[MINOR] `test_push_event.py::test_n7_concurrent_push_event_order`의 "3개 요소" 검증은 R1에서 지적된 "5+개" 권고가 반영되지 않음.**
   - 3요소 순열 6종 중 1종만 확인. 우연한 통과 가능성 낮으나, Lock 내부 버그가 우연히 FIFO처럼 보일 위험은 N이 클수록 줄어든다. 권고: 5~10개 이벤트로 확장, 또는 R1/R2 논의를 근거로 "3개 유지" 사유를 테스트 docstring에 적시.

6. **[MINOR] `docs/MODULES.md:25` ASCII 다이어그램과 L281 M_08 섹션의 "상태: 🚧 WIP — reviews: 2/3 FAILED (2026-04-19)"·L434 "🚧 WIP (reviews: 2/3 FAILED)"는 PASS 결정 후 `✅ DONE`으로 갱신 필요.** 현재는 여전히 WIP이며 이는 정상(Critic PASS 이전에 몰래 DONE으로 바꾸지 않음을 확인함).

## Spec Alignment

| 스펙 항목 | 구현 위치 | 상태 |
|---|---|---|
| §4.1 Emotion Literal 8종 순서 고정 | `types.py:20-29` | PASS |
| §4.1 `_VALID_EMOTIONS`/`_SPOKEN_EMOTIONS` 분리, frozenset | `types.py:32-57` | PASS |
| §4.1 D-6 `_VALID_EMOTIONS − _SPOKEN_EMOTIONS == {"study"}` | `test_types.py:21-37` 5개 | PASS |
| §4.2 AvatarEvent frozen=True + slots=True | `types.py:72` | PASS |
| §4.2 __post_init__ emotion·crossfade 검증 | `types.py:91-108` | PASS |
| §4.2 에러 메시지 튜플 순서(CHARACTER_SAESSAGI) | `types.py:93-102` tuple 리터럴 | PASS |
| §4.3 AvatarState.__init__ + default 검증 | `service.py:38-61` | PASS |
| §4.3 extract_emotion 동기 + TypeError | `service.py:81-98` + `tag_parser.py:27-71` | PASS |
| §4.3 push_event async + asyncio.Lock | `service.py:100-145` | PASS |
| §4.3 current_emotion·is_speaking·make_event | `service.py:68-75, 147-167` | PASS |
| §4.3 SendTextCallback 타입 alias | `service.py:25` | PASS |
| §5.1 D-2 첫 매칭 채택(유효 키 break) | `tag_parser.py:59-61` | PASS |
| §5.1 D-3 미지 키 → neutral + break | `tag_parser.py:62-66` | PASS |
| §5.1 D-6 `[emotion:study]` 미지 취급 | `_SPOKEN_EMOTIONS` 제외 + 동일 else 분기 | PASS |
| §5.2 완결 문자열 전제 (버퍼링 비보장) | `test_e4_incomplete_tag` | PASS |
| §6.4 공백 보존 | `re.sub("", text)`; N-3/N-4/E-5 테스트 | PASS |
| §7 송신 페이로드 정확 4키 | `service.py:126-131` + `test_payload_has_exactly_4_keys` | PASS |
| §8 TypeError(text, event) | `tag_parser.py:44-45`, `service.py:123-124` | PASS |
| §8 ValueError(emotion, crossfade, default) | `types.py:92-108`, `service.py:46-57` | PASS |
| §8 send_text 예외 전파 + `_last_*` 미갱신 + logger.error 1회 | `service.py:133-145` + `test_send_text_exception_logger_error_contains_emotion` | PASS |
| §8 CancelledError 전파 | `test_cancelled_error_propagates` | PASS |
| §9.3 동시성 Lock 직렬화 | `service.py:61, 133` + `test_n7_concurrent_push_event_order` | PASS (N=3은 MINOR) |
| §11.1 pytest/ruff/format 통과, 커버리지 ≥70% | 76/76 pass, 0 warnings(M_08 범위), ruff clean | PASS |
| §11.2 DoD "1줄 추가" 배선 | `service_context.py:216-218` | PASS |
| §11.2 DoD upstream `[happy]` 미매치 | `test_upstream_single_key_not_matched` | PASS |
| §11.2 DoD study emit + `"study"` 페이로드 | `test_n8_study_emit_via_push_event` | PASS |
| §13.1 M_08 builder "load_app_services 내 1줄 추가" | `service_context.py:216-218` | PASS |
| §13.3 M_08 builder가 수정하는 것 #1 | 동일 | PASS |
| §13.3 #2 test_service_context.py 업데이트 | `TestM08AvatarStateWiring` 2 tests | PASS |
| §16 docs/MODULES.md 갱신 | `docs/MODULES.md:281-314, 434` WIP 상태 유지 | PASS (DONE은 critic pass 후) |

## Test Coverage Analysis

| 스펙 테스트 ID | 구현 위치 | 상태 |
|---|---|---|
| N-1 단일 태그 | `test_n1_single_tag_extracted` | PASS |
| N-2 태그 없음 | `test_n2_no_tag` | PASS |
| N-3 다중 첫 채택 | `test_n3_multi_tag_first_wins` | PASS |
| N-4 대소문자 혼용 | `test_n4_case_insensitive` + `test_all_spoken_emotions_parse` | PASS |
| N-5 push_event 페이로드 | `test_n5_push_event_payload_and_state` | PASS |
| N-6 make_event 기본값 | `test_n6_make_event_defaults` | PASS |
| N-7 동시 순서 | `test_n7_concurrent_push_event_order` (3요소) | PASS (MINOR: N 작음) |
| N-8 study 직접 emit | `test_n8_study_emit_via_push_event` | PASS |
| E-1 빈 문자열 | `test_e1_empty_string` | PASS |
| E-2 태그만 | `test_tag_only_string` | PASS |
| E-3 중첩 브래킷 | `test_e3_nested_brackets` | PASS |
| E-4 미완결 태그 | `test_e4_incomplete_tag` | PASS |
| E-5 미지 키 neutral 폴백 | `test_e5_unknown_key_neutral_fallback` + 한글 `test_n4_korean_between_tags` | PASS |
| E-6 crossfade 경계 | `test_e6_crossfade_boundaries` + `test_types.py 4건` | PASS |
| E-7 push_event 실패 시 상태 불변 | `test_e7_push_event_failure_state_unchanged` | PASS |
| E-8 study → neutral + WARNING 1회 | `test_e8_study_tag_neutral_fallback` + `test_e8_study_tag_only` 모두 `== 1` | PASS |
| A-1 미지+유효, neutral 유지 + 로그 1회 | `test_a1_unknown_then_valid_neutral_wins` | PASS |
| A-2 XSS | `test_a2_xss_attempt` | PASS |
| A-3 10KB 성능 | `test_a3_very_long_input` (20ms) | PASS |
| A-4 비-str | `test_a4_non_string_inputs` | PASS |
| DoD upstream `[happy]` 미매치 | `test_upstream_single_key_not_matched` | PASS |
| DoD 페이로드 4키 정확 | `test_payload_has_exactly_4_keys` | PASS |
| DoD AppServiceContext 배선 | `TestM08AvatarStateWiring` 2건 | PASS |
| B2 회귀 (logger.error emotion 포함, 1회) | `test_send_text_exception_logger_error_contains_emotion` | PASS |

**Total avatar_state 모듈**: 49 tests(정상 7 + 엣지 9 + 적대적 4 + 보조 29) — DoD 하한(정상 ≥5, 엣지 ≥5, 적대적 ≥3) 충족.
**Total service_context 통합 테스트 (M_08 범위)**: 2 tests(none-before, injected-after). 배선 라인 삭제 시 `assert isinstance(ctx.avatar_state, AvatarState)`가 FAIL 내므로 회귀 검출 가능. 검증 완료.

### 배선 회귀 재현성 검증 (Fresh 관찰)

`tests/app/test_service_context.py:270-298` `test_avatar_state_injected_on_load_app_services`:
- `_make_ctx_raw()`로 인스턴스 생성 → `await ctx.load_app_services(app_cfg)` 호출 → `assert isinstance(ctx.avatar_state, AvatarState)` + `assert ctx.avatar_state.current_emotion == "neutral"`.
- 만약 `service_context.py:217`의 `self.avatar_state = AvatarState(default="neutral")` 라인을 삭제하면, `ctx.avatar_state`는 `__init__`에서 설정된 None 그대로이므로 `isinstance(None, AvatarState)`가 False → `AssertionError` 발생. FAIL 정확히 재현 가능. 
- 테스트는 mock을 쓰지 않고 실제 `AvatarState` 클래스 import 후 `isinstance` 검증 — 우회 불가.

### 외부 네트워크/보안 검증

- `src/avatar_state/**`에 `http`·`requests`·`fetch`·`urllib`·`socket` import 전무. 표준 라이브러리 `re`/`dataclasses`/`asyncio` + `loguru`만 사용.
- 새 의존성 0건 (스펙 §12.1 "pyproject.toml 수정 없음" 준수).
- PII 로그 마스킹: 로그에 들어가는 값은 (a) `event.emotion`(8종 enum), (b) `m.group(0)` (`[emotion:...]` 태그 원문). 사용자 개인정보 없음.
- 파일 쓰기 없음.

### 코드 품질

- 하드코딩된 경로·URL·비밀 없음.
- 중복·데드 코드: R2 NB-R2-3이 지적한 `if first_emotion is None` 분기는 제거되어 `first_emotion = "neutral"` 단순 대입으로 개선됨. 현재 dead code 없음.
- 네이밍: `_VALID_EMOTIONS`/`_SPOKEN_EMOTIONS` 분리와 주석이 D-6 의도를 명확히 전달.

## 검토하지 못한 영역

1. **프로덕션 실환경에서의 `load_app_services` 호출 체인**: 본 리뷰는 mock 환경에서의 테스트만 검증했다. 실제 `AppConfig` 로딩 경로에서 `upstream ServiceContext.__init__`이 여타 부작용(파일 읽기 등)을 일으키고 이후 `load_app_services`가 호출되는지는 M_01 테스트 통합 범위. 본 모듈 관점에서는 OK.
2. **M_05/M_06/M_11 소비자 측 `ctx.avatar_state` 사용 경로**: 아직 미구현. 본 리뷰 범위 밖이나 future critic이 해당 모듈 구현 시 `ctx.avatar_state is not None` 가드가 적절히 추가되는지 확인 필요.
3. **M_12 프론트 `avatar-state` 메시지 수신 핸들러**: 미구현. M_12 스펙 생성 시 §7 페이로드 스키마 일치 여부 확인 필요.

## Recommendation

**PASS.** 이전 두 라운드의 Blocking 4건(R1 B1/B2, R2 N-B1/N-B2)이 모두 실제 파일에서 해소되었고 새로운 Blocking 결함은 발견되지 않았다. 스펙 모든 § (4.1, 4.2, 4.3, 5.1, 5.2, 6.4, 7, 8, 9.3, 11.1, 11.2, 13.1, 13.3)이 코드·테스트에 정확히 반영된다. 배선 회귀 재현성도 확인했다.

단, 문서 드리프트 3건은 별도 CR-0x로 분리하거나 M_08 DONE 전 스펙 편집 커밋에서 일괄 정리 권고:
- 스펙 §5.1 L316, §8 표 L436의 `%r` → `{!r}` 수정.
- 스펙 §10 E-8 L562, §10.4 L590의 `caplog` → "loguru sink 헬퍼 또는 propagate 활성화된 caplog"로 수정.

`docs/MODULES.md` L284/L434의 M_08 상태를 `✅ DONE`으로 갱신하는 것은 본 PASS 직후 builder/integrator의 다음 커밋에서 수행하면 된다(Critic 자신이 문서를 수정하지 않음).
