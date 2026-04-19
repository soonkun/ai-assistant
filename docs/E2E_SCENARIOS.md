# E2E 시나리오

Phase 3 통합 단계를 위한 **설계 계약서**. 이 문서는 Integrator 에이전트가 `tests/e2e/`에 실제 테스트 코드를
쓰기 전에, 어떤 시나리오를 어떤 수락 기준으로 검증할지 사용자와 합의하기 위한 단일 진실 공급원이다. 본
문서를 사용자가 승인해야만 Integrator가 테스트 구현에 착수한다.

- 기반 문서: `REQUIREMENTS.md`, `docs/ARCHITECTURE.md`, `docs/MODULES.md`, 각 모듈 `specs/M_NN_*.md`.
- 본 문서는 구현 코드를 쓰지 않는다. 의사코드·assertion 목록만 기술한다.
- 본 문서는 **REQUIREMENTS.md에 이미 있는 요구사항의 검증**만 다룬다. 새 기능 제안 금지 — 필요하면
  §6 Open Questions로 분리해 사용자 승인을 먼저 받는다.

---

## 1. 개요와 범위

### 1.1 본 프로젝트에서 "E2E"의 정의

| 구분 | 포함 | 제외 |
|---|---|---|
| **조립 범위** | FastAPI 앱 (`create_app`) + `AppWebSocketHandler` + `AppServiceContext` + M_02~M_11 실제 인스턴스 | Electron UI(M_12) 렌더, 스프라이트 PNG 실 로드, 펫 모드 창 |
| **진입점** | `ws://127.0.0.1:<test_port>/client-ws` WebSocket 프레임 주고받기 | 브라우저 자동화, 수동 QA |
| **모델 추론** | 로컬 Ollama Gemma 4 E4B, faster-whisper large-v3(또는 medium), MeloTTS 한국어, BGE-M3 | 외부 HTTP 호출(OpenAI, HuggingFace 등) — **절대 금지** |
| **DB** | 실제 LanceDB(테스트 임시 폴더), 실제 SQLite(테스트 임시 파일) | 프로덕션 경로 `data/` 쓰기 금지 |
| **스케줄러** | 최소 1건은 실제 `AsyncIOScheduler` 트리거. 그 외는 `FakeScheduler` + 클럭 주입 허용 | 실제 09:00 KST 대기 |
| **UI 레이어** | `ai-speak-signal`, `avatar-state`, `full-text`, `control` 같은 **WebSocket 프레임 스키마 검증** | 스프라이트 crossfade 시각 검증(Phase 4 수동 체크리스트로 분리) |

"E2E PASS"의 의미: **프론트엔드를 붙이지 않은 채로도 백엔드 파이프라인이 REQUIREMENTS §1~§5, §8의 기능을
관찰 가능한 출력으로 증명할 수 있다.** §3 아바타 V1 스프라이트 표시·펫 모드, §6 화면 인식 시각 검증, §7 MCP
외부 MCP 서버 연동은 본 Phase에서 다루지 않는다(§6 Open Questions 참조).

### 1.2 테스트 환경 전제

| 항목 | MIN 프로파일(로컬) | RECOMMENDED 프로파일(스테이지) |
|---|---|---|
| OS | Windows 10/11 또는 WSL2 Ubuntu 22.04 | Windows 10/11 |
| Python | 3.12 (pyproject.toml 제약) | 3.12 |
| Ollama 엔드포인트 | `OLLAMA_BASE_URL` 환경변수 우선 → 없으면 `http://127.0.0.1:11434` | `http://127.0.0.1:11434` 고정 |
| Gemma 모델 | `gemma4:e4b` (사전 `ollama pull` 완료 가정) | 동일 |
| Whisper 모델 파일 | `assets/models/whisper-medium-int8/` | `assets/models/whisper-large-v3-int8/` |
| TTS 모델 파일 | `assets/models/melotts-ko/` | 동일 |
| BGE-M3 모델 파일 | `assets/models/bge-m3/` | 동일 |
| 임시 데이터 경로 | `tmp_path` fixture(`pytest`의 `tmp_path_factory`)로 테스트마다 격리 | 동일 |
| LanceDB 경로 | `<tmp_path>/vector_store/` | 동일 |
| SQLite 경로 | `<tmp_path>/calendar.db` | 동일 |
| 로그 경로 | `<tmp_path>/logs/` | 동일 |
| 타임존 | `Asia/Seoul` 고정 (`ZoneInfo("Asia/Seoul")`) — 테스트 시작 시 `TZ=Asia/Seoul` 설정 | 동일 |
| 테스트 포트 | OS 할당(`socket.getsockname()[1]`) — 하드코딩 금지 | 동일 |

### 1.3 오프라인 보장 방법

1. **`pytest-socket`** 도입.
   - `tests/e2e/conftest.py`에서 `pytest_configure`에 `disable_socket()` 호출.
   - `enable_socket()`은 `allow_hosts=["127.0.0.1", "localhost", <OLLAMA_HOST>]` 화이트리스트로만 조건 허용.
   - `OLLAMA_BASE_URL`이 사설 IP(예 `192.168.x.x`)일 때 host 부분만 추출해 화이트리스트에 추가.
2. **공용 네트워크 차단 fixture** `block_external_network`:
   - 모든 E2E 테스트에 자동 `autouse=True`로 적용.
   - Python `socket.getaddrinfo`를 patch해 화이트리스트 외 호스트 resolve 시 `RuntimeError("offline policy violation: %s")` 발생.
3. **정적 검사**: `tests/e2e/test_static_guard.py`에서 `grep -rE "https?://(?!127\\.0\\.0\\.1|localhost|<사설IP>)"` 로 src/ 전체를 스캔. 히트 시 FAIL.
4. **적대적 fixture** (E2E-32): 네트워크 차단 하에 어떤 모듈이라도 외부 호스트로 socket.connect 시도 시 즉시
   test fail.

---

## 2. 시나리오 카탈로그

- 시나리오 ID 형식: `E2E-XX-<slug>` (두 자리 숫자, 카테고리는 숫자 범위로 구분: 01~19 golden, 20~29 edge, 30~39 adversarial).
- 본 섹션 총 시나리오 수: **골든 9 + 엣지 8 + 적대적 4 = 21건**.
- 각 시나리오는 필수 필드 9종을 모두 채운다(비워둘 경우 Integrator가 사용자에게 재질의).

### 2.1 골든 패스 (Golden Paths) — 9건

#### E2E-01-chat-happy

