# GAP Analysis — Open-LLM-VTuber vs 요구사항

## 분석 요약

- 전체 분류: **REUSE 6개, EXTEND 14개, NEW 10개**
- upstream은 FastAPI + WebSocket 기반 서버, Factory 패턴 ASR/TTS/LLM/VAD 어댑터 시스템, MCP 통합, Live2D 아바타 파이프라인을 갖추고 있다.
- faster-whisper, Piper TTS, Silero VAD, Ollama(OpenAI 호환) LLM 어댑터가 이미 구현되어 있어 §8 모델 요구사항 대부분에 EXTEND 적용 가능하다.
- 문서 RAG(§2), 스케줄링·다이어리(§4), 휴식 권고(§5)는 upstream에 전혀 없으므로 NEW로 처음부터 구현해야 한다.
- 캐릭터 아바타(§3)는 upstream이 Live2D 기반이나, 요구사항은 스프라이트 PNG 7종이므로 렌더러 교체가 필요하다(EXTEND).
- upstream의 `input_types.py`가 이미 `ImageSource.SCREEN`을 정의하고 있어 화면 인식(§6) 파이프라인의 일부는 존재한다.

---

## 항목별 분류

### §1.1 음성 대화

| 기능 | 분류 | upstream 근거 | 필요 작업 |
|---|---|---|---|
| STT (faster-whisper) | EXTEND | `src/open_llm_vtuber/asr/faster_whisper_asr.py` — `VoiceRecognition` 클래스 존재 | `language: 'ko'` 설정, 한국어 모델 경로 지정, 오프라인 번들용 모델 사전 다운로드 |
| VAD (Silero) | REUSE | `src/open_llm_vtuber/vad/silero.py` — `VADEngine` + `StateMachine` 완전 구현 | conf.yaml에서 `silero_vad` 섹션 파라미터 튜닝만 필요 |
| TTS (Piper 한국어) | EXTEND | `src/open_llm_vtuber/tts/piper_tts.py` — `TTSEngine` 구현 존재, 한국어 모델 경로 예시 없음 | 한국어 Piper 모델(`ko_KR-*`) 확보 및 모델 경로 설정 |
| TTS (CosyVoice 2 옵션) | REUSE | `src/open_llm_vtuber/tts/cosyvoice2_tts.py` — Gradio 기반 클라이언트 구현 존재 | CosyVoice 2 서버 별도 구동 필요 (오프라인 배포 계획 수립 필요) |
| Full Duplex (끼어들기 인터럽트) | REUSE | `src/open_llm_vtuber/agent/agents/basic_memory_agent.py` — `handle_interrupt()` 구현; VAD가 `<\|PAUSE\|>` 신호 전송; WebSocket 핸들러가 중단 처리 | 추가 구현 불필요, 설정 확인만 |
| 마이크 연속 청취 | REUSE | `src/open_llm_vtuber/vad/silero.py` — 연속 청취 + 발화 구간 감지 | 추가 구현 불필요 |

### §1.2 텍스트 대화

| 기능 | 분류 | upstream 근거 | 필요 작업 |
|---|---|---|---|
| 채팅 UI 텍스트 입력 | REUSE | `src/open_llm_vtuber/conversations/conversation_handler.py` — `msg_type == "text-input"` 처리 분기 존재 | 추가 구현 불필요 |
| 음성·텍스트 히스토리 통합 | REUSE | `src/open_llm_vtuber/chat_history_manager.py` — JSON 파일 기반 단일 히스토리; `store_message()`, `get_history()` 존재 | 추가 구현 불필요 |

### §2 문서 RAG

| 기능 | 분류 | upstream 근거 | 필요 작업 |
|---|---|---|---|
| 문서 파싱 (PDF/DOCX/PPTX/HWP/TXT/MD) | NEW | upstream에 문서 파싱 코드 없음 | Docling + PyMuPDF 기반 신규 구현 |
| 청크·임베딩 (BGE-M3) | NEW | upstream에 임베딩 파이프라인 없음 | sentence-transformers + BGE-M3 신규 구현 |
| 벡터 DB (LanceDB) | NEW | upstream에 벡터 DB 없음 | LanceDB 신규 구현 |
| 인용 포함 질의응답 | NEW | upstream에 RAG 파이프라인 없음 | retriever + citation formatter 신규 구현 |
| 리랭커 (Qwen3-Reranker-8B) | NEW | upstream에 리랭커 없음 | 필요 시 신규 구현 |

