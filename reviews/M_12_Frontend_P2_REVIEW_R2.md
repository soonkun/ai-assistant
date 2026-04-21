# Critic Review R2: M_12 Frontend Phase 2 — SpriteAvatarRenderer (재검수)

R1 Critic(`reviews/M_12_Frontend_P2_REVIEW.md`)이 MAJOR 2 + MINOR 4로 FAIL 판정한 이후의 수정본을 fresh 세션에서 독립 재검수한다. R1 지적이 맞는지가 아니라, **현재 코드가 스펙과 맞는가**를 처음 보는 것처럼 판단한다.

## 1. 독립 검증 결과

| 항목 | 명령 | 결과 |
|---|---|---|
| `SpriteAvatarRenderer.tsx` 존재 | `wc -l` | 418 LOC |
| `allFailedRef` 사용 여부 | `grep allFailedRef` | **0건** (R1 MAJOR #1 해소 신호) |
| `useState(allFailed)` | grep | L65 `const [allFailed, setAllFailed] = useState(false)` |
| 렌더 함수 `if (allFailed)` 가드 | grep | L320 `if (allFailed) { return <img width={1} ... /> }` |
| 내부 `let everyFailed` (shadowing 제거) | grep | L121 `let everyFailed = true` — OK |
| WS `resolveEmotion`·`resolveCrossfadeMs` import | L25 | PASS |
| WS `avatar-state` 경로 `resolveCrossfadeMs(message.crossfade_ms, prev.crossfadeMs)` | L288 | PASS |
| WS 범위 밖 시 `console.warn` 1회 | L293 | PASS |
| `validators.ts` 신규 | cat | 순수 함수 2개 (`resolveEmotion`, `resolveCrossfadeMs`) |
| `public/assets/character/saessagi/*.png` 8종 | ls | happy/neutral/sad/sleepy/study/surprised/thinking/worried |
| `public/character/` (구 경로) 제거 | ls | `No such file or directory` — PASS |
| `BASE_PATH === '/assets/character/saessagi'` | L23 | PASS (스펙 §8.1 경로 정합) |
| `validators.test.ts` it 블록 수 | grep | 7건 (resolveEmotion 3 + resolveCrossfadeMs 4) |
| `SpriteAvatarRenderer.test.tsx` it 블록 수 | grep | 9건 (R1 동일 + TC-09에 placeholder assert 추가) |
| TC-09 placeholder DOM assertion | grep `img[width=\"1\"]` | L288 `container.querySelector('img[width="1"]')` PASS |
| `tsc -p tsconfig.node.json` | exit | **0** |
| `tsc -p tsconfig.web.json` | exit | **0** |
| `eslint --ext .ts,.tsx src/` | exit | **0** (warnings/errors 0) |
| `vitest run` | 결과 | **2 files, 16 tests passed** (3.53 s) |
| 외부 네트워크 `fetch('http://…')` / `fetch('//…')` 신규 | grep | **0건** |
| pdf.js / BrowserWindow Pet / playwright 실구현 | grep | **0건** (P3~P5 scope 유지) |
| frontend/ 외부 파일 변경 | `git diff HEAD --stat` | **0건** |

## 2. R1 결함별 해소 여부

### MAJOR #1 — neutral조차 실패 시 placeholder 리렌더 누락

- **해소: YES**
- 증거:
  - `allFailedRef` (useRef) → `[allFailed, setAllFailed] = useState(false)` (L65)로 전환 완료.
  - `preloadEmotions`에서 모든 결과가 rejected이면 `setAllFailed(true)` 호출 (L133)하여 **리렌더 트리거**.
  - 렌더 함수 L320 `if (allFailed) return <img width={1} height={1} ... />` — 실제 DOM에 1px placeholder 노출.
  - 내부 루프 변수는 `everyFailed`로 리네임되어 외부 `allFailed` state와 shadowing 없음 (L121).
  - TC-09에 `container.querySelector('img[width="1"]')` DOM assertion 추가 (L288) — 회귀 보장.
- 잠재 주의: jsdom 환경에서 `HTMLImageElement.prototype.decode`를 reject로 override하는 테스트가 실제 브라우저의 `img.onerror` 경로와 다를 수 있으나, 현재 preloadEmotions는 `decode()` 기반이므로 일관됨.

### MAJOR #2 — WS `avatar-state` crossfade_ms 범위 검증 부재

- **해소: YES**
- 증거:
  - `websocket-handler.tsx:25` validators import.
  - L287~L298 블록에서 `useAvatarStore.getState()`를 `prev`로 캡처 후 `resolveCrossfadeMs(message.crossfade_ms, prev.crossfadeMs)` 호출.
  - 범위 밖일 때 `prev.crossfadeMs`가 유지되어 store 오염 차단.
  - L293 `console.warn` 1회 기록 (원본값과 유지값 둘 다 메시지 포함).
  - 유효 emotion/speaking은 정상 갱신되므로 speaking 전환 독립성 유지.
- 잠재 주의: `prev = useAvatarStore.getState()`로 한 번 캡처 후 `prev.setAvatarState(...)` 호출. `setAvatarState`는 zustand가 제공하는 action이며 내부적으로 `set((prev)=>...)` 함수형 업데이트 사용 (store 정의 L27), 따라서 캡처 시점과 실행 시점 사이 race가 있어도 덮어쓰기 위험 없음. OK.

### MINOR #1 — 경로 `assets/` prefix

- **해소: YES**
- 증거:
  - `BASE_PATH = '/assets/character/saessagi'` (L23) 스펙 §8.1/§13.1 N-1 기대 URL과 정합.
  - PNG 에셋이 `public/assets/character/saessagi/` 8종으로 실재 배치.
  - `public/character/` 구 경로 제거 확인(존재하지 않음).
  - Vite `public/` 루트 서빙 관례로 런타임 URL은 `/assets/character/saessagi/<e>.png` — 스펙 문자열 완전 일치.

### MINOR #2~#4 (참고)

R1 리포트에서 후속 PR로 이월 가능하다고 명시. R2 재확인:
- `handle.setSpeaking`은 여전히 내부 state만 갱신(L299~L301). store와 불일치 가능성 존재하나 사용자 경로는 WS→store→useEffect이므로 실무 영향 없음. 후속 PR에서 통일 권고.
- `dispose()` 후 store 구독 차단 플래그 없음 — unmount 시 자동 해제로 충분한 실질적 안전성.
- crossfade 진행 중 새 setEmotion 호출 시 타이머 취소 없음(L247) — 플리커 가능성은 있으나 스펙 §8.2.1 명시 범위 밖.

## 3. 새 결함 탐색 (R1 앵커 배제)

### [CRITICAL] — 0건

### [MAJOR] — 0건

### [MINOR] — 2건 (참고, FAIL 사유 아님)

1. **[MINOR-R2 #1] `Emotion` 타입이 `components/avatar/types.ts`와 `store/avatar-store.ts` 두 곳에 중복 정의**
   - 파일: `src/renderer/src/components/avatar/types.ts:3` / `src/renderer/src/store/avatar-store.ts:3`
   - R1에서도 "OK (중복 정의 2곳 존재)"로 이월된 건. 향후 8종 외 감정 추가 시 유지보수 위험.
   - 권고: `store/avatar-store.ts`가 `components/avatar/types.ts`에서 re-export하도록 통합.

2. **[MINOR-R2 #2] 렌더러 내부 `resolveEmotion`(useCallback, emitError 포함)과 `validators.ts::resolveEmotion`(순수 함수)이 동명이지만 동작이 다르다**
   - 파일: `src/renderer/src/components/avatar/SpriteAvatarRenderer.tsx:82-92` vs `src/renderer/src/components/avatar/validators.ts:9-12`
   - 렌더러 것은 `console.warn` + `emitError` 부작용 있음, validators 것은 순수. 향후 코드 독해 시 혼동.
   - 권고: 렌더러 쪽을 `resolveEmotionWithError` 등으로 개명하거나, validators를 사용한 뒤 렌더러에서 폴백 여부를 비교해 부작용만 별도 처리.

### 체크리스트 확인

| 질문 | 답 |
|---|---|
| `resolveEmotion`/`resolveCrossfadeMs` 시그니처가 테스트와 일치? | YES (unknown, number prev) |
| WS 핸들러에 orphan `VALID_EMOTIONS`/`Emotion` import 잔존? | NO (단, store/avatar-store.ts에 별개 Emotion 타입 존재 — import 아님) |
| `useAvatarStore.getState()` 캐시된 `prev`로 `setAvatarState` 호출 시 덮어쓰기 위험? | NO (zustand 함수형 업데이트 사용) |
| 테스트가 1px placeholder를 실제로 assert? | YES (L288) |
| tsc.node + tsc.web exit 0? | YES |
| eslint 0 errors? | YES |
| vitest 전체 PASS(≥16건)? | YES (16/16, 3.53 s) |
| 외부 네트워크 신규? | NO |
| P3~P5 실구현 선행? | NO |
| frontend/ 외 파일 변경? | NO |

## 4. 최종 판정

### **PASS**

- CRITICAL: 0
- MAJOR: 0 (R1 MAJOR #1·#2 모두 해소)
- MINOR #1 (경로 prefix): 해소
- MINOR-R2 #1·#2: 이월 가능, FAIL 사유 아님

### 근거 요약
1. R1이 지적한 두 MAJOR가 구조적 변경(useState 전환 + 공통 validators 헬퍼)으로 정확히 해결되었고, 해결을 직접 검증할 테스트(TC-09 DOM assert, validators.test.ts 7건)가 동반됨.
2. 경로 이슈는 에셋 파일 실제 이동 + BASE_PATH 상수 + 구 경로 제거로 완결.
3. 품질 게이트(tsc×2, eslint, vitest 16건) 모두 exit 0.
4. 외부 네트워크·P3~P5 scope 침범·frontend 외 파일 변경 모두 0건.
5. 신규 도입 결함 없음 (두 MINOR는 리팩토링 가벼운 개선).

### 다음 Critic이 보아야 할 영역 (R3 이후)
- Electron production 빌드 시 `public/assets/` 자산이 `resources/app.asar.unpacked/` 또는 dist에 실제 복사되는지 (scope P5).
- 실기기에서 16 FPS 스프라이트 prefetch latency와 GPU 합성 결과 (scope P5).
- 적대적 테스트 3건(§13.3 A-1 악성 JSON, A-2 크기 공격, A-4 CSP) — P2 범위 외이나 DoD 시점에 추가 필요.

---

*검토 시각*: 2026-04-21
*검토자*: Critic R2 (opus, fresh session, R1 결과 독립 검증)
*참조*: `specs/M_12_Frontend_SPEC.md` §5.1·§7.2·§8·§13.1, `reviews/M_12_Frontend_P2_REVIEW.md` (R1)
