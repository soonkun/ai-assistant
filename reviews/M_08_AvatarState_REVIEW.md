# M_08 AvatarState Critic Review

Date: 2026-04-19
Verdict: FAIL

## Summary

구현 전체 형태·배선·테스트 카운트는 스펙의 외형 요건을 충족하지만, 두 가지 실재 결함이 남아 있다.
(1) **스펙 §5.1 의사코드와 `tag_parser.py:67` 구현이 모순된다.** 의사코드에는 else 분기 후 `break`가 없고 주석이 "이후 매치는 미지 키라도 폴백 덮어쓰기 하지 않음"이라고만 서술하여, 뒤에 등장하는 유효 키는 덮어쓰는 동작으로 읽힌다. 반면 §10 A-1 추가 케이스와 구현은 "뒤 유효 키 덮어쓰기 금지"를 요구한다. 스펙-코드 일관성이 깨져 있고 스펙 본문이 패치되지 않은 상태다.
(2) **`service.py:128-131` logger.error가 `%r` 포맷 지정자를 쓰고 있어 loguru가 이를 치환하지 못한다.** 실패 시 로그가 literally `"emotion=%r"`로 남아 §8 에러 정책의 "로그는 logger.error 1회" 요구가 사실상 무의미해진다.

두 건 모두 "조용한 실패"를 스펙이 금지(§8 "조용한 실패는 안 만든다"·D-5 근거)한다는 프로젝트 원칙에 직접 반하는 결함이므로 Blocking 으로 판정한다.

## Findings

### Blocking (FAIL 사유)

1. **[BLOCKING] `specs/M_08_AvatarState_SPEC.md` §5.1 의사코드와 `src/avatar_state/tag_parser.py:56-67` 구현 불일치.**
   - 스펙 §5.1 의사코드(304-318행)는 for 루프의 else 분기에 **break 가 없다**. 주석 "이후 매치는 미지 키라도 폴백 덮어쓰기 하지 않음"만으로는 "뒤에 오는 **유효** 키" 처리를 규정하지 못한다. 이 의사코드대로 실행하면 `[emotion:joy] [emotion:happy]` 입력에서 두 번째 루프 이터레이션이 `if key in _SPOKEN_EMOTIONS:` 분기에 들어가 `first_emotion = "happy"; break`로 "happy"를 반환한다.
   - 그러나 §10 A-1 "추가" 항(567-568행)은 `emotion == "neutral"` 을 단언하며, 구현자가 덧붙인 `tag_parser.py:66-67`의 `break`(else 분기 마지막)가 "neutral"을 유지시킨다.
   - 결과: 스펙 문서 내부(§5.1 vs §10 A-1)가 모순되고, 코드는 §10 쪽에 맞춰 의사코드를 무시했다. 빌더가 "의사코드와 테스트가 모순돼 break 추가"로 정정했다는 보고가 있었다면 **스펙 §5.1 의사코드 자체를 패치**해 의사코드에도 else 분기 끝에 `break`를 명시하거나 주석을 "이후 매치(유효 키 포함)를 모두 무시"로 수정해야 한다. 현재 스펙 본문은 패치되지 않았다.
   - CLAUDE.md "specs/M_NN_SPEC.md 없이 src/에 파일을 만드는 것"·"스펙에 없는데 자의적으로 추가된 동작" 금지 규정과 직접 충돌. 권고 조치: 스펙 §5.1 의사코드를 다음으로 수정한다.
     ```
     else:
         logger.warning(...)
         if first_emotion is None:
             first_emotion = "neutral"
         break  # 첫 등장 미지 키가 neutral 로 확정되면 루프 종료
     ```
   - 또는 스펙의 주석을 유지한 채 코드의 `break`를 제거하고 §10 A-1 추가 케이스의 기대값을 `emotion == "happy"`로 바꾸어야 한다. 어느 쪽이든 스펙-코드 일관성 복구 전까지 PASS 불가.

2. **[BLOCKING] `src/avatar_state/service.py:128-131` logger.error 포맷 문자열이 loguru 컨벤션을 위반하여 emotion 값이 로그에 기록되지 않는다.**
   - 해당 줄:
     ```python
     logger.error(
         "push_event: send_text 실패 (emotion=%r). 상태 미갱신.",
         event.emotion,
     )
     ```
   - loguru는 brace-style `{}`만 해석한다(`{!r}` 등). `%r`은 literal로 출력되며 `event.emotion` 인자는 소리없이 무시된다. 실제 실행 로그 예:
     ```
     ERROR | avatar_state.service:push_event:128 - push_event: send_text 실패 (emotion=%r). 상태 미갱신.
     ```
   - 스펙 §8 "조용한 실패는 안 만든다" 원칙을 정면으로 위배한다. 운영자가 로그에서 어느 감정이 실패했는지 식별할 수 없다.
   - 동일 모듈의 `tag_parser.py:63`은 `"unknown emotion tag: {!r}"` 식으로 올바르게 brace-style을 쓰고 있으므로 **구현자 자체가 컨벤션을 알고 있었다**. 이 한 줄의 정규화 누락은 리뷰 통과 전에 반드시 고쳐야 한다.
   - 권고 조치: `"push_event: send_text 실패 (emotion={!r}). 상태 미갱신."` 로 교체. 테스트에도 로그 내용 단언(`'happy'` 문자열 포함 여부)을 최소 1개 추가해 회귀 방지.