### §3 캐릭터 아바타

| 기능 | 분류 | upstream 근거 | 필요 작업 |
|---|---|---|---|
| 감정 태그 파싱 (`[emotion:happy]`) | REUSE | `src/open_llm_vtuber/live2d_model.py` — `extract_emotion()` 메서드가 `[key]` 형식 태그 파싱 | 태그 형식 `[emotion:happy]` → `[happy]` 변환 여부 확인 필요 |
| 스프라이트 스왑 렌더러 | EXTEND | upstream은 Live2D 렌더러 전제. `Live2dModel` 클래스가 `model_dict.json` 기반으로 동작 | `AvatarRenderer` 인터페이스 신규 정의 + 스프라이트 PNG 기반 구현체 교체 |
| 펫 모드 (투명 배경, 최상위, 클릭 관통) | REUSE | upstream README 및 `assets/i2_pet_vscode.jpg`, `assets/i4_pet_desktop.jpg`에서 기능 확인; 프론트엔드 구현체 존재 | 프론트엔드 서브모듈 실제 구현 확인 필요 (미확인) |
| 드래그 이동 | REUSE | README에서 "drag your AI companion anywhere" 명시 | 프론트엔드 서브모듈 실제 구현 확인 필요 (미확인) |
| 아이들 애니메이션 (숨쉬기, 깜빡임) | EXTEND | upstream은 Live2D 모션 기반. 스프라이트 방식으로는 CSS/JS 애니메이션 새로 작성 필요 | 스프라이트용 CSS 애니메이션 신규 구현 |
| 립싱크 (opacity 펄스) | EXTEND | upstream은 Live2D 립싱크. V1 opacity 펄스는 별도 구현 필요 | 스프라이트용 opacity 펄스 신규 구현 |
| 표정 crossfade (200~300ms) | NEW | upstream Live2D에서는 자체 fade 지원. 스프라이트 방식 crossfade 구현 없음 | CSS transition 기반 crossfade 신규 구현 |

### §4 스케줄링·다이어리

| 기능 | 분류 | upstream 근거 | 필요 작업 |
|---|---|---|---|
| 자연어 → 일정 파싱 (function calling) | NEW | upstream MCP + OpenAI tool call 인프라 존재(`basic_memory_agent.py`)하나 캘린더 툴 없음 | `add_event()` 함수 스키마 정의 + 캘린더 MCP 서버 신규 구현 |
| SQLite 로컬 저장 | NEW | upstream은 채팅 히스토리를 JSON으로 저장. SQLite 일정 DB 없음 | SQLite 스키마 + CRUD 신규 구현 |
| 10분 전 알림 (팝업 + 음성) | NEW | upstream에 스케줄러/타이머 없음 | APScheduler 기반 스케줄러 신규 구현 |
| 아침 일정 브리핑 | NEW | upstream에 없음 | 신규 구현 |
| 일정 조회 (자연어 쿼리) | NEW | upstream MCP function call 인프라 재사용 가능 | `get_events()` 함수 정의 신규 구현 |

### §5 휴식 권고 (유휴 감지)

| 기능 | 분류 | upstream 근거 | 필요 작업 |
|---|---|---|---|
| 마우스·키보드 유휴 감지 | NEW | upstream에 OS 입력 모니터링 없음 | `pynput` 또는 `pywin32` 기반 신규 구현 |
| 휴식 권고 메시지 트리거 | NEW | `conversation_handler.py`의 `ai-speak-signal` 프로액티브 발화 인프라 존재, 하지만 유휴 조건 없음 | 유휴 감지 → `ai-speak-signal` 주입 신규 구현 |
| 쿨다운 로직 | NEW | upstream에 없음 | 신규 구현 |
| 방해 금지 모드 | NEW | upstream에 없음 | 신규 구현 |

### §6 화면 인식

