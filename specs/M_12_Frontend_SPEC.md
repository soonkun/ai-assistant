# M_12 Frontend — 스펙

> 분류: **FORK**(`upstream/Open-LLM-VTuber-Web`) + **NEW**(SpriteAvatarRenderer, PetWindowController, CitationViewer).
>
> 작성 근거:
> - `REQUIREMENTS.md` §3.1/§3.2/§3.3(스프라이트 7종 + study, crossfade 200~300ms, 숨쉬기/깜빡임/말하기 펄스, 펫 모드 투명·항상 위·클릭 관통, 드래그 이동), §4.2(일정 10분 전 팝업+음성, 아침 브리핑), §5(DND 토글), §6(화면 공유 트리거·연속 캡처 개인정보 경고), §7(인용 클릭 → 해당 페이지 하이라이트), §9(외부 네트워크 금지), §10(단일 사용자·모바일 제외).
> - `docs/ARCHITECTURE.md` L13~L95(프론트-백엔드 블록 다이어그램, `ws://127.0.0.1:12393/client-ws`), L103~L106(UI 레이어 = M_08+M_12 FORK+스프라이트 교체), L129~L142(RAG 질의응답 — 인용 배지 → PDF viewer), L157~L176(프로액티브 발화 경로 = `ai-speak-signal`), L178~L189(화면 인식 `screenshot-trigger`·`start-continuous-capture` + 개인정보 경고 1회), L300·L318·L372·L382(Electron 예산·빌드 산출물).
> - `docs/MODULES.md` L420~L439(M_12 초안: 분류/상태/목적/주요 책임/공개 API 시그니처/의존).
> - `docs/research/frontend_structure.md` L3~L15(서브모듈 비어 있음, `.gitmodules` url·branch=build), L28~L84(WS 메시지 타입 표), L86~L112(펫 모드·드래그 이동 구현 미확인).
> - `docs/CHARACTER_SAESSAGI.md` L5~L17(파일 배치 — `assets/character/saessagi/<emotion>.png` 8종 확정), L21~L34(표정 표), L46~L53(아이들 애니메이션: 숨쉬기/깜빡임/흔들림/바운스), L55~L68(감정 태그 프로토콜 — `_SPOKEN_EMOTIONS` 7종과 `study` 시스템 감정 분리).
> - `specs/M_01_AppCore_SPEC.md` §"WebSocket 메시지 타입"(L370~L505) — upstream REUSE 20종 + 신규 수신 4종(`screenshot-trigger`·`start-continuous-capture`·`stop-continuous-capture`·`set-dnd`) + 신규 송신 3종(`continuous-capture-state`·`avatar-state`·`dnd-state`), L411~L504 payload 계약. CR-10·CR-11 반영 완료.
> - `specs/M_08_AvatarState_SPEC.md` §4.1(Emotion Literal 8종, `_SPOKEN_EMOTIONS` 7종/`_VALID_EMOTIONS` 8종 분리), §6.3 D-3(백엔드가 1차 폴백 — 프론트는 서버가 준 키를 그대로 렌더하되 에셋 미보유 시 `neutral.png` 2차 폴백만 수행), §7(송신 페이로드 `{type:"avatar-state", emotion, crossfade_ms, speaking}`).
> - `specs/M_11_ProactiveDispatcher_SPEC.md` §1.3 #2(프론트 팝업 UI는 M_12 책임), §7.1/§7.3(payload: `{type:"ai-speak-signal", text, topic∈{morning_briefing,event_reminder,idle_rest,overwork}, context}`), §8.2 D-13(마지막 활성 클라이언트 단일 송신).
> - `docs/E2E_SCENARIOS.md` §E2E-01/07/31(`avatar-state` 프레임 수신·감정 태그 7종), §E2E-05/06/09/24/25(`ai-speak-signal` topic별 프레임), §E2E-26(세션 미형성 시 `screenshot-trigger` 친화 에러), §Q-3(UI 골든패스 미확정), §617(펫 모드·IdleMonitor는 E2E 범위 외 — 수동 QA).
> - `CLAUDE.md` "절대 금지"(외부 네트워크 호출, upstream 파일 수정), "오프라인 빌드 의무"(npm 패키지 번들, 모델 파일 git 제외).
> - `scripts/bundle_deps.sh` L25~L160(현행 Python wheel·HF 모델 번들링. npm 캐시 블록은 현재 **미존재** — 본 스펙이 신설 요구).

---

## §1. 목적·분류·상태

### §1.1 목적
사용자가 직접 상호작용하는 Electron 기반 데스크톱 클라이언트를 제공한다. 기능 축은 4개다.

1. upstream `Open-LLM-VTuber-Web`(branch `build`)의 채팅 UI·WebSocket 클라이언트·히스토리 패널을 **포크**해 재사용.
2. `AvatarRenderer` 스프라이트 구현(`SpriteAvatarRenderer`) — 표정 PNG 8종(7종 발화 + `study` 시스템) crossfade·아이들 애니메이션.
3. 펫 모드(`PetWindowController`) — 투명·항상 위·클릭 관통·드래그 이동을 제어하는 Electron BrowserWindow 컨트롤러.
4. `CitationViewer` — RAG 인용 클릭 시 로컬 PDF를 pdf.js로 열어 해당 페이지 스크롤 + bbox 하이라이트.

### §1.2 분류
- **FORK**: upstream `frontend/` 서브모듈 트리(React 채팅 UI, WS 클라이언트, 히스토리, 설정).
- **NEW**: `components/Avatar/SpriteAvatarRenderer.tsx`, `components/PetWindow/PetWindowController.ts`, `components/CitationViewer/*`, `ipc/pet-mode.ts` 및 Electron `main/` 엔트리.
- **DROP**: upstream의 Live2D 관련 코드 경로(후술 §3.3).

### §1.3 상태
`docs/MODULES.md` L459 기준 🔲 TODO. 본 스펙은 구현 착수 전 단계이며, 스펙 승인(사용자) + Open Questions 해소(§17) 이후 Builder 세션을 연다.

---

## §2. 요구사항 연결

| REQUIREMENTS.md / 설계 문서 | M_12 기여 |
|---|---|
| §3.1 캐릭터 새싹이, `assets/character/saessagi/` | `SpriteAvatarRenderer`가 해당 경로의 8종 PNG를 preload (§8.1). |
| §3.2 렌더링 — 스프라이트 스왑, 펫 모드(투명·항상 위·클릭 관통), 드래그 이동 | `SpriteAvatarRenderer` + `PetWindowController` (§8, §9). |
| §3.3 `[emotion:...]` 태그 → 표정 전환, crossfade 200~300ms, 숨쉬기/깜빡임/말할 때 흔들림·펄스 | `avatar-state` 프레임 수신 → `setEmotion/setSpeaking`(§7, §8.2). 태그 파싱 자체는 백엔드 M_08 책임이므로 프론트는 결과 Emotion 문자열만 소비. |
| §4.2 "일정 10분 전 팝업 + 음성 알림", "아침 브리핑" | `ai-speak-signal` 수신 시 topic별 토스트/배지 UI + 기존 `audio` 재생 경로 유지(§7.2, §10.1). |
| §5 DND 토글 | 설정 패널에 토글 → WS로 `set-dnd` 전송 요건은 존재하지 않음(백엔드 DND 주체는 M_10/M_11; 프론트는 `conf.yaml`/REST 없이 **초기 설정 시** 반영). DND 동기화 송수신 채널은 Open Question Q-10. |
| §6 화면 인식 — 사용자 트리거, 연속 캡처, 개인정보 경고 | 화면 공유 버튼·연속 캡처 토글이 `screenshot-trigger`·`start-continuous-capture`·`stop-continuous-capture`를 송신하고, 시작 시 1회 개인정보 경고 모달(§7.2, §10.1). |
| §7 인용 클릭 시 원문 PDF 해당 페이지 하이라이트 | `CitationViewer.openCitation(hit)` (§8.3). |
| §9 외부 네트워크 금지 | CSP `default-src 'self'`, WS/fetch/XHR는 loopback만 허용, 빌드 산출물 내 외부 CDN 0건(§11). |
| §10 단일 사용자, 모바일 제외 | 다중 창 브로드캐스트 로직 없음. iPad/모바일 뷰포트 CSS 생략(§3.2). |
| docs/ARCHITECTURE.md L115~L173 | WS 프레임 스키마 준수(§7). |
| docs/E2E_SCENARIOS.md §E2E-01/07/31 | `avatar-state` 소비 테스트(§13.1 E2E 매핑). |

---

## §3. upstream 포크 관리 정책

### §3.1 서브모듈 체크아웃
`upstream/Open-LLM-VTuber/.gitmodules`:

```
[submodule "frontend"]
    path = frontend
    url = https://github.com/Open-LLM-VTuber/Open-LLM-VTuber-Web
    branch = build
```

현 상태: 디렉터리 존재, 파일 없음(`docs/research/frontend_structure.md` L3~L5). 본 프로젝트 루트에서는 `upstream/Open-LLM-VTuber/frontend/`에 체크아웃된다. 체크아웃 명령은 `git submodule update --init upstream/Open-LLM-VTuber/frontend`.

