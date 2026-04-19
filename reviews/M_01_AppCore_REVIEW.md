# M_01 AppCore — Critic Review

**Verdict**: PASS ✅

**1차 검수**: 2026-04-18 — FAIL (Critical 6, Major 12)  
**2차 검수**: 2026-04-18 — FAIL (Critical 1 신규: A-4 upstream 경로 미사용)  
**3차 검수**: 2026-04-18 — **PASS** (fresh Opus critic)  
**검수 에이전트**: fresh critic (Opus) × 3회 — 각 builder 세션과 분리

---

## Critical Issues (FAIL 사유 — 모두 수정 필요)

### CRITICAL-1: `AppServiceContext.close()` 순서 테스트 불완전
- **파일**: `tests/app/test_service_context.py`
- **문제**: `test_close_calls_all_services`는 `idle_stop < proactive_stop`만 검사. spec §"에러 처리 정책"이 요구하는 5단계 전체 순서(`idle→proactive→rag→calendar→super`) 검증 없음.
- **수정**: `call_order.index()` 체인으로 5단계 순서 모두 assert.

### CRITICAL-2: upstream 무결성 테스트 자체가 무의미 (tautological)
- **파일**: `tests/app/test_upstream_integrity.py`
- **문제**: `.gitignore`에 `upstream/`이 제외돼 있어 `git diff --name-only upstream/Open-LLM-VTuber/`는 항상 빈 결과. builder가 upstream 파일을 수정해도 테스트가 통과함.
- **DoD 위반**: DoD line 709 — "upstream 파일 수정되지 않았음을 확인하는 테스트" 요건 미충족.
- **수정**: `upstream.sha256` 매니페스트 파일 생성 후 해시 비교, 또는 git submodule HEAD SHA 비교.

### CRITICAL-3: N-5 WebSocket 스모크 테스트가 `create_app()`을 테스트하지 않음
- **파일**: `tests/app/test_create_app.py` lines 84-95
- **문제**: `_make_mock_ws_app()`이라는 수동 제작 FastAPI 인스턴스에 연결. 실제 `create_app()` 반환값은 전혀 사용되지 않음.
- **DoD 위반**: DoD line 704 — "`create_app()` WebSocket 연결 성공" 요건 미충족.
- **수정**: `TestClient(create_app(...))` 사용, 실제 라우트에서 초기 메시지 수신 확인.

### CRITICAL-4: `AppWebSocketServer`가 `super().__init__()` 미호출 — LSP 위반
- **파일**: `src/app/server.py` line 35-36
- **문제**: `WebSocketServer`를 상속하면서 부모 생성자를 호출하지 않음. spec §"REUSE" 요건 위반, Liskov 치환 원칙 위반.
- **수정**: (a) `super().__init__()` 호출 후 라우터만 교체, 또는 (b) 상속 제거 후 컴포지션으로 재설계.

### CRITICAL-5: `AppServiceContext` 필드 타입이 `Any | None` — 스펙 명시 타입 위반
- **파일**: `src/app/service_context.py` lines 26-38
- **문제**: `self.rag_service: Any | None = None` 등 — spec은 `"RagService | None"` forward-ref 구체 타입 요구.
- **수정**: `if TYPE_CHECKING:` 블록으로 forward import, `self.rag_service: "RagService | None" = None` 형태로 변경.

### CRITICAL-6: A-4 adversarial 테스트가 실제 JSONDecodeError 경로를 테스트하지 않음
- **파일**: `tests/app/test_ws_handler.py` lines 307-340
- **문제**: `_route_message`에 bytes를 직접 전달 → `AttributeError` 발생 (JSONDecodeError 아님). `JSONDecodeError` 처리 경로는 `handle_websocket_communication` while 루프 내에 있음.
- **수정**: TestClient로 실제 WS 연결 후 `ws.send_bytes(b"invalid")` 전송, 연결 유지 + error 메시지 미전송 확인.

---

## Major Issues (3개 이상 → 추가 FAIL 요인)

### MAJOR-1: `_continuous_capture_loop` — 첫 캡처 전 `interval_sec`만큼 대기
- **파일**: `src/app/ws_handler.py` line 204
- `while True: sleep() → capture` 순서. 사용자는 즉시 캡처를 기대.
- **수정**: `capture → sleep` 순서로 변경하거나 동작을 명시적으로 문서화.

### MAJOR-2: `_tasks_lock`, `_continuous_tasks` 초기화가 `super().__init__()` 이후
- **파일**: `src/app/ws_handler.py` lines 44-47
- `super().__init__()`이 `_init_message_handlers()`를 호출하는 시점에 `_tasks_lock`이 아직 미설정. 현재 런타임 crash 없지만 취약한 순서.
- **수정**: `_continuous_tasks = {}` / `_tasks_lock = asyncio.Lock()` 을 `super().__init__()` 이전에 배치.

### MAJOR-3: `_cancel_continuous_task`가 락 없이 호출됨 — 경쟁 조건
- **파일**: `src/app/ws_handler.py` lines 179-187
- `handle_disconnect`에서 락 없이 호출. 3-연속-실패 자동종료 경로와 경쟁 가능.
- **수정**: `_cancel_continuous_task` 내부에서 락을 취득하거나, 모든 호출부가 락을 보유하도록 통일.

### MAJOR-4: `enforce_private_url` — 잘못된 scheme에 misleading 에러 메시지
- **파일**: `src/app/url_guard.py` line 82
- `ftp://127.0.0.1` → "must be loopback or private" (실제 문제는 scheme). Spec §"URL 검증 로직"은 scheme 검사를 명시.
- **수정**: scheme 검사를 먼저 수행, scheme-specific 에러 메시지 반환.

### MAJOR-5: `ftp://` scheme adversarial 케이스 테스트 누락
- `test_invalid_scheme_blocked`는 `is_private_or_loopback`만 테스트. `enforce_private_url`에 대한 scheme adversarial 테스트 없음.

### MAJOR-6: `create_app`에서 `load_from_config` 예외를 지나치게 포괄적으로 삼킴
- **파일**: `src/app/main.py` lines 63-67
- `pydantic.ValidationError`, `FileNotFoundError`, `PrivacyViolationError`까지 삼켜 half-initialized 앱 기동.
- **수정**: 좁은 예외(모델 지연 로딩 실패)만 삼키고, validation/config 오류는 re-raise.

### MAJOR-7: `AppConfig`에서 `ollama`, `paths` 필드가 optional로 변경됨 (스펙은 required)
- 스펙 class 정의에 `default_factory` 없음 → required 의도. 구현은 `Field(default_factory=...)`.
- E-1 테스트는 이 동작을 검증하므로 사실상 ambiguous. **Planner가 스펙 명확화 필요.**

### MAJOR-8: `HardwareProfile` 잘못된 값 시 `ValueError` 미처리
- **파일**: `src/app/config.py` lines 134-136
- `SAESSAGI_PROFILE=foo` → uncaught `ValueError`.
- **수정**: try/except로 `ConfigLoadError` 변환 또는 경고 후 기본값 사용.

### MAJOR-9: `asyncio_mode = "auto"` 설정과 `@pytest.mark.asyncio` 중복 사용
- 기능상 문제없으나 의도 불명확.

### MAJOR-10: `test_a3_spam_keeps_one_task` RSS 측정이 비결정적 (WSL 환경)
- **파일**: `tests/app/test_ws_handler.py` lines 267-300
- `psutil.memory_info().rss` GC 타이밍에 따라 플레이키 가능.
- **수정**: RSS 대신 `len(_continuous_tasks) <= 1` 상태 단언으로 교체.

### MAJOR-11: PII 마스킹이 loguru sink 레벨에서 실제로 동작하는지 미검증
- **파일**: `tests/app/test_logging.py`
- `pii_mask()` 함수만 테스트. `init_logging()`이 설치한 필터가 실제 로그 출력에서 PII를 제거하는지 검증 없음.
- **DoD 위반**: "3종 패턴 동작함" 요건 미충족.
- **수정**: StringIO sink 설치 후 PII 포함 로그 발생 → 출력 내 PII 없음 assert.

### MAJOR-12: `test_ws_handler.py` — `psutil` top-level import (dev 의존)
- `import psutil` 모듈 최상단. dev deps 없는 환경에서 전체 모듈 import 실패.
- **수정**: 함수 내부로 이동하거나 `pytest.importorskip`.

---

## Minor Issues

- **MINOR-1**: `_call_stop`/`_call_close`에서 `asyncio.iscoroutine()` 대신 `hasattr(..., "__await__")` 사용 (비일관)
- **MINOR-2**: `logging.py:29` — `record: dict` (loguru `Record` 타입 미사용)
- **MINOR-3**: `SAESSAGI_LOG_LEVEL="verbose"` 잘못된 값 미검증
- **MINOR-4**: `src/app/server.py:19` — `type: ignore[misc]` 코드 스멜
- **MINOR-5**: `test_service_context.py` — `super().close()` 호출 횟수만 검사, 순서 미검사
- **MINOR-6**: `test_create_app.py` line 16-17 — FastAPI 중복 import
- **MINOR-7**: `conf.valid.yaml`의 TTS 설정 키가 스펙 §"설정 구조"와 불일치 (M_04 구현 시 충돌 예상)
- **MINOR-8**: `FullConfig.upstream: Any` — 하위 모듈의 타입 안전성 손실
- **MINOR-9**: `AppWebSocketHandler.__init__`의 `default_context_cache` 파라미터 타입이 subclass이나 부모 타입으로 업캐스트됨 (duck typing 의존)

