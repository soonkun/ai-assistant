# M_12 Frontend Phase 1 — Critic Review (R2)

- 검수자: fresh Critic R2 (Opus 4.7)
- R1 판정: FAIL (reviews/M_12_Frontend_P1_REVIEW.md)
- 본 R2: **PASS**
- 날짜: 2026-04-21

---

## 1) 독립 검증 결과

### 1.1 webPreferences (src/main/window-manager.ts)
```
71:        sandbox: true,
72:        contextIsolation: true,
73:        nodeIntegration: false,
```
세 플래그 모두 REQUIREMENTS §11.2 및 Electron 보안 모범에 부합.

### 1.2 Pet Mode IPC 브리지 — 네 계층 메서드 일치
| 계층 | 메서드 |
|---|---|
| wrapper `ipc/pet-mode.ts` | `enable / disable / setClickThrough(on,forward) / setAlwaysOnTop(on) / dragStart(payload)` |
| preload `src/preload/index.ts` | `enable / disable / setClickThrough / setAlwaysOnTop / dragStart` → `pet-mode:*` invoke |
| preload d.ts | 5개 시그니처 모두 노출 |
| main `ipcMain.handle` | `pet-mode:enable / :disable / :setClickThrough / :setAlwaysOnTop / :dragStart` (TODO P3 로그) |

dragStart grep 카운트: `pet-mode.ts:4 / index.ts:2 / index.d.ts:1 / main/index.ts:2` → **4/4 위치 모두 등록**.

### 1.3 websocket-service.tsx
`grep "live2d_model" → exit=1 (0건)`. `model_info`/`ModelInfo`도 DROP 주석만 남음.
`sendScreenshotTrigger(prompt?: string, monitorIndex?: number)` — **optional로 전환됨**.

### 1.4 설정 탭 리네임
- 파일: `setting/avatar.tsx` 존재, `setting/live2d.tsx` 부재.
- setting-ui.tsx: `import Avatar from './avatar'`, Tabs.Trigger/Content value=`"avatar"` (2곳).
- i18n EN/ZH: `"avatar": "Avatar"/"头像"`, `"avatar": { ... }` 버킷. `live2d` 키 0건.
- setting-styles.tsx: `live2d` 버킷 제거, `avatar` 잔존물 없음.

### 1.5 CSP (src/renderer/index.html:7)
`media-src 'self' blob: data:;` 포함 — 오디오/비디오 blob URL 허용.

### 1.6 require() / 외부 네트워크
- renderer/preload 내 `require()` 호출 0건 (nodeIntegration=false 안전).
- 신규 외부 네트워크 호출 0건. `about.tsx`의 github/docs URL은 upstream 반입분이며 `openExternalLink()` → `shell.openExternal()` 경로(렌더러 fetch 아님). P1 수정 범위 외.

### 1.7 Live2D 잔재
`grep -rn "live2d\|Live2D" src/` 모든 매치가 아래 범주에 한정:
- `M_12 §3.3 DROP` 설명 주석 (App.tsx, avatar.tsx, websocket-*.tsx, audio-manager.ts, use-*.ts(x), main.tsx)
- P2 placeholder 안내
- `// useInterrupt 경로 변경: canvas/live2d → hooks/utils/use-interrupt`(경로 변경 사유 주석)

활성 코드 경로의 Live2D import/호출 **0건**. 미사용 WebSDK/ 디렉터리는 별건(M_12 §3.3의 P2 정리 대상이며 P1 범위 외).

### 1.8 품질 게이트
- `tsc -p tsconfig.node.json` → exit 0
- `tsc -p tsconfig.web.json` → exit 0
- `eslint src/` → exit 0

---

## 2) R1 지적별 해소 여부

| R1 # | 심각도 | 내용 | R2 결과 |
|---|---|---|---|
| 1 | CRITICAL | nodeIntegration=true | **해소** (false+sandbox+contextIsolation) |
| 2 | CRITICAL | PetModeApi 메서드명 불일치 | **해소** (wrapper↔preload 5종 일치) |
| 3 | MAJOR | dragStart 4곳 누락 | **해소** (wrapper/preload/d.ts/main 모두 등록) |
| 4 | MAJOR | live2d_model 필드 잔존 | **해소** (0건) |
| 5 | MAJOR | 설정 탭/파일명/i18n live2d 잔존 | **해소** (avatar 리네임 완료) |
| 6 | MINOR | CSP media-src 누락 | **해소** |
| 7 | MINOR | useLive2DModel dead comment | **해소** (use-interrupt.ts 정리) |
| 8 | MINOR | sendScreenshotTrigger prompt 필수 | **해소** (optional) |
| 9 | MINOR | App.tsx live2dContainerRef 변수명 | **해소** (avatarContainerRef/avatarBaseStyle/avatarPetStyle) |
| 10 | MINOR | setting-styles live2d 버킷 | **해소** |
| 11 | MINOR | audio-manager Live2D lip sync 주석 | **해소** (DROP 주석만 남음) |

---

## 3) 새 결함 발견

없음. 신규 CRITICAL/MAJOR/MINOR 0건.

참고(P1 범위 외, P2 backlog 후보):
- `src/renderer/WebSDK/` 디렉터리(upstream 반입 Cubism SDK) 미사용 상태로 잔존. 번들 크기 영향 있으나 활성 import 0건이라 런타임 문제 없음. M_12 §3.3 P2 정리 항목에 포함되는지 확인 권고.

---

## 4) 최종 판정

**PASS**

- R1 CRITICAL 2건, MAJOR 3건, MINOR 6건 모두 해소.
- typecheck/eslint 전부 exit 0.
- Live2D 잔재는 DROP 설명 주석 범주로만 한정.
- 신규 보안·네트워크·require() 위반 0건.

M_12 Frontend Phase 1 완료 판정 승인.