### Non-blocking (개선 권고)

1. **[MAJOR] §10 A-1 테스트가 로그 횟수 1회를 단언하지 않는다.**
   - 스펙 §10 A-1 "추가" 항: "로그 1회." 그러나 `tests/avatar_state/test_extract_emotion.py::test_a1_unknown_then_valid_neutral_wins`는 `any("joy" in w for w in warnings)`만 확인하고 `len(warnings) == 1`을 단언하지 않는다. 현재 구현(break 있음)이라도 로그가 1회임을 테스트로 고정해야 §5.1·§10 간 서로 다른 해석이 재등장했을 때 회귀가 감지된다.
   - 권고: `assert len(warnings) == 1` 추가.

2. **[MAJOR] `test_e8_study_tag_neutral_fallback`·`test_e8_study_tag_only` 가 스펙 §10 E-8 "WARNING 레벨 1건" 단언을 약화시켰다.**
   - 스펙 §10 E-8: "`caplog`에 `WARNING` 레벨 1건이 기록되며 메시지에 `"[emotion:study]"` 문자열 포함." 구현은 caplog 대신 loguru sink를 자체 구현(옳은 선택)했으나, 첫 테스트는 "`[emotion:study]` 문자열 포함"만 검사하고 두 번째는 `len(warnings) >= 1`만 검사한다. 정확한 "1건" 단언이 빠져 있어 향후 이중 로그 회귀를 놓칠 수 있다.
   - 권고: 두 테스트 모두 `len(warnings) == 1`로 고정.

3. **[MAJOR] `caplog` 사용 요구를 test 헬퍼로 우회한 것은 정당하지만, 스펙 §10 E-8·A-1 기재 자체를 정정해야 한다.**
   - 스펙 §10 E-8: "caplog 에 WARNING 레벨 1건". 현 테스트는 `_capture_warnings` 헬퍼(loguru sink)로 우회. 이 자체는 loguru의 `caplog` 미연동 특성상 옳은 선택이며 실제 로그가 실제로 emit됨을 검증한다. 다만 스펙 §10 E-8과 §10.4 "로깅 검증은 `caplog` fixture로"가 현실과 어긋난다.
   - 권고: 스펙 §10.4의 "`caplog` fixture" 문구를 "loguru sink 기반 헬퍼 또는 `caplog`(단, loguru는 propagate 필요)"로 갱신.

4. **[MAJOR] `tag_parser.py` 의 "첫 등장 미지 키"가 자체 Early Break 되는 동작이, §10 A-1의 본문(565-566행)과는 별개로 "unknown → unknown → valid" 흐름에서도 valid 키를 가린다.**
   - 실증: `extract_emotion("[emotion:joy] [emotion:weird] [emotion:happy]")` 반환 = `("  ", "neutral")`, warning 1회(첫 번째만), 두 번째 unknown(`weird`)은 경고조차 기록되지 않는다.
   - 스펙 §5.1 의사코드에는 (break가 없으므로) 두 unknown 각각에 대해 warning이 나야 하고 세 번째에서 valid 를 채택해야 한다.
   - 위 Blocking 1번을 어떻게 결정하느냐에 따라 이 동작이 옳을 수도 있지만, 어느 쪽이든 스펙과 코드가 같은 의미로 서술되어야 한다. 최소한 A-1 테스트에 "unknown → unknown → valid" 서브 케이스를 추가해 고정할 것.

5. **[MAJOR] sync callable 주입에 대한 방어/문서화 부재.**
   - 스펙 §4.3: `SendTextCallback = Callable[[dict[str, Any]], Awaitable[None]]`. 동기 함수가 주입되면 `await send_text(payload)`가 `TypeError: object NoneType can't be used in 'await' expression` 류 예외로 실패한다. 테스트에 이 시나리오가 없고 구현에도 런타임 타입 체크가 없다.
   - 권고: `A-5` 같은 적대적 테스트 1건 추가(동기 함수 주입 → TypeError 전파), 또는 스펙 §14에 "동기 send_text 주입은 호출자 책임"을 명시.

