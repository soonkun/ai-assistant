# R-06: Gemma 4 E4B Vision 스파이크

## 상태

**TODO: 실제 Ollama gemma4:e4b 모델 연결 후 실행 필요**

이 문서는 스텁(stub)입니다. 실제 Ollama 서버와 gemma4:e4b 모델이 준비된 환경에서
`scripts/spike_gemma_vision.py`를 실행하고 결과를 이 문서에 기록해야 합니다.

## 스파이크 목적

M_05 스펙 §범위 In-Scope §6:
> `BatchInput.images`를 upstream `_to_messages`가 `image_url` 블록으로 변환.
> Ollama `gemma4:e4b`가 멀티모달 지원하는 전제(R-06 스파이크 필수)

## 확인 항목

- [ ] Ollama에서 gemma4:e4b 모델이 `/api/tags`에 등록됨
- [ ] OpenAI 호환 `/v1/chat/completions` 엔드포인트에서 `image_url` 타입 content 블록 수용
- [ ] 스트리밍 응답 정상 수신 (TTFT 측정)
- [ ] 이미지 내용이 응답에 반영됨 (정성 평가)
- [ ] `BatchInput.images` → upstream `_to_messages` → messages 변환 검증

## 실행 방법

```bash
# 1. Ollama 서버 시작
ollama serve

# 2. 모델 준비 (오프라인 환경: ollama/models/ 사전 배치)
ollama pull gemma4:e4b

# 3. 스파이크 실행
cd /mnt/c/projects/ai-assistant
python scripts/spike_gemma_vision.py \
  --base-url http://127.0.0.1:11434 \
  --image assets/test_images/sample.png
```

## 결과 (미작성)

실제 실행 후 아래 항목을 채워 주세요:

### 환경
- Ollama 버전:
- 모델 버전:
- GPU 유무:
- 실행 일시:

### 헬스체크
- `/api/version` 응답:
- `/api/tags` 응답 (관련 모델):

### 멀티모달 입력 테스트
- 테스트 이미지:
- 요청 메시지:
- 응답:
- TTFT (Time To First Token):
- 총 응답 시간:

### 결론
- gemma4:e4b 멀티모달 지원 여부:
- M_05 구현 영향:
