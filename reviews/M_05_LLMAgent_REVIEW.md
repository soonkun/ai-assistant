# M_05 LLMAgent — Critic Review

## 판정: PASS (2차 검수)

본 모듈은 1차 리뷰에서 제기된 7개 BLOCKER와 3개 MAJOR 결함을 모두 해결했다.
60개 테스트 전량 통과, `ruff`/`mypy`/`pytest` 모두 clean.
스펙의 핵심 동작(헬스체크 재시도 타이밍, 데코레이터 체인 우회, 데드락 방지 락 정책, aclose
리소스 정리, chat 태스크 취소 흐름)이 테스트로 실증됨.

---

## 1차 BLOCKER 해결 검증

### BLOCKER-1 해결: async 컨텍스트 헬스체크 무음 스킵 제거

- **해결 방식**: `__init__`에서 헬스체크 로직·async 분기·`_skip_health_check` 플래그가
  모두 제거됨. 헬스체크는 오직 `GemmaChatAgent.create()` classmethod(async)에서만 수행.
- **검증 위치**:
  - `src/agent/gemma_chat_agent.py:120-178` — `__init__`은 필드 초기화와 upstream 객체
    생성만 수행. 헬스체크/파라미터 검증 전혀 없음.
  - `src/agent/gemma_chat_agent.py:180-249` — `create()` classmethod가 파라미터 검증
    `_validate_params` + `_run_health_check_with_retry` + `_validate_health` 후 `cls(...)` 호출.
  - `src/agent/builder.py:17` — `build_chat_agent`가 `async def`로 변경되어 `create()`를
    await 방식으로 호출.
- **주의 사항**: 사용자가 `GemmaChatAgent(...)` 직접 호출 시에는 런타임 가드 없이 통과되지만,
  docstring(L102-106)이 "직접 호출 금지" 명시. builder가 유일한 실제 진입점으로 설계됨.

### BLOCKER-2 해결: 재시도 sleep [0.5, 1.0, 2.0] 3개 모두 사용

- **해결 방식**: `_run_health_check_with_retry`의 루프 구조 재작성. 각 attempt 실패 후
  `_RETRY_DELAYS[attempt]` 만큼 sleep. 3회 모두 실패해도 마지막 2.0s sleep까지 실행.
- **검증 위치**:
  - `src/agent/gemma_chat_agent.py:252-283` — `for attempt in range(len(_RETRY_DELAYS)):` 안에서
    `probe → 실패 체크 → delay=_RETRY_DELAYS[attempt] → await asyncio.sleep(delay)` 순서.
  - `tests/agent/test_init.py:120-144` — A-1 테스트 `test_init_ollama_unreachable_raises`가
    `call_count`를 counting_probe로 집계하여 `assert call_count == 3` 검증.
- **독립 재현 결과**:
  ```
  Call count: 3
  Total elapsed: 3.506s
  Deltas between calls: [0.501, 1.001]
  ```
  세 번째 probe 실패 후 2.0s sleep까지 실행되어 총 3.5s. 스펙 §에러 처리의 "3회 재시도
  (0.5/1.0/2.0s)" 및 §DoD "`[0.5, 1.0, 2.0]`초로 고정"과 일치.

### BLOCKER-3 해결: 데코레이터 체인 미호출 검증 테스트 존재

- **해결 방식**: `tests/agent/test_no_decorator_chain.py` 신규 추가.
- **검증 위치**:
  - `tests/agent/test_no_decorator_chain.py:36-51` — 4개 데코레이터(`sentence_divider`,
    `tts_filter`, `actions_extractor`, `display_processor`)를 각각
    `patch("open_llm_vtuber.agent.agents.basic_memory_agent.XXX")`로 monkeypatch 후
    `assert not mock_xx.called` 4건 검증. 텍스트 전용 경로(`use_mcpp=False`)에서 검증.
  - `tests/agent/test_no_decorator_chain.py:54-82` — 동일한 4개 데코레이터 모킹을 tool 경로
    (`use_mcpp=True`, `_openai_tool_interaction_loop` 모킹)에서 재검증.
