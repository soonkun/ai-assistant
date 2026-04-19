# M_08 AvatarState Critic Review — Round 2

Date: 2026-04-19
Verdict: FAIL
Previous verdict: FAIL (reviews/M_08_AvatarState_REVIEW.md)

## Summary

이전 Round 1 FAIL 사유 중 "스펙 §5.1 의사코드 불일치"(B1)와 "logger.error 포맷 `%r` 버그"(B2)는 모두 실제 파일에서 해소되었음을 확인했다. Non-blocking 지적 중 A-1/E-8 로그 1회 단언(NB1), 에러 메시지 tuple 순서(NB3), 테스트 Callable 타입 annotation(NB4)도 반영됐다.

그러나 **새로운 Blocking 결함 2건을 발견**했다. (1) 이전 NB2("service_context.py M_08 초기화 try/except 과잉")의 수정 과정에서 **배선 블록 자체가 삭제되었다**. 현재 `load_app_services`는 `avatar_state`를 생성하지 않으며 스펙 §11.2 DoD "AppServiceContext.avatar_state 주입 경로가 `load_app_services`에 1줄 추가"와 §13.1, §13.3 "M_08 builder가 수정하는 것 — 1. `load_app_services` 내 1줄"을 정면 위배한다. (2) `service_context.py:20`의 TYPE_CHECKING import가 `from typing import Any as AvatarState`인 채로 남아있어 실제 타입 힌트로 작동하지 않는다.