6. **[MINOR] 에러 메시지 정렬 순서와 §4.1 D-1 "순서 고정" 의도 불일치.**
   - 스펙 §4.1: "순서도 해당 문서 순으로 고정하여 로그·테스트 가독성 향상." 그러나 `types.py:94`와 `service.py:47`의 `sorted(_VALID_EMOTIONS)`는 alphabetical 정렬이라 CHARACTER_SAESSAGI 순서(neutral, happy, surprised, sad, worried, thinking, sleepy, study)가 아니다.
   - 권고: 정렬 대신 Literal 선언 순서를 반영하는 상수 tuple `_VALID_EMOTIONS_ORDERED`를 두고 에러 메시지에 그걸 쓰거나, 스펙의 "순서 고정" 문구를 완화.

7. **[MINOR] `tag_parser.py:65`의 `if first_emotion is None` 검사는 `break`가 있기에 항상 True다(Dead code).**
   - 현재 코드는 첫 번째 else 진입 시 무조건 break 하므로 `first_emotion`이 그 시점에 None이 아닐 수 없다(이전 iteration에서 valid 라면 이미 break). 즉 `if first_emotion is None:` 은 항상 참. 읽기 어려움.
   - 권고: Blocking 1번을 스펙 의사코드 패치로 해결하면 이 if 조건은 의미를 되찾는다(break 제거 버전). 현재 code 유지 시에는 if 제거하고 바로 `first_emotion = "neutral"`.

8. **[MINOR] `src/app/service_context.py:215-223`의 M_08 배선이 `try/except Exception:` 광범위 캐치.**
   - CLAUDE.md 체크리스트 C-10: "`except Exception:` 같은 광범위 캐치가 있나?" — `AvatarState.__init__`이 실패할 수 있는 유일한 경로는 `ValueError` (default 검증)인데 `default="neutral"` 고정 호출이라 절대 실패할 수 없다. 이 try/except는 불필요하며 오히려 실패를 삼킨다.
   - 권고: try/except 제거 후 `self.avatar_state = AvatarState(default="neutral")` 한 줄로 단순화.

9. **[MINOR] `tests/avatar_state/test_extract_emotion.py:28` callable 타입 annotation 오타.**
   - `def _capture_warnings(func: "callable") -> "tuple[object, list[str]]":` — 소문자 `callable`은 타입이 아니라 내장 함수. `Callable[[], object]` 또는 `Callable[[], tuple[str, ...]]` 이어야 한다.
   - 영향: mypy 는 문자열 annotation 이라 통과하지만 의도 전달 실패. ruff RUF100 등에서 잡힐 수 있음.

10. **[MINOR] `AvatarEvent(speaking=truthy_string)` 런타임 방어 없음.**
    - 스펙 §8 E-7은 "mypy로만 차단"을 명시하므로 스펙 정합성은 있다. 다만 M_06/M_11 같은 외부 호출자가 `AvatarEvent(speaking="yes")` 같이 호출하면 타입 힌트 없이 조용히 진행되어 프론트의 `payload["speaking"]`이 문자열이 되고 M_12가 오동작할 여지가 있다. 주의 사항으로만 기록.

## Spec Alignment

| 스펙 항목 | 구현 위치 | 상태 |
|---|---|---|
| §4.1 Emotion Literal 8종 | `src/avatar_state/types.py:20-29` | PASS |
| §4.1 `_VALID_EMOTIONS`·`_SPOKEN_EMOTIONS` 분리·불변(frozenset) | `types.py:32-57` | PASS |
| §4.2 AvatarEvent frozen+slots | `types.py:72` | PASS |
| §4.2 AvatarEvent 검증(`_VALID_EMOTIONS` 경로, crossfade 200-300) | `types.py:91-100` | PASS |
| §4.3 AvatarState.__init__ signature + default 검증 | `service.py:38-51` | PASS |
| §4.3 extract_emotion signature | `service.py:71-88` + `tag_parser.py:27-72` | PASS |
| §4.3 push_event signature + asyncio.Lock | `service.py:90-135` | PASS(단 로그 버그 존재) |
| §4.3 current_emotion·is_speaking·make_event | `service.py:57-65,137-157` | PASS |
| §5.1 D-2 첫 매칭 채택 | `tag_parser.py:57-67` | 모호 (Blocking 1번 참조) |
| §5.1 D-3 미지 키 → neutral | `tag_parser.py:62-66` | 모호 (Blocking 1번 참조) |
| §5.1 D-6 `[emotion:study]` → neutral | 동일 경로 (`_SPOKEN_EMOTIONS` 부재) | PASS |
| §6.4 공백 보존 | `re.sub("", text)` | PASS (테스트 N-3,E-5 확인) |
| §7 송신 페이로드 스키마 | `service.py:116-121` | PASS (테스트 `test_payload_has_exactly_4_keys`) |
| §8 crossfade 범위 외 → ValueError | `types.py:96-100` | PASS |
| §8 default 8종 외 → ValueError | `service.py:46-47` | PASS |
| §8 send_text 예외 전파 + 상태 미갱신 + 로그 1회 | `service.py:123-135` | FAIL (로그 포맷 버그, Blocking 2번) |
| §9.3 동시성 Lock 직렬화 | `service.py:123` + 테스트 N-7 | PASS |
| §11.1 pytest/ruff/mypy/coverage 통과 | 전체 496건 pass, 커버리지 100% | PASS |
| §11.2 upstream `[<key>]` 미매치 | `test_upstream_single_key_not_matched` | PASS |
| §13 AppServiceContext 배선 1줄 | `service_context.py:215-223` (9줄로 비대) | PARTIAL (과도한 try/except, Non-blocking 8번) |
| §16 docs/MODULES.md 갱신 | `docs/MODULES.md:284,314` | PASS |