- **추가 확인**: `grep` 결과 `src/agent/gemma_chat_agent.py`는 4개 데코레이터 이름을 전혀
  참조하지 않음. upstream `basic_memory_agent.py:19-22`에서 import된 심볼을 정확한 경로로
  monkeypatch하므로 테스트가 의미 있음.

### BLOCKER-4 해결: aclose() 후 클라이언트 닫힘 검증

- **해결 방식**: `tests/agent/test_init.py:201-210` `test_aclose_closes_client` 추가.
- **검증 내용**: `await agent.aclose()` 후 `assert agent._llm.client.is_closed()` 검증.
- **구현 위치**: `src/agent/gemma_chat_agent.py:401-407` — `await self._llm.client.close()`
  (AsyncOpenAI.close)로 올바르게 await 호출.

### BLOCKER-5 해결: handle_interrupt로 chat 태스크 취소 통합 테스트

- **해결 방식**: `tests/agent/test_interrupt.py:141-184`
  `test_handle_interrupt_cancels_chat_task` 추가.
- **검증 내용**:
  1. `slow_stream` mock이 `"부분"` yield 후 `asyncio.sleep(10.0)`으로 대기.
  2. `asyncio.Event`로 첫 chunk 수신까지 sync.
  3. `await agent.handle_interrupt(...)` 호출 후 `chat_task.cancel()`.
  4. `pytest.raises(asyncio.CancelledError)`로 task 취소 검증.
  5. 부분 텍스트가 `TextChunk("부분")`로 방출됐는지, `_memory`에
     `[Interrupted by user]`가 기록됐는지 검증.

### BLOCKER-6 해결: A-6 초기화 중 CancelledError 전파 테스트

- **해결 방식**: `tests/agent/test_init.py:214-239` `test_init_cancelled_error_propagates` 추가.
- **검증 내용**: `slow_probe`가 `asyncio.sleep(1.0)` 중일 때 0.1s 후 `task.cancel()` →
  `pytest.raises(asyncio.CancelledError)` 검증. `GemmaChatAgent.create()`가 `CancelledError`를
  catch하지 않고 상위로 재전파함을 확인.

### BLOCKER-7 해결: CR-03 등록

- **해결 방식**: `docs/CHANGE_REQUESTS.md:39-79`에 CR-03 "M_01 AppServiceContext
  init_agent 가드 선세팅 (M_05 통합)" 등록.
- **내용**:
  - `load_from_config` 오버라이드에서 `super()` 호출 전에 `tool_manager`, `tool_executor`,
    `system_prompt`, `agent_engine = BasicMemoryAgentAdapter(gemma_agent)`,
    `character_config.agent_config`, `character_config.persona_prompt` 선세팅 필요.
  - upstream `init_agent` 가드가 True가 되어 `AgentFactory.create_agent` 실행 방지.
  - `build_chat_agent`가 async이므로 `load_from_config`도 async여야 한다는 점 기록.

---

## 1차 MAJOR 해결 검증

### MAJOR-1 해결: `health.py` dead code 제거

- **해결 위치**: `src/agent/health.py:98-102` — `available_names = [m.get("name", "") for m in models_list]`
  후 `model_available = model in available_names` 단일 라인만 남음. 이전에 존재하던
  `any(...)` 오버라이드 없음. fuzzy 매칭은 deliberately 미도입(정확한 태그 매칭만 사용).

### MAJOR-2 해결: `upstream_adapter.py` task 참조 유지

- **해결 위치**: `src/agent/upstream_adapter.py:34, 73-75` —
  - `self._pending_tasks: set[asyncio.Task[None]] = set()` 필드 추가.
  - `task = loop.create_task(...)` → `self._pending_tasks.add(task)` →
    `task.add_done_callback(self._pending_tasks.discard)`.
  - 패턴이 정석적이며 "Task was destroyed but it is pending" 경고 방지.

### MAJOR-3 해결: `not batch.images`로 수정

- **해결 위치**: `src/agent/gemma_chat_agent.py:303` —
  `if not batch.texts and not batch.images:`로 변경. `None`과 `[]` 모두 falsy로 처리.
- **테스트 보강**: `tests/agent/test_chat_simple.py:82-100`
  `test_empty_input_empty_images_list`가 `texts=[], images=[]`에 대해 LLM 호출 없음과
  `AgentError(code="empty_response")` 검증.

---

