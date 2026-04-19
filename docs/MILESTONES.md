# MILESTONES — Phase 2 구현 순서와 DoD

본 문서는 Phase 1 Planner 산출물이다. `docs/MODULES.md`에 정의된 12개 모듈을 어떤 순서로, 어떤 완료 기준으로 구현할지 기술한다.

- 기간 단위: 인일(person-day, 1인 8시간 환산). 실제 일정은 테스트·리뷰 라운드에 따라 변동 가능.
- DoD(Definition of Done) 공통 항목(CLAUDE.md "산출물 체크리스트"에서 차용):
  - `specs/M_NN_*.md` 작성 및 사용자 승인
  - `src/<module>/` 구현 완료
  - `tests/<module>/` 테스트: 정상 ≥5, 엣지 ≥5, 적대적 ≥3
  - `pytest`, `ruff check`, `ruff format --check`, `mypy src/` 모두 통과
  - `reviews/M_NN_*.md`에 Critic PASS
  - `docs/MODULES.md`의 해당 모듈 상태가 ✅ DONE으로 갱신
- 본 문서는 위 공통 DoD에 **모듈 고유 기준**을 덧붙인다.

---

## 구현 순서 요약

```
[Week 1]   M_01 → M_03 (reuse 검증)
[Week 2]   M_02 (ASR) ─┬─ M_04 (TTS)            # 병렬 가능
                       └─ M_07 (Vector search)   # 병렬 가능
[Week 3]   M_09 (Calendar)   ← M_06 HOLD로 단독 진행
[Week 4]   M_05b (ToolRouter) ← M_07, M_09 (M_06 연결은 샘플 확보 후 추가)
           M_05  (LLMAgent)  ← M_05b
[Week 5]   M_08 (AvatarState), M_10 (IdleMonitor)   # 병렬
[Week 6]   M_11 (ProactiveDispatcher)
[Week 7-8] M_12 (Frontend: fork, 스프라이트 렌더러, 펫 모드 검증)
[Week 8b]  M_06 (DocumentIngest) ← HWPX 샘플 확보 후 착수, M_07 의존
[Week 9]   Integration + E2E (integrator 에이전트)
[Week 10]  오프라인 번들 빌드, 검증, 출시
```

총 Phase 2 예상 기간: **8~10주 (1인 기준)**. 병렬화 시 5~7주로 단축 가능하나 본 프로젝트는 1인/세션 가정.

---

## M_01 AppCore

- **예상 공수**: 2 인일
- **DoD 고유 기준**
  - `AppServiceContext`가 upstream `ServiceContext`를 상속하고 6개 확장 필드(rag/calendar/idle/avatar/proactive/screenshot)를 `None` 초기화.
  - FastAPI `create_app()`이 YAML 설정을 로드해 `/client-ws` 엔드포인트를 띄운다.
  - `OLLAMA_BASE_URL` 환경변수가 없으면 `conf.yaml`의 값 사용, 그것도 없으면 `http://127.0.0.1:11434`.
  - 비사설 URL(예: `https://*.com`)을 설정하면 기동이 거부된다(화이트리스트 검증).
  - WebSocket 메시지 타입 등록: upstream 기본 + `screenshot-trigger`, `start-continuous-capture`, `stop-continuous-capture`.
  - 새 메시지 타입 3종에 대한 단위 테스트(정상 수신/에러 분기) 포함.

## M_02 ASREngine

- **예상 공수**: 1.5 인일
- **DoD 고유 기준**
  - `KoreanWhisperASR.async_transcribe_np`가 16kHz/mono/float32 numpy 배열을 받아 한국어 문자열을 반환한다.
  - 모델 경로는 `assets/models/whisper-large-v3-int8/`로 고정, 부재 시 `ASRInitError`.
  - 10초 한국어 샘플 WAV에 대해 WER(Word Error Rate) ≤ 20%(FLEURS-ko 임의 샘플 10건으로 측정).
  - `language="en"` 전달 시 영어 인식 동작 확인(CJK 혼합 케이스 포함).
  - 빈 오디오(≤100ms) 입력 시 빈 문자열 반환, 예외 없음.

