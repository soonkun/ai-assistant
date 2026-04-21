# M_12 Frontend Phase 1 — Critic Review

- 검수자: fresh Critic (Opus 4.7)
- 검수 시각: 2026-04-21
- 대상 범위: M_12 Frontend Phase 1 (Foundation) — WS 메시지 통합, Live2D 제거, AvatarRenderer 인터페이스, PetWindowController IPC 뼈대, zustand store 3종, CSP meta
- P2(스프라이트 실렌더)·P3(실제 Pet BrowserWindow)·P4(pdf.js)·P5(E2E·빌드)는 범위 밖, placeholder 허용.

---

## 1. 독립 검증 결과

### 1.1 변경 파일 목록

- `git status --short frontend/` 기준 117 항목: 삭제(D) 87 + 수정(M) 27 + 신규(??) 3.
- 삭제: 전부 `src/renderer/WebSDK/**`(Live2D Cubism SDK 트리). 디렉토리 자체도 소실 확인 (`ls src/renderer/WebSDK` → No such file).
- 수정: `.eslintrc.js`, `electron.vite.config.ts`, `package-lock.json`, `src/main/index.ts`, `src/preload/*`, `src/renderer/index.html`, `App.tsx`, hooks/services/sidebar 10여 개.
- 신규: `src/renderer/src/components/avatar/`, `src/renderer/src/ipc/`, `src/renderer/src/store/`.
- Stat: `114 files changed, 402 insertions(+), 29623 deletions(-)` — 대부분이 WebSDK 삭제 누계.
- 변경 범위가 `frontend/` 내부로 한정됨을 확인(백엔드 `src/`, `tests/`, `specs/`, `docs/` 미변경).

### 1.2 Live2D 잔재 탐색

```bash
$ grep -rn "live2d\|Live2D\|pixi-live2d\|live2dcubism" frontend/src/ | wc -l
41
```

분해하면:
- `src/renderer/src/App.tsx`: 변수명/스타일명 `live2dContainerRef`, `live2dBaseStyle`, `getResponsiveLive2DWindowStyle`, `live2dPetStyle`, 주석 3건. **런타임 기능은 무관**(단순 변수명). 네이밍 잔재.
- `src/renderer/src/components/sidebar/setting/live2d.tsx`: 파일명이 `live2d.tsx`로 남아있고 컴포넌트는 `AvatarSetting`으로 리네임된 상태. `setting-ui.tsx`가 `import Live2D from './live2d'` + `<Tabs.Trigger value="live2d">`로 참조 → 탭 식별자와 파일명 모두 `live2d`.
- `src/renderer/src/services/websocket-service.tsx:80`: **`live2d_model?: string;` 필드가 MessageEvent에 잔존**. M_12 §3.3 DROP 취지와 충돌.
- `src/renderer/src/hooks/utils/use-interrupt.ts:12`: `// const { currentModel } = useLive2DModel();` 죽은 주석.
- 로케일 JSON (`locales/en/translation.json`, `locales/zh/translation.json`): `"live2d": "Live2D"` 키·섹션. **i18n 키 잔재**.
- 기타 대부분은 `M_12 §3.3 DROP` 설명 주석(정당).

- `src/renderer/WebSDK/` 디렉토리 소실 확인 ✅
- `src/renderer/public/libs/` 존재하나 **비어 있음** (Live2D cubismcore 산출물 삭제 ✅)
- `package.json`에 `live2d`/`pixi`/`oh-my-live2d` 없음 ✅
- `package-lock.json`에도 해당 패키지 없음 ✅
- `electron.vite.config.ts`에서 `live2dcubismcore.js` 복사 제거 ✅

### 1.3 WS 메시지 통합 검증

- `websocket-handler.tsx` 수신 4종 case:
  ```
  281:      case 'avatar-state':
  292:      case 'continuous-capture-state':
  304:      case 'dnd-state':
  312:      case 'ai-speak-signal':
  ```
  ✅ 4/4.