본 프로젝트 전용 포크 경로는 `frontend/`(리포지토리 최상위; `docs/ARCHITECTURE.md` L372 "Electron 빌드 산출물" 라인과 일치). 전략 선택은 Open Question **Q-1**(서브모듈을 그대로 `upstream/.../frontend/`에서 활용할지, 본 리포 루트 `frontend/`로 **복제**해 독립 포크로 둘지).

### §3.2 포크 수정 파일 최소화 원칙
upstream React 컴포넌트 중 **교체 대상**은 다음 범주뿐이다:

1. `components/avatar/*` 또는 upstream Live2D 진입점 — 본 프로젝트의 `components/Avatar/SpriteAvatarRenderer.tsx`로 치환.
2. WebSocket 이벤트 dispatcher — 신규 타입 핸들러 추가. 수신(클라→서버) 4종(`screenshot-trigger`, `start-continuous-capture`, `stop-continuous-capture`, `set-dnd`) + 송신(서버→클라) 3종(`avatar-state`, `continuous-capture-state`, `dnd-state`). CR-10·CR-11 반영.
3. Electron main 프로세스 엔트리 — 기본 브라우저 창 외에 `PetWindow` 추가 생성 로직.
4. 설정 패널 — DND 토글·화면 공유 토글·프로파일 선택(min/recommended)의 UI 노출.

**건드리지 않는** upstream 컴포넌트: 히스토리 패널, 배경 이미지 갤러리, 그룹 채팅 UI(단일 사용자라 기능상 비활성화만), 설정 YAML 선택. 포크 수정 diff는 **체크리스트 기반 PR**로 관리(§15 DoD).

### §3.3 Live2D 의존 제거
upstream의 `pixi.js`, `pixi-live2d-display`, `pixi-live2d-display-lipsyncpatch`, Live2D Cubism Core 등은 본 프로젝트에서 **불필요**. 제거 정책:

1. `package.json`의 `dependencies`에서 Live2D 관련 패키지 전부 제거.
2. upstream의 Live2D 진입 모듈을 `SpriteAvatarRenderer`로 import 레벨 치환.
3. 번들러(Vite 가정 — 실제 여부는 Q-2)에서 Live2D asset 경로를 tree-shake.
4. 그럼에도 upstream 트리의 Live2D 이미지 `assets/i*_pet*.jpg`(참조: `frontend_structure.md` L92~L93)는 참고용으로만 남기고 빌드 산출물에는 포함하지 않음.

근거: `docs/ARCHITECTURE.md` L103 "스프라이트 렌더러 신규 교체".

### §3.4 오프라인 번들링
- `scripts/bundle_deps.sh`에 **npm 캐시 수집 블록** 신설(§12.2 상세).
- 빌드 머신에서 `npm ci` 수행 후 `node_modules/` 또는 `npm pack` 캐시를 `assets/npm_cache/`에 보관.
- 오프라인 설치 머신에서는 `npm ci --offline --prefer-offline --cache assets/npm_cache`로 복원.
- 외부 CDN 참조 금지(§11.1).

---

## §4. In-Scope / Out-of-Scope

### §4.1 In-Scope (V1)
1. Electron 메인 프로세스 엔트리 + 렌더러 번들(Chat Window).
2. `SpriteAvatarRenderer` V1 — 스프라이트 PNG 8종 crossfade, 숨쉬기/깜빡임/말할 때 opacity 펄스.
3. `PetWindowController` V1 — 투명·항상 위·클릭 관통·드래그 이동.
4. `CitationViewer` V1 — pdf.js 로컬 오프라인 번들 기반 PDF 페이지 렌더 + bbox 하이라이트(있을 때만).
5. WebSocket 클라이언트 — upstream 메시지 21종 + 본 프로젝트 신규 6종(수신 3 + 송신 3) 처리.
6. 설정 패널 — DND 토글, 프로파일 표시, 화면 공유 연속 모드 토글.
7. 프로액티브 수신 UI — `ai-speak-signal` topic별 토스트·배지 스타일 분기(§10.1).
8. 단위 테스트 매트릭스(§13) — vitest + @testing-library/react + playwright-electron(선택, Q-6).

### §4.2 Out-of-Scope (V1, 명시적 제외)
1. **Live2D 렌더러**. `AvatarRenderer` 인터페이스는 향후 구현체 추가 가능하도록 유지하지만, V2 옵트인 과제로 분리(`REQUIREMENTS.md` §3.2 "향후 레이어 합성·Live2D 교체 가능"은 인터페이스 여백 확보만 의미).
2. **모바일·iPad 반응형 레이아웃**. 데스크톱 Windows 10/11 전제(`REQUIREMENTS.md` §0, §10).
3. **OCR 또는 PDF 이외 포맷 인라인 뷰어**(DOCX/PPTX/HWPX/MD/TXT). 해당 포맷은 폴백 UI(§8.3.2)로 "원본 경로 표시 + 시스템 기본 앱으로 열기" 버튼만.
4. **스프라이트 PNG 자체 제작**. 이미지는 `docs/CHARACTER_SAESSAGI.md` 기반으로 이미 `assets/character/saessagi/`에 배치(L5~L17). M_12는 소비만.
5. **입 레이어 분리 립싱크**(`docs/CHARACTER_SAESSAGI.md` L36~L44 "mouth_*.png"). V2 업그레이드. V1은 전체 이미지 opacity 펄스(§8.2.3).
6. **감정 태그 문자열 파싱**. 백엔드 M_08이 1차 폴백까지 마친 결과(`avatar-state.emotion`)만 프론트가 소비(`specs/M_08_AvatarState_SPEC.md` §6.3 D-3).
7. **DND·프로파일의 영속 저장소 변경**. 설정 패널은 현재 WS 기반 토글만 노출하며 `conf.yaml` 직접 편집은 하지 않음(Q-10).
8. **다국어(i18n)**. 기본 한국어만. 영어 토글 필요 여부는 Open Question Q-8.
9. **앱 인스톨러 제작**(MSI/NSIS). `PROJECT_PLAN.md` Phase 4 책임이며 배포 형태는 Open Question Q-7.
10. **자체 업데이트 채널**. 오프라인 환경이므로 자동 업데이트 금지(외부 네트워크 호출 금지 조항).

---

## §5. 공개 API (프론트 내부)

> 시그니처는 TypeScript. 실제 구현은 `frontend/src/` 트리에 둔다(§14). 모든 async는 cancel·reject를 호출자가 처리. 런타임 `Error` 서브클래스를 사용한다.

### §5.1 `AvatarRenderer` 인터페이스 (확장)

`docs/MODULES.md` L431~L437 기반. 다음을 **확장**한다:

```ts
// frontend/src/components/Avatar/AvatarRenderer.ts
export type Emotion =
  | "neutral" | "happy" | "surprised" | "sad"
  | "worried" | "thinking" | "sleepy" | "study";  // 8종, M_08 §4.1 일치

export interface AvatarRendererErrorEvent {
  code: "asset_missing" | "invalid_emotion" | "invalid_crossfade_ms" | "mount_failed";
  detail: string;        // logger 용 메시지
  offendingEmotion?: Emotion | string;
}

export interface AvatarRenderer {
  /** Preload 스프라이트 이미지. mount 이전에 호출 권장. */
  preload(images: readonly string[]): Promise<void>;

  /** DOM 컨테이너에 마운트. 중복 호출 시 예외. */
  mount(container: HTMLElement): void;

  /** 감정 변경. 8종 외 값 수신 시 neutral 2차 폴백 + onError('invalid_emotion') 발행
   *  (M_08 §6.3 D-3: 백엔드 1차 폴백, 프론트 2차 폴백). */
  setEmotion(emotion: Emotion, crossfadeMs: number): void;

  /** 말하기 펄스 토글. speaking=false면 즉시 복원. */
  setSpeaking(on: boolean): void;

  /** 에러 이벤트 구독. 중복 등록 허용. 반환값은 해제 콜백. */
  onError(cb: (e: AvatarRendererErrorEvent) => void): () => void;

  /** DOM 해제·타이머 정리. 이후 호출은 모두 no-op. */
  dispose(): void;
}
```

### §5.2 `PetWindowController`

```ts
// frontend/src/components/PetWindow/PetWindowController.ts (renderer-side)
export interface PetWindowController {
  /** 투명 창을 실제로 생성(아직 없으면) + 포커스. 멱등. */
  enable(): Promise<void>;

  /** 창 종료 + 상태 저장 없음(§10.3). */
  disable(): Promise<void>;

  /** 클릭 관통 토글. forward=true면 이벤트를 under-window로 포워딩(Electron 규약). */
  setClickThrough(on: boolean, forward: boolean): Promise<void>;

  /** 항상 위 토글. */
  setAlwaysOnTop(on: boolean): Promise<void>;

  /** 드래그 시작 훅. main 프로세스로 IPC 송신. */
  dragStart(ev: MouseEvent): void;
}
```

메인 프로세스에는 아래 IPC 채널만 공개한다(§9.4):