| 기능 | 분류 | upstream 근거 | 필요 작업 |
|---|---|---|---|
| 스크린샷 트리거 + 멀티모달 입력 | EXTEND | `src/open_llm_vtuber/agent/input_types.py` — `ImageSource.SCREEN` enum 정의, `BatchInput.images` 필드 존재; `basic_memory_agent.py`가 이미지 처리 | 스크린샷 캡처 코드(`mss`) + WebSocket 전송 로직 추가 |
| 연속 화면 공유 모드 | EXTEND | upstream에 단발 캡처만 있고 연속 모드 없음 | N초 자동 캡처 루프 신규 구현 |
| Gemma 4 비전 입력 | EXTEND | `openai_compatible_llm.py` — `image_url` 형식 멀티모달 메시지 구성 가능 | Gemma 4 E4B Ollama 엔드포인트 + 비전 메시지 포맷 확인 필요 |

### §7 MCP 확장 포인트

| 기능 | 분류 | upstream 근거 | 필요 작업 |
|---|---|---|---|
| MCP 서버 등록·실행 프레임워크 | REUSE | `src/open_llm_vtuber/mcpp/` — `ServerRegistry`, `MCPClient`, `ToolExecutor`, `ToolAdapter`, `ToolManager` 완전 구현 | `mcp_servers.json`에 사내 서버 추가만 필요 |
| DuckDuckGo 검색 MCP | REUSE | `mcp_servers.json`에 `ddg-search` 항목 존재(`uvx duckduckgo-mcp-server`) | 오프라인 환경에서 비활성 처리만 필요 |
| 파일 시스템 MCP | EXTEND | `mcp_servers.json`에 파일시스템 MCP 없음 | `@modelcontextprotocol/server-filesystem` npm 패키지 추가 및 허용 폴더 설정 |
| 사내 위키/Confluence MCP | NEW | upstream에 없음 | 가능 여부 미확인, 필요 시 MCP 서버 신규 구현 |

### §8 모델

| 기능 | 분류 | upstream 근거 | 필요 작업 |
|---|---|---|---|
| LLM: Gemma 4 E4B (Ollama) | EXTEND | `src/open_llm_vtuber/agent/stateless_llm/ollama_llm.py` — Ollama LLM 어댑터 존재 | conf.yaml `model: 'gemma4:e4b'`로 변경; 함수 호출 지원 여부 테스트 필요 |
| 임베딩: BGE-M3 | NEW | upstream에 임베딩 어댑터 없음 | sentence-transformers 기반 신규 구현 |
| STT: faster-whisper large-v3 | EXTEND | `asr/faster_whisper_asr.py` 존재 | 모델 경로 + 한국어 설정 |
| TTS: Piper (한국어) | EXTEND | `tts/piper_tts.py` 존재 | 한국어 ONNX 모델 확보 |
| TTS: CosyVoice 2 (옵션) | REUSE | `tts/cosyvoice2_tts.py` 존재 | 서버 배포 방식 확정 |
| 리랭커: Qwen3-Reranker-8B | NEW | upstream에 없음 | 필요 시 신규 구현 |

---

## upstream 핵심 구조 요약

### 어댑터 패턴

모든 AI 엔진은 추상 인터페이스를 상속하고 Factory 클래스를 통해 선택된다.

- `ASRInterface` → `ASRFactory` → `faster_whisper_asr.py`, `sherpa_onnx_asr.py` 등
- `TTSInterface` → `TTSFactory` → `piper_tts.py`, `cosyvoice2_tts.py` 등
- `VADInterface` → `VADFactory` → `silero.py`
- `AgentInterface` → `AgentFactory` → `BasicMemoryAgent`, `LettaAgent` 등
- `StatelessLLMInterface` → `StatelessLLMFactory` → `openai_compatible_llm.py`, `ollama_llm.py`, `claude_llm.py` 등

새 어댑터 추가 방법: (1) 인터페이스 상속 클래스 작성 → (2) Factory `if/elif` 분기 추가 → (3) `config_manager/` Pydantic 모델 확장 → (4) `conf.default.yaml`에 설정 블록 추가.

### ServiceContext

`src/open_llm_vtuber/service_context.py` — 의존성 주입 컨테이너. 각 WebSocket 세션마다 인스턴스 생성. `asr_engine`, `tts_engine`, `vad_engine`, `agent_engine`, `mcp_client` 등 모든 엔진 참조 보유. `load_from_config()`로 초기화, `load_cache()`로 재사용.

### 이벤트 버스 / WebSocket 프로토콜