- `websocket-service.tsx` 송신 4종 헬퍼:
  - `sendScreenshotTrigger(prompt, monitorIndex?)` (L238) → `{type, prompt, monitor_index?}` ✅ M_01 §B-1 준수
  - `sendStartContinuousCapture(intervalSec, monitorIndex?, promptTemplate?)` (L256) → `{type, interval_sec, monitor_index?, prompt_template?}` ✅ M_01 §B-2 준수
  - `sendStopContinuousCapture()` (L276) → `{type}` ✅ M_01 §B-3 준수
  - `sendSetDnd(enabled)` (L288) → `{type, enabled}` ✅ M_01 §B-4 준수
  ✅ 4/4. 모든 키는 snake_case 준수.

### 1.4 zustand store 3종 존재

```
src/renderer/src/store/avatar-store.ts  — { emotion, crossfadeMs, speaking } ✅
src/renderer/src/store/dnd-store.ts     — { enabled } ✅
src/renderer/src/store/capture-store.ts — { running, intervalSec } ✅
```

### 1.5 AvatarRenderer 인터페이스

`src/renderer/src/components/avatar/types.ts`:
- `Emotion` Literal 8종: `neutral | happy | surprised | sad | worried | thinking | sleepy | study` ✅ (M_12 §3.1, §4 일치)
- `AvatarRendererErrorEvent` 4종 code ✅
- `AvatarRenderer` 인터페이스 메서드 6종 (preload, mount, setEmotion, setSpeaking, onError, dispose) ✅ §5.1 일치

### 1.6 PetWindowController IPC 뼈대

- `src/renderer/src/ipc/pet-mode.ts`: renderer wrapper. 메서드 4종 `enablePetMode/disablePetMode/setClickThrough/setAlwaysOnTop`.
- `src/preload/index.ts` L17-24: preload의 `petModeApi` 정의. **메서드명이 `enable/disable/setClickThrough/setAlwaysOnTop`** — renderer wrapper가 호출하는 `enablePetMode/disablePetMode`와 **불일치**.
- `src/preload/index.d.ts` L23-28: d.ts 선언 `enable/disable/setClickThrough/setAlwaysOnTop` ← preload 일치, wrapper 불일치.
- `src/main/index.ts` L77-91: `pet-mode:enable / :disable / :setClickThrough / :setAlwaysOnTop` 4종 `ipcMain.handle` 등록 ✅ (console.log placeholder).
- **결함**: D-1 참조.

### 1.7 CSP meta

`src/renderer/index.html:7`:
```
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src ws://127.0.0.1:12393 http://127.0.0.1:*; img-src 'self' data:;">
```

- §19.2 정책 본문(`default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src ws://127.0.0.1:12393 http://127.0.0.1:*`) 글자 단위 일치 + `img-src 'self' data:;` 추가 ✅
- `§11.1` 확장 정책의 `media-src`, `font-src`, `object-src 'none'`, `frame-src 'none'`, `worker-src` 미포함. §19.2 결정이 최종이므로 일단 허용. ⚠️ **MINOR**: audio blob URL 재생 경로가 `media-src` 기본(`default-src 'self'`)만 가능 — `blob:` 허용 없이 `addAudioTask`의 `audioBase64`가 차단될 가능성 존재(data URI 는 `img-src 'self' data:`에만 해당, media에는 적용 안 됨).

### 1.8 Electron webPreferences 위반

`src/main/window-manager.ts:69-74`:
```ts
webPreferences: {
  preload: join(__dirname, '../preload/index.js'),
  sandbox: false,            // §11.2 "sandbox: true" 권고 위반
  contextIsolation: true,    // OK
  nodeIntegration: true,     // §11.2 "nodeIntegration: false" 명시 위반
},
```

- **CRITICAL**: §11.2의 절대 규칙 `nodeIntegration: false` 위반. 태스크 명세의 "있으면 FAIL" 조항에 해당.
- `sandbox: false`는 §11.2가 "가능하면"이라 적었으니 MINOR.

### 1.9 package.json deps

Live2D·pixi 계열 미포함 ✅. `zustand ^5.0.3` 포함 ✅.