## M_03 VADEngine

- **예상 공수**: 0.5 인일
- **DoD 고유 기준**
  - upstream `silero.py`를 `VADFactory`로 그대로 생성 확인.
  - `threshold`, `min_silence_duration_ms`가 `conf.yaml`에서 주입 가능.
  - 5초 묵음 + 3초 발화 합성 오디오에서 `<|PAUSE|>` / `<|RESUME|>` 신호가 정확한 타임스탬프 ±150ms 이내에서 발생.

## M_04 TTSEngine

- **예상 공수**: 3 인일
- **DoD 고유 기준**
  - `MeloTTSEngine.async_generate_audio("안녕하세요")`가 WAV 파일(24kHz)을 생성하고 절대 경로 반환.
  - 첫 청크(스트리밍) 생성까지 CPU(i7-12700 기준) 800ms 이하.
  - `XttsV2Engine`: 화자 WAV(3~6초)가 주어지면 한국어 합성 가능, 없으면 `__init__`에서 `ValueError`.
  - MeloTTS 모델 번들 크기 ≤ 500MB 확인(`scripts/bundle_deps.sh`로 측정).
  - XTTS v2는 모델이 없으면 import 자체를 지연시켜 앱 기동을 막지 않는다.

## M_07 VectorSearch

- **예상 공수**: 3 인일
- **DoD 고유 기준**
  - `Embedder.embed_passages(["안녕하세요"])`가 `(1,1024)` float32 배열 반환.
  - `VectorStore.upsert` → `search` 왕복이 동일 `doc_id` 청크를 상위 3위 내에서 재현한다(자체 round-trip 테스트).
  - `RagService.retrieve(query)`가 `min_score=0.35` 미만일 때 `found=False`.
  - 단일 쿼리 검색(top_k=8)이 CPU에서 평균 300ms 이하.
  - LanceDB 테이블 스키마: `vector`(1024 float32), `doc_id`, `doc_name`, `page`, `section`, `chunk_id`, `text`, `bbox`, `source_path`.
  - `Embedder`는 `float16` 저장 모델을 `device="cpu"`에서 로드할 때 자동으로 float32로 승격.

## M_09 CalendarService

- **예상 공수**: 1.5 인일
- **DoD 고유 기준**
  - `add_event(title, start, duration_minutes)`가 `start` tz-aware 여부를 검사하고 없으면 Asia/Seoul로 가정.
  - `get_events(start, end)`가 `start <= e.start < end` 범위를 반환, 정렬은 `start asc`.
  - `events_due_within(10)`이 현재 시각 기준 10분 이내 이벤트만 반환하며, 이미 지난 이벤트는 제외.
  - SQLite 파일이 없을 때 자동 생성, 스키마 마이그레이션은 `PRAGMA user_version` 기반 단순 번호 비교.
  - 1만건 이벤트 데이터에서 `get_events(1일 범위)`가 50ms 이하.

## M_05b ToolRouter

- **예상 공수**: 2 인일
- **DoD 고유 기준**
  - `tool_specs()` 반환값이 Gemma/Ollama tool schema 포맷을 통과(JSON Schema validator + 스파이크 스크립트와 동일 구조).
  - `dispatch("add_event", {...})`가 M_09을 호출, 성공 결과의 `payload`에 `event_id`가 포함.
  - `dispatch("search_docs", {...})`는 M_07의 `RetrievalResult`를 `{answer_hints, citations}` 형태로 변환해 반환.
  - `dispatch("take_screenshot", {...})`는 Windows 환경에서 `mss`로 PNG를 캡처해 base64 문자열로 반환, 미지원 환경에서는 `ok=False` + 명시적 메시지.
  - 알 수 없는 툴 이름 → `ok=False`, `error="unknown_tool"`.
  - 잘못된 인자(JSON Schema 위반) → `ok=False`, `error`에 필드명 포함.

## M_05 LLMAgent