## Test Coverage Analysis

| 스펙 테스트 ID | 구현 위치 | 상태 |
|---|---|---|
| N-1 단일 태그 | `test_extract_emotion.py::test_n1_single_tag_extracted` | PASS |
| N-2 태그 없음 | `test_n2_no_tag` | PASS |
| N-3 다중 태그 첫 채택 | `test_n3_multi_tag_first_wins` | PASS |
| N-4 대소문자 혼용 | `test_n4_case_insensitive` | PASS |
| N-5 push_event 페이로드 | `test_push_event.py::test_n5_push_event_payload_and_state` | PASS |
| N-6 make_event 기본값 | `test_n6_make_event_defaults` | PASS |
| N-7 동시 순서 | `test_n7_concurrent_push_event_order` | PASS (3개로만 검증, 권고: 5+개) |
| N-8 study 직접 emit | `test_n8_study_emit_via_push_event` | PASS |
| E-1 빈 문자열 | `test_e1_empty_string` | PASS |
| E-2 태그만 | `test_tag_only_string` | PASS |
| E-3 중첩 브래킷 | `test_e3_nested_brackets` | PASS |
| E-4 미완결 태그 | `test_e4_incomplete_tag` | PASS |
| E-5 한글 사이 공백 없음 | `test_n4_korean_between_tags` | PASS (N 분류지만 실질 E-5) |
| E-6 crossfade 경계값 | `test_e6_crossfade_boundaries` + test_types 4건 | PASS |
| E-7 push_event 실패 시 상태 불변 | `test_e7_push_event_failure_state_unchanged` | PASS |
| E-8 `[emotion:study]` 미지 키 취급 | `test_e8_study_tag_neutral_fallback` + `test_e8_study_tag_only` | PASS (로그 1건 단언 부재, Non-blocking 2번) |
| A-1 미지 키 + neutral | `test_a1_unknown_then_valid_neutral_wins` | PASS (로그 1회 단언 부재, Non-blocking 1번) |
| A-2 XSS | `test_a2_xss_attempt` | PASS |
| A-3 10KB 성능 | `test_a3_very_long_input` (20ms 단언) | PASS |
| A-4 비-str 입력 | `test_a4_non_string_inputs` | PASS |

총 구현 테스트 카운트: **49건** (스펙 최소 18건, DoD 정상≥5/엣지≥5/적대적≥3 모두 충족).
커버리지: **100%** (src/avatar_state/ 전체, 84 stmts).

## Recommendation

**FAIL.** Blocking 1(스펙-코드 불일치)과 Blocking 2(로그 포맷 버그)를 다음 조치로 해소한 뒤 fresh critic 에게 재검수 요청:

1. 스펙 `§5.1` 의사코드에 `break`를 명시하거나 주석을 "이후 매치(유효 키 포함)를 모두 무시"로 수정해 테스트 A-1 의도와 일치시킨다.
2. `src/avatar_state/service.py:128-131`의 로그 포맷을 `%r` → `{!r}` 로 교정하고, emotion 값이 실제로 로그에 남는지 확인하는 단위 테스트(예: loguru sink 캡처 후 `"'happy'"` 문자열 포함 단언) 1건 추가.
3. 아래 비차단 결함들도 함께 처리하면 재검수 속도 향상:
   - Non-blocking 1, 2 (로그 1건 단언 추가)
   - Non-blocking 8 (service_context 과도한 try/except 정리)
   - Non-blocking 9 (테스트 callable annotation 정정)

위 Blocking 2건만 해결되면 PASS 가능 상태로 본다.