| 필드 | 값 |
|---|---|
| **이름** | 텍스트 채팅 1턴 해피패스 |
| **REQUIREMENTS** | §1.2 텍스트 대화 · §1.1 TTS · §3.3 감정 태그 |
| **관련 모듈** | M_01, M_04, M_05, M_08 |
| **전제 조건** | Ollama `gemma4:e4b` 가동, MeloTTS 로드 가능, `AvatarState` 주입됨, 빈 SQLite/LanceDB. |
| **흐름** | 1) WS 연결 수립 → `full-text` 수신. 2) 클라이언트가 `{"type":"text-input","text":"안녕 새싹이야, 오늘 기분 어때?"}` 송신. 3) 서버가 Gemma 호출 → 스트리밍 TextChunk. 4) TTS 스트리밍 → `audio` 프레임 수신. 5) AvatarState가 감정 태그를 추출해 `avatar-state` 프레임 송신. |
| **수락 기준** | - WS frames: `full-text` 1건 + `control("start-mic")` 또는 동등 제어 + `audio` ≥1건 + `avatar-state` ≥1건 수신. <br>- `audio` 프레임의 `url`이 `file://<tmp>/cache/` 이하 WAV 경로(또는 upstream 스키마의 동등 필드)로 존재. <br>- `avatar-state.emotion`이 `Emotion` 8종 중 하나. <br>- Gemma 응답 텍스트에서 `[emotion:*]` 원문 태그가 **제거**된 상태로 `full-text` 프레임 text에 들어감. <br>- 외부 HTTP 호출 0건(네트워크 차단 fixture). |
| **실행 시간 목표** | ≤ 25초 (CPU-only, 모델 로드 포함 초기 1회). 이후 warm-up 재실행 시 ≤ 15초. |
| **잠재 flaky** | Gemma TTFT 변동(R-01). 대응: pytest `timeout=60`으로 관대하게. |

#### E2E-02-voice-happy

| 필드 | 값 |
|---|---|
| **이름** | 음성 채팅 1턴 해피패스 (WAV → ASR → Gemma → TTS) |
| **REQUIREMENTS** | §1.1 STT · §1.1 VAD · §1.1 TTS |
| **관련 모듈** | M_02, M_03, M_05, M_04, M_08 |
| **전제 조건** | `tests/e2e/fixtures/audio/greeting_ko.wav` (3~5초 한국어 "안녕하세요", 16kHz mono)가 존재. ASR 모델 파일 배치 완료. |
| **흐름** | 1) WS 연결. 2) `raw-audio-data` 또는 `mic-audio-data`(upstream 호환) 프레임으로 WAV float32 청크 송신. 3) `mic-audio-end` 신호. 4) 서버: VAD → ASR → Gemma → TTS 파이프라인. |
| **수락 기준** | - ASR이 빈 문자열이 아닌 한국어 결과 리턴(로그 또는 `control`/`full-text` 프레임으로 관찰). <br>- Gemma 응답 `full-text` 수신. <br>- `audio` 프레임 최소 1건. <br>- `avatar-state` 최소 1건. <br>- 네트워크 차단 fixture 통과. |
| **실행 시간 목표** | ≤ 30초 (CPU-only, ASR+LLM+TTS 총합). |
| **잠재 flaky** | Whisper int8 결과 변동으로 텍스트 정확 일치 금지. substring match(`"안녕"` 포함) 정도로 완화. |

#### E2E-03-tool-call-calendar

| 필드 | 값 |
|---|---|
| **이름** | 자연어 일정 등록 (Gemma function calling → CalendarService INSERT) |
| **REQUIREMENTS** | §4.1 일정 등록 (function calling) |
| **관련 모듈** | M_05, M_05b, M_09 |
| **전제 조건** | 빈 SQLite `calendar.db`. 테스트 시작 시 고정 클럭을 `AppServiceContext.clock=FakeClock(2026-04-20 09:00 KST)`로 주입(스펙 M_09/M_11 clock DI 활용). Gemma가 ISO 8601 변환을 수행 가능(FC 스파이크 10/10 근거). |
| **흐름** | 1) `text-input`: `"내일 10시에 마케팅팀 회의 1시간 잡아줘"`. 2) Gemma가 `add_event(title="마케팅팀 회의", start="2026-04-21T10:00:00+09:00", duration_minutes=60)` 툴 호출. 3) ToolRouter가 CalendarService.add_event 호출. 4) Gemma 최종 응답 스트림. |
| **수락 기준** | - `sqlite3.connect(<tmp>/calendar.db)` → `SELECT COUNT(*) FROM events WHERE title='마케팅팀 회의'` = 1. <br>- 해당 row의 `start_utc`가 `2026-04-21T01:00:00Z`(KST 10시 = UTC 01시) 또는 ±1분 이내. <br>- `duration_minutes=60`. <br>- `full-text` 프레임 본문에 "등록" 또는 "추가" 또는 "확인" 관련 한국어 포함(substring). <br>- `ToolCallStart`/`ToolCallResult` 로그 또는 이벤트가 `add_event`로 관찰됨(`ok=True`). |
| **실행 시간 목표** | ≤ 30초. |
| **잠재 flaky** | Gemma가 ISO 포맷을 `Z` vs `+09:00` 다르게 낼 수 있음 → CalendarService 저장 시 UTC 정규화되므로 동등 허용. |

#### E2E-04-tool-call-search

| 필드 | 값 |
|---|---|
| **이름** | RAG 검색 + 인용 포맷 포함 응답 |
| **REQUIREMENTS** | §2.2 질의응답 (페이지·섹션 인용) |
| **관련 모듈** | M_05, M_05b, M_07 |
| **전제 조건** | M_06 HOLD 상태이므로, Integrator가 사전 시드 스크립트 `tests/e2e/fixtures/seed_rag.py`로 `RetrievalResult`용 청크를 직접 `VectorStore.upsert`. 시드 청크 예: `DocumentChunk(doc_name="규정.pdf", page=12, section="예산 승인 절차", text="...")` 3~5건. BGE-M3 실제 임베딩으로 저장. |
| **흐름** | 1) `text-input`: `"예산 승인 절차가 어떻게 돼?"`. 2) Gemma가 `search_docs(query="예산 승인 절차", top_k=5)` 툴 호출. 3) RagService.retrieve → BGE-M3 embed → LanceDB search. 4) Gemma가 citations를 context로 받아 최종 응답 생성. |
| **수락 기준** | - `search_docs` 툴 호출이 최소 1회 발생(로그/이벤트 관찰). <br>- `ToolResult.payload.hits` 또는 동등 필드에 1건 이상. <br>- `full-text` 프레임에 `` `규정.pdf` 12페이지 `` 문자열 또는 `'예산 승인 절차' 섹션` 중 최소 하나 포함(§7.1 format_citation 규약). <br>- `found=True`이면 "문서를 찾지 못했다" 문구 **부재**. |
| **실행 시간 목표** | ≤ 30초. |
| **잠재 flaky** | Gemma가 tool call을 생략하고 추측할 가능성(R-01). 시스템 프롬프트에 "검색 필수" 명시로 완화. 3회 재시도 허용 표시. |

#### E2E-05-proactive-morning-briefing

