# M_02 ASREngine — Critic Review

**Verdict**: PASS ✅

**1차 검수**: 2026-04-18 — FAIL (Critical 7, Major 6)
**2차 검수**: 2026-04-18 — **PASS** (fresh Opus critic)
**검수 에이전트**: fresh critic (Opus) × 2회 — 각 builder 세션과 분리

---

## Critical Issues (FAIL 사유 — 모두 수정 필요)

### C-1: A-2 테스트 — download_root 검증이 model_path보다 먼저 일어남을 명시적으로 검증하지 않음
- A-2 테스트는 URL 문자열이 파일시스템에 존재하지 않는다는 우연에 의존.
- `WhisperModel call_count == 0` 검증은 있으나 "download_root 검증이 먼저"라는 순서 보장이 없음.
- **수정**: download_root 검증이 model_path 검증보다 먼저 실행됨을 명시적으로 검증하는 테스트 추가.

### C-4: threading.Lock vs asyncio.Lock 스펙 모순
- `src/asr/korean_whisper_asr.py:153` — threading.Lock 사용.
- 스펙 §성능·메모리 동시성 line 296: "구현에서 `asyncio.Lock`으로 추가 보호".
- 스펙 §스펙 외 사항 10: "동시 transcribe는 `asyncio.Lock`으로 직렬화".
- **수정**: threading.Lock이 올바른 선택(asyncio.to_thread 환경)이라면 스펙을 수정하거나 설명 주석 추가.

### C-6: `scripts/bundle_deps.sh` 미존재
- CLAUDE.md §오프라인 빌드 의무: "새 의존성을 추가하면 반드시 `scripts/bundle_deps.sh`에도 반영".
- DoD line 454: "`faster-whisper`, `ctranslate2`가 `pyproject.toml`과 `scripts/bundle_deps.sh` 양쪽에 반영됨."
- **수정**: `scripts/bundle_deps.sh` 생성 후 faster-whisper, ctranslate2, 모델 다운로드 커맨드 추가.

### C-11: `build_asr_engine`의 conf.yaml model_path 오버라이드가 동작하지 않음
- `src/asr/builder.py:57` — `getattr(app_config.paths, "asr_model_path", None)` 항상 None 반환.
- `PathsConfig`에 `asr_model_path` 필드 없음 → 오버라이드 경로가 dead code.
- 스펙 line 234: "명시 > 프로파일 기본 > 하드코드 기본" 계층 구조 미충족.
- **수정**: `PathsConfig`에 `asr_model_path: str | None = None` 추가 + 테스트 추가.

### C-12: `initial_prompt`가 conf.yaml에서 builder 경로로 전달되지 않음
- `src/asr/builder.py:69-74` — `initial_prompt` 파라미터 하드코딩 없이 미전달.
- N-4 테스트는 직접 생성자 호출로만 검증 — production 경로(builder) 미검증.
- **수정**: builder에서 `initial_prompt` 전달 로직 추가.

### C-N3: N-3 async 테스트가 threading 동작을 검증하지 않음
- `timeout=0` + mock으로 즉시 종료 → CancelledError 전파 경로 실제 검증 안 됨.
- 스펙 N-3: "부모 구현이 스레드로 `transcribe_np`를 호출" — 이 assertion 없음.
- **수정**: `threading.current_thread()` 확인 또는 실제 스레드 디스패치 검증.

### C-E7: E-7 WARNING 로그 스펙 모순
- 스펙 §에러 처리 표: "device=auto + CUDA 가용 판별 실패 → cpu로 폴백, **경고 로그**"
- 스펙 §테스트 E-7: "`asr.resolved_device == "cpu"`. **WARNING 없음**"
- 구현은 WARNING 발생 → 테스트는 WARNING 검증 안 함 → 사실상 WARNING 상태 미정.
- **수정**: 스펙 모순 해결 후 테스트에 WARNING 여부 명시적 assert 추가.

---

## Major Issues

- M-1: `_check_cuda_available`의 `except Exception:` — ImportError 포함 모든 예외를 silent swallow
- M-2: `transcribe_np`의 포괄적 `except Exception:` — 향후 asyncio 변경 시 취약
- M-3: `download_root` 양성 케이스 테스트 없음 (기존 디렉토리 → 성공 경로)
- M-5: `caplog.at_level` logger name 하드코딩 → propagation 설정 변경 시 취약
- M-6: conftest의 MockSegment/MockInfo가 테스트 파일에서 중복 정의 (dead code)
- M-7: `# type: ignore[misc]` 코드 스멜

---

## Summary

**FAIL** — critical 7건.

**재검수 전 필수 수정:**
1. C-6: `scripts/bundle_deps.sh` 생성
2. C-11: `PathsConfig.asr_model_path` 필드 추가 + builder 연동
3. C-12: builder에서 `initial_prompt` 전달
4. C-4: threading.Lock 결정 확정 + 스펙 주석 또는 수정
5. C-N3: N-3 테스트에 스레드 디스패치 검증 추가
6. C-E7: E-7 WARNING 모순 해결 + 명시적 assert
7. C-1/A-2: download_root 순서 검증 강화