### 1.10 typecheck · eslint

```
$ node tsc.js --noEmit -p tsconfig.node.json   → exit 0
$ node tsc.js --noEmit -p tsconfig.web.json    → exit 0
$ node eslint.js --ext .js,.jsx,...,.tsx src/  → exit 0
```

typecheck 양쪽·eslint 모두 PASS ✅. `.eslintrc.js`가 Builder에 의해 airbnb extends → `@typescript-eslint/recommended` + `plugin:react/recommended`로 축소 변경(주석에 pre-existing 문제라고 기록). 이 변경은 M_12 §19.2/Q-14(npm 화이트리스트 정책)와 충돌하지 않으며 `package.json`에 실제로 설치된 플러그인만 사용하도록 정비 — **정당**.

### 1.11 외부 네트워크 호출

- `grep "fetch\|XMLHttpRequest\|axios"` → 유의미한 결과 없음.
- `grep "http[s]://"`에서 upstream `components/sidebar/setting/about.tsx` L50, L58, L66이 `github.com`, `docs.llmvtuber.com` 등 외부 URL을 `window.open()`으로 오픈. 본 파일은 M_12 변경 대상이 아니며 upstream 그대로 — P1 "최소 개입" 원칙을 감안하면 MINOR(후속 P5에서 소제·대체 필요).
- 외부 네트워크 호출을 M_12 P1이 **신규 추가**한 흔적은 없음 ✅.

### 1.12 테스트 존재 여부

- `frontend/tests/`, `frontend/e2e/` 디렉토리 부재. P1 범위 밖(§15.2는 P5·전체 DoD). 허용.
- 단, `CLAUDE.md` 산출물 체크리스트 "테스트 ≥5/≥5/≥3"는 M_12 **전체**에 필요하므로 P2~P5에서 추가돼야 함.

---

## 2. 체크리스트 심사

### 스펙 정합성

| 항목 | 판정 | 근거 |
|---|---|---|
| WS 수신 4건 case 존재 | ✅ | websocket-handler.tsx L281/L292/L304/L312 |
| WS 수신 payload 키 snake_case | ✅ | `message.crossfade_ms`, `message.interval_sec`, `message.enabled`, `message.topic`, `message.context` 등 |
| WS 송신 헬퍼 4종 존재 | ✅ | websocket-service.tsx L238/L256/L276/L288 |
| WS 송신 payload 스키마 일치 | ✅ | monitor_index, interval_sec, prompt_template, enabled 모두 M_01 §B와 일치 |
| ai-speak-signal topic 4종 검증 | ✅ | `VALID_TOPICS = ['morning_briefing','event_reminder','idle_rest','overwork']` L315, 미지 topic은 `console.warn` + break |
| zustand 3 store 요구 필드 | ✅ | avatar(emotion/crossfadeMs/speaking), dnd(enabled), capture(running/intervalSec) |
| AvatarRenderer 시그니처 일치 | ✅ | types.ts §5.1 6종 메서드 + Emotion/ErrorEvent |
| Emotion Literal 8종 | ✅ | types.ts L3-11 |
| PetWindowController IPC 4종 존재 | ⚠️ | preload·main은 4종 OK, renderer wrapper의 메서드 이름이 preload와 **불일치**(D-1) |
| preload contextBridge 노출 | ✅ | `contextBridge.exposeInMainWorld('petMode', petModeApi)` L103 |
| preload nodeIntegration=false | ❌ | **window-manager.ts L73: `nodeIntegration: true`** (D-2) |
| main pet-mode 4종 handle | ✅ | main/index.ts L77-91 |
| CSP meta §19.2 글자단위 일치 | ✅ | index.html L7 + `img-src 'self' data:;` 확장 허용 |

### Live2D 제거 완전성