- **예상 공수**: 3 인일
- **DoD 고유 기준**
  - `chat(batch)`가 스트리밍 `AgentEvent` 이터레이터를 반환, 첫 `TextChunk`까지 TTFT를 로그에 기록.
  - tool call 이벤트 수신 → M_05b 호출 → 결과를 messages에 주입 → 최종 답변 생성까지 전 과정이 단일 `chat()` 실행 내에서 완결.
  - `handle_interrupt(heard_text)`가 upstream의 interrupt injection 경로를 사용해 현재 턴을 조기 종료하고 다음 턴에 "(끊어들은 텍스트)"를 user turn으로 삽입.
  - Ollama 연결 실패(3회 재시도) → `AgentBackendError` + 사용자 친화 메시지("모델 서버에 연결할 수 없어요").
  - Gemma FC 스파이크의 10건 케이스가 통합 테스트로 포함되어 회귀 시 자동 실패한다.
  - `OLLAMA_BASE_URL` 환경변수가 사설 IP/loopback이 아니면 기동 거부.

## M_08 AvatarState

- **예상 공수**: 1 인일
- **DoD 고유 기준**
  - `extract_emotion("오늘 [emotion:happy] 기분 좋아")` → `("오늘  기분 좋아", "happy")`.
  - 7종 감정(`neutral, happy, surprised, sad, worried, thinking, sleepy`) 외 값 → `neutral`로 폴백 + 로그 경고.
  - `push_event` 호출 시 WebSocket 송신 페이로드가 스키마에 부합(`{type:"avatar-state", emotion, crossfade_ms, speaking}`).
  - 여러 번 연속 호출되어도 최종 1건만 전송되도록 직렬화(내부 async lock).

## M_10 IdleMonitor

- **예상 공수**: 1.5 인일
- **DoD 고유 기준**
  - `start()` 후 45분 무입력 가정(가상 시계 주입) → `idle_rest` 콜백 1회 호출.
  - 이어서 10분 뒤 같은 상태 유지 → 쿨다운으로 추가 호출 없음.
  - 2시간 연속 입력 → `overwork` 콜백 1회 호출, 쿨다운 존중.
  - `set_dnd(True)` 후에는 모든 이벤트가 drop되며, 해제 후 다음 조건 달성 시 다시 방출.
  - 훅 초기화 실패 시 예외를 삼키고 서비스는 no-op로 기동.

## M_11 ProactiveDispatcher

- **예상 공수**: 2 인일
- **DoD 고유 기준**
  - `start()` 후 매일 09:00에 `morning_briefing` emit. APScheduler `CronTrigger` 사용.
  - 1분 주기 `events_due_within(10)` 폴링 → 일정 10분 전 `event_reminder`를 딱 1회 emit.
  - `IdleMonitor`에서 전달된 `idle_rest`/`overwork` 이벤트를 같은 쿨다운 규칙으로 재방출.
  - `emit()`가 쿨다운/DND로 drop된 경우 `False` 반환.
  - 모든 emit이 upstream `ai-speak-signal` 메시지 형태(`{"type":"ai-speak-signal","text":<prompt>}`)로 WebSocket에 전달.

## M_12 Frontend

- **예상 공수**: 8 인일 (fork + 스프라이트 렌더러 + 펫 모드 검증 + PDF viewer 연동)
- **DoD 고유 기준**
  - upstream `frontend` 서브모듈을 본 레포 하위로 fork(별도 저장소 또는 서브디렉토리)해 커스터마이즈.
  - `SpriteSwapRenderer`가 PNG 7종을 로드해 `setEmotion` 호출 시 200~300ms CSS crossfade 수행.
  - 숨쉬기/깜빡임/립싱크 펄스 애니메이션이 CSS keyframes로 구현되어 JS 호출 없이도 동작.
  - 펫 모드(`BrowserWindow({transparent:true, frame:false, alwaysOnTop:true})` + `setIgnoreMouseEvents(true,{forward:true})`)가 Windows 10·11에서 실제 동작 확인.
  - 드래그 이동: 지정된 드래그 핸들 영역(캐릭터 몸통 전체) 클릭 중에는 `setIgnoreMouseEvents(false)`로 전환해 드래그 가능.
  - 인용 배지 클릭 → pdf.js가 해당 PDF를 열고 `page` 파라미터로 스크롤, `bbox`가 있으면 하이라이트 사각형 렌더.
  - 서버가 없는 상태에서 UI만 기동해도 "서버에 연결 중…" 오류 페이지가 뜨며 재시도를 반복.