별도의 이벤트 버스 클래스는 없다. 클라이언트 ↔ 서버 간 통신은 JSON WebSocket 메시지로 이루어진다.

주요 메시지 타입:
- 클라이언트→서버: `text-input`, `mic-audio-end`, `mic-audio-data`, `ai-speak-signal`, `config-switch`
- 서버→클라이언트: `full-text`, `set-model-and-conf`, `config-switched`, `error`, `audio`(TTS 스트림)

VAD 내부 신호: `<|PAUSE|>` (발화 시작), `<|RESUME|>` (발화 종료 + 오디오 청크).

### 설정 파일 스키마 (`conf.yaml` 최상위 구조)

```
system_config:      host, port, config_alts_dir, tool_prompts
character_config:   conf_name, conf_uid, live2d_model_name, character_name, persona_prompt
  agent_config:     conversation_agent_choice, agent_settings, llm_configs
  asr_config:       asr_model, faster_whisper, sherpa_onnx_asr, ...
  tts_config:       tts_model, piper_tts, cosyvoice2_tts, ...
  vad_config:       vad_model, silero_vad
live_config:        bilibili_live
```

`characters/` 디렉토리에 YAML 파일 추가 시 런타임에 캐릭터 전환 가능. 기본 `conf.yaml`과 deep merge 방식으로 오버라이드.

---

## 재사용 가능한 핵심 컴포넌트 목록

| 파일 경로 | 재사용 이유 |
|---|---|
| `src/open_llm_vtuber/asr/faster_whisper_asr.py` | faster-whisper 어댑터 완성 구현, 언어 설정만 변경하면 한국어 동작 |
| `src/open_llm_vtuber/asr/asr_interface.py` | 표준 ASR 인터페이스, 새 어댑터 추가 시 상속 |
| `src/open_llm_vtuber/tts/piper_tts.py` | Piper TTS 완성 구현, 한국어 모델 경로만 변경 |
| `src/open_llm_vtuber/tts/tts_interface.py` | 표준 TTS 인터페이스 |
| `src/open_llm_vtuber/tts/cosyvoice2_tts.py` | CosyVoice 2 연동 구현 존재 |
| `src/open_llm_vtuber/vad/silero.py` | Silero VAD 완성 구현, 그대로 재사용 가능 |
| `src/open_llm_vtuber/agent/agents/basic_memory_agent.py` | MCP tool call, 인터럽트 처리, 이미지 처리 파이프라인 포함 |
| `src/open_llm_vtuber/agent/agents/agent_interface.py` | 표준 에이전트 인터페이스 |
| `src/open_llm_vtuber/agent/stateless_llm/ollama_llm.py` | Ollama LLM 연동 (Gemma 4 E4B에 바로 적용 가능) |
| `src/open_llm_vtuber/agent/stateless_llm/openai_compatible_llm.py` | OpenAI 호환 멀티모달 메시지 구성 |
| `src/open_llm_vtuber/agent/input_types.py` | `ImageSource.SCREEN` 포함 멀티모달 입력 타입 정의 |
| `src/open_llm_vtuber/mcpp/` (전체) | MCP 서버 등록·실행·도구 호출 프레임워크 완성 구현 |
| `src/open_llm_vtuber/service_context.py` | 의존성 주입 컨테이너 패턴, 확장하여 재사용 |
| `src/open_llm_vtuber/conversations/single_conversation.py` | 대화 오케스트레이션 흐름 |
| `src/open_llm_vtuber/chat_history_manager.py` | 채팅 히스토리 저장/로드 (JSON 파일 기반) |
| `src/open_llm_vtuber/config_manager/` (전체) | Pydantic 기반 타입 안전 설정 관리 |
| `src/open_llm_vtuber/live2d_model.py` | `extract_emotion()` — `[key]` 태그 파싱 로직 재사용 가능 |
| `src/open_llm_vtuber/server.py` + `routes.py` | FastAPI WebSocket 서버 골격 |

---

## NEW 항목 목록 (처음부터 구현 필요)