| 필드 | 값 |
|---|---|
| **이름** | 아침 브리핑 cron 트리거 → WebSocket 발화 지시 |
| **REQUIREMENTS** | §4.2 아침 첫 실행 시 오늘 일정 브리핑 |
| **관련 모듈** | M_09, M_11, M_01 |
| **전제 조건** | 실제 `AsyncIOScheduler` 사용. `FakeClock(initial=2026-04-20 08:59:55 KST)` 주입은 **불가**(APScheduler는 실제 시계 사용) → 대신 `morning_time` 생성자 인자를 "현재시각+3초"로 덮어쓴 dispatcher 인스턴스로 교체 fixture. CalendarService에 오늘 일정 2건 시드(`add_event` 두 번 호출). |
| **흐름** | 1) WS 연결. 2) `dispatcher.start()` 실행. 3) 3초 대기. 4) cron 트리거 발화 → `_job_morning_briefing` → `events = calendar.get_events(today_start, today_end)` → `emit("morning_briefing", {"events":[...]})`. 5) `_get_active_client_send_text`로 WS send_text. |
| **수락 기준** | - 클라이언트가 `{"type":"ai-speak-signal","text":<str>,"topic":"morning_briefing","context":{"events":[...]}}` 프레임 1건 수신(≤ 10초 대기). <br>- `context.events` 길이 = 2. <br>- 쿨다운 기록이 `_last_emitted_at["morning_briefing"]`에 남음(다음 E2E-06과 독립). <br>- 실제 `AsyncIOScheduler` 인스턴스가 사용됐음을 `isinstance(dispatcher._scheduler, AsyncIOScheduler)`로 확인. |
| **실행 시간 목표** | ≤ 15초. |
| **잠재 flaky** | 3초 대기 동안 cron이 늦게 발화할 수 있음. 대응: `asyncio.wait_for(ws.receive_json(), timeout=10)`. "3초"는 트리거 예약이지 발화 보장이 아니므로 타임아웃은 넉넉히. 근거: `reviews/M_11_*_REVIEW_R2.md` §검토하지 못한 영역 #1. |

#### E2E-06-proactive-idle-rest

| 필드 | 값 |
|---|---|
| **이름** | IdleMonitor 유휴 감지 → ProactiveDispatcher 콜백 → 발화 지시 |
| **REQUIREMENTS** | §5 휴식 권고 |
| **관련 모듈** | M_10, M_11, M_01 |
| **전제 조건** | `IdleMonitor`에 `backend=NoopBackend` 주입(Linux/CI 대응). `dispatcher.set_dnd(False)`. 쿨다운 기본 30분, 초기 `_last_emitted_at["idle_rest"]=None`. |
| **흐름** | 1) WS 연결. 2) `dispatcher.start()` 후 `idle_monitor.start()`. 3) Integrator가 `idle_monitor._on_event_callback("idle_rest")` 콜백을 **직접 호출**(백엔드 무관). 4) ProactiveDispatcher가 쿨다운·DND 체크 통과 후 emit. |
| **수락 기준** | - WS에 `{"type":"ai-speak-signal","topic":"idle_rest",...}` 프레임 1건 수신. <br>- 로그에 `"idle_rest"` 키워드 포함 레벨 INFO 이상. <br>- 같은 콜백을 즉시 재호출해도 두 번째는 쿨다운 드롭(아래 E2E-24 쿨다운은 DND 관점이므로 구분). |
| **실행 시간 목표** | ≤ 8초. |
| **잠재 flaky** | 없음(콜백 직접 호출). |

#### E2E-07-avatar-emotion-roundtrip

| 필드 | 값 |
|---|---|
| **이름** | Gemma `[emotion:happy]` 태그 → AvatarState 파싱 → 프론트 `avatar-state` 프레임 |
| **REQUIREMENTS** | §3.3 감정 태그 (happy/surprised/sad/worried/thinking/sleepy/neutral) |
| **관련 모듈** | M_05, M_08 |
| **전제 조건** | Gemma 시스템 프롬프트에 "응답 끝에 [emotion:*] 태그 붙여라"가 포함된 테스트 프로파일 사용. 7종 발화 감정 중 하나가 나올 확률 보장 목적. |
| **흐름** | 1) `text-input`: `"기쁜 소식 알려줘"`. 2) Gemma 응답 스트리밍. 3) AvatarState `extract_emotion`이 태그 감지 후 `push_event(AvatarEvent(...))`. 4) `SendTextCallback`으로 `avatar-state` 송신. |
| **수락 기준** | - `avatar-state` 프레임 수신 ≥1. <br>- `avatar-state.emotion ∈ {"neutral","happy","surprised","sad","worried","thinking","sleepy"}` (7종, study 제외 — M_08 §4.1). <br>- `full-text` 프레임 text에 `[emotion:` 원문 부재(태그 제거됨). <br>- crossfade_ms 필드 값이 200~300 범위 또는 기본 250. |
| **실행 시간 목표** | ≤ 25초. |
| **잠재 flaky** | Gemma가 태그를 안 붙일 수 있음 → 시스템 프롬프트 강화 또는 테스트를 mock Agent로 대체(옵션). |

#### E2E-08-citation-links

| 필드 | 값 |
|---|---|
| **이름** | search_docs 결과의 인용 포맷 문자열이 클라이언트 프레임에 전달 |
| **REQUIREMENTS** | §2.2 인용 포맷 |
| **관련 모듈** | M_05b, M_07 |
| **전제 조건** | E2E-04와 동일 시드 + 추가로 `page=None, section="1. 서론"`인 docx 시드 1건. |
| **흐름** | 1) `text-input`: `"서론 요약해줘"`. 2) search_docs 툴 호출. 3) Gemma 응답 생성. |
| **수락 기준** | - `full-text` 또는 citation 전용 필드에 다음 중 하나 이상: <br>  · `` `회의록.docx` '1. 서론' 섹션 `` <br>  · `` `규정.pdf` 12페이지, '예산 승인 절차' 섹션 `` <br>- `ToolResult.payload.citations` 배열 존재(있다면). <br>- 백틱·single quote 이스케이프 이슈 없음. |
| **실행 시간 목표** | ≤ 30초. |
| **잠재 flaky** | Gemma가 citation 문구를 생략하고 자유서술 할 가능성 → 시스템 프롬프트에 "반드시 인용 포함" 명시. |

#### E2E-09-event-reminder-interval

| 필드 | 값 |
|---|---|
| **이름** | 일정 10분 전 알림 interval cron → event_reminder emit |
| **REQUIREMENTS** | §4.2 알림 |
| **관련 모듈** | M_09, M_11 |
| **전제 조건** | 실제 `AsyncIOScheduler` + `reminder_check_interval_seconds=2` 생성자 주입(스펙 §4 DI 허용). `reminder_lead_minutes=10`. FakeClock은 캘린더 쿼리·emit에만 주입(APScheduler는 실제 시계). CalendarService에 `start=now()+9분` 이벤트 1건 시드. |
| **흐름** | 1) dispatcher start. 2) 최대 5초 대기. 3) interval 트리거 → `events_due_within(10)` → 시드 이벤트 1건 반환 → `emit("event_reminder", {"event_id":...})`. |
| **수락 기준** | - `ai-speak-signal` 프레임 `topic="event_reminder"` 1건 수신. <br>- `context.event_id` 존재. <br>- `_notified_reminders`에 해당 event_id 기록. <br>- 다음 tick에서 재발사 없음. |
| **실행 시간 목표** | ≤ 12초. |
| **잠재 flaky** | interval 미세 타이밍 → timeout 10초 여유. |

### 2.2 엣지/회복 시나리오 — 8건

#### E2E-20-ollama-down