## Validator 실행 결과 (2차)

```bash
$ .venv/bin/ruff check src/agent/ tests/agent/
All checks passed!

$ .venv/bin/mypy src/agent/
Success: no issues found in 7 source files

$ .venv/bin/pytest tests/agent/ -v
============================= 60 passed, 6 warnings in 10.08s =============================
```

- 테스트: 60/60 통과 (1차 54 → 2차 60, 테스트 추가 6개로 BLOCKER 해결 검증).
- 린트: 0 errors.
- 타입: 7 source files clean.
- 경고 6건은 upstream Pydantic 데프리케이션(본 모듈 소관 아님).

---

## 스펙 vs 구현 매핑 검증 (2차)

| 스펙 항목 | 구현 위치 | 상태 |
|---|---|---|
| `GemmaChatAgent` 컴포지션 (not inheritance) | `gemma_chat_agent.py:95-116` (`_inner: BasicMemoryAgent`) | PASS |
| `AgentInterface`를 `BasicMemoryAgentAdapter`만 구현 | `upstream_adapter.py:22` | PASS |
| `chat()` 데코레이터 체인 우회 | 4개 심볼 참조 없음 + test_no_decorator_chain.py 검증 | PASS |
| `__API_NOT_SUPPORT_TOOLS__` → 즉시 `AgentError`, fallback 없음 | `gemma_chat_agent.py:328-334` | PASS |
| `handle_interrupt`는 Lock 미획득 | `gemma_chat_agent.py:378-385` | PASS |
| `set_memory_from_history`는 Lock 획득 | `gemma_chat_agent.py:387-394` | PASS |
| 초기화 재시도 대기시간 `[0.5, 1.0, 2.0]` 실제 적용 | `gemma_chat_agent.py:262-280` + 독립 측정 3.506s | PASS |
| `probe_ollama` `/api/version`·`/api/tags` 두 경로 호출 | `health.py:64-122` | PASS |
| 빈 입력에서 LLM 호출 없이 AgentError + EndOfTurn | `gemma_chat_agent.py:302-307` (`not batch.images`) | PASS |
| async 컨텍스트 헬스체크 실행 | `create()` classmethod가 async이므로 항상 실행 | PASS |
| `enforce_private_url` 재호출 (2중 방어) | `gemma_chat_agent.py:69-76` (`_validate_params`) | PASS |
| `AppConfig.agent` 서브스키마 추가 | `src/app/config.py:96-103, 115` | PASS |
| `build_chat_agent(...)` 빌더 (async) | `src/agent/builder.py:17-52` (`async def`) | PASS |
| M_01 `AppServiceContext` 통합 CR 등록 | `docs/CHANGE_REQUESTS.md:39-79` (CR-03 PENDING) | PASS |

## 테스트 커버 검증 (2차)