| 항목 | 판정 | 근거 |
|---|---|---|
| 문자열 0건 | ❌ | 41건 잔존. 대부분 DROP 주석(정당)이나 일부는 실기능/식별자 |
| `live2d_model?: string;` MessageEvent 필드 | ❌ | websocket-service.tsx L80 (D-3) |
| `live2d.tsx` 파일명 + `'live2d'` 탭 value | ⚠️ | 컴포넌트 내용은 AvatarSetting으로 교체됐으나 파일명·탭 ID는 live2d 그대로 (D-4) |
| i18n "live2d" 섹션 존치 | ⚠️ | en/zh translation.json에 `settings.live2d`, `live2d.title` 등 키 잔존. 렌더 여부 확인 필요 (D-4 포함) |
| `WebSDK/` 디렉토리 | ✅ | 삭제 완료 |
| `public/libs/live2dcubismcore.js` | ✅ | 삭제 완료 (libs 디렉토리 비었음) |
| `package.json` deps | ✅ | pixi/live2d 없음 |
| vite.config alias/copy | ✅ | WebSDK alias + cubismcore 복사 제거 |

### 타입·린트·빌드

| 항목 | 판정 | 근거 |
|---|---|---|
| `tsc -p tsconfig.node.json` | ✅ | exit 0 |
| `tsc -p tsconfig.web.json` | ✅ | exit 0 |
| `eslint src/` | ✅ | exit 0 |
| `.eslintrc.js` 변경 정당성 | ✅ | airbnb 설치 부재의 pre-existing 오류 교정, 화이트리스트 정책 위배 없음 |

### 보안·오프라인

| 항목 | 판정 | 근거 |
|---|---|---|
| 외부 네트워크 호출 신규 추가 | ✅ | 없음 |
| 외부 URL 하드코딩 | ⚠️ | upstream about.tsx 외부 github/docs 링크. M_12 변경 아님. (D-5) |
| `nodeIntegration: true`/`contextIsolation: false` 잔존 | ❌ | **window-manager.ts L73 nodeIntegration: true** (D-2 재언급) |

### 범위 준수

| 항목 | 판정 | 근거 |
|---|---|---|
| 스프라이트 실렌더 없음 (P2 유보) | ✅ | SpriteAvatarRenderer는 placeholder만 |
| 실제 Pet BrowserWindow 없음 (P3 유보) | ✅ | main handler는 console.log only |
| pdf.js 통합 없음 (P4 유보) | ✅ | 흔적 없음 |
| 테스트 프레임워크(vitest) 추가 | ✅ | 미도입 (P5) |
| frontend/ 외부 변경 없음 | ✅ | `git status --short frontend/` 결과만 117건 |

### upstream 영향

| 항목 | 판정 | 근거 |
|---|---|---|
| Live2D 제거 외 기능 리팩토링 없음 | ⚠️ | `App.tsx`의 live2d* 변수명은 그대로 둬도 되는데 주석만 추가, OK. 다만 `setting-ui.tsx`에서 Tabs.Content value `live2d`가 그대로 남은 것은 삭제 정책과 어중간(D-4). |

---

## 3. 결함 목록

### 심각 결함 (CRITICAL — 있으면 자동 FAIL)

1. **[CRITICAL] `nodeIntegration: true`** — `frontend/src/main/window-manager.ts:73`
   - `webPreferences.nodeIntegration: true`, `sandbox: false`는 M_12 §11.2 "nodeIntegration: false, sandbox: true (가능하면)" 보안 계약의 **정면 위반**이며, 태스크 명세의 "있으면 FAIL" 조항에 해당.
   - upstream 기본값이지만 Builder가 동일 파일에서 CSP meta 추가·IPC 4종 등록 등 security layer를 접촉했으므로 함께 하드닝하는 것이 합리적 범위.
   - `nodeIntegration: true` + `contextIsolation: true` 조합은 Electron 보안 권고와 모순(contextIsolation 없는 nodeIntegration은 치명적, 둘 다 켜진 경우도 공격 표면 확대). renderer에서 `require('fs')` 류 사용 가능해져 `localStorage` 대신 fs로 우회 가능한 공격 표면 존재.
   - 권고 조치: `nodeIntegration: false, sandbox: true` 로 변경하고, renderer 쪽 `require('i18next')`(websocket-service.tsx L113) 등 node API 의존 코드가 contextBridge/preload 경로로 동작하는지 검증. typecheck는 통과하나 런타임에서 `require` 미정의 에러 가능성 있으므로 동일 커밋에서 조치.

