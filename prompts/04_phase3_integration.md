# 04 — Phase 3: 통합·E2E

모든 모듈이 Critic PASS된 후 실행한다.

---

## 프롬프트

```
Phase 3 통합을 시작한다.

integrator 에이전트를 호출:

입력:
- REQUIREMENTS.md (사용자 시나리오 원천)
- docs/ARCHITECTURE.md
- 모든 specs/ 와 src/

1단계: E2E 시나리오 작성
- tests/e2e/SCENARIOS.md
- REQUIREMENTS §1~§7 의 각 기능당 1~2개 시나리오
- 최소 15개

시나리오 예시는 .claude/agents/integrator.md 참조.

나에게 확인 질문:
"이 시나리오 목록이 사용자가 실제로 할 일을 충분히 커버하는가?"
내 승인 후 2단계로.

2단계: 시나리오를 실제 테스트로 구현
- tests/e2e/test_*.py
- 각 시나리오당 하나의 테스트 함수
- 실제 모듈을 호출하되, 외부 의존(마이크·스피커·실시간)은 필요한 만큼만 페이크.

3단계: 실행 및 결과 기록
- pytest tests/e2e/ -v
- docs/E2E_RESULTS.md에 각 시나리오 PASS/FAIL 기록

4단계: 실패 분석
- 단일 모듈 결함 → 해당 모듈 M_<NN>로 critic 재호출 후 Phase 2 루프.
- 모듈 간 계약 위반 → planner로 돌려 인터페이스 수정.
- 절대 integrator가 src/ 코드를 직접 고치지 마라.

5단계: 수용 기준 문서
- docs/ACCEPTANCE.md
- 각 요구사항별 "사용자 관점에서 이러면 OK" 기술
- 수동 검증이 필요한 항목은 체크리스트로

최종 산출물 요약 보고:
- 완료된 모듈 수
- E2E 시나리오 PASS 비율
- 남은 기술 부채 (IMPROVEMENT_IDEAS.md 참조)
- 다음 릴리즈(v2)로 넘길 항목
```

---

## 배포 준비 (Phase 4, 선택)

통합이 끝나면 오프라인 인스톨러 번들을 만든다.

```
배포 번들 생성:

1. scripts/bundle_deps.sh 실행 — 모든 Python 휠, npm 패키지, 모델 GGUF를 dist/ 에 모음.
2. 설치 스크립트 작성 — 오프라인 PC에서 원클릭 설치되도록.
3. 스모크 테스트 — 배포 번들을 깨끗한 VM에 설치하고 E2E 시나리오 전체 실행.
```