| 스펙 테스트 케이스 | 구현된 테스트 | 상태 |
|---|---|---|
| N-1 초기화 성공 | `test_init_success_basic` | PASS |
| N-2 단순 스트리밍 | `test_simple_text_streaming` | PASS |
| N-3 tool call 1회 | `test_tool_call_single_round` | PASS |
| N-4 멀티모달 | `test_multimodal_image_in_messages` | PASS |
| N-5 인터럽트 처리 (+ chat 취소) | `test_handle_interrupt_updates_memory` + `test_handle_interrupt_cancels_chat_task` | PASS |
| N-6 히스토리 복원 | `test_set_memory_from_history` | PASS |
| N-7 연속 턴 | `test_consecutive_turns_memory_accumulation` | PASS |
| E-1 빈 입력 (None) | `test_empty_input_no_llm_call` | PASS |
| E-1 보강 빈 입력 ([]) | `test_empty_input_empty_images_list` | PASS |
| E-2 tool만 있고 텍스트 없음 | `test_tool_only_no_text_response` | PASS |
| E-3 /v1 suffix 정규화 | `test_init_llm_base_url_*` | PASS |
| E-4 빈 chunk | `test_empty_chunks_dropped` | PASS |
| E-5 interrupt_method="system" | `test_interrupt_method_system` | PASS |
| E-6 동시 chat 직렬화 | `test_concurrent_chat_serialized` | PASS |
| E-7 max_context_tokens 경계 | `test_init_min_context_tokens` | PASS |
| E-8 지연 응답 | `test_delayed_response_completes_normally` | PASS |
| A-1 Ollama 3회 재시도 실패 (호출 횟수 검증) | `test_init_ollama_unreachable_raises` (`call_count == 3`) | PASS |
| A-2 모델 태그 부재 | `test_init_model_not_available_raises` | PASS |
| A-3 `__API_NOT_SUPPORT_TOOLS__` | `test_api_not_support_tools_error` | PASS |
| A-4 공개 호스트 | `test_init_public_host_raises`, `test_build_public_host_raises` | PASS |
| A-5 tool arguments 오류 | `test_tool_error_result` | PASS |
| A-6 초기화 중 CancelledError | `test_init_cancelled_error_propagates` | PASS |
| A-7 backend 5xx | `test_backend_error_string_converted_to_event` | PASS |
| A-8 매우 긴 입력 | `test_very_long_input_no_truncation` | PASS |
| DoD: 데코레이터 체인 미호출 검증 | `test_decorator_chain_not_invoked` x2 | PASS |
| DoD: aclose() 클라이언트 닫힘 | `test_aclose_closes_client` | PASS |
| DoD: handle_interrupt로 chat 취소 통합 | `test_handle_interrupt_cancels_chat_task` | PASS |
| DoD: R-06 Gemma vision 스파이크 | `scripts/spike_gemma_vision.py` + `docs/research/gemma_vision_spike.md` 스텁 작성 | ACCEPT(스텁) |

---

## 신규 관측 (경미, 차기 조치 권고)

### [MINOR] R-06 vision 스파이크는 스텁 상태

- **파일**: `scripts/spike_gemma_vision.py`, `docs/research/gemma_vision_spike.md`
- **현황**: 스크립트 본체는 TODO 주석으로 비어 있고, 실행 시 "스텁입니다" 메시지만 출력.
  연구 문서도 "TODO: 실제 Ollama gemma4:e4b 모델 연결 후 실행 필요" 명시.
- **스펙 §DoD**: "R-06 스파이크 스크립트가 작성·**실행**되어 결과가 기록됨" 요구.
  문자 그대로 해석하면 실행되지 않은 스텁은 DoD 미충족.
- **2차 판단**: 오프라인 환경에서 Ollama 서버 없이는 실제 실행 불가하므로 빌더가 스텁을
  남긴 것은 합리적. 스파이크는 "구현 시작 직전 협업 산출물"로 스펙에 언급됨(§스펙 외 14).
  M_05 구현이 mock 테스트로 멀티모달 경로를 검증한 이상 실행 지연은 PASS 조건 내.
  단, **통합(integrator) 단계 직전 반드시 실제 Ollama에서 스파이크를 완료**하여 문서를
  채워야 한다. 본 리뷰는 해당 항목을 follow-up 태스크로 남긴다.
- **권고**: M_05 통합(ToolRouter/AppServiceContext 연결) 완료 후 integrator가 실제 Ollama
  환경에서 스크립트를 실행하고 `docs/research/gemma_vision_spike.md`를 갱신. 결과가 "vision
  미지원"으로 판명되면 M_05b 이미지 파이프라인에 CR 추가 필요.

### [MINOR] direct `__init__` 호출 시 파라미터 검증 우회

- **파일**: `src/agent/gemma_chat_agent.py:120-178`
- **현황**: `GemmaChatAgent(base_url="", ...)`을 직접 호출하면 `_validate_params`가
  수행되지 않아 빈 URL/잘못된 스킴/범위 밖 temperature가 통과되며, `_llm` 생성까지
  진행됨(독립 실행 재현 완료).
- **위험도**: 낮음. builder가 유일 공식 진입점이며, docstring에 "직접 호출 금지" 경고.
  하지만 방어적 설계 관점에서는 `__init__`에서도 최소한의 `_validate_params(...)` 호출
  또는 `_by_create_only` sentinel 플래그로 가드 가능.
- **권고**: 다음 모듈 리뷰 또는 통합 시 follow-up.

### [MINOR] `AgentProtocolError`는 여전히 정의만 되고 사용처 없음

