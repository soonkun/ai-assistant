# Research: Piper TTS 한국어 모델 가용성

## 질문

1. 공식 Piper 모델 저장소(rhasspy/piper-voices)에 한국어(`ko_KR`) 모델이 있는가?
2. 각 모델의 라이선스가 사내 오프라인 상업적 사용에 허용되는가?
3. 모델 파일 크기(ONNX)는 얼마인가?
4. 공식 저장소 외에 사용 가능한 한국어 Piper 모델이 있는가?
5. Piper 한국어 음성 품질에 대한 사용자 평가나 데모가 있는가?

> WebFetch로 HuggingFace 직접 확인 (2026-04-18 기준).

---

## 후보 목록

| 모델명 | 품질 | 라이선스 | 파일 크기 | 상업 사용 |
|---|---|---|---|---|
| rhasspy/piper-voices ko_KR | — | — | — | **해당 없음 (존재하지 않음)** |
| neurlang/piper-onnx-kss-korean | train (미지정) | CC-BY-NC-SA-4.0 | 63.5 MB | **불가** |

---

## 핵심 발견

### 공식 저장소 (rhasspy/piper-voices)

- **한국어(`ko`) 디렉토리 없음.** `voices.json` 및 디렉토리 트리 직접 확인.
- 지원 언어 44개 코드(ar, bg, ca, cs, cy, da, de, el, en, es, eu, fa, fi, fr, hi, hu, id, is, it, ka, kk, ku, lb, lv, ml, ne, nl, no, pl, pt, ro, ru, sk, sl, sq, sr, sv, sw, te, tr, uk, ur, vi, zh)에 `ko` 없음.
- 출처: `https://huggingface.co/rhasspy/piper-voices/tree/main`, `voices.json` 직접 확인.

### 커뮤니티 모델: neurlang/piper-onnx-kss-korean

- **라이선스: CC-BY-NC-SA-4.0** → 상업적 사용 명시적 금지.
- 학습 데이터: KSS Dataset (CC-BY-NC-SA-4.0, "You CANNOT use this dataset for ANY COMMERCIAL purpose" 원문 명시).
- ONNX 파일 크기: **63.5 MB**.
- 단일 화자 (전문 여성 성우), 샘플 레이트 22,050 Hz.
- 포넴 타입: pygoruut (표준 eSpeak-ng 아님) — Python `piper-tts` 호환성 **미확인**.
- 오디오 데모: **없음**.
- Piper 품질 등급: `train` (x_low/low/medium/high 미지정).
- 출처: `https://huggingface.co/neurlang/piper-onnx-kss-korean` 직접 확인.

---

## 미해결 의문

1. neurlang 모델이 Python `piper-tts` 패키지와 호환되는가? (README는 Rust `piper-rs`만 예시)
2. 공식 저장소에 한국어 추가 계획이 있는가? (GitHub Issues 확인 필요, 접근 차단)
3. 상업적 허용 라이선스(MIT/Apache-2.0)의 한국어 오픈 음성 데이터로 직접 Piper 모델 훈련이 필요한가?
4. Supertonic-2(nrl-ai, MIT + OpenRAIL-M)가 Piper 어댑터로 래핑 가능한가?
5. CosyVoice 2가 대안이 될 수 있는가? (E03 항목, 별도 서버 구동 필요)

---

## 참조 링크

- `https://huggingface.co/rhasspy/piper-voices/tree/main` — 공식 저장소 (ko 없음 확인)
- `https://huggingface.co/rhasspy/piper-voices/raw/main/voices.json` — voices.json (ko 항목 없음)
- `https://huggingface.co/neurlang/piper-onnx-kss-korean` — 커뮤니티 모델 (CC-BY-NC-SA-4.0)
- `https://huggingface.co/datasets/Bingsu/KSS_Dataset` — KSS 데이터셋 라이선스 원문
- `/mnt/c/projects/ai-assistant/REQUIREMENTS.md:15` — Piper 한국어 기본 TTS 요구사항