| 필드 | 값 |
|---|---|
| **이름** | Ollama 백엔드 다운 시 재시도 후 친화 메시지 |
| **REQUIREMENTS** | §1.2 텍스트 대화 + 비기능 §9(외부 호출 금지는 유지) |
| **관련 모듈** | M_05, M_01 |
| **전제 조건** | `OLLAMA_BASE_URL`을 존재하지 않는 로컬 포트(`http://127.0.0.1:65530`)로 오버라이드. 해당 포트는 listen하지 않음. |
| **흐름** | 1) WS 연결. 2) `text-input`: "안녕". 3) Agent가 3회 재시도 후 `AgentBackendError`. |
| **수락 기준** | - 프로세스 크래시 없음. <br>- 클라이언트에 `full-text` 또는 `error` 프레임으로 사용자 친화 메시지 수신(한국어 또는 영어). <br>- 로그에 `AgentBackendError` 3회 재시도 기록(spec M_05 §에러 처리). <br>- 네트워크 화이트리스트는 유지됨(127.0.0.1). |
| **실행 시간 목표** | ≤ 15초. |
| **잠재 flaky** | 재시도 백오프 시간 편차. 재시도 간격을 테스트에선 0.1s로 DI(가능하면). |

#### E2E-21-empty-asr

| 필드 | 값 |
|---|---|
| **이름** | 무음 WAV → ASR 빈 문자열 → Gemma 호출 생략 |
| **REQUIREMENTS** | §1.1 VAD + STT |
| **관련 모듈** | M_02, M_03, M_05 |
| **전제 조건** | `tests/e2e/fixtures/audio/silence_2s.wav` (16kHz mono, 전부 0). |
| **흐름** | 1) 무음 WAV 업로드. 2) VAD가 음성 구간을 찾지 못함 또는 ASR이 빈 문자열. |
| **수락 기준** | - Gemma 호출 0회(로그 또는 mock Agent 관찰). <br>- `full-text` 프레임이 있다면 본문이 빈 문자열 또는 "들리지 않았어요" 류 안내. <br>- `audio` 프레임 0건. <br>- 예외 전파 없음. |
| **실행 시간 목표** | ≤ 8초. |
| **잠재 flaky** | 없음. |

#### E2E-22-no-match-rag

| 필드 | 값 |
|---|---|
| **이름** | search_docs 결과 min_score 미달 → "관련 문서 없음" |
| **REQUIREMENTS** | §2.2 "추측 금지", "등록된 문서에서 답을 찾지 못했습니다" 고정 응답 |
| **관련 모듈** | M_05, M_05b, M_07 |
| **전제 조건** | LanceDB에 완전히 관련 없는 청크 1건만 시드(예: `text="고양이가 식탁 위에 앉았다"`). `min_score=0.35`. |
| **흐름** | 1) `text-input`: "예산 승인 절차가 뭐야?". 2) Gemma → search_docs. 3) RagService retrieve → 상위 점수 미달. 4) `RetrievalResult.found=False`. 5) Gemma가 `no_match_reason`을 받아 "등록된 문서에서 답을 찾지 못했습니다" 고정 문구 응답. |
| **수락 기준** | - `ToolResult.payload.found == False` 또는 `no_match_reason` 존재. <br>- `full-text` 프레임 본문에 "찾지 못했" 또는 "등록된 문서" 또는 "관련 내용" 키워드 포함. <br>- citation 문자열 **없음**. |
| **실행 시간 목표** | ≤ 20초. |
| **잠재 flaky** | Gemma가 지시를 어기고 추측할 가능성 → 시스템 프롬프트 강화 + "fail-open이면 FAIL" 원칙. |

#### E2E-23-calendar-duplicate

| 필드 | 값 |
|---|---|
| **이름** | 동일 (title, start) 중복 INSERT 허용 + 경고 로그 |
| **REQUIREMENTS** | §4.1 일정 등록 (M_09 §7.1 중복 허용 결정) |
| **관련 모듈** | M_05b, M_09 |
| **전제 조건** | 빈 SQLite. |
| **흐름** | 1) `text-input`: `"내일 10시 회의 추가해줘"` (첫 번째). 2) 완료 후 같은 문구 재전송(두 번째). |
| **수락 기준** | - `SELECT COUNT(*) FROM events WHERE title='회의'` = 2. <br>- 두 id가 다름. <br>- 로그에 `WARNING` 레벨의 중복 경고 1건 이상(M_09 spec §7.1). <br>- 프로세스 크래시 없음. |
| **실행 시간 목표** | ≤ 40초 (2턴 포함). |
| **잠재 flaky** | Gemma가 두 번째 호출 시 자연어를 다르게 해석(예: duration 30분으로 변경)할 가능성 → title만 동일하면 허용으로 완화. |

#### E2E-24-dnd-drop

| 필드 | 값 |
|---|---|
| **이름** | DND ON 상태에서 proactive emit 시도 → 드롭 + 쿨다운 기록 없음 |
| **REQUIREMENTS** | §5 "방해 금지 모드" |
| **관련 모듈** | M_10, M_11 |
| **전제 조건** | `dispatcher.set_dnd(True)` 호출 후 상태 확인. 쿨다운 초기 상태. |
| **흐름** | 1) `idle_monitor._on_event_callback("idle_rest")` 수동 호출. 2) ProactiveDispatcher emit 시도. |
| **수락 기준** | - WS에 `ai-speak-signal` 프레임 **0건**. <br>- `emit()` 반환값 `False`(내부 관찰 또는 이벤트 훅). <br>- `_last_emitted_at["idle_rest"]` 변경 **없음**(여전히 None 또는 이전 값). <br>- DND OFF 후 재호출 시 즉시 emit 성공(쿨다운 미기록 확인). |
| **실행 시간 목표** | ≤ 5초. |
| **잠재 flaky** | 없음. |

#### E2E-25-ws-reconnect

| 필드 | 값 |
|---|---|
| **이름** | 클라이언트 disconnect → reconnect → `_active_ws` 재바인딩 → proactive 페이로드 전달 |
| **REQUIREMENTS** | §5, §4.2 (proactive 발화가 재연결 후에도 도달) |
| **관련 모듈** | M_01 (`AppWebSocketHandler`), M_11 |
| **전제 조건** | late-binding 구현 확인(`_get_active_client_send_text`가 ws를 호출 시점에 read) — `reviews/M_11_*_REVIEW_R2.md` Non-blocking MINOR #3 대응 E2E 버전. |
| **흐름** | 1) ws1 연결 → `_active_ws=ws1`. 2) ws1 disconnect → `_active_ws=None`(B2). 3) ws2 연결 → `_active_ws=ws2`. 4) `idle_monitor._on_event_callback("overwork")` 호출. 5) dispatcher emit. |
| **수락 기준** | - ws2가 `{"type":"ai-speak-signal","topic":"overwork",...}` 프레임 1건 수신. <br>- ws1에는 어떤 프레임도 송신되지 않음(ws1이 수집한 프레임 = 연결 유지 중 받은 것뿐). <br>- 과거 ws1로 send_text 시도 로그 0건. |
| **실행 시간 목표** | ≤ 10초. |
| **잠재 flaky** | disconnect 처리 race. 대응: reconnect 전 `await asyncio.sleep(0.1)`. |