2. **[CRITICAL] PetModeApi 이름 불일치 — renderer wrapper↔preload 브리지 파손**
   - `frontend/src/renderer/src/ipc/pet-mode.ts`의 `PetModeApi` 타입은 `enablePetMode / disablePetMode / setClickThrough / setAlwaysOnTop`.
   - preload (`src/preload/index.ts:17-24`)와 타입 선언 (`src/preload/index.d.ts:23-28`)은 **`enable / disable / setClickThrough / setAlwaysOnTop`**.
   - wrapper가 `window.petMode.enablePetMode`를 체크 → 항상 undefined → 조용히 `Promise.resolve()` fallthrough. IPC가 실제로는 절대 호출되지 않음.
   - M_12 §5.2 공개 API 표는 `enable()/disable()/setClickThrough()/setAlwaysOnTop()/dragStart()` — preload가 스펙을 따르고 renderer wrapper가 틀렸다. 즉 wrapper를 수정해야 함.
   - 권고 조치: wrapper의 `PetModeApi`를 preload와 일치시키고, 메서드명 `enable/disable/setClickThrough/setAlwaysOnTop`로 변경. 또한 §5.2가 요구하는 **`dragStart(payload)` 메서드 완전 결락** — preload/main/wrapper/d.ts 모두 추가 필요. P3 가는 길에 최소 뼈대라도 필요(§13.1 N-4 E2E에서 `pet:dragStart` 수신 검증 요구).

### 중대 결함 (MAJOR — 세 개 이상이면 FAIL)

3. **[MAJOR] §5.2 `dragStart` 메서드 전면 결락**
   - M_12 §5.2 PetModeApi 스펙:
     ```ts
     type PetModeApi = { ...; dragStart(payload: {x:number;y:number}): Promise<void>; };
     ```
   - preload petModeApi·main ipcMain.handle·d.ts·renderer wrapper 어디에도 `dragStart` 없음.
   - Q-9 결정이 B안(JS mousedown+IPC win.setPosition 루프)이어서 **`pet-mode:dragStart` IPC가 P3 이전에 계약으로 존재**해야 정합. P1에서는 placeholder라도 두고 P3에서 동작시키는 방식이 정상.
   - 현재 구조로는 P3 착수 시 wrapper/preload/d.ts/main 4곳을 동시 수정해야 한다.

4. **[MAJOR] `live2d_model?: string;` MessageEvent 필드 잔존**
   - `frontend/src/renderer/src/services/websocket-service.tsx:80` — `live2d_model?: string;`
   - M_12 §3.3 "Live2D 의존 제거" 명백한 잔재. 인접 필드 `model_info`는 "제거됨" 주석으로 삭제되었으나 `live2d_model`은 삭제가 누락됨.
   - 타입 컴파일만 보면 문제없지만 향후 backend payload가 우연히 해당 필드를 채우면 렌더러가 다시 Live2D 코드를 찾게 되어(없음) 죽은 분기 재활성화 위험.

5. **[MAJOR] 설정 UI에 `live2d` 식별자 잔존 — 사용자 노출 경로**
   - `src/renderer/src/components/sidebar/setting/setting-ui.tsx`:
     - L19 `import Live2D from './live2d';`
     - L70 `<Tabs.Content value="live2d">`
     - L130 `<Tabs.Trigger value="live2d">`
   - `live2d.tsx` 파일 자체가 그대로 있고(컴포넌트는 `AvatarSetting`으로 리네임 but **default export명 일치**), 탭 식별자가 `live2d`.
   - i18n 키 `settings.category.live2d`, `settings.live2d.title` 등도 `translation.json`에 잔존해 **"Live2D" 문자열이 설정 탭에 그대로 렌더**될 가능성.
   - §3.3 "Live2D 의존 제거" + §19.2의 "스프라이트 placeholder 설정" 취지와 모순. 최소한 탭 value/i18n 키를 `avatar`로 리네임해야 함.