---

## Spec Compliance Matrix

| Spec 항목 | 구현 | 상태 |
|---|---|---|
| `load_full_config(config_path) -> FullConfig` | `config.py:99` | ✅ |
| `PrivacyViolationError` | `errors.py:5` | ✅ |
| `is_private_or_loopback(url) -> bool` | `url_guard.py:28` | ✅ |
| `enforce_private_url` | `url_guard.py:68` | ⚠ MAJOR-4 |
| `AppServiceContext` 6 fields | `service_context.py:26-36` | ❌ CRITICAL-5 |
| `AppServiceContext.close` 순서 | `service_context.py:61` | ⚠ CRITICAL-1 |
| `AppWebSocketHandler` 3종 메시지 핸들러 | `ws_handler.py:49` | ✅ |
| `_handle_start_continuous_capture` | `ws_handler.py:120` | ⚠ MAJOR-1 |
| `create_app(config_path) -> FastAPI` | `main.py:17` | ⚠ MAJOR-6 |
| `AppWebSocketServer` REUSE | `server.py:19` | ❌ CRITICAL-4 |
| `init_logging` + PII sink | `logging.py:36` | ⚠ MAJOR-11 |
| DoD: upstream 무결성 테스트 | `test_upstream_integrity.py` | ❌ CRITICAL-2 |
| DoD: `create_app` WebSocket smoke | `test_create_app.py` N-5 | ❌ CRITICAL-3 |
| DoD: PII 마스킹 end-to-end | — | ❌ MAJOR-11 |

---

## Test Coverage Assessment

| 케이스 | 테스트 | 상태 |
|---|---|---|
| N-1 유효 설정 로드 | `test_n1_load_valid_config` | ✅ |
| N-2 env override | `test_n2_env_override_ollama_url` | ⚠ silent except |
| N-3 허용 URL | `test_allowed_urls` | ✅ |
| N-4 핸들러 등록 | `test_n4_new_handlers_registered` | ✅ |
| N-5 WS 스모크 | `test_n5_websocket_connection_smoke` | ❌ CRITICAL-3 |
| N-6 task 취소 | `test_n6_stop_cancels_task` | ✅ |
| E-1 누락 필드 기본값 | `test_e1_missing_app_fields_use_defaults` | ✅ |
| E-2 URL 차단 | `test_e2_*` | ✅ |
| E-3 중복 start | `test_e3_duplicate_start_replaces_task` | ✅ |
| E-4 disconnect | `test_e4_disconnect_cancels_task` | ✅ |
| E-5 캡처 실패 에러 | `test_e5_region_capture_failure_sends_error` | ✅ |
| E-6 close 지속 | `test_e6_close_continues_on_failure` | ⚠ 순서 미검증 |
| A-1 공개 URL | `test_a1_public_url_raises` | ✅ |
| A-2 suspicious IP | `test_a2_*` | ✅ |
| A-3 스팸 단일 태스크 | `test_a3_spam_keeps_one_task` | ⚠ MAJOR-10 |
| A-4 binary frame | `test_a4_binary_frame_no_error_sent` | ❌ CRITICAL-6 |
| A-5 oversized prompt | `test_a5_oversized_prompt_rejected` | ✅ |

명목 수: 정상 5+, 엣지 6, 적대 5 — 숫자는 충족. **그러나 N-5, A-4가 sham 테스트이므로 실효 적대 4, 정상 4.**

---

## Summary

**FAIL** — 6개 Critical + 12개 Major 이슈 확인.

**재검수 전 필수 수정 목록:**
1. CRITICAL-2: upstream 무결성 테스트를 해시 기반으로 재작성
2. CRITICAL-3: `create_app()` 실제 반환값으로 WebSocket 스모크 테스트
3. CRITICAL-4: `AppWebSocketServer.super().__init__()` 호출 또는 컴포지션으로 재설계
4. CRITICAL-5: `AppServiceContext` 필드 타입을 forward-ref 구체 타입으로 변경
5. CRITICAL-6: A-4 테스트를 TestClient binary send 경로로 재작성
6. CRITICAL-1: close 5단계 순서 전체 assert
7. MAJOR-3: `_cancel_continuous_task` 락 규율 통일
8. MAJOR-6: `ValidationError`/`FileNotFoundError`는 re-raise
9. MAJOR-11: loguru sink 레벨 PII 마스킹 end-to-end 테스트 추가
10. MAJOR-10: RSS 기반 어서션 → 상태 기반 어서션으로 교체

**재검수 시 fresh critic 필요** (CLAUDE.md 규칙).