#### E2E-26-session-not-ready-screenshot

| 필드 | 값 |
|---|---|
| **이름** | 세션 준비 전 `screenshot-trigger` → 친화 에러 |
| **REQUIREMENTS** | §6 화면 인식 (비차단 에러 정책) |
| **관련 모듈** | M_01 ws_handler, M_05b ScreenshotService |
| **전제 조건** | WS 연결 직후 `full-text` 수신 전에 `screenshot-trigger` 송신. |
| **흐름** | 1) WS 연결. 2) 즉시 `{"type":"screenshot-trigger","prompt":"화면 분석"}` 송신(client_contexts 미형성 타이밍). |
| **수락 기준** | - `{"type":"error","message":"screenshot_failed: session not ready"}` 프레임 수신. <br>- 서버 크래시 없음. <br>- 이후 정상 `text-input`은 문제없이 동작. |
| **실행 시간 목표** | ≤ 5초. |
| **잠재 flaky** | 세션 형성 속도 차 → 고의적 race 유발을 위해 `asyncio.sleep(0)`만으로 충분하지 않으면 upstream 초기화 hook을 monkeypatch로 지연시켜 재현. |

#### E2E-27-tts-init-fail-text-only

| 필드 | 값 |
|---|---|
| **이름** | TTS 초기화 실패 → 텍스트 채팅은 계속 동작 |
| **REQUIREMENTS** | §9 비기능 (우아한 저하) + M_04 배선 정책 |
| **관련 모듈** | M_04, M_01 |
| **전제 조건** | `conf.yaml`의 TTS 모델 경로를 존재하지 않는 디렉터리로 오버라이드. |
| **흐름** | 1) create_app → `TTSInitError` 포착 → `tts_engine=None` + warning 로그. 2) WS 연결. 3) `text-input`. |
| **수락 기준** | - 앱 기동 성공(프로세스 살아있음). <br>- `full-text` 프레임 수신. <br>- `audio` 프레임 **0건**. <br>- 로그에 `"TTSInitError"` 포함 WARNING 1건 이상. |
| **실행 시간 목표** | ≤ 15초. |
| **잠재 flaky** | 없음. |

### 2.3 적대적 시나리오 — 4건

#### E2E-30-tool-schema-violation

| 필드 | 값 |
|---|---|
| **이름** | Gemma가 잘못된 인자로 툴 호출 → ToolRouter가 JSON Schema 에러 리턴, 크래시 없음 |
| **REQUIREMENTS** | M_05b §에러 정책 |
| **관련 모듈** | M_05b |
| **전제 조건** | Gemma mock 또는 `FakeAgent`를 주입해 결정적으로 `add_event(title="X", start="not-a-date", duration_minutes=-5)` 호출 방출. Gemma 실제 추론은 변동성 높아 적대적 재현에 부적합. |
| **흐름** | 1) FakeAgent가 위 tool call 방출. 2) ToolRouter dispatch. |
| **수락 기준** | - `ToolResult.ok == False`. <br>- `ToolResult.error`에 JSON Schema validator 에러 메시지 포함(M_05b §에러 정책). <br>- CalendarService.add_event 호출 횟수 0. <br>- Gemma 후속 응답 생성 (에러 메시지를 context로 받음). <br>- 서버 프로세스 크래시 없음. |
| **실행 시간 목표** | ≤ 10초. |
| **잠재 flaky** | 없음(FakeAgent 결정론). |

#### E2E-31-unknown-emotion-tag

| 필드 | 값 |
|---|---|
| **이름** | `[emotion:ecstatic]` 미지 태그 → neutral 폴백 + warning |
| **REQUIREMENTS** | §3.3 감정 7종 (M_08 §4.1 미지 키 폴백) |
| **관련 모듈** | M_08 |
| **전제 조건** | FakeAgent가 고정 응답 `"정말 기뻐요! [emotion:ecstatic]"` 방출. |
| **흐름** | 1) FakeAgent 응답 → AvatarState.extract_emotion. 2) 미지 키 감지 → neutral 폴백. |
| **수락 기준** | - `avatar-state.emotion == "neutral"`. <br>- `full-text` 본문에 `[emotion:` 태그 **제거됨**. <br>- 로그에 `WARNING` 레벨 "unknown emotion tag" 포함(M_08 §5.1). <br>- 크래시 없음. |
| **실행 시간 목표** | ≤ 5초. |
| **잠재 flaky** | 없음. |

#### E2E-32-network-offline-guard

| 필드 | 값 |
|---|---|
| **이름** | 외부 네트워크 호출 시도 → 테스트 실패(네트워크 차단 fixture) |
| **REQUIREMENTS** | §9 프라이버시 — 외부 호출 절대 금지 |
| **관련 모듈** | 전체 |
| **전제 조건** | `block_external_network` autouse fixture 활성. 테스트용 mock 서비스가 `socket.create_connection(("8.8.8.8", 443))` 호출 시도. |
| **흐름** | 1) WS 연결. 2) 별도 async task로 외부 connect 시도. |
| **수락 기준** | - `RuntimeError("offline policy violation: 8.8.8.8:443")` 발생. <br>- 테스트 자체는 PASS 상태(에러 발생 자체가 기대 결과). <br>- 허용 호스트(127.0.0.1, OLLAMA_HOST)에 대한 connect는 **정상** 수행됨(대조군 assertion). |
| **실행 시간 목표** | ≤ 3초. |
| **잠재 flaky** | 없음. |

#### E2E-33-interrupt-midspeech

| 필드 | 값 |
|---|---|
| **이름** | AI 발화 중 사용자 인터럽트 → TTS 큐 드레인 + 즉시 듣기 전환 |
| **REQUIREMENTS** | §1.1 전이중(Full Duplex) |
| **관련 모듈** | M_02, M_03, M_04, M_05 |
| **전제 조건** | Agent가 긴 응답(1000자 이상)을 생성하도록 프롬프트 유도 또는 FakeAgent로 긴 텍스트 주입. TTS가 여러 청크 생성 중. |
| **흐름** | 1) `text-input`: 긴 답변 유도 질문. 2) TTS 첫 청크 송신 감지 후 `{"type":"interrupt-signal"}` 또는 VAD `<|PAUSE|>` 송신. 3) 서버가 `handle_interrupt` 처리. |
| **수락 기준** | - 인터럽트 이후 `audio` 프레임 송신 중단(추가 프레임 0건). <br>- `control` 프레임 "interrupt" 또는 동등 값 수신. <br>- 이후 새 `text-input` 전송 시 정상 응답 재개. <br>- 서버 크래시 없음. |
| **실행 시간 목표** | ≤ 30초. |
| **잠재 flaky** | 타이밍 race. 대응: TTS 청크 1건 수신 후 sleep 0.2s 보장한 뒤 interrupt 전송. |

---

## 3. 모듈 통합 포인트 표

