# 01 — Phase 0: GAP 분석

Open-LLM-VTuber에 이미 있는 것, 없는 것, 확장해야 할 것을 구분한다.

---

## 프롬프트

```
Phase 0: GAP 분석을 시작한다.

researcher 에이전트를 호출해 다음을 수행해라:

1. upstream/Open-LLM-VTuber 의 실제 코드를 읽어라.
   - 전체 폴더 구조 훑기
   - conf.yaml 스키마 분석
   - LLM/ASR/TTS 어댑터 구조
   - 이벤트·메시지 플로우
   - Live2D 렌더링 경로
   - 펫 모드·투명 창 구현 위치
   - 플러그인/MCP 추가 방식

2. REQUIREMENTS.md의 각 요구사항을 다음 세 범주로 분류해라:
   - **REUSE**: 이미 upstream에 있다. 거의 수정 없이 쓸 수 있음.
   - **EXTEND**: 일부 있다. 수정·확장 필요.
   - **NEW**: 없다. 새로 만들어야 함.

3. 출력:
   - docs/GAP_ANALYSIS.md
   - 각 요구사항별 상세 표 (요구사항 ID, 범주, 관련 파일·경로, 예상 작업량: S/M/L)
   - 상단에 전체 요약 (REUSE: n개 / EXTEND: n개 / NEW: n개)

4. 조사 끝에 나에게 질문: "GAP 분석이 맞는지, 혹은 추가로 조사가 필요한 영역이 있는지 확인 요청."

절대 하지 말 것:
- 코드 작성
- 아키텍처 결정 (그건 planner의 일)
- upstream 파일 수정
```

---

**다음 단계:** GAP 분석을 승인한 뒤 `02_phase1_architecture.md`로 이동.
