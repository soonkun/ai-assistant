# 02 — Phase 1: 아키텍처 설계

GAP 분석을 근거로 전체 아키텍처와 모듈 경계를 정의한다.

---

## 프롬프트

```
Phase 1: 아키텍처 설계를 시작한다.

planner 에이전트를 호출해 다음을 수행해라:

입력 문서:
- REQUIREMENTS.md
- docs/GAP_ANALYSIS.md
- upstream/Open-LLM-VTuber 코드

산출물:
1. docs/ARCHITECTURE.md
   - 시스템 블록 다이어그램(ASCII 아트로)
   - 주요 데이터 흐름 3~5개 (예: 음성 질의→RAG→TTS 응답)
   - 프로세스 경계 (어떤 게 같은 프로세스, 어떤 게 분리)
   - 핵심 결정과 근거:
     - 왜 LanceDB vs Qdrant
     - 왜 Piper vs CosyVoice 기본
     - 왜 Electron vs Tauri vs PyWebView
     - 왜 이 RAG 파이프라인
   - REQUIREMENTS §9의 비기능 요구사항을 어디서 어떻게 만족시키는지

2. docs/MODULES.md
   - 10~12개 모듈 목록
   - 각 모듈의:
     - 공개 API 시그니처 (Python 타입 힌트 포함)
     - 의존성 (다른 모듈 + 외부 라이브러리)
     - 진행 상태 (PLANNED / IN_PROGRESS / REVIEW / DONE)
   - 모듈 의존성 그래프 (ASCII 또는 Mermaid)

3. docs/MILESTONES.md
   - 10~12개 모듈의 구현 순서 (의존성 기반)
   - 각 모듈당 Definition of Done 체크리스트
   - 예상 작업량 (모듈당 Small/Medium/Large)
   - 병렬 가능한 모듈 표시

4. docs/RISKS.md
   - 식별된 리스크 목록 (기술·일정·보안·오프라인 제약)
   - 각 리스크별 영향도·확률·완화 방안

제출 후 나에게 질문:
"아키텍처와 모듈 분해에 동의하는가? 수정할 부분이 있는가?"
내 승인 없이 Phase 2로 넘어가지 마라.

절대 하지 말 것:
- src/ 또는 tests/ 아래에 파일 생성
- pyproject.toml 수정
- "나중에 결정" 미룸 (RISKS.md로 이동시켜라)
```

---

**다음 단계:** 아키텍처를 승인한 뒤 모듈 순서대로 `03_phase2_module_loop.md`를 반복.
