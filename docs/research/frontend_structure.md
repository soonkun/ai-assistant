# Research: Open-LLM-VTuber Frontend 구조

## 서브모듈 체크아웃 상태

**비어 있음.** `upstream/Open-LLM-VTuber/frontend/` 디렉토리가 존재하나 파일이 없다.

- `.gitmodules` 내용:
  ```
  [submodule "frontend"]
      path = frontend
      url = https://github.com/Open-LLM-VTuber/Open-LLM-VTuber-Web
      branch = build
  ```
- 서브모듈 체크아웃 명령: `git submodule update --init upstream/Open-LLM-VTuber/frontend`
- 출처: `/mnt/c/projects/ai-assistant/upstream/Open-LLM-VTuber/.gitmodules`

---

## 기술 스택

**미확인** — 서브모듈 미체크아웃, 외부 GitHub 접속 차단.  
체크아웃 후 `package.json` 확인 필요.

---

## WebSocket 메시지 타입 목록

서브모듈 코드 없이 백엔드 Python 코드에서 역추적 추출.

### 클라이언트 → 서버

| 메시지 type | 설명 | 출처 파일 |
|---|---|---|
| `add-client-to-group` | 그룹에 클라이언트 추가 | `websocket_handler.py` |
| `remove-client-from-group` | 그룹에서 클라이언트 제거 | 동일 |
| `request-group-info` | 그룹 정보 요청 | 동일 |
| `fetch-history-list` | 히스토리 목록 요청 | 동일 |
| `fetch-and-set-history` | 특정 히스토리 불러오기 | 동일 |
| `create-new-history` | 새 히스토리 생성 | 동일 |
| `delete-history` | 히스토리 삭제 | 동일 |
| `interrupt-signal` | 대화 인터럽트 (text: 들린 응답) | 동일 |
| `mic-audio-data` | 마이크 오디오 청크 (audio: float[]) | 동일 |
| `mic-audio-end` | 마이크 오디오 종료 → 대화 시작 | 동일 |
| `raw-audio-data` | VAD용 원시 오디오 청크 | 동일 |
| `text-input` | 텍스트 입력 (text: string, images: []) | 동일 |
| `ai-speak-signal` | 프로액티브 발화 트리거 | 동일 |
| `fetch-configs` | 설정 파일 목록 요청 | 동일 |
| `switch-config` | 설정 파일 전환 (file: string) | 동일 |
| `fetch-backgrounds` | 배경 이미지 목록 요청 | 동일 |
| `audio-play-start` | 오디오 재생 시작 알림 (display_text: dict) | 동일 |
| `request-init-config` | 초기 설정 요청 | 동일 |
| `heartbeat` | 연결 유지 핑 | 동일 |
| `frontend-playback-complete` | 프론트엔드 재생 완료 신호 | 동일 |

### 서버 → 클라이언트

| 메시지 type | 주요 필드 | 출처 파일 |
|---|---|---|
| `full-text` | `text: string` | `conversation_utils.py` |
| `set-model-and-conf` | `model_info, conf_name, conf_uid, client_uid` | `service_context.py:525,536,554` |
| `control` | `text: "start-mic"\|"interrupt"\|"mic-audio-end"\|"conversation-chain-start"\|"conversation-chain-end"` | `conversation_utils.py` |
| `group-update` | `members: [], is_owner: bool` | `chat_group.py:191` |
| `group-operation-result` | `success: bool, message: string` | `chat_group.py:209,224` |
| `history-list` | `histories: []` | `websocket_handler.py` |
| `history-data` | `messages: []` | 동일 |
| `new-history-created` | `history_uid: string` | 동일 |
| `history-deleted` | `success: bool, history_uid: string` | 동일 |
| `error` | `message: string` | 동일 |
| `audio` | `audio: base64\|null, volumes: [], slice_length: int, display_text: dict, actions: dict, forwarded: bool` | `stream_audio.py` |
| `user-input-transcription` | `text: string` | `conversation_utils.py` |
| `backend-synth-complete` | (없음) | `conversation_utils.py` |
| `force-new-message` | (없음) | `conversation_utils.py` |
| `config-files` | `configs: []` | `websocket_handler.py` |
| `config-switched` | `message: string` | 동일 |
| `background-files` | `files: []` | 동일 |
| `tool_call_status` | `name: string, ...` | `conversation_utils.py` |
| `heartbeat-ack` | (없음) | `websocket_handler.py` |

**출처 파일 전체 목록:**
- `upstream/src/open_llm_vtuber/websocket_handler.py`
- `upstream/src/open_llm_vtuber/conversations/conversation_utils.py`
- `upstream/src/open_llm_vtuber/utils/stream_audio.py`
- `upstream/src/open_llm_vtuber/service_context.py`
- `upstream/src/open_llm_vtuber/chat_group.py`

---

## 펫 모드 구현

**미확인** — 서브모듈 비어 있음.

존재 근거:
- `upstream/assets/i2_pet_vscode.jpg`, `i4_pet_desktop.jpg` — 펫 모드 스크린샷 이미지 파일 존재.
- `upstream/README.KR.md:49` — "특히 투명 배경 데스크톱 펫 모드를 지원하여, AI 동반자가 화면 어디에서든 함께할 수 있습니다"

구현 기술(Electron `transparent: true`? Tauri? CSS backdrop-filter?) 미확인.

---

## 드래그 이동 구현

**미확인** — 서브모듈 비어 있음. 서버 측 코드에 드래그 관련 메시지 타입 없음 → 순수 프론트엔드 구현으로 추정.

---

## 미확인 사항

1. 프론트엔드 기술 스택 — `git submodule update --init upstream/Open-LLM-VTuber/frontend` 실행 후 `package.json` 확인 필요.
2. 펫 모드 투명 배경 구현 방식.
3. 드래그 이동 구현 파일 및 좌표 처리.
4. `build` 브랜치의 실제 빌드 산출물 구조.
5. 클라이언트가 보내는 추가 메시지 타입 (백엔드에서 무시되는 타입 포함).

---

## 참조

- `/mnt/c/projects/ai-assistant/upstream/Open-LLM-VTuber/.gitmodules`
- `/mnt/c/projects/ai-assistant/upstream/Open-LLM-VTuber/src/open_llm_vtuber/websocket_handler.py`
- `https://github.com/Open-LLM-VTuber/Open-LLM-VTuber-Web` (branch: build) — 외부 접속 필요
