# Research: Gemma 4 E4B Function Calling 지원 상태

## 질문

1. Ollama에서 `gemma4:e4b` 모델이 OpenAI 호환 tool call API(`tools` 파라미터)를 지원하는가?
2. 한국어 "내일 오후 3시에 회의 있어" 입력 시 `add_event({title, start, duration})` 구조화 JSON 인자를 정확히 추출하는가?
3. Gemma 4 E4B의 context window 크기와 멀티모달(이미지 입력) 지원 여부.
4. 라이선스가 사내 오프라인 상업적 사용에 허용되는가?

> **주의:** WebSearch/WebFetch 도구가 이 환경에서 차단되어 학습 지식(컷오프 2025-08)과 로컬 코드 기반으로 조사. 미확인 항목은 온라인 환경에서 별도 검증 필요.

---

## 조사 결과

### 1. Ollama tool call 지원 여부

- Gemma 4는 2025년 4월 Google DeepMind가 공개한 모델 패밀리. E4B는 dense 4B 파라미터 변형.
- Gemma 3 계열(2B/9B/27B)은 Ollama v0.3+ 에서 tool calling 지원이 추가되었다 (학습 지식).
- Gemma 4 E4B도 동일한 Ollama tool call 인프라를 사용할 가능성이 있으나 **직접 확인 불가**.
- upstream `openai_compatible_llm.py:214-223`에 `"does not support tools"` 에러 자동 감지 후 `self.support_tools = False` fallback 처리가 구현되어 있어, tool call 미지원 시 코드베이스 자체는 graceful degradation됨.

**미확인**: `https://ollama.com/library/gemma4` 에서 `gemma4:e4b` 태그의 tool call 지원 플래그 직접 확인 필요.

### 2. 한국어 인자 처리 정확도

- 한국어 function calling 공개 벤치마크 수치 **미확인** (BFCL 등).
- Gemma 4는 다국어 지원 포함. 한국어가 지원 언어 목록에 포함됨 (학습 지식).
- 인자 값이 한국어로 입력될 경우 영어/한국어 반환 여부는 프롬프트 설계에 의존.
- "내일 오후 3시" → ISO 8601 datetime 변환은 시스템 프롬프트에 현재 날짜를 주입하지 않으면 실패 가능성 있음. 4B 파라미터 모델에서 상대 날짜 처리 안정성 **미확인**.

### 3. 컨텍스트 크기 및 멀티모달

- `REQUIREMENTS.md:88` 명시: "131K 컨텍스트, 멀티모달, 함수 호출"
- Gemma 4 공개 문서 기준 컨텍스트 128K~131K 토큰 (학습 지식).
- Gemma 4는 이미지 입력 지원 멀티모달 모델로 발표됨. Gemma 3에서 vision 지원 추가 후 Gemma 4도 계승.
- **미확인**: E4B 특정 변형이 vision 기능을 포함하는지(text-only 변형 여부). Ollama 모델 페이지에서 확인 필요.
- upstream `openai_compatible_llm.py`가 `image_url` 형식 멀티모달 메시지를 이미 지원하므로, Ollama가 Gemma 4 vision을 지원하면 추가 구현 없이 사용 가능.

### 4. 라이선스

- Google "Gemma Terms of Use" 적용 (Apache-2.0 아님, 자체 약관).
- 상업적 사용 허용: MAU 임계치(Gemma 3 기준 1억 명) 이하에서 허용.
- 사내 1인 1PC 오프라인 비서 용도는 내부 사용으로 분류되어 제한 대상 외로 해석 가능.
- 모델 재판매·재배포 금지. Google 사용 정책(Prohibited Use Policy) 준수 의무.
- **미확인**: Gemma 4 Terms of Use 원문이 Gemma 3와 동일한 구조인지. 사내 배포 전 법무팀 검토 권고.

---

## 미해결 의문

1. `gemma4:e4b` Ollama 태그 실제 존재 여부 및 tool call 지원 플래그 활성화 여부.
2. E4B 변형이 vision(이미지 입력) 포함인지 text-only인지.
3. "내일 오후 3시" → ISO 8601 변환 시 현재 날짜 컨텍스트 없이 처리 가능한가.
4. Gemma 4 Terms of Use 원문에서 사내 오프라인 상업적 사용 명시적 허용 여부.
5. BFCL 등 공개 function calling 벤치마크에서 Gemma 4 E4B 실제 점수.

---

## 참조 링크·파일

- `/mnt/c/projects/ai-assistant/REQUIREMENTS.md:88` — 131K 컨텍스트, 멀티모달, function calling 명시
- `/mnt/c/projects/ai-assistant/docs/GAP_ANALYSIS.md` — E10(Gemma 4 E4B 연동), E09(비전 입력) EXTEND 분류
- `upstream/src/open_llm_vtuber/agent/stateless_llm/openai_compatible_llm.py:214-223` — tool call 미지원 시 자동 fallback
- `upstream/src/open_llm_vtuber/agent/stateless_llm/ollama_llm.py` — OllamaLLM 구현
- `https://ollama.com/library/gemma4` — Ollama Gemma 4 모델 페이지 (접근 미확인)
- `https://ai.google.dev/gemma/terms` — Gemma Terms of Use 원문 (접근 미확인)