```ts
// frontend/src/ipc/pet-mode.ts (preload로 window.petMode에 바인딩)
type PetModeApi = {
  enable(): Promise<void>;
  disable(): Promise<void>;
  setClickThrough(on: boolean, forward: boolean): Promise<void>;
  setAlwaysOnTop(on: boolean): Promise<void>;
  dragStart(payload: { x: number; y: number }): Promise<void>;
};
```

### §5.3 `CitationViewer`

```ts
// frontend/src/components/CitationViewer/CitationViewer.ts
export interface SearchHit {
  source_path: string;       // 로컬 절대 경로 (file://)
  page: number;              // 1-based
  section?: string;
  bbox?: { x: number; y: number; w: number; h: number }; // PDF 좌하단 원점
  chunk_id?: string;
  score?: number;
}

export interface CitationViewer {
  openCitation(hit: SearchHit): Promise<void>; // 페이지 스크롤 + bbox 하이라이트
  close(): void;
}
```

### §5.4 `WebSocketClient` (기존 upstream의 얇은 래퍼)
upstream 채널을 그대로 쓰되 신규 메시지 타입 6종만 추가한다. 새 타입을 **새로 만들지 않는다**(§7 제약).

---

## §6. 상태 저장소 (클라이언트 측)

- 라이브러리: upstream이 사용 중인 `zustand`(추정; 서브모듈 체크아웃 후 확정 — Q-4).
- 슬라이스:
  - `avatarSlice`: `{ emotion: Emotion, speaking: boolean, crossfadeMs: number }`.
  - `petSlice`: `{ enabled: boolean, clickThrough: boolean, alwaysOnTop: boolean }`.
  - `captureSlice`: `{ continuous: boolean, intervalSec: number }`.
  - `citationSlice`: `{ viewerOpen: boolean, currentHit: SearchHit | null }`.
  - `proactiveSlice`: `{ lastTopic: ProactiveTopic | null, toastQueue: ProactiveToast[] }`.
- 영속화: localStorage는 **사용하지 않는다**(단일 사용자·단일 PC, 서버 측 conf.yaml이 진실 원천).

---

## §7. WebSocket 메시지 스키마 — 준수표

> **제약 (§7.0)**: 본 모듈은 메시지 타입을 **추가하지 않는다**. `specs/M_01_AppCore_SPEC.md` §"WebSocket 메시지 타입"에 정의된 타입만 사용한다. 신규 타입이 필요하면 `docs/CHANGE_REQUESTS.md`에 CR을 올린 뒤 M_01 스펙을 먼저 갱신해야 한다.

### §7.1 클라이언트 → 서버
upstream 21종(`M_01_AppCore_SPEC.md` L376~L407)을 전부 보존. 본 프로젝트 신규 4종(CR-10 set-dnd 포함):

| type | 페이로드 | 트리거 |
|---|---|---|
| `screenshot-trigger` | `{type, prompt?:str, monitor_index?:int=0, region?:null}` (M_01 §B-1) | 화면 공유 버튼 클릭 / 음성 의도 |
| `start-continuous-capture` | `{type, interval_sec?:int, monitor_index?:int, prompt_template?:str}` (M_01 §B-2) | 연속 모드 토글 ON + 개인정보 경고 모달 확인 후 |
| `stop-continuous-capture` | `{type}` (M_01 §B-3) | 연속 모드 토글 OFF |
| `set-dnd` | `{type, enabled:bool}` (M_01 §B-4, CR-10) | 설정 패널 DND 토글. 성공 시 서버가 `dnd-state` 응답을 송신하여 UI가 그 응답 기준으로 최종 상태를 반영(SSoT). |

### §7.2 서버 → 클라이언트
upstream 19종 + 본 프로젝트 신규 3종(CR-10 `dnd-state` 반영. CR-11로 예약 해제된 타입은 §19 Q-11 참조):

| type | 페이로드 | 프론트 처리 |
|---|---|---|
| `avatar-state` | `{type,emotion:Emotion,crossfade_ms:int,speaking:bool}` (M_08 §7) | `AvatarRenderer.setEmotion/setSpeaking` 호출. `emotion`이 8종 밖이면 `neutral` 폴백 + onError. `crossfade_ms` 범위 밖(< 200 or > 300)이면 **에러 로깅 후 무시**(§10.2). |
| `continuous-capture-state` | `{type, running:bool, interval_sec?:int}` (M_01 §C) | 설정 패널의 연속 모드 ON 표시 동기화. |
| `dnd-state` | `{type, enabled:bool}` (M_01 §C, CR-10) | 설정 패널 DND 토글의 단일 진실 소스(SSoT). `set-dnd` 요청에 대한 서버 응답 수신 시 토글 상태 확정. |
| `ai-speak-signal` | 서버가 먼저 보낼 때(`{text, topic, context}`; M_11 §7) | **프런트는 프로액티브 토스트 표시 + 응답 대기 UI로 전환**. 실제 TTS 음성은 이후 `audio` 프레임으로 들어오므로 기존 upstream 경로 유지. 프로액티브 토스트 경로는 이 타입 **단일**로 통일됨(CR-11). M_11은 본 타입만 사용(§7.3, `specs/M_11_ProactiveDispatcher_SPEC.md` §7.3). |

### §7.3 `ai-speak-signal` 역방향 처리 계약
upstream에선 `ai-speak-signal`이 **클라이언트 → 서버** 방향의 수신 타입으로 정의된다(`frontend_structure.md` L46; `websocket_handler.py` L91). 본 프로젝트는 M_11이 **서버 → 클라이언트** 방향으로 동일 타입을 **재사용**한다(`M_11_ProactiveDispatcher_SPEC.md` §7, ARCHITECTURE L170). 프론트는 수신 측 처리로서:

1. payload.topic ∈ {`morning_briefing`, `event_reminder`, `idle_rest`, `overwork`} 검증. 미지 topic은 warn 로그 후 무시.
2. topic별 UI:
   - `morning_briefing`: 토스트 + 채팅 영역에 "아침 브리핑 시작" 배지 1회 표시.
   - `event_reminder`: 토스트(title=`context.title`, body=`"N분 뒤 시작"`) + 10초 유지.
   - `idle_rest` / `overwork`: 토스트 + 아바타 표정은 변경하지 **않는다**(M_11 §1.3 #4). 아바타 변경이 필요하면 별도 `avatar-state` 프레임이 뒤따른다.
3. 이후 백엔드가 upstream 프로액티브 경로로 LLM 응답을 스트리밍하므로, 프런트는 `full-text` / `audio` / `avatar-state` 프레임을 평소처럼 수신·표시.
4. `proactive_speak_prompt` 경로는 서버 단독 처리이며 프런트가 별도로 프롬프트를 합성하지 않는다.

---

## §8. 스프라이트 렌더러 동작 스펙

### §8.1 자산 로딩
- 경로 루트: `assets/character/saessagi/` (`CHARACTER_SAESSAGI.md` L5~L17).
- 파일명 규약: `<emotion>.png` (소문자 고정). Emotion 8종 문자열과 **완전 일치**. 다른 접미사·해상도 구분자 금지.
- preload 전략: 창 mount 전 8종 전부 `HTMLImageElement.decode()`로 프리페치. 실패 시 onError(`asset_missing`) 발행 + placeholder(투명 1px) 대체.
- 해상도: `docs/CHARACTER_SAESSAGI.md` L19 "같은 해상도, 같은 중심점". 크기 mismatch 검증은 V1 범위 외(단순 이미지 스왑).

### §8.2 애니메이션

#### §8.2.1 Crossfade
- 두 개의 겹쳐진 `<img>` 레이어. 새 이미지가 opacity 0→1, 기존 이미지가 1→0로 동시에 페이드.
- 지속 시간: 백엔드 페이로드의 `crossfade_ms` 사용. 범위: 정확히 `[200, 300]` (M_08 §6.3 D-5 "clamp 하지 않음, ValueError"와 대칭).
- 프론트 정책: 범위 밖 값 수신 시 **무시 + onError(`invalid_crossfade_ms`) 발행**. 전환을 건너뛰고 직전 상태 유지(사용자 시각적 혼란 최소화). 클램프 금지(백엔드 정책 일관).
- 타이밍 함수: CSS `ease-out` 또는 `ease-in-out` — Q-3.

#### §8.2.2 아이들 — 숨쉬기
- `transform: scaleY(1.0 → 1.02 → 1.0)`, 주기 2초, `ease-in-out`. `docs/CHARACTER_SAESSAGI.md` L50.
- 항상 실행(emotion 변경과 독립). `speaking=true`여도 지속.

#### §8.2.3 아이들 — 깜빡임
- 간격: 5~10초 균등 랜덤(`Math.random() * 5000 + 5000`).
- 방식: V1은 `opacity 1 → 0.6 → 1`(0.15초 내 왕복). `CHARACTER_SAESSAGI.md` L51 대체안 채택.
- `blink.png` 레이어 분리 버전은 V2 (§4.2 #5).

#### §8.2.4 말하기 펄스
- 조건: `AvatarState.speaking=true`.
- 동작: 전체 이미지 `opacity 1.0 ↔ 0.85`, 주기 200ms 펄스. `speaking=false` 수신 시 **즉시 1.0으로 복원** (inline style 제거 또는 transition 200ms → 0ms 단축 중 택1, Q-3).
- 흔들림(`rotate ±0.5°`, 0.4초 주기, `CHARACTER_SAESSAGI.md` L52)은 **V1 포함**하되, 펫 모드에서는 흔들림이 hit-region에 영향을 주지 않도록 transform-origin 중앙 고정.

#### §8.2.5 `study` 감정
- `study`는 백엔드가 장기 작업 중 직접 emit(`M_08_AvatarState_SPEC.md` §6.3 D-6). 프런트는 수신 시 `study.png`를 그대로 렌더.
- `speaking=true`로 들어와도 펄스는 적용(M_08 §7 주석 "강제하지 않음"). 시각적으로는 study 아이콘 + 미세 펄스.
- LLM 응답 문자열에 직접 `[emotion:study]`가 들어온 경우는 백엔드에서 `neutral`로 폴백되므로 프런트에는 `neutral`만 도달한다.

### §8.3 에러·누락 정책
| 상황 | 동작 |
|---|---|
| `setEmotion("joy")` 등 8종 외 | `neutral` 폴백 + `onError("invalid_emotion")` + `console.warn` 1회 |
| `setEmotion("happy")`인데 `happy.png` 로딩 실패 | `neutral.png` 2차 폴백 + `onError("asset_missing")` |
| `neutral.png`조차 실패 | 투명 1px placeholder + 에러 토스트 "아바타 로딩 실패" |
| `setEmotion` 호출 시 아직 mount 전 | 마지막 호출을 버퍼링하고 mount 직후 적용. crossfade 생략(즉시 표시) |

---

## §8.3 PDF 인용 뷰어

### §8.3.1 렌더 파이프라인
1. `openCitation(hit)` 진입.
2. `hit.source_path`를 `file://` URL로 변환 후 `pdfjsLib.getDocument(...)` 호출. worker는 로컬 `assets/pdfjs/pdf.worker.min.mjs` 경로.
3. `getPage(hit.page)` → `render(viewport)`.
4. `hit.bbox`가 있으면 PDF 좌표(좌하단 원점, 단위 pt)를 pdf.js viewport(좌상단 원점, 단위 px)로 변환:
   - `x_px = bbox.x * scale`
   - `y_px = (page_height - bbox.y - bbox.h) * scale`
   - `w_px = bbox.w * scale`, `h_px = bbox.h * scale`
   - 위 식은 pdf.js의 `viewport.convertToViewportRectangle` 결과와 동일해야 한다(구현 검증은 단위 테스트 §13.2).
5. 변환된 좌표로 반투명 박스 오버레이(`position: absolute; border: 2px solid rgba(255,200,0,0.9); background: rgba(255,200,0,0.25)`).

### §8.3.2 PDF 이외 포맷 폴백
- `source_path`의 확장자가 `.pdf`가 아니면(예: `.docx`/`.pptx`/`.hwpx`/`.md`/`.txt`):
  1. 인라인 뷰어 대신 **폴백 카드** 렌더: "원본 경로: <path>" + "시스템 기본 앱으로 열기" 버튼.
  2. 버튼 클릭 시 Electron `shell.openPath(absolutePath)` IPC 호출. 결과 문자열 비어 있지 않으면 에러 토스트.
  3. 섹션/페이지 번호 정보만 텍스트로 병기.
- `REQUIREMENTS.md` §2.1은 PDF 외에도 DOCX/PPTX/HWPX/MD/TXT 등록을 요구하나 §2.2 인용 **하이라이트 뷰어**는 PDF만 의무(`docs/ARCHITECTURE.md` L138 "인용 클릭 시 PDF viewer"). 따라서 폴백은 명세 준수.

### §8.3.3 pdf.js 버전·라이선스
- V1 후보: `pdfjs-dist >=4.6,<5` (Apache-2.0). Open Question Q-5(pdf.js vs MuPDF-wasm 번들 크기·라이선스).
- worker.min.mjs는 빌드 타임에 `assets/pdfjs/`로 복사. 런타임 CDN 금지.

### §8.3.4 대용량 PDF
- 100MB 이상 PDF도 pdf.js가 lazy 페이지 렌더로 처리하므로 열기는 성공해야 함. 메모리 상한: 렌더러 프로세스 RSS < 1.2GB를 넘기면 뷰어를 **닫고** 에러 토스트(§11.2 근거: 펜 모드 외 일반 창 예산).

---

## §9. 펫 모드 Electron 설정

### §9.1 BrowserWindow 옵션
```ts
const petWin = new BrowserWindow({
  transparent: true,
  frame: false,
  alwaysOnTop: true,
  hasShadow: false,
  skipTaskbar: true,
  resizable: false,
  movable: true,
  webPreferences: {
    contextIsolation: true,
    nodeIntegration: false,
    sandbox: true,
    preload: path.join(__dirname, "pet-preload.js"),
  },
});
```

- 크기: 초기 300x400. Q-12(크기/위치 영속화 여부).
- URL 로딩: `petWin.loadFile("dist/pet.html")`. 메인 채팅 창(`main.html`)과 번들 **분리**해 Live2D/chat 리소스가 로드되지 않도록(§3.3).

### §9.2 클릭 관통 (Click-Through)
- 기본: `petWin.setIgnoreMouseEvents(true, { forward: true })` — 커서 이벤트는 모두 밑창으로 전달되지만, 렌더러에서 hover 이벤트는 감지 가능(Electron 30.x 규약).
- 버튼/말풍선 hit-region: hover 이벤트 수신 시 IPC로 `setIgnoreMouseEvents(false)` 전환, pointer leave 시 `setIgnoreMouseEvents(true, { forward: true })` 복귀.
- 이 토글 주기는 50ms 디바운스(빠른 움직임 시 플리커 방지).
- Windows 10/11에서 `{ forward: true }`가 실제로 동작하는지는 실기기 확인 필요(Open Question Q-9).

### §9.3 드래그 이동 전략 선택
두 가지 후보:

**(A) CSS `-webkit-app-region: drag`**
- 장점: 순수 CSS, OS 네이티브 드래그.
- 단점: `setIgnoreMouseEvents(true, ...)` 상태와 **충돌** 가능성. 드래그 영역은 hit-region 전환이 필수이며 pointer-events도 함께 오버라이드돼야 한다. Electron 30.x에서 두 기능 병용 가능 여부는 실기기 확인 필요(Q-9).

**(B) JS mousedown + IPC `win.setPosition(x, y)` 루프**
- 장점: click-through 정책과 독립적으로 드래그 영역 제어.
- 단점: 메인↔렌더러 IPC 오버헤드(드래그 중 1ms 미만이어야 함, §11.3).

**결정 보류**: Open Question Q-9에 위임. 스펙은 두 선택지를 제안만 한다.

### §9.4 IPC 계약
- 채널명은 접두사 `pet:`으로 통일 — `pet:enable`, `pet:disable`, `pet:setClickThrough`, `pet:setAlwaysOnTop`, `pet:dragStart`.
- preload에서 `contextBridge.exposeInMainWorld("petMode", api)`로 제한 노출. 그 외 Node API는 노출 금지.
- 메인 프로세스 핸들러는 **입력값 범위 검증**(bool 여부, 좌표 정수 여부)을 반드시 수행(§10.3).

### §9.5 창 수명
- 펫 모드 종료 시 `BrowserWindow.destroy()` 완전 해제. 재개는 새 인스턴스 생성.
- 메인 앱 종료 시 펫 창도 함께 종료(`app.on("before-quit")`).

---

## §10. 에러 정책

### §10.1 네트워크·WebSocket
- 재연결: 지수 백오프 `min(2^n, 30)` 초, n=0부터 시작. 상한 30s. 무한 재시도(오프라인 환경이라 사용자가 Ollama 재기동 중일 수 있음).
- 수동 재연결 버튼: 설정 패널 하단.
- 연결 끊김 중에는 `proactiveSlice`와 `avatarSlice`를 동결(state freeze)하되 UI는 "연결 끊김" 배지만 표시.
- 수신 버퍼 초과(1MB 이상 단일 프레임) 시 해당 프레임 드롭 + 에러 로그(방어적).

### §10.2 스프라이트·아바타
§8.3 표 준수. 모든 에러는 `AvatarRenderer.onError`로 흘러가며 상위에서 Sentry-형 로거(로컬 파일 `data/logs/frontend.log`)에만 기록. 원격 송출 금지.

### §10.3 IPC 검증
- 메인 프로세스는 렌더러에서 온 IPC 인자를 JSON-schema(또는 `zod`)로 검증.
- 스키마 위반 시 IPC handler가 reject + 로그, 렌더러는 에러 토스트.

### §10.4 pdf.js 로딩 실패
- pdf.js worker 로드 실패 시 CitationViewer는 즉시 §8.3.2 폴백 UI로 전환.
- 한 번 실패한 뷰어는 재시도하지 않음(사용자가 재시작할 때까지).

### §10.5 마이크·화면 권한
- 마이크 권한 거부: 텍스트 입력 패널을 강조 + 안내 문구 "마이크 권한이 없어 텍스트로만 대화할 수 있어요". 음성 관련 버튼 비활성화.
- 화면 캡처 권한 거부: `screenshot-trigger` 전송 버튼 비활성화 + 설정 패널에 안내. 실제 권한 체크는 백엔드 M_05b `ScreenshotService`가 수행(프런트는 백엔드 에러 응답만 반영).

### §10.6 프로액티브 수신 중복
- `ai-speak-signal` 동일 topic 3초 이내 재수신 시 토스트만 업데이트, 음성 재생은 백엔드의 쿨다운에 위임(프런트는 중복 제거 로직을 넣지 않는다).

---

## §11. 보안·오프라인 제약

### §11.1 CSP
`index.html`과 Electron 세션에 적용:

```
default-src 'self';
script-src 'self';
style-src 'self' 'unsafe-inline';   -- upstream 기존 스타일 호환이 필요하면 Q-13
img-src 'self' data:;
media-src 'self' blob:;
connect-src 'self' ws://127.0.0.1:* ws://localhost:*;
font-src 'self';
object-src 'none';
frame-src 'none';
worker-src 'self';
```

- 외부 CDN/폰트 금지. 모든 리소스는 번들 내장.
- `ws://` 호스트는 루프백만. 백엔드 M_01 바인드 주소(`127.0.0.1:12393`) 기본.

### §11.2 Electron webPreferences (모든 창 공통)
- `contextIsolation: true`
- `nodeIntegration: false`
- `sandbox: true` (가능하면; 일부 preload IPC는 contextBridge로 한정)
- `webSecurity: true`
- `allowRunningInsecureContent: false`

### §11.3 네트워크 바인드 assertion
- 앱 시작 직후 `net.request`/`fetch`/`WebSocket`를 monkeypatch해 target host가 `127.0.0.1`/`localhost`/ RFC1918(10/8, 172.16/12, 192.168/16) 외면 **throw**.
- 검증 대상 라이브러리가 직접 소켓을 여는 경우(예: pdf.js fontSrc)는 CSP로 2차 방어.

### §11.4 npm 빌드
- `package-lock.json`을 커밋. `npm ci --offline --cache assets/npm_cache`로 재현.
- `scripts/bundle_deps.sh`에 npm 캐시 수집 블록 신설(§12.2).
- postinstall 스크립트 실행 허용 패키지 화이트리스트 관리(Q-14).

---

## §12. 성능·메모리 요구사항

### §12.1 수치
| 항목 | 목표 | 근거 |
|---|---|---|
| Electron 메인 프로세스 RSS (유휴) | ≤ 200 MB | `docs/ARCHITECTURE.md` L318 Electron 250MB 총예산 중 메인 할당 |
| 렌더러 프로세스 RSS (채팅창) | ≤ 350 MB | 동일 라인(250MB 내 여유 + pdf.js 로딩 허용) |
| 펫 모드 투명 창 CPU 평균 | ≤ 2% (i5 10세대 기준) | §1.3 요구, V1 스프라이트 단순 DOM 애니메이션 |
| 스프라이트 전환 지연 (requestAnimationFrame 1프레임) | ≤ 16 ms | §8.2.1, 60fps 기준 |
| WS 재연결 초기 지연 | ≤ 1s | §10.1 백오프 n=0 |
| PDF 첫 페이지 렌더 | ≤ 500ms (10MB 이하 PDF) | pdf.js 레퍼런스 |

### §12.2 `scripts/bundle_deps.sh` 신규 블록
현 파일(scripts/bundle_deps.sh L25~L160) 아래에 다음 블록을 추가해야 한다(스펙 단계에서는 파일 수정 금지, Builder가 구현):

```bash
# === M_12 Frontend npm 캐시 수집 ===
# 대상: frontend/package.json + frontend/package-lock.json
# 실행 전 조건:
#   - node >= 20 LTS
#   - npm >= 10
#   - 인터넷 연결
NPM_CACHE_DIR="${PROJECT_ROOT}/assets/npm_cache"
mkdir -p "${NPM_CACHE_DIR}"
(cd "${PROJECT_ROOT}/frontend" \
 && npm ci --cache "${NPM_CACHE_DIR}" --prefer-offline=false)
# Electron 설치 후 바이너리 복사 (offline 환경 대비)
(cd "${PROJECT_ROOT}/frontend" \
 && npm exec --offline -- electron-rebuild || true)
```

오프라인 설치 머신에서는 `npm ci --offline --cache "${NPM_CACHE_DIR}"`로 복원.

### §12.3 번들 크기 상한
- 최종 `frontend/dist/` 크기 **≤ 150 MB** (Electron 바이너리 제외).
- pdf.js 포함. Live2D·pixi 제거로 여유 확보.
- 초과 시 번들 분석(`rollup-plugin-visualizer` 권장; Q-4)으로 원인 파악.

---

## §13. 테스트 매트릭스

> 위치: `frontend/tests/` (vitest + @testing-library/react) 및 `frontend/e2e/` (playwright-electron, Q-6).
> 네이밍: `*.test.tsx`(단위), `*.e2e.ts`(통합).

### §13.1 정상 케이스 (≥5)
1. **N-1 emotion 수신**: `{type:"avatar-state",emotion:"happy",crossfade_ms:250,speaking:false}` 수신 → `setEmotion("happy",250)` 호출, DOM `<img>` src가 `/assets/character/saessagi/happy.png`로 전환.
2. **N-2 speaking 펄스**: `avatar-state` `speaking:true` 이후 `speaking:false` 수신 시 opacity가 1.0으로 즉시 복원.
3. **N-3 펫 모드 on/off**: 설정 토글 → `PetWindowController.enable()` IPC 호출 → 새 BrowserWindow 생성 검증(e2e).
4. **N-4 펫 모드 드래그**: mousedown → mousemove → IPC `pet:dragStart` 1회 이상 수신(JS 전략 기준; CSS 전략 선택 시 `getBounds()` 변화 검증).
5. **N-5 인용 PDF 열기**: `SearchHit{source_path:"/assets/sample.pdf",page:3,bbox:{x:100,y:100,w:200,h:50}}`로 `openCitation` 호출 → pdf.js `getPage(3)` 호출, 오버레이 DOM 존재.
6. **N-6 프로액티브 토스트**: `{type:"ai-speak-signal",topic:"event_reminder",context:{title:"회의",minutes_until:10}}` 수신 → 토스트 DOM에 "회의"/"10분" 텍스트 포함.
7. **N-7 연속 캡처 상태 동기화**: `continuous-capture-state` 수신 시 `captureSlice.continuous`가 해당 bool로 갱신.

### §13.2 엣지 케이스 (≥5)
1. **E-1 알 수 없는 emotion**: `"joy"` 수신 → `neutral` 폴백 + onError.
2. **E-2 crossfade_ms 범위 밖**: 150, 350, -1, 9999 수신 시 상태 미변경 + onError.
3. **E-3 비PDF 인용**: `source_path: "foo.docx"` 전달 시 폴백 카드 렌더, pdf.js 호출 0회.
4. **E-4 WebSocket 단절**: 백엔드 프로세스 강제 종료 → 1s 후 1회 재연결 시도, 실패 시 2s, 4s… 30s 상한 유지(테스트에서 최소 3회 백오프 간격 검증).
5. **E-5 마이크 권한 거부**: navigator.mediaDevices.getUserMedia reject → 음성 버튼 disabled + 안내 문구.
6. **E-6 study 감정 수신**: `emotion:"study"` 수신 시 `study.png` 렌더. `speaking:true`여도 펄스 적용(§8.2.5).
7. **E-7 `bbox` 누락 PDF**: `hit.bbox undefined` → 페이지 스크롤은 수행, 오버레이 DOM 없음.

### §13.3 적대적 케이스 (≥3)
1. **A-1 악성 JSON**: WebSocket에서 `{type:"avatar-state",emotion:"<script>alert(1)</script>",crossfade_ms:"250"}` 수신 → emotion 문자열 자체는 DOM 삽입되지 않으며(값은 map key로만 사용) `neutral` 폴백, `crossfade_ms`가 숫자 아니면 onError.
2. **A-2 100MB PDF**: `openCitation`으로 100MB 파일 열기 → 렌더러 RSS < 1.2GB 유지, 초과 시 뷰어 자동 닫힘 + 에러 토스트.
3. **A-3 펫 모드 hit-region 우회 시도**: click-through 켜진 상태에서 발화 버튼 좌표로 합성 click 이벤트 100회 전송 → 실제 버튼은 hover로만 활성화되므로 click 핸들러는 호출되지 않음(E2E with synthetic events).
4. **A-4 CSP 위반 시도**: 렌더러에서 `new Image().src = "https://evil.example/x.gif"` 실행 → CSP 로그에 "Refused to load the image" 기록, 실제 네트워크 요청 0건(playwright의 route intercept로 검증).
5. **A-5 preload 우회**: `window.require` / `process` 접근 시도 → `undefined`.

### §13.4 E2E 매핑 (docs/E2E_SCENARIOS.md)
| E2E ID | M_12 관여 |
|---|---|
| E2E-01 (음성 대화 골든) | `full-text`/`audio`/`avatar-state` 수신·렌더(프런트 통합은 §13.1 N-1~N-2) |
| E2E-05 (morning_briefing) | `ai-speak-signal` topic 분기(§7.3) |
| E2E-06 (event_reminder 10분 전) | 토스트 + context.title/minutes_until |
| E2E-07 (감정 태그 happy) | §13.1 N-1 |
| E2E-09 (overwork) | `ai-speak-signal` topic=overwork 토스트 |
| E2E-24 (쿨다운 드롭) | 프런트는 drop 자체를 관찰하지 못함(프레임 0건). 관측은 백엔드. |
| E2E-25 (활성 클라이언트 라우팅) | 2개 WS 동시 연결에서 신연결만 수신 확인 |
| E2E-26 (세션 미형성 시 screenshot-trigger) | 에러 토스트 렌더 |
| E2E-31 (알 수 없는 emotion) | §13.2 E-1 |
| E2E-30 (search_docs 인용 포맷) | 인용 배지 렌더 + 클릭 시 CitationViewer(비 PDF는 폴백) |

---

## §14. 파일 구조

```
frontend/
├── package.json
├── package-lock.json
├── tsconfig.json
├── vite.config.ts            # (Q-2 번들러 확정에 따라 Vite 가정)
├── electron-builder.yml      # (Q-7 인스톨러 결정 후)
├── main/
│   ├── main.ts               # app.whenReady, BrowserWindow 생성
│   ├── pet-window.ts         # PetWindow 메인 측 생성 및 IPC 핸들러
│   ├── preload-chat.ts
│   └── preload-pet.ts
├── src/
│   ├── App.tsx               # 채팅 메인 엔트리 (upstream 포크)
│   ├── components/
│   │   ├── Avatar/
│   │   │   ├── AvatarRenderer.ts
│   │   │   └── SpriteAvatarRenderer.tsx
│   │   ├── PetWindow/
│   │   │   └── PetWindowController.ts
│   │   ├── CitationViewer/
│   │   │   ├── CitationViewer.tsx
│   │   │   └── pdfjs-loader.ts
│   │   └── (upstream 포크 컴포넌트들)
│   ├── store/
│   │   └── index.ts          # zustand slices (§6)
│   ├── ipc/
│   │   └── pet-mode.ts       # window.petMode 정의
│   ├── ws/
│   │   └── client.ts         # WebSocket 클라이언트 래퍼 (§7)
│   └── styles/
├── assets/
│   ├── character/            # 심볼릭 링크 or 빌드 시 복사
│   │   └── saessagi/*.png    # (루트 assets/에서 복사)
│   └── pdfjs/
│       ├── pdf.mjs
│       └── pdf.worker.min.mjs
├── tests/
│   ├── Avatar.test.tsx
│   ├── PetWindow.test.ts
│   ├── CitationViewer.test.tsx
│   ├── ws-client.test.ts
│   └── proactive-toast.test.tsx
└── e2e/
    ├── emotion-flow.e2e.ts
    ├── pet-mode.e2e.ts
    └── citation.e2e.ts
```

---

## §15. Definition of Done

### §15.1 공통(CLAUDE.md 산출물 체크리스트)
- [ ] 본 스펙(`specs/M_12_Frontend_SPEC.md`) 사용자 승인.
- [ ] `frontend/src/`·`frontend/main/` 구현 완료.
- [ ] `frontend/tests/` 테스트: 정상 ≥5, 엣지 ≥5, 적대적 ≥3.
- [ ] `npm run lint`·`npm run typecheck`·`npm run test`·`npm run build` 모두 통과.
- [ ] `reviews/M_12_Frontend_REVIEW.md`에 Critic PASS.
- [ ] `docs/MODULES.md` M_12 상태 `✅ DONE` 갱신.

### §15.2 M_12 고유
- [ ] upstream 서브모듈 체크아웃 또는 복제가 성공하고(Q-1 결정에 따름), Live2D 의존이 `package.json`에서 제거됨.
- [ ] `AvatarRenderer` 인터페이스가 §5.1대로 정의되고 `SpriteAvatarRenderer`가 `preload`/`mount`/`setEmotion`/`setSpeaking`/`onError`/`dispose`를 모두 구현.
- [ ] `assets/character/saessagi/` 8종 PNG 프리로드가 unit test로 검증.
- [ ] `PetWindowController.enable()`가 Electron에서 투명·항상 위·frame 없음 창을 실제로 생성(e2e 스냅샷 혹은 `getBounds`/`isAlwaysOnTop` assertion).
- [ ] click-through ON 상태에서 hover 이벤트가 IPC로 전달되는지 확인(Q-9 해소 필요).
- [ ] `CitationViewer.openCitation({bbox})`가 오버레이 DOM rect를 정확히(±1px) 배치(단위 테스트 §13.1 N-5, §13.2 E-7).
- [ ] `ai-speak-signal` topic 4종 모두에 대해 UI 토스트가 렌더(§7.3).
- [ ] CSP가 `index.html`과 Electron session 양쪽에 적용되며 외부 URL 로드 시도 시 차단 로그 확인.
- [ ] `scripts/bundle_deps.sh`에 npm 캐시 수집 블록이 추가되고, 오프라인 PC에서 `npm ci --offline` 재현.
- [ ] 렌더러 프로세스 RSS 350MB·펫 모드 CPU 2% 요구(§12.1) 벤치마크 스크립트 통과.

---

## §16. 의존성

### §16.1 npm (Frontend)
| 패키지 | 버전 핀(예상) | 용도 | 비고 |
|---|---|---|---|
| `electron` | `^30.0.0` | 데스크톱 셸 | Windows 10/11 호환, BrowserWindow `transparent+frame:false` 지원 |
| `react` | `^18.3` | UI | upstream 호환 추정 |
| `react-dom` | `^18.3` | DOM | — |
| `typescript` | `^5.4` | 타입 | — |
| `vite` 또는 upstream 번들러 | `^5` | 번들 | Q-2 |
| `zustand` | `^4.5` | 상태 | upstream 채택 여부 확인 필요(Q-4) |
| `pdfjs-dist` | `>=4.6,<5` | PDF 뷰 | Q-5 |
| `@testing-library/react` | `^15` | 단위 테스트 | |
| `vitest` | `^1.6` | 테스트 러너 | |
| `playwright` / `playwright-electron` | `^1.44` | E2E | Q-6 |
| `electron-builder` | `^24` | 설치 패키지 | Q-7 |
| `zod` | `^3.23` | IPC 스키마 검증 | §10.3 |

`pixi.js`, `pixi-live2d-display`, 관련 Live2D 바이너리는 **전부 제거**(§3.3).

### §16.2 오프라인 번들
- `scripts/bundle_deps.sh`에 `NPM_CACHE_DIR` 블록 추가(§12.2).
- 오프라인 설치 스크립트(`scripts/install.ps1` 등 Phase 4)에서 `npm ci --offline` 경로 반영.

### §16.3 런타임 전제
- Node 미설치 환경에서 실행되어야 하므로 **Electron 바이너리만** 배포(백엔드 Python과는 별개 프로세스).
- Windows 10/11 x64 전용(`REQUIREMENTS.md` §0). 32-bit 빌드 금지.

---

## §17. Open Questions — 사용자 승인 필요

> 각 항목은 **추천안** + **사용자 결정 필요 사유**를 병기. 사용자 승인 없이 Builder 착수 금지.

### Q-1. upstream `Open-LLM-VTuber-Web` 서브모듈 체크아웃 경로·시점
- 선택지 A: 인터넷 가능한 별도 단말에서 `git submodule update --init`으로 `upstream/.../frontend/`에 체크아웃 후 트리 복사로 사내 PC 전달.
- 선택지 B: 사내 빌드 머신이 인트라넷 프록시를 경유해 GitHub에 접근(가능 여부는 IT 확인).
- 선택지 C: 스펙만 먼저 확정하고 Builder 착수 시점에 지연 체크아웃.
- **추천안**: A. 본 리포 루트의 `frontend/`는 독립 포크로 운영(서브모듈 종속성 최소화). 근거: `CLAUDE.md` 절대 금지 "외부 네트워크 호출", 오프라인 빌드 의무.
- **결정 필요 사유**: 사내망 정책·빌드 머신 인터넷 가용성 확인 없이 Builder가 착수하면 의존성 획득 단계에서 blocking됨.

### Q-2. 스프라이트 전환 엔진 — React CSS vs Canvas 2D vs WebGL(Pixi 없이)
| 항목 | React + CSS | Canvas 2D | WebGL(바닐라) |
|---|---|---|---|
| 구현 복잡도 | 낮음 | 중간 | 높음 |
| GPU 사용 | 없음 | 없음 | 있음 |
| 펫 모드 투명 | 우수 | 양호 | 불확실(투명 + always on top에서 합성 이슈) |
| 번들 크기 증가 | 0 | 0 | 소(2~5KB) |
| 애니메이션 정밀도 | CSS transition 의존 | 수동 rAF | 수동 rAF |
- **추천안**: React + CSS transition. 근거: V1 요구사항(페이드·scaleY·opacity 펄스)이 순수 CSS로 충분하고 펫 모드 투명 합성에서 가장 검증된 경로.
- **결정 필요 사유**: 장기적으로 Live2D 통합(§3.3 V2)을 고려하면 WebGL 기반이 유리하나, V1 범위와 상충. 사용자가 장기 전략을 확정해야 함.

### Q-3. crossfade easing·speaking 펄스 복원 방식
- 선택지 A: `ease-in-out` + speaking=false 시 transition 200ms→0s 단축(즉시 복원).
- 선택지 B: `ease-out` + speaking 페이드아웃도 200ms.
- **추천안**: A (즉시 복원이 `REQUIREMENTS.md` §3.3 "말할 때 opacity 펄스"의 사용자 기대와 일치).
- **결정 필요 사유**: 청각·시각 동기화 취향은 UX 결정. 스펙이 자의로 고르면 후속 QA에서 뒤집힐 위험.

### Q-4. Electron main↔renderer 상태 동기화 라이브러리
- 선택지 A: `zustand` + custom IPC(현 upstream 추정 스택 유지).
- 선택지 B: `electron-store`(영속화 포함) + React context.
- 선택지 C: Redux + electron-redux.
- **추천안**: A. 근거: 영속화 대상이 최소(§6 localStorage 미사용), 의존 최소화.
- **결정 필요 사유**: upstream 서브모듈 체크아웃 전에는 upstream이 실제 어떤 상태 라이브러리를 쓰는지 확정 불가(§3.1 Q-1과 연동).

### Q-5. PDF 뷰어 엔진 — pdf.js vs MuPDF-wasm
| 항목 | pdf.js | MuPDF-wasm |
|---|---|---|
| 라이선스 | Apache-2.0 | AGPL-3.0 (상용 유료 옵션 있음) |
| 번들 크기 | ~1.4 MB | ~8~15 MB |
| bbox 좌표 API | 공식 `viewport.convertToViewportRectangle` | 지원하나 문서 부족 |
| 렌더 품질 | 양호 | 매우 우수 |
- **추천안**: pdf.js. 근거: 번들 크기·라이선스(AGPL 위험 회피).
- **결정 필요 사유**: 사내 문서 품질이 복잡한 한국어 PDF일 경우 pdf.js 렌더가 깨질 수 있음. 샘플 PDF 테스트 필요.

### Q-6. E2E 테스트 러너 — playwright-electron vs Spectron(EOL) vs 수동 QA
- **추천안**: `playwright-electron`. 근거: Spectron EOL(2022), 펫 모드 창 전환 테스트에 가장 성숙.
- **결정 필요 사유**: CI가 오프라인 빌드 머신이라면 playwright 브라우저 바이너리 다운로드 필요. 오프라인 환경에서 E2E 자동화를 수동 QA로 대체할지 결정해야 함(`docs/E2E_SCENARIOS.md` §Q-3/§617와 연결).

### Q-7. 배포 형태 — 단일 실행 파일 vs 설치형(MSI/NSIS) vs 포터블 ZIP
- 선택지 A: `electron-builder` NSIS 설치형.
- 선택지 B: 포터블 ZIP(압축 해제 후 실행).
- 선택지 C: MSIX (Windows 11 모던).
- **추천안**: A. 근거: 사내 IT 배포 친화, 아이콘·시작 메뉴 등록 용이.
- **결정 필요 사유**: 사내 보안정책(서명 인증서 필요 여부, AppLocker 정책)에 따라 결정. Phase 4 인스톨러 설계와 연동.

### Q-8. 프런트 로케일 정책 — 한국어 고정 vs 영어 토글 제공
- **추천안**: 한국어 고정. 근거: `REQUIREMENTS.md` §1.1 "한국어 여성 목소리 기본", §4.1 한국어 자연어 파싱 전제.
- **결정 필요 사유**: 임원 데모·외국인 사용자 대응 여부는 사용자 결정 필요.

### Q-9. 펫 모드 click-through + 드래그 이동 병용 가능 여부 (실기기 검증 요구)
- 선택지 A: CSS `-webkit-app-region: drag` + hover로 `setIgnoreMouseEvents(false)` 전환.
- 선택지 B: JS mousedown + IPC `win.setPosition()` 루프.
- Electron 30.x Windows 11 환경에서 A의 실제 동작 여부가 불확실(레거시 이슈 `electron/electron#1354` 계열).
- **추천안**: B 우선 구현(확실히 동작). A는 Q-9 해결 후 최적화 단계에 도입.
- **결정 필요 사유**: 실기기 스파이크 실행 후 결정. Planner가 가정으로 고정하면 후속 rework.

### Q-10. DND 토글의 프런트-백엔드 동기화 채널
- 현재 M_11 `set_dnd`는 서버 내부 API이며 WS 메시지 타입으로 노출되지 않았다(§2 요구사항 표 참조).
- 선택지 A: 신규 WS 수신 타입 `set-dnd`(`{type,"enabled":bool}`)를 M_01에 추가 — CR 필요.
- 선택지 B: REST 엔드포인트 `POST /api/dnd` 신설 — M_01 범위 확장.
- 선택지 C: 프런트는 설정 패널에서 `conf.yaml` 저장 권고 안내만 하고 재기동.
- **추천안**: A (CR로 M_01 스펙 갱신 후 진행).
- **결정 필요 사유**: 스펙은 기존 메시지 타입만 사용하는 제약(§7.0)이 있어 자의 추가 금지.

### Q-11. `proactive-notification` 타입 실제 송신 주체·스키마 확정
- `M_01_AppCore_SPEC.md` L472는 타입만 예약. M_11은 `ai-speak-signal` 경로로 통합 사용(§7.3). `proactive-notification`는 현재 **누구도 송신하지 않는다**.
- 선택지 A: 타입 자체를 M_01에서 제거(스펙 정합).
- 선택지 B: M_11이 토스트 전용 경량 메시지로 `proactive-notification`을 **추가로** 송신(TTS와 분리).
- **추천안**: A. 근거: 이미 `ai-speak-signal`이 topic·context를 실어 보내므로 중복.
- **결정 필요 사유**: 스펙 문서 간 충돌 해소 필요(사용자 결정 후 M_01 갱신 또는 유지).

### Q-12. 펫 창 위치·크기 영속화
- 선택지 A: 영속화 안 함(재기동 시 디폴트 우측 하단).
- 선택지 B: 로컬 JSON(`data/pet-window.json`)에 좌표 저장.
- **추천안**: B. 근거: 사용자 편의.
- **결정 필요 사유**: 저장 매커니즘이 백엔드 `data/` 디렉터리 권한과 충돌할 수 있음. 경로를 프런트 전용(`%APPDATA%/saessagi`)으로 할지 결정.

### Q-13. CSP `style-src 'unsafe-inline'` 허용 여부
- upstream React가 emotion·styled-components 등 런타임 스타일 삽입을 사용하면 `'unsafe-inline'` 필요.
- 선택지 A: `'unsafe-inline'` 허용(개발 편의).
- 선택지 B: CSS Modules/Tailwind 등으로 전환해 `'unsafe-inline'` 제거(보안 강화).
- **추천안**: A를 단기, B를 V2.
- **결정 필요 사유**: 보안팀 승인 필요.

### Q-14. npm postinstall 스크립트 허용 정책
- `electron`·`canvas` 등 native 모듈이 postinstall에서 바이너리 빌드를 요구.
- 선택지 A: `--ignore-scripts` + `electron-rebuild` 수동 수행.
- 선택지 B: 화이트리스트(예: `electron`, `electron-builder`)만 허용.
- **추천안**: B. 근거: 빌드 성공률·보안 균형.
- **결정 필요 사유**: 사내 보안정책(postinstall 금지 여부) 확인.

### Q-15. upstream 서브모듈 vs 프로젝트 `frontend/` 디렉토리 관계 확정
- `docs/ARCHITECTURE.md` L372는 리포 루트 `frontend/`를 전제. upstream은 `upstream/.../frontend/` 서브모듈.
- 선택지 A: upstream 서브모듈을 그대로 사용 + 패치만 본 리포에 둠(`patches/` 디렉터리).
- 선택지 B: upstream 서브모듈의 특정 커밋을 루트 `frontend/`에 **복사**(독립 포크).
- **추천안**: B. 근거: 포크 diff 추적 용이, 사내망에서 서브모듈 업데이트 불필요.
- **결정 필요 사유**: upstream 라이선스(원 Open-LLM-VTuber-Web 라이선스)·기여 정책과의 호환성 확인 필요.

---

## §18. 스펙 외 사항 (명시적 제외)

1. 스프라이트 PNG 자체 제작·수정(`docs/CHARACTER_SAESSAGI.md` 기준 제공됨).
2. 감정 태그 문자열 파싱·폴백 1차 처리(M_08 책임).
3. 프로액티브 발화 스케줄·쿨다운·DND 정책(M_11/M_10 책임).
4. Ollama·ASR·TTS·벡터 DB 구동(M_01~M_07 책임).
5. 오프라인 인스톨러 구축·Ollama 서비스 등록(Phase 4 책임).
6. Windows 방화벽/서명 인증서 관리(운영 문서 책임).
7. 향후 V2 기능(Live2D 렌더러, 입 레이어 분리 립싱크, 모바일 UI, 영어 i18n 토글, DuckDuckGo MCP UI, 사내 위키 MCP UI).

---

## 부록 A. upstream 경로·심볼 인덱스

- `upstream/Open-LLM-VTuber/.gitmodules`: 서브모듈 url · branch.
- `upstream/Open-LLM-VTuber/src/open_llm_vtuber/websocket_handler.py` L42~L98: 수신 메시지 타입 enum (M_12가 준수).
- `upstream/Open-LLM-VTuber/src/open_llm_vtuber/conversations/conversation_handler.py` L32~L55: `ai-speak-signal` 서버 처리.
- `upstream/Open-LLM-VTuber/src/open_llm_vtuber/utils/stream_audio.py` L77: `audio` 프레임 스키마.
- 프런트 서브모듈 코드는 현재 체크아웃되지 않아 실재 경로 확인은 Q-1 해결 후 재조사.

---

## §19. Open Questions 결정 기록 (2026-04-21 승인)

> 사용자가 Planner에게 최적안 결정을 위임(2026-04-21). Q-1~Q-15 모두 스펙 §17 **추천안을 채택**. Q-10·Q-11은 스펙 문서 간 충돌 해소를 위해 **CR-10·CR-11 별건 발행**(후술). Builder 착수 조건은 본 §19로 확정된다.

### §19.1 결정표

| Q | 결정 | 채택 이유 | 후속 조치 |
|---|---|---|---|
| Q-1 | **A** — 별도 단말에서 서브모듈 체크아웃 후 트리 복사 | `CLAUDE.md` 절대 금지 "외부 네트워크 호출"·오프라인 빌드 의무 준수. | Builder 착수 직전 1회성 수동 단계. Q-15와 병행. |
| Q-2 | **React + CSS transition** | V1 요구(§3.1/§3.2)가 CSS로 충분하고 펫 모드 투명 합성에서 가장 검증된 경로. | WebGL은 V2 Live2D 도입 검토 시 재평가. |
| Q-3 | **ease-in-out + speaking=false 시 즉시 복원** | `REQUIREMENTS.md` §3.3 "말할 때 opacity 펄스" UX 직관과 일치. | §3.1.3에 반영(즉시 복원 명시). |
| Q-4 | **zustand + custom IPC** | 영속화 대상 최소(§6)·의존 최소화. upstream 스택 추정과 정합. | Builder가 upstream 체크아웃 후 실제 스택 확인하여 소규모 편차만 흡수. |
| Q-5 | **pdf.js** | Apache-2.0(AGPL 회피), 번들 1.4 MB. bbox API 공식 지원. | 사내 한국어 PDF 샘플로 렌더 품질 1건 스파이크 — Builder 초기 단계 Task. |
| Q-6 | **playwright-electron** | Spectron EOL, 펫 모드 창 전환 E2E 성숙도. | 오프라인 번들은 `scripts/bundle_deps.sh` npm 블록에 playwright 브라우저 바이너리 캐시 포함. CI 불가 시 수동 QA로 폴백(§11 P2 태깅). |
| Q-7 | **electron-builder NSIS 설치형** | 사내 IT 배포 친화, 아이콘·시작 메뉴 등록. | Phase 4 인스톨러 스펙과 연동. 서명 인증서는 운영 문서 책임(§18-6). |
| Q-8 | **한국어 고정** | `REQUIREMENTS.md` §1.1 "한국어 여성 목소리 기본", §4.1 한국어 자연어 파싱. | V2 영어 토글은 §18-7 V2 항목. |
| Q-9 | **B 우선** — JS mousedown + IPC `win.setPosition()` 루프 | A(`-webkit-app-region: drag` + click-through 병용)는 Electron 30.x에서 불확실. B는 확실히 동작. | Builder 초기 스파이크 1건: A 동작 여부 재검증 → 성공 시 후속 최적화 PR. |
| Q-10 | **A** — `set-dnd` WS 수신 타입 **신규 추가** | M_11 `set_dnd` API가 존재하나 WS 노출 없음. REQUIREMENTS §5 DND 토글 UX를 충족하려면 프런트→백엔드 채널 필요. | **CR-10 발행**(docs/CHANGE_REQUESTS.md). M_01 스펙 갱신 대상. |
| Q-11 | **A** — M_01 `proactive-notification` 타입 **제거** | 현재 누구도 송신하지 않음. `ai-speak-signal`이 topic·context 수용. 스펙 정합 회복. | **CR-11 발행**. M_01 스펙 L472·관련 문서 갱신 대상. |
| Q-12 | **B** — 영속화. 경로 `%APPDATA%/saessagi/pet-window.json` | 사용자 편의. 백엔드 `data/` 권한 충돌 회피. | §6.5에 경로 명시(본 개정으로 편입). |
| Q-13 | **A 단기 허용** — CSP `style-src 'self' 'unsafe-inline'` | upstream React 런타임 스타일 삽입 지원. V2에서 CSS Modules 전환 후 제거. | 보안 리스크는 §9.2에 인수인계 — 내부망·단일 사용자 전제로 허용치 내. |
| Q-14 | **B** — 화이트리스트(`electron`, `electron-builder`, `electron-rebuild`, `canvas`) | 빌드 성공률·보안 균형. `--ignore-scripts` 뒤 수동 재빌드보다 현실적. | `package.json`에 npm `overrides` + `.npmrc`로 제한. |
| Q-15 | **B** — upstream 특정 커밋을 루트 `frontend/`에 복사(독립 포크) | 포크 diff 추적 용이, 사내망에서 서브모듈 업데이트 불필요. | Q-1과 결합. 복사 커밋 해시를 `frontend/UPSTREAM_COMMIT.md`에 기록. |

### §19.2 결정에 따른 스펙 본문 갱신 지점

- §3.1.3 speaking 펄스 복원 방식 = 즉시(ease-in-out) — Q-3 반영.
- §3.2 펫 모드 드래그 이동 초기 구현 = B(JS+IPC) — Q-9 반영.
- §6.5 신설: 펫 창 위치 영속화 경로 `%APPDATA%/saessagi/pet-window.json` — Q-12 반영.
- §7.1 WS 수신 타입 표에 `set-dnd` 예정 추가 — CR-10 PASS 시 편입.
- §7.2 WS 송신 타입 표에서 `proactive-notification` 제거 예정 — CR-11 PASS 시 편입.
- §9.2 CSP 정책 = `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src ws://127.0.0.1:12393 http://127.0.0.1:*` — Q-13 반영.
- §13 의존·번들 — pdf.js(Q-5), playwright-electron(Q-6), electron-builder NSIS(Q-7), npm 화이트리스트(Q-14).
- §14 파일 구조 루트 = `frontend/`(독립 포크) — Q-1·Q-15 반영.

> Builder는 본 §19.2 지점들을 착수 첫 커밋에 반영한 뒤 기능 구현에 들어간다.

### §19.3 Builder 착수 전 필수 선행 작업

1. ✅ **서브모듈 획득** — 2026-04-21 완료. upstream `main` 브랜치 커밋 `d176e7df2366952e3bacbf12cf9a8b18a4315932` 소스를 루트 `frontend/`에 복사(독립 포크). 절차·근거는 `frontend/UPSTREAM_COMMIT.md`에 기록. `.gitmodules`가 지시한 `build` 브랜치는 배포 산출물이어서 `main`으로 전환 후 반입. 서브모듈은 원래 `build` 커밋(`06a659b...`)으로 복원해 upstream 히스토리 보존.
2. ✅ **CR-10 처리** — 2026-04-21 Critic PASS. `specs/M_01_AppCore_SPEC.md` §B-4 `set-dnd` + §C `dnd-state` 추가, `src/app/ws_handler.py` 구현. 리뷰: `reviews/M_01_AppCore_CR10_REVIEW.md`.
3. ✅ **CR-11 처리** — 2026-04-21 Critic PASS R2. `specs/M_01_AppCore_SPEC.md` §C에서 `proactive-notification` 제거 + M_08/M_10/M_12 연관 정리. 리뷰: `reviews/M_01_AppCore_CR11_REVIEW.md`(R1 FAIL), `_R2.md`(R2 PASS).
4. **Q-9 실기기 스파이크**: 옵션 A(`-webkit-app-region: drag` + click-through 전환) 동작 여부 1회 검증. 결과를 `docs/research/electron_pet_mode_spike.md`에 기록(필수 아님 — B로 착수 가능).
5. **Q-5 한국어 PDF 샘플 스파이크**: 사내 PDF 샘플 1건으로 pdf.js 렌더 품질 확인. 실패 시 MuPDF-wasm 재평가 CR 제출.

### §19.4 승인 서명

- Planner 최적안 결정 위임(사용자, 2026-04-21).
- Planner 결정 기록(본 §19) 작성 완료 — 2026-04-21.
- Builder 착수 조건 = §19.3 #1 완료 + CR-10/CR-11 PASS.