## M_06 DocumentIngest ⚠️ HOLD

> **착수 조건**: `assets/hwpx_samples/` 에 실제 사내 HWPX 파일 5건(PII 제거) 배치 후 착수.
> M_12 완료 이후, 샘플이 준비되는 시점에 맞춰 Week 8b에 삽입.

- **예상 공수**: 4 인일 (HWPX 포함)
- **DoD 고유 기준**
  - `ingest_file`이 PDF / DOCX / PPTX / HWPX / TXT / MD 6종 확장자를 모두 처리.
  - PDF는 `page` 필드와 `bbox` 필드를 모두 채움(pypdfium2 텍스트 블록 좌표).
  - HWPX는 스파이크 합성 샘플 3종 + 실제 사내 샘플 5종 모두 섹션·단락 추출 성공(`docs/research/hwpx_spike.md` 회귀 포함).
  - 청크 크기 기본 800자, overlap 100자. 청크 경계는 문장 경계에 맞추는 것을 우선(한국어는 `pysbd` 또는 `kss` 사용 여부를 SPEC 단계에서 결정).
  - 손상된 HWPX 파일 1개를 포함한 배치에서 전체 실패 없이 성공 N건 + skip 1건으로 처리.
  - 지원하지 않는 확장자(`.xlsx` 등) → `UnsupportedFormatError` raise, 배치에서는 skip + warning.

---

## 통합·E2E 마일스톤 (M_13 상당, Integrator 담당)

- **예상 공수**: 5 인일
- **DoD**
  - 시나리오 E2E 테스트 (GPU/CPU 각 1회씩 실행 결과 보관):
    1. 마이크 입력 → 한국어 답변 음성 출력(인터럽트 포함).
    2. "내일 오후 3시에 마케팅 팀 회의 있어" → `CalendarService`에 이벤트 적재 → `get_events`로 조회 가능.
    3. 사전 등록된 PDF에 대해 "승인 절차" 질문 → 답변 + 인용(`파일명.pdf` 12페이지) 반환.
    4. 45분 유휴 조작 시 프로액티브 메시지 발화 확인.
    5. 09:00 `morning_briefing` 트리거 확인(가상 시계).
    6. "화면 봐줘" → 화면 캡처 → Gemma 4 E4B 멀티모달 응답 수신.
  - 메모리 실측: `psutil`로 상위 10분 구간의 피크 RSS 측정 → RISKS.md R-02 판정.
  - 응답 지연 실측: GPU·CPU 환경에서 위 시나리오 1의 "발화 끝 → AI 첫 음성" 시간 기록.

## 오프라인 번들 빌드 마일스톤

- **예상 공수**: 3 인일
- **DoD**
  - `scripts/bundle_deps.sh`가 모든 Python 휠, Ollama 모델, BGE-M3, Whisper, MeloTTS, Silero VAD 파일을 `dist/offline-bundle/`에 수집.
  - `scripts/install.ps1`이 깨끗한 Windows 11 VM에서 외부 인터넷이 차단된 상태로 실행되어 기동까지 성공.
  - `scripts/verify_offline.ps1`이 Ollama 바인드 주소(`127.0.0.1`) 확인 + Windows 방화벽 아웃바운드 드롭 규칙 테스트를 수행.

---

## 변경 통제

본 마일스톤 순서나 DoD를 수정하려면 `docs/CHANGE_REQUESTS.md`를 생성하고 사용자 승인을 받는다. Builder/Critic이 독자 판단으로 변경하지 않는다(CLAUDE.md).
