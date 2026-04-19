# Research: BGE-M3 한국어 검색 성능

## 질문

1. BGE-M3 모델의 한국어 문서 검색 벤치마크 수치 (BEIR, MIRACL, KorQuAD 등)
2. 한국어 RAG 용도로 BGE-M3 대비 경쟁 모델(multilingual-e5, ko-sroberta 등) 비교 수치
3. 모델 크기(파라미터 수, 파일 크기)와 추론 속도 (CPU 기준)
4. 라이선스가 사내 오프라인 상업적 사용에 허용되는가
5. Qwen3-Reranker-8B 조합 시 성능 개선 수치

> **주의:** WebSearch/WebFetch 도구가 이 환경에서 차단되어 학습 지식(컷오프 2025-08) 기반 조사. 수치 항목은 모두 미확인. 온라인 환경에서 직접 검증 필요.

---

## 벤치마크 결과

| 모델 | 데이터셋 | 지표 | 점수 | 출처 |
|---|---|---|---|---|
| BGE-M3 | MIRACL (ko) | nDCG@10 | **미확인** | https://arxiv.org/abs/2402.03216 (접근 필요) |
| BGE-M3 | BEIR 평균 | nDCG@10 | **미확인** | 동일 |
| multilingual-e5-large | MIRACL (ko) | nDCG@10 | **미확인** | 접근 필요 |
| ko-sroberta-multitask | KorSTS | Spearman | **미확인** | 접근 필요 |

수치를 출처 URL 없이 기재하는 것은 규칙 위반이므로 생략. 외부망 접속 후 논문 Table에서 직접 확인 필요.

---

## 모델 스펙 (학습 지식 기반, 미확인)

| 항목 | 값 | 확인 필요 URL |
|---|---|---|
| 파라미터 수 | 약 570M (XLM-RoBERTa large 기반) | https://huggingface.co/BAAI/bge-m3 |
| 모델 파일 크기 | float32 약 2.2GB, int8 약 570MB | 동일 |
| 임베딩 차원 | 1024 | 동일 |
| 최대 시퀀스 길이 | 8192 tokens | 동일 |
| 라이선스 | MIT (추정) | 동일 — 직접 확인 필요 |
| 오프라인 사용 | 가능 (snapshot_download 후 로컬) | - |
| 한국어 학습 포함 | 포함 (다국어 사전학습) | 논문 학습 데이터 섹션 |

CPU 추론 속도: 직접 벤치마크 없음. 570M 모델 기준 CPU 단일 쿼리 수백 ms 예상이나 실측 필요.

---

## Qwen3-Reranker-8B 조합 효과

공개 수치 없음. 외부 검색 차단으로 조회 불가. 리랭커 추가 시 Precision 향상은 일반적 패턴이나 한국어 특화 수치 미확인.

---

## 미해결 의문

1. BGE-M3 MIRACL 한국어 nDCG@10 구체 수치 (논문 Table 확인 필요)
2. multilingual-e5-large 대비 한국어 상대 성능 차이
3. CPU-only 환경(i7/i9 기준)에서 ms/query 실측치 — 리랭커 포함 시 응답 지연 영향 평가 필요
4. Qwen3-Reranker-8B 한국어 리랭킹 성능 (모델 카드 확인 필요)
5. MIT 라이선스 원문 확인 (https://huggingface.co/BAAI/bge-m3)
6. REQUIREMENTS.md §9 메모리 제약(12GB 이하)에서 BGE-M3(2.2GB) + Gemma 4 E4B + Qwen3-Reranker-8B(8B) 동시 적재 가능 여부

---

## 참조 링크

- `https://huggingface.co/BAAI/bge-m3` — 모델 카드, 라이선스, 벤치마크 (접근 필요)
- `https://arxiv.org/abs/2402.03216` — BGE-M3 논문, 다국어 벤치마크 테이블 (접근 필요)
- `https://huggingface.co/BAAI/Qwen3-Reranker-8B` — 리랭커 모델 카드 (접근 필요)
- `/mnt/c/projects/ai-assistant/REQUIREMENTS.md:89,98` — BGE-M3 선택 명시, 메모리 12GB 제약