| 항목명 | 이유 |
|---|---|
| 문서 파싱 엔진 (PDF/DOCX/PPTX/HWP/TXT/MD) | upstream에 파일 파싱 코드 전혀 없음 |
| 청크 + 임베딩 파이프라인 (BGE-M3) | upstream에 임베딩 기능 없음 |
| 벡터 DB 연동 (LanceDB) | upstream에 벡터 DB 없음 |
| RAG 질의응답 + 인용 생성기 | upstream에 없음 |
| 스케줄링 DB (SQLite) + CRUD | upstream에 없음 |
| 자연어 일정 파싱 (function calling 스키마) | MCP 인프라는 있으나 캘린더 툴 스키마 없음 |
| 10분 전 알림 + 아침 브리핑 스케줄러 | upstream에 타이머/스케줄러 없음 |
| 마우스·키보드 유휴 감지 (Windows API) | upstream에 OS 입력 모니터링 없음 |
| 쿨다운 + 방해 금지 모드 로직 | upstream에 없음 |
| 스프라이트 PNG 렌더러 (`AvatarRenderer` 구현체) | upstream은 Live2D 전용, 스프라이트 방식 없음 |
| 스프라이트용 CSS 애니메이션 (숨쉬기, 깜빡임, 립싱크 펄스, crossfade) | upstream은 Live2D 모션 사용 |
| 스크린샷 캡처 코드 + 연속 공유 루프 | upstream에 캡처 코드 없음 (타입 정의만 있음) |

---

## 미확인 사항

1. **펫 모드 / 드래그 이동 구현**: `frontend/`는 Git 서브모듈로, 현재 체크아웃 여부 미확인. README에는 기능이 언급되지만 실제 프론트엔드 코드를 읽지 못했다.
2. **Gemma 4 E4B 함수 호출 지원 여부**: Ollama에서 `gemma4:e4b` 모델이 OpenAI 호환 tool call API를 지원하는지 미확인. upstream `openai_compatible_llm.py`는 tool call 지원하나, 모델 자체 지원 여부는 별도 검증 필요.
3. **Piper 한국어 모델 가용성**: `piper_tts.py`에 한국어 예시 없음. 공식 Piper 모델 저장소에서 `ko_KR` 모델 존재 여부 및 품질 미확인.
4. **HWP/HWPX 파싱 라이브러리**: 오픈소스 HWP 파서의 완성도 및 라이선스 미확인.
5. **CosyVoice 2 오프라인 배포**: `cosyvoice2_tts.py`는 Gradio 웹UI 클라이언트 방식. 사내 인트라넷 환경에서 로컬 구동 방법 미확인.
6. **BGE-M3 한국어 실제 성능**: 한국어 문서 검색 벤치마크 수치 미확인.
7. **`frontend/` 서브모듈 코드**: WebSocket 메시지 타입 전체 목록 및 펫 모드 구현 세부사항 미확인.

---

## 참조 파일

- `upstream/Open-LLM-VTuber/src/open_llm_vtuber/asr/faster_whisper_asr.py`
- `upstream/Open-LLM-VTuber/src/open_llm_vtuber/tts/piper_tts.py`
- `upstream/Open-LLM-VTuber/src/open_llm_vtuber/tts/cosyvoice2_tts.py`
- `upstream/Open-LLM-VTuber/src/open_llm_vtuber/vad/silero.py`
- `upstream/Open-LLM-VTuber/src/open_llm_vtuber/agent/agents/basic_memory_agent.py`
- `upstream/Open-LLM-VTuber/src/open_llm_vtuber/agent/stateless_llm/ollama_llm.py`
- `upstream/Open-LLM-VTuber/src/open_llm_vtuber/agent/stateless_llm/openai_compatible_llm.py`
- `upstream/Open-LLM-VTuber/src/open_llm_vtuber/agent/input_types.py`
- `upstream/Open-LLM-VTuber/src/open_llm_vtuber/mcpp/` (전체)
- `upstream/Open-LLM-VTuber/src/open_llm_vtuber/service_context.py`
- `upstream/Open-LLM-VTuber/src/open_llm_vtuber/live2d_model.py`
- `upstream/Open-LLM-VTuber/src/open_llm_vtuber/chat_history_manager.py`
- `upstream/Open-LLM-VTuber/src/open_llm_vtuber/conversations/conversation_handler.py`
- `upstream/Open-LLM-VTuber/mcp_servers.json`
- `upstream/Open-LLM-VTuber/config_templates/conf.default.yaml`
