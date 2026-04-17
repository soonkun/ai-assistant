# 03 — Phase 2: 모듈 반복 루프

**이 파일은 한 모듈마다 한 번씩 실행한다.** M_01부터 M_10(또는 M_12)까지 순서대로.

각 모듈은 4단계를 거친다: **Plan → Build → Validate → Critic**. 실패 시 fresh critic으로 재시도.

---

## 3-1. Plan 단계

```
Phase 2 모듈 M_<NN> <module_name>의 스펙 작성을 시작한다.

planner 에이전트를 호출:

입력:
- REQUIREMENTS.md의 §<관련 섹션>
- docs/ARCHITECTURE.md
- docs/MODULES.md에서 M_<NN> 항목
- (의존성이 있는 모듈이 이미 있다면) specs/M_<선행>_SPEC.md

산출물:
- specs/M_<NN>_<module_name>_SPEC.md
- 템플릿은 .claude/agents/planner.md 참조

제출 후 나에게 확인 질문:
"이 스펙으로 Builder에 넘겨도 되는가?"
내 승인 없이 Build 단계로 넘어가지 마라.
```

---

## 3-2. Build 단계

**새로운 Claude Code 세션에서 (`/clear` 후) 시작**

```
Phase 2 모듈 M_<NN> 구현을 시작한다.

builder 에이전트를 호출:

입력:
- specs/M_<NN>_<n>_SPEC.md (이게 너의 계약이다)
- REQUIREMENTS.md (참고)
- docs/MODULES.md (다른 모듈 API 참고용)

작업 순서:
1. 스펙 전체를 정독. 이해 안 되는 부분 있으면 멈추고 질문.
2. 테스트 먼저 작성 (tests/<module>/test_*.py). 전부 실패해야 정상.
3. src/<module>/ 에 구현. 최소로 시작.
4. ruff format && ruff check && mypy src/ && pytest 가 다 통과할 때까지 반복.
5. 구현 완료 보고 (.claude/agents/builder.md의 출력 형식대로).

절대 하지 말 것:
- 스펙을 벗어난 "개선"
- 스펙에 빠진 부분을 임의로 채움 (질문해라)
- 외부 네트워크 호출 추가
```

---

## 3-3. Validate 단계

**Build 단계 끝나면 같은 세션에서 이어서 실행**

```
validator 에이전트로 전환해 M_<NN> 모듈의 독립 검증을 수행해라.

.claude/agents/validator.md의 명령을 순서대로 실행하고,
원시 출력을 그대로 보고. 하나라도 FAIL이면 종합 판정 FAIL.
```

실패 시: Builder에 다시 돌려보내 같은 세션에서 수정. 수정 후 Validator 재실행. 3회 이상 실패하면 세션 중단하고 Planner에게 스펙 검토 요청.

---

## 3-4. Critic 단계

**반드시 `/clear`로 컨텍스트 초기화 후 새 세션에서 시작**

```
Phase 2 모듈 M_<NN> 적대적 리뷰를 시작한다.

critic 에이전트를 호출:

너는 이 구현을 처음 본다. Builder의 설명도, 이전 리뷰도 읽지 마라.
오직 스펙(specs/M_<NN>_*.md)과 코드(src/<module>/, tests/<module>/)만 본다.

.claude/agents/critic.md의 체크리스트 20개 항목을 모두 수행하고,
reviews/M_<NN>_<n>_REVIEW.md에 저장.

최종 판정:
- PASS: 심각·중대 결함 없음.
- FAIL: 심각 1개 이상 OR 중대 3개 이상.

FAIL 시 구체적인 파일:라인 근거와 함께 재작업 지시.
```

### 재검수 규칙

Critic이 FAIL을 주면:
1. Builder 세션으로 전환해서 지적 사항 수정.
2. Validator 재실행.
3. **새 Critic 세션을 띄운다** (`/clear` 후). 이전 리뷰를 모르는 새 Critic이 처음부터 20항목을 다시 본다.
4. 3회 연속 FAIL이면 Planner에게 돌려보내 스펙 재검토.

---

## 3-5. 모듈 종료

Critic PASS 시:
1. `docs/MODULES.md`에서 M_<NN>의 상태를 `✅ DONE`으로 갱신.
2. git commit.
3. 다음 모듈(M_<NN+1>)로 이동.

---

**모든 모듈이 DONE되면** `04_phase3_integration.md`로 이동.
