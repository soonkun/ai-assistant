# M_03 VADEngine — Critic Review

**Verdict**: PASS ✅

**1차 검수**: 2026-04-18 — FAIL (Critical 3, Major 6)
**2차 검수**: 2026-04-18 — FAIL (Critical 2, Major 7)
**3차 검수**: 2026-04-18 — **PASS** (fresh Opus critic)
**검수 에이전트**: fresh critic (Opus) × 3회 — 각 builder 세션과 분리

---

## Critical Issues (FAIL 사유 — 모두 수정 필요)

### C-1: A-5 (중복 init_vad 호출) 테스트 완전 누락
- 스펙 §A-5: `ctx.init_vad(vad_config)` 2회 호출 시 `load_silero_vad.call_count == 1` 검증
- `tests/vad/test_wiring.py::TestA5`는 "src/vad/ 네트워크 호출 없음"으로 전혀 다른 케이스
- DoD: "본 스펙의 N/E/A 케이스 전량" — A-5가 없으면 DoD 미충족
- **수정**: upstream `service_context.py` `init_vad` 중복 호출 단락(short-circuit) 검증 테스트 추가

### C-2: A-3 동적 네트워크 패턴 검사가 vacuous (silero-vad 미설치 환경)
- `test_upstream_integrity.py`: `inspect.getsource()` → `TypeError` → `except` 분기 → **무조건 통과**
- root `conftest.py`가 `silero_vad`를 MagicMock으로 대체하므로 실제 소스 접근 불가
- 스펙 A-3: "매칭 1건이라도 있으면 FAIL" — 보호가 실질적으로 없는 상태
- **수정**: 파일 경로로 직접 `upstream/Open-LLM-VTuber/src/open_llm_vtuber/vad/silero.py` 텍스트를 읽어 패턴 검사

### C-3: A-2 (ImportError) 테스트가 패키지 미설치 우연에 의존
- `test_import.py`: `sys.modules`에서 pop 후 reload → 현재 환경에서는 silero-vad 미설치라 통과
- silero-vad가 설치된 환경(spec DoD 요건)에서는 reload 성공 → 테스트 FAIL
- **수정**: `sys.modules["silero_vad"] = None` 센티널로 ImportError 강제 발생

---

## Major Issues

### M-1: `tests/vad/conftest.py` 픽스처 4개 — 사용 안 되거나 잘못된 경로로 패치
- `mock_load_silero_vad`: `"silero_vad.load_silero_vad"` 패치 (원본 정의 위치) → 실제 테스트는 `"open_llm_vtuber.vad.silero.load_silero_vad"`로 별도 패치 → 픽스처 dead code이자 오해 유발
- **수정**: 미사용 픽스처 제거 또는 올바른 경로로 수정 후 실제 테스트에서 사용

### M-2: N-4 WARNING 로그 assertion 누락
- 스펙 §N-4: "WARNING 로그 1건 (`caplog`)" — `test_wiring.py::TestN4`는 `caplog` 인자만 있고 검증 없음
- **수정**: `caplog`으로 WARNING 레코드 1건 assert. upstream이 INFO만 내보내면 M_01 배선 레이어에서 WARNING 추가 필요

### M-3: E-1 (`target_sr=8000`) 로그 경고 assertion 누락
- 스펙 §E-1: "로그 경고 1건" — 테스트가 `window_size_samples`만 확인하고 로그 미검증
- **수정**: `caplog`으로 warning 레코드 검증 추가

### M-4: A-3 금지 패턴에 `websockets` 누락
- upstream `silero.py`가 `websockets` import — 스펙 §DROP에서 명시 금지
- 테스트 regex에 `\bwebsockets\b` 추가 필요

### M-5: 테스트 클래스 번호가 스펙 번호와 불일치 — 추적성 파괴
- `TestE1` → 실제 스펙 E-6, `TestA2` → 실제 스펙 A-1의 변종, `TestA5` → 스펙 A-3 
- **수정**: 스펙 케이스 번호와 일치하도록 rename 또는 `# spec: §A-5` 주석 추가

### M-6: A-4 스펙 케이스 (잘못된 타입 orig_sr="16000") 미구현
- 스펙 §A-4: `orig_sr="16000"` (str) → pydantic 강제 변환 또는 거부 확인
- 현재 `TestA4ModelLoadError`는 모델 로드 실패 케이스 — 다른 케이스

---

## Summary

**FAIL** — Critical 3건, Major 6건.

**재검수 전 필수 수정:**
1. C-1: A-5 중복 init_vad 테스트 추가
2. C-2: A-3 동적 검사를 파일 직접 읽기로 교체
3. C-3: A-2를 `sys.modules["silero_vad"] = None` 방식으로 재작성
4. M-1: dead/mis-patched 픽스처 제거
5. M-2: N-4 WARNING assert 추가 (또는 M_01에 WARNING 로그 추가)
6. M-3: E-1 log assert 추가
7. M-4: A-3 regex에 `websockets` 추가