| from | to | 인터페이스 | 메시지/콜러블 | 관련 E2E |
|---|---|---|---|---|
| Client WS | `AppWebSocketHandler` | WebSocket | `text-input`, `mic-audio-data`, `mic-audio-end`, `raw-audio-data`, `interrupt-signal`, `screenshot-trigger`, `start-continuous-capture`, `stop-continuous-capture` | E2E-01~04, 07, 08, 20~27, 33 |
| `AppWebSocketHandler` | upstream `ConversationHandler` | `_handle_conversation_trigger` | `text-input`/`mic-audio-end`/`ai-speak-signal` 라우팅 | E2E-01, 02, 05, 09 |
| `ConversationHandler` | M_02 ASR | `async_transcribe_np` | np.ndarray → str | E2E-02, 21, 33 |
| `ConversationHandler` | M_05 `GemmaChatAgent` | `chat(BatchInput)` → `AsyncIterator[AgentEvent]` | TextChunk, ToolCallStart, ToolCallResult, EndOfTurn | E2E-01~04, 07, 08, 20, 22, 27, 30 |
| M_05 | M_05b `CompositeToolExecutor` | `ToolExecutor.dispatch(name, args)` | `add_event`, `get_events`, `search_docs`, `take_screenshot` | E2E-03, 04, 08, 22, 30 |
| M_05b | M_09 CalendarService | `add_event`, `get_events`, `events_due_within` (sync, run_in_executor) | — | E2E-03, 05, 09, 23 |
| M_05b | M_07 RagService | `retrieve` (sync, run_in_executor), `format_citation` | — | E2E-04, 08, 22 |
| M_05b | ScreenshotService | `capture_once()` | base64 data URL | E2E-26 (음성 경로는 Phase 4) |
| M_05 | M_08 AvatarState | `extract_emotion(text)`, `push_event(event, send_text)` | → WS `avatar-state` 프레임 | E2E-01, 07, 31 |
| M_11 ProactiveDispatcher | WS(`_active_client_send_text`) | `SendTextCallback(payload: dict)` | `{type:"ai-speak-signal",text,topic,context}` | E2E-05, 06, 09, 24, 25 |
| M_10 IdleMonitor | M_11 | `on_event(cb)` 콜백 | `"idle_rest"`, `"overwork"` | E2E-06, 25 |
| M_09 CalendarService | M_11 | `get_events`, `events_due_within`, `get_event` | — | E2E-05, 09, 23 |
| M_08 AvatarState | WS | `SendTextCallback` | `avatar-state` 프레임 | E2E-07, 31 |
| FastAPI startup hook | M_10, M_11 | `idle_monitor.start()`, `proactive_dispatcher.start()` | — | E2E-05, 06, 09 (간접) |
| `AppServiceContext._active_ws` | WS handle_new_connection/disconnect | `WebSocket 참조 갱신 (super() 후)` | — | E2E-25 |

---

## 4. 테스트 실행 전략

### 4.1 파일 배치

```
tests/e2e/
├── conftest.py                      # 서버 기동/종료, WS 클라이언트, 네트워크 차단, 시드 헬퍼
├── fixtures/
│   ├── audio/
│   │   ├── greeting_ko.wav          # E2E-02
│   │   └── silence_2s.wav           # E2E-21
│   ├── rag_seed/
│   │   ├── budget_policy.md         # E2E-04, 08, 22 시드 원문
│   │   └── meeting_minutes.md
│   └── seed_rag.py                  # VectorStore.upsert 실행 헬퍼
├── helpers/
│   ├── ws_client.py                 # async WS 클라이언트 (websockets 라이브러리)
│   ├── frame_collector.py           # 수신 프레임 타입별 분류 유틸
│   ├── fake_agent.py                # FakeAgent (E2E-30, 31, 33)
│   └── clock.py                     # FakeClock 재사용 (M_10/M_11 호환)
├── test_e2e_01_chat_happy.py
├── test_e2e_02_voice_happy.py
├── ... (시나리오 1파일 1테스트)
└── test_static_guard.py             # 소스 전체 외부 URL 정적 검사
```

**명명 규칙**: `test_<scenario_id>.py` (예: `test_e2e_03_tool_call_calendar.py`). 한 파일당 시나리오 1개,
혼합 금지. 공통 fixture는 `conftest.py` / `helpers/`로 위임.

### 4.2 픽스처 정책

| fixture | scope | 책임 |
|---|---|---|
| `event_loop` | session | `asyncio.new_event_loop()` 공유(uvicorn + pytest-asyncio) |
| `tmp_data_root` | function | `tmp_path_factory.mktemp("e2e")` 격리 |
| `app_config` | function | `conf.yaml` 템플릿 + tmp 경로 overrides |
| `test_app` | function | `create_app(app_config)` → FastAPI 앱 |
| `uvicorn_server` | function | `uvicorn.Server` 백그라운드 기동, `host=127.0.0.1`, `port=0`(OS 할당), URL 반환 |
| `ws_client` | function | `websockets.connect(<url>/client-ws)`, context manager |
| `block_external_network` | session, **autouse** | `pytest-socket` + custom getaddrinfo patch |
| `seed_rag` | function | E2E-04/08/22 전용 LanceDB 시드 |
| `seed_calendar` | function | E2E-05/09/23 전용 SQLite 시드 |
| `fake_agent` | function | E2E-30/31/33 전용 FakeAgent 주입 |
| `clock` | function | FakeClock (proactive, calendar 테스트에만) |

### 4.3 실제 모델 vs Mock

| 시나리오 | Gemma | Whisper | MeloTTS | BGE-M3 | 비고 |
|---|---|---|---|---|---|
| E2E-01 | 실제 | - | 실제 | - | CPU 기동 시 warm-up 중요 |
| E2E-02 | 실제 | 실제 | 실제 | - | 최장 실행 |
| E2E-03 | 실제 | - | - | - | TTS 프레임 수 무관, 생략 가능 |
| E2E-04 | 실제 | - | - | 실제 | 시드에만 BGE-M3 필요 |
| E2E-05 | - | - | - | - | mock Agent 허용(쿼리 없이 cron만) |
| E2E-06 | - | - | - | - | 콜백만 |
| E2E-07 | 실제 or Fake | - | - | - | Fake 우선 권장(태그 보장) |
| E2E-08 | 실제 | - | - | 실제 | E2E-04와 병합 가능 |
| E2E-09 | - | - | - | - | cron만 |
| E2E-20 | - (endpoint down) | - | - | - | Ollama 미기동 |
| E2E-21 | - | 실제 | - | - | 무음 검증 |
| E2E-22 | 실제 or Fake | - | - | 실제 | Fake 우선 |
| E2E-23 | 실제 | - | - | - | 2턴 연속 |
| E2E-24 | - | - | - | - | policy 테스트 |
| E2E-25 | - | - | - | - | mock Agent |
| E2E-26 | - | - | - | - | ws handler 단독 |
| E2E-27 | 실제 or Fake | - | - (fail) | - | TTS 경로 차단 |
| E2E-30 | Fake | - | - | - | 결정적 재현 필수 |
| E2E-31 | Fake | - | - | - | 태그 결정적 |
| E2E-32 | - | - | - | - | offline guard |
| E2E-33 | 실제 or Fake | 실제 or none | 실제 | - | VAD interrupt 경로 |