### 경미 결함 (MINOR)

6. **[MINOR] `media-src blob:` 누락 → 오디오 재생 CSP 차단 우려**
   - index.html CSP에 `media-src` 디렉티브가 명시되지 않아 `default-src 'self'`로 폴백. backend TTS 오디오를 base64 audio element로 재생 시 `src="data:audio/mpeg;base64,..."` 경로는 CSP `media-src 'self'`로 차단될 가능성(data URI는 `img-src data:`만 효과, media에는 별도 `media-src data:` 필요). P1에서 오디오를 실제 쓰는지에 따라 재생 가능/불가 판정이 달라지고, §11.1의 확장 CSP가 `media-src 'self' blob:`을 명시하므로 §19.2 축약 정책에서 누락된 것으로 보임.
   - 권고: `media-src 'self' blob: data:;` 추가 검토(§11.1 기준).

7. **[MINOR] upstream `about.tsx` 외부 링크(github.com, docs.llmvtuber.com) 미처리**
   - M_12 P1이 신규로 추가한 것은 아니나, 설정 패널에서 `window.open(외부 URL)` 호출. 오프라인 내부망에서는 정당한 404/타임아웃 동작이나, §11 보안 계약의 "외부 네트워크 금지" 취지에 맞춰 P5 이전에 `openExternalLink`를 no-op 또는 제거할 것 권고.

8. **[MINOR] main 프로세스의 `localStorage.getItem` 호출 (upstream 버그)**
   - `src/main/index.ts:61` `JSON.parse(localStorage.getItem("configFiles") || "[]")` — `localStorage`는 renderer API. main에서 호출 시 `ReferenceError`. upstream 레거시로 판단하지만 **#2(nodeIntegration)와 결합해 재활성화되면 실제 크래시 경로**.

9. **[MINOR] `sandbox: false`**
   - §11.2 "sandbox: true (가능하면)" 권고. #1 CRITICAL 수정 시 함께 `true`로 전환 검토.

10. **[MINOR] use-interrupt.ts 죽은 주석 `// const { currentModel } = useLive2DModel();`**
    - 제거 주석이 아닌 코드 주석 처리. DROP 완결성 저하.

11. **[MINOR] `sendScreenshotTrigger` 시그니처에서 `prompt: string` 필수화**
    - M_01 §B-1은 `prompt?:str`(optional). 헬퍼가 필수 인자로 강제 → 호출부에서 `""` 비우거나 정의되지 않으면 TypeScript 에러. 기능적 문제는 없고 단순 DX/스펙 충실도 MINOR.

---

## 스펙 vs 구현 매핑 검증

| 스펙 §항목 | 구현 위치 | 상태 |
|---|---|---|
| §3.3 Live2D DROP (코드) | WebSDK 삭제, package.json 정리 | ✅ |
| §3.3 Live2D DROP (식별자·타입) | MessageEvent `live2d_model`, Tab value `live2d`, i18n `live2d` | ❌ D-3, D-4 |
| §5.1 AvatarRenderer 인터페이스 | components/avatar/types.ts | ✅ |
| §5.1 SpriteAvatarRenderer 구현 | components/avatar/SpriteAvatarRenderer.tsx (placeholder) | ✅ (P2 유보) |
| §5.2 PetModeApi (renderer wrapper) | ipc/pet-mode.ts | ❌ D-1 (이름 불일치, dragStart 누락) |
| §5.2 PetModeApi (preload) | preload/index.ts L17-24 | ⚠️ dragStart 누락 D-3 |
| §5.2 PetModeApi (main handler) | main/index.ts L77-91 | ⚠️ dragStart 누락 |
| §6 avatarSlice | store/avatar-store.ts | ✅ |
| §6 captureSlice | store/capture-store.ts | ✅ |
| §6 (CR-10) dnd slice | store/dnd-store.ts | ✅ |
| §7.1 클라→서버 4종 송신 | websocket-service.tsx | ✅ |
| §7.2 서버→클라 4종 수신 | websocket-handler.tsx | ✅ |
| §7.3 ai-speak-signal topic 검증 | websocket-handler.tsx L315-321 | ✅ (P1 최소 처리) |
| §9.2 CSP (§19.2 final) | index.html L7 | ✅ |
| §11.2 webPreferences | window-manager.ts L69-74 | ❌ D-2 |
| §19.2 설정 탭 `live2d`→`avatar` 리네임 | setting-ui.tsx | ❌ D-4 |