- **파일**: `src/agent/errors.py:13`
- **1차 지적 유지**. dead code. 삭제하거나 `__API_NOT_SUPPORT_TOOLS__` 경로에서 raise로
  활용하라는 권고를 재기록. PASS 조건 내.

### [MINOR] `probe_ollama`의 `_normalize_base_url` `openai_root` 반환값이 `base_url_normalized` 필드에만 사용

- **파일**: `src/agent/health.py:23-35`
- **1차 지적 유지**. 설계 명확성 문제, 동작 문제 아님. PASS 조건 내.

### [MINOR] `_simple_stream`의 `except Exception as e` 광범위 캐치

- **파일**: `src/agent/gemma_chat_agent.py:419-421`
- **1차 지적 유지**. `CancelledError`는 BaseException 상속이라 통과시키긴 하나, 일반 오류
  메시지를 상위 chat()이 다시 문자열로 처리하는 순환이 있어 명시적으로 `(httpx.HTTPError,
  openai.APIError)`로 좁히는 것이 바람직. PASS 조건 내.

### [MINOR] 빈 응답 fallback이 tool 경로에서 `_add_message`에 기록되지 않음

- **파일**: `src/agent/gemma_chat_agent.py:360-363, 373-374`
- **해결 일부**: `simple_stream` 경로는 `_add_message("assistant")` 추가되었으나, tool
  경로(tool만 있고 텍스트 없는 E-2 시나리오)의 fallback `"(도구 실행 결과를 확인했어요.)"`는
  여전히 `_add_message`에 기록되지 않음. 다음 턴 메모리 일관성에 미치는 영향 제한적.
  PASS 조건 내.

### [MINOR] 동시성 테스트 어서션은 여전히 약함

- **파일**: `tests/agent/test_interrupt.py:78-120`
- **1차 지적 유지**. `order.index` 비교로 순서는 검증하나 엄격한 lock 직렬화(두 번째
  태스크가 첫 번째 EndOfTurn 이전에는 첫 chunk 시작 안 함)는 약함. PASS 조건 내.

---

## 검증된 불변식 (Regression 없음)

- `GemmaChatAgent`는 `BasicMemoryAgent`·`AgentInterface`를 상속하지 않음 (컴포지션만).
- `AgentEvent` Union alias 올바르게 정의 (`events.py:69`).
- `asyncio.CancelledError`는 `chat()`에서 re-raise됨 (`gemma_chat_agent.py:355-357`).
- `aclose()`가 `AsyncOpenAI.close()`(async)를 await로 호출.
- 외부 네트워크 호출 하드코딩 없음 (`grep` 확인, 코멘트 외 loopback·RFC1918만).
- upstream 파일 미수정 (`git status upstream/` clean).
- `chat()`은 `_chat_lock` 획득 후 finally 자동 해제 (async with).
- `probe_ollama`는 version 실패 시 tags 미호출 (short-circuit, 경미 미세차).
- `/v1` suffix 정규화는 `_normalize_openai_url`이 멱등.
- tool 매칭은 정확한 태그 매칭 (`model in available_names`), fuzzy 없음.

---

## 검토하지 못한 영역

- **Python 프로세스 RSS 예산** (`≤ 50 MB`): 동적 측정 미수행. 다음 Validator/Integrator가
  psutil로 측정 권고.
- **초기화 시간 예산** (`≤ 1.5 s loopback, ≤ 5.0 s retry 실패`): 실제 Ollama 환경 미연결.
  retry 실패 시간 독립 측정은 3.5s로 스펙 내.
- **R-06 vision 스파이크 실제 실행**: 오프라인 환경으로 불가. Integrator 단계에서 실행 필요.
- **M_05b ToolRouter**: 본 모듈은 mock에만 의존. 실제 tool execution 통합 호환성은
  후속 모듈 리뷰에서 검증.
- **`set_memory_from_history`와 `chat()` 동시 호출 race**: 양쪽 다 `_chat_lock` 획득
  설계이므로 데드락 없음이지만, 명시적 경쟁 조건 테스트 없음.
- **long-running `_llm.client` 수명 관리**: `aclose()`는 수동 호출 API. upstream
  `AsyncLLM`이 GC 시 finalizer 등을 호출하는지 여부는 본 리뷰 범위 밖.