**FakeAgent 정책**: §2.3 적대적 시나리오는 Gemma 실제 추론 변동성이 재현성을 해친다. `helpers/fake_agent.py`에
결정적 응답 시퀀스를 주입해 `BasicMemoryAgentAdapter` 자리를 대체. M_05 공개 API와 호환되는 Mock이어야 한다.

### 4.4 실행 옵션

- **pytest 마커**: `@pytest.mark.e2e` 모든 E2E 파일에 적용. CI에서는 기본 비활성:
  `pytest -m "not e2e"`. 로컬/스테이지에서 명시 활성: `pytest -m e2e`.
- **서브마커**:
  - `@pytest.mark.e2e_model` — 실제 모델 필요(Ollama + Whisper + TTS + BGE-M3). 환경변수 `E2E_WITH_MODELS=1`일 때만 수집.
  - `@pytest.mark.e2e_fast` — Fake/mock 사용, 모델 불필요(E2E-05, 06, 09, 24, 25, 26, 30, 31, 32).
- **병렬 실행 금지**: `pytest-xdist` 사용 금지(서버 포트 충돌, 모델 메모리 경합).
- **타임아웃**: 전체 스위트 `pytest --timeout=120` 기본. 각 시나리오는 §2 "실행 시간 목표"를 `@pytest.mark.timeout(n)`로 개별 지정.

### 4.5 실행 시간 상한

| 스위트 | 목표 | 근거 |
|---|---|---|
| `e2e_fast` 전체 | ≤ 60초 | Fake Agent 기반, 모델 로드 없음 |
| `e2e_model` 전체 (MIN 프로파일, CPU-only) | ≤ 10분 | Gemma TTFT 10~30s × 골든 6건 + 엣지 3건 |
| `e2e_model` 전체 (GPU) | ≤ 3분 | TTFT 0.5s |

---

## 5. 수락 기준 (Phase 3 종료 조건)

Phase 3 완료 = 아래 7가지 조건을 **전부 만족**한 상태로 `docs/ACCEPTANCE.md`에 기록.

1. **전 시나리오 PASS**: 골든 9건 + 엣지 8건 + 적대적 4건 = 21건 모두 `pytest -m e2e` 통과
   (환경 프로파일 MIN/RECOMMENDED 중 최소 하나에서).
2. **외부 네트워크 호출 0건**: `block_external_network` fixture 적용 하에 `socket.create_connection` 추적
   로그가 화이트리스트(127.0.0.1, localhost, `OLLAMA_HOST`) 외 호스트를 0회 호출.
3. **함수 커버리지 80% 이상**: 통합 실행이 다음 패키지의 공개 함수(`def`/`async def` 모두, private `_`로
   시작하지 않는 것)를 최소 1회 이상 실행한 비율이 ≥80%.
   - 대상: `src/app/`, `src/proactive/`, `src/tool_router/`.
   - 측정: `pytest-cov` + `--cov-report=term-missing`, 함수 단위 집계는 coverage.py `report --show-missing --precision=0`에서 function 집계 후 수동 계산.
4. **AsyncIOScheduler 실기동 스모크 1건 이상**: E2E-05 또는 E2E-09 중 최소 하나가 실제 `AsyncIOScheduler`
   인스턴스로 cron/interval 트리거 관찰 — `reviews/M_11_*_REVIEW_R2.md` §검토하지 못한 영역 #1 해소.
5. **startup hook 호출 E2E 검증**: E2E-05 또는 E2E-06 중 최소 하나가 `create_app` 경유로 기동되어
   `ctx.proactive_dispatcher.start()`가 `startup` 이벤트에 의해 호출됐음을 assert — 리뷰 R2 §검토하지 못한 영역 #2 해소.
6. **프라이버시 정적 검사 통과**: `test_static_guard.py`가 `src/` 전체에서 외부 URL 0건 확인.
7. **문서 갱신**: `docs/ACCEPTANCE.md` 신규 생성, 각 시나리오 결과·실행시간·환경을 기록.

---

## 6. Open Questions / 사용자 결정 필요 사항

아래는 **Integrator가 착수 전에 사용자(=프로젝트 오너)의 결정**을 받아야 하는 항목이다. 이 문서는 결정을
미루지 않고 선택지를 제시한다. 해당 항목이 결정되지 않으면 `docs/RISKS.md`에 즉시 등재.

### Q-1. 실제 모델을 쓰는 E2E를 CI에서 돌릴 것인가?

- **옵션 A (권장)**: 로컬·스테이지 전용. CI(GitHub Actions 등)에서는 `e2e_fast`만 돌린다. 이유: Gemma E4B
  8.5GB + Whisper 1.6GB + MeloTTS 450MB = 약 11GB 모델 파일이 CI runner 디스크·시간 제약 초과.
- **옵션 B**: 별도 GPU runner에서 nightly 1회 실행. `actions/runners` 자체 호스팅 필요.
- **옵션 C**: 모든 E2E를 mock/fake 기반으로 전환. 적대적 재현성은 높지만 §1.1에서 정의한 "실제 추론까지 포함"
  원칙 위배.
- 본 문서 기본 가정: **옵션 A**. 사용자 승인 필요.

### Q-2. 테스트용 Ollama 인스턴스 정책

- **옵션 A**: 테스트 시작 시 `curl http://<OLLAMA_BASE_URL>/api/tags`로 health check만 하고, 미기동 시
  `e2e_model` 자동 skip. Ollama 기동은 수동.
- **옵션 B**: conftest가 `ollama serve`를 subprocess로 자동 기동·종료. 기동 시간 ~5초 추가.
- 본 문서 기본 가정: **옵션 A**. 사용자 승인 필요.

### Q-3. M_12 Frontend 붙은 뒤 UI 골든패스를 본 문서에 포함할지

- **옵션 A**: 포함하지 않는다. 본 Phase 3은 백엔드 관점 E2E만. UI는 Phase 4(수동 QA 체크리스트) 또는 Phase 5
  별도 E2E.
- **옵션 B**: Playwright/Spectron 기반 UI 자동화를 본 문서에 추가. 복잡도 상승.
- 본 문서 기본 가정: **옵션 A**. 사용자 승인 필요.

### Q-4. M_06 HOLD 중 RAG 시드 데이터 소스

- **옵션 A (제안)**: `docs/`, `specs/` 아래의 자체 MD 파일 3~5개를 TXT/MD 경로로 시드. 라이선스·오프라인
  둘 다 안전. 단 M_06이 착수되면 진짜 HWPX 샘플로 교체해야 함.
- **옵션 B**: 공개 도메인 PDF(예: 공공데이터 정책 문서) 수동 다운로드 후 `tests/e2e/fixtures/rag_seed/`에
  커밋. 저작권 확인 필요.
- 본 문서 기본 가정: **옵션 A**. 사용자 승인 필요.

### Q-5. ASR 모델 파일 부재 시 정책