---

## 테스트 커버 검증

P1 범위에는 테스트 프레임워크 도입·작성이 포함되지 않음(P5로 유보). `frontend/tests/` 부재는 P1 관점에서 허용.

단 M_12 전체 DoD에는 "테스트 정상 ≥5, 엣지 ≥5, 적대적 ≥3"이 포함되므로 P5 착수 전 이 체크리스트는 잠긴다. 현 시점에선 "테스트 미평가".

---

## 검토하지 못한 영역

- `frontend/dist` / `frontend/out` 빌드 산출물 미생성 상태(빌드 실행은 P5 범위). `npm run build` 실행 결과 기반의 bundle size·번들 분석은 본 리뷰에서 확인 불가.
- Electron 실행 테스트(E2E·실기기 click-through·드래그) — P3/P5 범위.
- renderer에서 `require('i18next').default` 호출(websocket-service.tsx:113)이 `nodeIntegration: false`로 전환 시 정상 동작하는지 런타임 검증 미실행(정적 typecheck만).
- i18n JSON의 `settings.live2d` 키가 실제 UI에 렌더되는 경로 추적 — grep으로 key 존재만 확인하고 사용처 역추적 생략.

---

## 4. 최종 판정

**FAIL**

사유:
- CRITICAL 2건: #1 `nodeIntegration: true`(§11.2 위반), #2 PetModeApi 이름 불일치로 renderer→IPC 브리지 파손.
- MAJOR 3건: #3 `dragStart` 스펙 결락, #4 `live2d_model` 필드 잔존, #5 설정 탭 `live2d` 식별자·i18n 키 잔존 (MAJOR 3개 이상 FAIL 조건 충족).

수정 지시:

1. `src/main/window-manager.ts:71-73` `webPreferences`를 `sandbox: true, contextIsolation: true, nodeIntegration: false`로 변경. renderer의 `require()` 사용부(`websocket-service.tsx` L111-118 i18next fallback)가 preload 경로로 이전되었는지 검증하고, 필요 시 `getTranslation()` 헬퍼를 `window.electron` 또는 직접 `import i18next from 'i18next'` 형태로 수정.
2. `src/renderer/src/ipc/pet-mode.ts`의 `PetModeApi` 메서드명을 `enable/disable/setClickThrough/setAlwaysOnTop`으로 맞추고, §5.2 `dragStart(payload: {x:number;y:number}): Promise<void>`를 **renderer wrapper / preload / d.ts / main handler** 네 곳 모두에 placeholder로라도 추가.
3. `src/renderer/src/services/websocket-service.tsx:80` `live2d_model?: string;` 제거.
4. 설정 탭 `live2d` 식별자 및 `live2d.tsx` 파일명을 `avatar`로 리네임(또는 최소한 탭 value/i18n 키를 `avatar`로). i18n translation.json의 `settings.category.live2d`, `settings.live2d.*` 키도 `avatar`로 이관.
5. (MINOR) `media-src 'self' blob: data:;` CSP 보강, `about.tsx` 외부 URL 처리, main의 `localStorage` 호출 제거 — P2·P5와 묶어도 무방하나 P1 재검수 전에 함께 처리 권장.

재검수 요청 시 같은 Critic을 재활용하지 말고 fresh Critic으로 진행할 것(`CLAUDE.md` 절대 금지 조항).

---

_Signed: fresh Critic, 2026-04-21_