두 결함 모두 M_08 모듈 자체(src/avatar_state/**)는 정상이지만 **통합 지점에서 스펙 계약이 깨져 있다**. M_08을 "완료"로 선언하기에 부족하므로 FAIL.

## Previous Findings Re-verified

| 지적 ID | 설명 | 현 상태 | 증거 |
|---|---|---|---|
| B1 (Blocking) | 스펙 §5.1 의사코드에 `break` 누락, tag_parser.py 구현과 불일치 | **해소** | `specs/M_08_AvatarState_SPEC.md:314, 318` 양쪽 분기 모두 `break` 명시. 주석도 "이후 매치(유효 키 포함)를 모두 무시"로 업데이트됨. `tag_parser.py:61,67`의 `break`와 의미 일치. |
| B2 (Blocking) | service.py logger.error가 `%r` (stdlib style) — loguru 미치환 | **해소** | `service.py:138-141`이 brace-style `{!r}` 사용. 테스트 `test_send_text_exception_logger_error_contains_emotion` (`test_push_event.py:214-233`)이 loguru sink로 캡처하여 `"sad" in records[0]` 단언, 실제 치환 작동 확인. |
| NB1 | A-1/E-8 테스트가 `logger.warning` 1회 호출 단언 부재 | **부분 해소** | A-1 (`test_extract_emotion.py:197`) `assert len(warnings) == 1` 추가됨. E-8 메인 테스트(`L168`)도 추가됨. 단 `test_e8_study_tag_only`(`L176`)는 여전히 `len(warnings) >= 1`로 약함. MINOR로 잔존. |
| NB2 | service_context.py M_08 초기화 try/except 과잉 | **과교정 (블록 전체 삭제)** — **새 Blocking 유발** | `load_app_services` 내 M_08 배선 라인 자체가 없음. `ctx.avatar_state`는 영원히 None. 아래 New Finding B-R2-1 참조. |
| NB3 | 에러 메시지가 `sorted()` 호출, Literal 선언 순서 아님 | **해소** | `types.py:93-102`, `service.py:47-56` 모두 tuple 리터럴로 선언 순서 고정. |
| NB4 | `test_extract_emotion.py:28` callable 소문자 annotation | **해소** | `test_extract_emotion.py:30` `Callable[[], Any]`로 수정. `collections.abc.Callable` import됨. |

## New Findings

### Blocking

1. **[BLOCKING B-R2-1] `src/app/service_context.py::load_app_services`에 M_08 배선 라인이 없다 — 스펙 §11.2 DoD 위반.**
   - 스펙 §11.2 DoD(L619): "AppServiceContext.avatar_state 주입 경로가 `src/app/service_context.py::load_app_services`에 1줄 추가"
   - 스펙 §13.1(L671): "단지 `load_app_services` 메서드 내부에서 `None` 대신 `AvatarState(default="neutral")`을 할당하는 **1줄 추가**만 수행"
   - 스펙 §13.3(L704): "M_08 builder가 수정하는 것: 1. `src/app/service_context.py::load_app_services` 내 1줄"
   - 현재 `service_context.py:196-250`에 `AvatarState` 생성 호출이 **0건**. `__init__`(L41)에서 `self.avatar_state: "AvatarState | None" = None` 초기화 후 어떤 메서드도 이 필드를 갱신하지 않는다.
   - 증거: `rg "avatar_state" src/` 결과 `service_context.py`에는 L20·L41 두 곳뿐이고 실제 인스턴스화 없음. `tests/app/test_service_context.py:41`의 `assert ctx.avatar_state is None`이 이 누락된 상태를 테스트로 고정 — 배선 추가 시 이 단언도 함께 변경해야 한다.
   - 파급: M_05 `GemmaChatAgent`, M_06 `DocumentIngest`, M_11 `ProactiveDispatcher` 등 M_08 소비자가 실제 사용 시점에 `self.avatar_state`가 `None`이므로 아바타 이벤트 송신 불가. 본 모듈 src/tests 는 100% 통과하지만 **프로젝트 레벨에서 M_08은 죽어 있다.**
   - 원인 추정: 이전 리뷰 NB2("try/except 과잉 사용") 수정자가 try/except를 제거하는 대신 블록 전체를 삭제한 과교정(overcorrection). 이전 리뷰의 권고는 "단순 1줄로 만들라"였지 "삭제하라"가 아니었다.
   - 권고 조치: `load_app_services` 내 M_09 CalendarService 배선(L205-213) 뒤에 다음 1줄 추가:
     ```python
     from avatar_state import AvatarState
     self.avatar_state = AvatarState(default="neutral")
     ```
     그리고 `tests/app/test_service_context.py:41`의 단언을 적절히 갱신(`assert ctx.avatar_state is not None` 또는 load_app_services 이후 시점 테스트 추가).

2. **[BLOCKING B-R2-2] `src/app/service_context.py:20`의 TYPE_CHECKING alias가 실제 타입을 import하지 않는다.**
   - 해당 줄: `from typing import Any as AvatarState`
   - 주석(L15-16): "각 모듈 구현 완료 후 실제 타입으로 교체할 것"
   - M_08 구현은 완료되었으나 alias가 그대로다. 이로 인해 `self.avatar_state: "AvatarState | None"`(L41) 타입 힌트는 사실상 `Any | None` = `Any`로 붕괴. mypy가 M_08 소비자(M_05 등)의 `ctx.avatar_state.push_event(...)` 호출 시 타입 검증을 하지 못한다.
   - 비교: M_09 CalendarService(`service_context.py:207`)는 `from calendar_service.service import CalendarService`로 정식 import, 정확한 타입 힌트 확보. M_08만 누락.
   - 권고 조치: L20을 제거하고 L17-22의 TYPE_CHECKING 블록에 `from avatar_state import AvatarState` 추가(또는 파일 상단 정식 import).

### Non-blocking

1. **[MAJOR NB-R2-1] `test_e8_study_tag_only`(`test_extract_emotion.py:176`)의 warning 개수 단언이 여전히 `>= 1`.**
   - 이전 리뷰 NB1·NB2가 "로그 1건 단언 추가"를 권고했고 메인 E-8 케이스는 반영됐으나 서브 케이스는 누락. 회귀 방지 약화.
   - 권고: `assert len(warnings) == 1`로 강화.

2. **[MAJOR NB-R2-2] 스펙 §8 에러 정책 표(L436)와 §10 E-8(L562)이 `caplog` 및 `%r` 사용을 여전히 명시.**
   - 실제 구현은 loguru sink 기반 헬퍼(`_capture_warnings`)와 `{!r}`로 바뀌었음에도 스펙 본문은 업데이트되지 않았다. 이전 리뷰 NB3 "스펙 §10.4의 caplog fixture 문구 갱신"이 반영되지 않음.
   - §8 표(L436) `logger.warning("unknown emotion tag: %r", raw_tag)` 의사코드도 loguru 포맷으로 통일해야 일관성 확보.
   - 이 자체는 runtime 동작에 영향 없으므로 non-blocking이지만, 스펙-구현 이원화 상태는 미래 regression 위험.

3. **[MINOR NB-R2-3] `tag_parser.py:64-65`의 `if first_emotion is None: first_emotion = "neutral"`는 dead branch 수준으로 자명.**
   - 현재 구현상 else 분기에 진입하는 순간 `first_emotion`은 반드시 None. 루프는 첫 else 진입에서 break하므로 이 if가 실행되는 유일한 경로는 `first_emotion is None` 일 때뿐. 의도(미래에 break가 없어질 경우의 안전장치)는 이해하나 현 코드만 보면 조건문이 무의미.
   - 권고: 주석 추가로 "의사코드 §5.1 단계 4 보수 형태 유지" 명시 또는 조건 제거.

4. **[MINOR NB-R2-4] `test_push_event.py:22-44` `_capture_errors_async` 헬퍼의 예외 다시 throw 패턴이 과잉.**
   - `except Exception` 후 `exc_to_raise` 저장 → finally에서 handler 제거 → re-raise. `try/finally`만 쓰고 `except`를 생략해도 동일 동작이며 더 간결. 실제 loguru sink 정리는 finally만으로 충분.
   - 권고: 단순화(`try: result = await ... finally: logger.remove(handler_id)`).

5. **[MINOR NB-R2-5] `test_push_event.py:214-233` B2 회귀 테스트가 `_capture_errors_async` 헬퍼를 쓰지 않고 인라인으로 중복 작성.**
   - 이미 헬퍼가 정의되어 있는데 회귀 테스트만 별도 패턴으로 작성돼 코드 스타일 불일치. 헬퍼 사용으로 통일 가능.

6. **[MINOR NB-R2-6] `docs/MODULES.md:25`의 ASCII 다이어그램에 M_08이 M_04 옆에 배치되어 있지만 "M_08 AvatarState" 가 M_04 TTS의 자매로 보일 수 있다.**
   - 다이어그램 L23-25의 칼럼 정렬로 "M_02 ASR / M_03 VAD / M_04 TTS / M_05 LLM / M_08 Avatar / M_10 Idle / M_11 Proactive"는 단순 나열이지만 화살표 위치가 M_04/M_05/M_08을 같은 parent로 묶는 것으로 오해 소지. 구현 내용에 영향 없음, 문서 개선 제안.

## Spec Alignment

| 스펙 항목 | 구현 위치 | 상태 |
|---|---|---|
| §4.1 Emotion Literal 8종 | `types.py:20-29` | PASS |
| §4.1 `_VALID_EMOTIONS`·`_SPOKEN_EMOTIONS` 분리, frozenset | `types.py:32-57` | PASS |
| §4.1 D-6 `_VALID_EMOTIONS − _SPOKEN_EMOTIONS == {"study"}` | `test_types.py:25-27` | PASS |
| §4.2 AvatarEvent frozen+slots | `types.py:72` | PASS |
| §4.2 __post_init__ 검증(emotion·crossfade) | `types.py:91-108` | PASS |
| §4.3 AvatarState.__init__ + default 검증 | `service.py:38-61` | PASS |
| §4.3 extract_emotion 시그니처 | `service.py:81-98` + `tag_parser.py:27-72` | PASS |
| §4.3 push_event 시그니처 + asyncio.Lock | `service.py:100-145` | PASS |
| §4.3 current_emotion·is_speaking·make_event | `service.py:67-75, 147-167` | PASS |
| §5.1 D-2 첫 매칭 채택 | `tag_parser.py:57-67` (break 2회) | PASS |
| §5.1 D-3 미지 키 → neutral + break | `tag_parser.py:62-67` | PASS |
| §5.1 D-6 `[emotion:study]` 미지 취급 | `_SPOKEN_EMOTIONS`에서 study 제외 | PASS |
| §6.4 공백 보존 | `re.sub("", text)` | PASS |
| §7 송신 페이로드 4키 스키마 | `service.py:126-131` | PASS |
| §8 ValueError(crossfade·default) | `types.py:104-108`, `service.py:46-57` | PASS |
| §8 TypeError(text/event) | `tag_parser.py:44-45`, `service.py:123-124` | PASS |
| §8 send_text 예외 전파 + `_last_*` 미갱신 + logger.error 1회 | `service.py:133-145` + B2 회귀 테스트 | PASS |
| §9.3 동시성 Lock | `service.py:61, 133` + N-7 | PASS |
| §11.1 pytest/ruff/mypy | 50 pass, ruff clean, mypy clean, coverage 100% | PASS |
| §11.2 AppServiceContext 배선 1줄 | `service_context.py::load_app_services` | **FAIL (B-R2-1)** |
| §13.1 "1줄 추가" | 동일 | **FAIL (B-R2-1)** |
| §13.3 "builder가 수정하는 것 #1" | 동일 | **FAIL (B-R2-1)** |
| §16 docs/MODULES.md 갱신 | `docs/MODULES.md:281-314` | PASS |

## Test Coverage Analysis

| 스펙 테스트 ID | 구현 위치 | 상태 |
|---|---|---|
| N-1 단일 태그 | `test_n1_single_tag_extracted` | PASS |
| N-2 태그 없음 | `test_n2_no_tag` | PASS |
| N-3 다중 첫 채택 | `test_n3_multi_tag_first_wins` | PASS |
| N-4 대소문자 혼용 | `test_n4_case_insensitive` + `test_all_spoken_emotions_parse` | PASS |
| N-5 push_event 페이로드 | `test_n5_push_event_payload_and_state` | PASS |
| N-6 make_event 기본값 | `test_n6_make_event_defaults` | PASS |
| N-7 동시 순서 | `test_n7_concurrent_push_event_order` | PASS |
| N-8 study 직접 emit | `test_n8_study_emit_via_push_event` | PASS |
| E-1 빈 문자열 | `test_e1_empty_string` | PASS |
| E-2 태그만 | `test_tag_only_string` (Normal 클래스에 배치) | PASS |
| E-3 중첩 브래킷 | `test_e3_nested_brackets` | PASS |
| E-4 미완결 태그 | `test_e4_incomplete_tag` | PASS |
| E-5 미지 키 (한글 사이 삽입은 `test_n4_korean_between_tags`) | `test_e5_unknown_key_neutral_fallback` + `test_n4_korean_between_tags` | PASS |
| E-6 crossfade 경계 | `test_e6_crossfade_boundaries` + `test_types.py 4건` | PASS |
| E-7 push_event 실패 시 상태 불변 | `test_e7_push_event_failure_state_unchanged` | PASS |
| E-8 study 폴백 | `test_e8_study_tag_neutral_fallback` (log 1 단언 OK) + `test_e8_study_tag_only` (log `>=1` 약함, NB-R2-1) | PASS (부분 약화) |
| A-1 미지+유효 | `test_a1_unknown_then_valid_neutral_wins` (log 1 단언 OK) | PASS |
| A-2 XSS | `test_a2_xss_attempt` | PASS |
| A-3 10KB 성능 | `test_a3_very_long_input` (20ms 단언) | PASS |
| A-4 비-str | `test_a4_non_string_inputs` | PASS |
| DoD upstream `[happy]` 미매치 | `test_upstream_single_key_not_matched` | PASS |
| DoD 페이로드 4키 | `test_payload_has_exactly_4_keys` | PASS |
| B2 회귀(logger.error emotion 포함) | `test_send_text_exception_logger_error_contains_emotion` | PASS (신규) |

**총 테스트 카운트**: 50건 (정상 8 + 엣지 10 + 적대적 7 + 기타 25). 스펙 하한(정상 ≥5, 엣지 ≥5, 적대적 ≥3) 충족.
**커버리지**: `src/avatar_state/` 100% (86 stmts, 0 miss).
**미충족**: `tests/app/test_service_context.py`에 M_08 배선 결과 테스트 부재(B-R2-1과 동일 원인).

## Recommendation

**FAIL.** 다음 조치로 Blocking 2건을 해소한 뒤 fresh critic 재검수 요청:

1. **B-R2-1 해소**: `src/app/service_context.py::load_app_services` 내 M_09 배선(L213) 직후에 다음 블록 추가:
   ```python
   # M_08: AvatarState 배선 (load_app_services 내 1줄 추가, 스펙 §13.1)
   from avatar_state import AvatarState
   self.avatar_state = AvatarState(default="neutral")
   logger.info("AvatarState 초기화 완료")
   ```
   과도한 try/except 없이 단순 1~3줄만. `AvatarState(default="neutral")`는 스펙 §8 표에 따라 절대 실패하지 않는다.

2. **B-R2-2 해소**: `service_context.py:20`의 `from typing import Any as AvatarState`를 제거하고 `from avatar_state import AvatarState`로 교체. TYPE_CHECKING 블록 내 위치 유지 가능.

3. **테스트 갱신**: `tests/app/test_service_context.py:41`의 `assert ctx.avatar_state is None`을 `load_app_services` 호출 전/후 시나리오에 맞게 분리. 예:
   - `ctx.__init__` 직후: `assert ctx.avatar_state is None`
   - `await ctx.load_app_services(app_config)` 이후: `assert isinstance(ctx.avatar_state, AvatarState)` 및 `assert ctx.avatar_state.current_emotion == "neutral"`

4. **Non-blocking 병행 처리 (재검수 속도 향상)**:
   - NB-R2-1: `test_e8_study_tag_only` 로그 카운트 `== 1` 단언 강화
   - NB-R2-2: 스펙 §8 표와 §10 E-8/§10.4 문구를 loguru 기반으로 업데이트
   - NB-R2-3: `tag_parser.py:64-65` dead-equivalent 조건에 의도 주석 추가

Blocking 2건만 해소되면 M_08 PASS 가능 상태로 본다. 본 모듈 코어(src/avatar_state/**) 자체는 품질 양호하다.