- **옵션 A**: `assets/models/whisper-*/` 부재 시 E2E-02, E2E-21, E2E-33을 skip (`pytest.skip`).
- **옵션 B**: FakeASR을 주입해 고정 문자열 리턴. 음성 경로 커버리지는 잃지만 실행은 보장.
- 본 문서 기본 가정: **옵션 A**. 사용자 승인 필요.

### Q-6. 적대적 시나리오의 Gemma mock 필수 여부

- §2.3 E2E-30/31/33은 FakeAgent 주입을 전제로 한다. 실제 Gemma로는 재현성이 낮다. Integrator가 FakeAgent를
  구현하려면 M_05 `GemmaChatAgent`와 시그니처 호환 Mock이 필요하다.
- **결정 필요**: Mock 생성 권한을 Integrator에게 부여하는가? 본 문서 기본 가정: **Yes**. 이유: M_05 공개 API를
  존중한 Mock이므로 CLAUDE.md "REQUIREMENTS에 없는 기능 추가 금지" 위배 없음(테스트 인프라).

---

## 7. 리스크와 완화

### R-E2E-1: 실제 모델 I/O의 flaky성

- **증상**: Gemma TTFT가 CPU에서 10~30s 편차(아키텍처 §6.2 근거). Whisper int8도 짧은 오디오에서 타임아웃.
- **완화**: 
  1. `@pytest.mark.timeout(60)` 관대하게 설정.
  2. 자동 재시도 금지(결함 은폐). 실패 시 `pytest --last-failed`로 수동 재실행.
  3. 실패 시 `tests/e2e/artifacts/<scenario>/` 아래에 WS 프레임 dump + 로그 수집 hook(`pytest_runtest_makereport`).
- **잔여 리스크**: TFFT 초과로 E2E-01, E2E-02 간헐 실패 가능. RECOMMENDED(GPU) 환경에서는 해소.

### R-E2E-2: APScheduler 실제 기동과 FakeScheduler 간 동작 차이

- **증상**: FakeScheduler는 `trigger_job()`으로 즉시 실행. 실제 `AsyncIOScheduler`는 이벤트 루프에 예약.
- **완화**: E2E-05, E2E-09가 실제 `AsyncIOScheduler` 사용 필수(§5 수락 기준 #4). `morning_time` 또는
  `reminder_check_interval_seconds`를 테스트 편의용 작은 값(3초, 2초)으로 오버라이드.
- **잔여 리스크**: 이벤트 루프 경합으로 트리거 지연 관측 → 타임아웃 10초 확보.

### R-E2E-3: Windows vs Linux 플랫폼 차이

- **증상**: IdleMonitor의 `PynputBackend`/`Win32IdleBackend`는 Linux에서 `NoopBackend`로 폴백. 
- **완화**: 
  - E2E-06, E2E-24, E2E-25는 `NoopBackend` + 콜백 직접 호출로 우회. Linux CI 호환.
  - Windows 실기동 QA는 **E2E 범위 외**, `docs/WINDOWS_SMOKE_CHECKLIST.md`(별도 문서, Phase 4 산출)에 수동 체크리스트로 분리.
- **잔여 리스크**: 실제 Windows 입력 이벤트 후크 동작은 자동화 불가 → 수동 QA 의존.

### R-E2E-4: WebSocket 프레임 스키마 누락 검증

- **증상**: upstream이 `full-text`, `control`, `audio` 프레임 스키마를 수시 변경할 수 있음.
- **완화**: 각 assertion은 **필드 존재**(hasattr/keys)만 확인하고 **값 타입**은 느슨하게. 스키마 변경 추적은
  `tests/app/test_upstream_integrity.py`(기존 파일) 활용.
- **잔여 리스크**: upstream 메이저 변경 시 다수 E2E 파일 동시 수정 필요.

### R-E2E-5: Gemma가 시스템 프롬프트 지시를 무시

- **증상**: E2E-04, E2E-07, E2E-08, E2E-22에서 Gemma가 citation/태그를 생략할 가능성.
- **완화**: 
  1. 시스템 프롬프트에 "반드시 인용 포함", "반드시 태그 붙여라" 명시.
  2. 3회 재시도는 금지(결함 은폐). 실패 시 FAIL 유지.
  3. 백업으로 E2E-07, E2E-22, E2E-30, E2E-31은 FakeAgent 모드 버전도 함께 제공.
- **잔여 리스크**: 실제 Gemma 버전이 바뀌면 프롬프트 튜닝 필요 → M_05 system prompt 업데이트와 연동.

### R-E2E-6: 테스트 데이터 누적으로 디스크 고갈

- **증상**: 매 테스트마다 LanceDB·SQLite·WAV 캐시 생성 → `tmp_path` 정리 의존.
- **완화**: `tmp_path_factory`가 pytest 세션 종료 시 자동 정리. 단 세션 도중에는 누적 → `--basetemp` 명시로
  격리.
- **잔여 리스크**: 21건 × 수백MB(LanceDB+WAV) = 수GB 임시 사용. 디스크 여유 20GB 권장.

### R-E2E-7: `block_external_network` fixture가 내부 정상 트래픽 차단

- **증상**: Ollama(`127.0.0.1:11434`)나 테스트 서버(`127.0.0.1:<port>`) 자체가 차단되어 E2E 전체 실패.
- **완화**: pytest-socket의 `allow_hosts` 파라미터에 `["127.0.0.1", "localhost"]` + `OLLAMA_BASE_URL` 파싱
  host 추가. 정적 검사(`test_static_guard.py`)만으로 대체 불가 — 런타임 가드 병행.
- **잔여 리스크**: 개발 환경의 `OLLAMA_BASE_URL=http://192.168.219.109:11434`는 사설 IP이므로 화이트리스트에
  포함. 프로덕션 빌드에서는 127.0.0.1로 강제 — 기존 `enforce_private_url` 정책 준수.

---

## 8. 요약

- **E2E의 정의**: 백엔드 FastAPI + WebSocket + 로컬 모델(Ollama/Whisper/MeloTTS/BGE-M3) 실제 추론까지. UI는 제외.
- **시나리오 수**: 골든 9 + 엣지 8 + 적대적 4 = **21건** (요구 최소 17건 상회).
- **오프라인 보장**: `pytest-socket` + custom getaddrinfo patch + 정적 URL 스캔.
- **실제 AsyncIOScheduler 스모크**: E2E-05, E2E-09 필수 포함(R2 리뷰 §검토하지 못한 영역 #1 해소).
- **startup hook 검증**: E2E-05 또는 E2E-06이 `create_app` 경유 기동(리뷰 §2 해소).
- **FakeAgent 허용 범위**: 적대적 시나리오(E2E-30/31/33)와 proactive 단독 시나리오(E2E-05/06/09/24/25).
- **M_06 HOLD 대응**: MD 파일 기반 RAG 시드(Q-4 옵션 A 기본 가정).
- **Windows 전용 기능**(IdleMonitor 입력 후크, 펫 모드)은 E2E 범위 외 — 별도 수동 QA 체크리스트.

본 문서가 승인되면 Integrator가 `tests/e2e/conftest.py`와 시나리오별 테스트 파일 21개를 `docs/MODULES.md`
상태를 건드리지 않고 순차 구현한다.
