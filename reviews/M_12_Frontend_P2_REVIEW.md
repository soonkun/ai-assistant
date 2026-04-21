# Critic Review: M_12 Frontend Phase 2 — SpriteAvatarRenderer 실구현

## 1. 독립 검증 결과

| 검증 항목 | 결과 |
|---|---|
| `src/renderer/public/character/saessagi/*.png` 8종 | PASS (happy/neutral/sad/sleepy/study/surprised/thinking/worried) |
| `SpriteAvatarRenderer.tsx` 라인 수 | 418 LOC (placeholder 24 LOC → 실구현) |
| `useImperativeHandle`·`decode`·`Promise.allSettled`·`scaleY`·`opacity`·`rotate` 키워드 | 모두 포함 |
| `websocket-handler.tsx` VALID_EMOTIONS 2차 방어 (line 287) | PASS |
| 테스트 `it` 블록 수 | 9건 (정상 5 + 엣지 4) |
| `tsc -p tsconfig.node.json` | exit 0 |
| `tsc -p tsconfig.web.json` | exit 0 |
| `eslint src/` | exit 0 (warnings/errors 0) |
| `vitest run` | 9/9 PASS, 4.40 s |
| 외부 네트워크 `fetch('http://...')` / `fetch('//...')` | 0건 신규 추가 |
| pdf.js·Pet BrowserWindow·playwright 실구현 | 0건 (P3~P5 scope 유지) |
| frontend/ 외부 파일 변경 | 0건 (git diff HEAD 기준) |

## 2. §8 각 항목 심사

### §8.1 자산 로딩
- 8종 PNG `public/character/saessagi/` 존재 **PASS**
- `preloadEmotions`가 `Promise.allSettled + HTMLImageElement.decode()` 사용 **PASS**
- 실패 emotion을 `failedEmotions` Set 기록 + `resolveAsset`에서 neutral 폴백 **PASS**
- `onError({code:'asset_missing'})` 발행 **PASS**
- 스펙 §8.1 경로 문자열 `assets/character/saessagi/` vs 구현 `/character/saessagi/` — Vite `public/` 루트 서빙 관례 충돌. §13.1 N-1 기대 URL `/assets/character/saessagi/happy.png`과 **부분 불일치**.

### §8.2.1 Crossfade
- 2 레이어 `<img>` A/B 토글 **PASS**
- 새 레이어 opacity 0→1, 기존 1→0 동시 전환 (fadingIn state 기반) **PASS**
- `[200, 300]` 범위 검증 `if (crossfadeMs < 200 || crossfadeMs > 300)` **PASS** (clamp 금지)
- 범위 밖 → `onError('invalid_crossfade_ms')` + 전환 건너뛰기 `return` **PASS**
- `transition: opacity ${storeCrossfadeMs}ms ease-in-out` **PASS** (Q-3 ease-in-out)

### §8.2.2 숨쉬기
- `@keyframes saessagi-breathe`: scaleY 1.0→1.02→1.0, 2s, ease-in-out, infinite **PASS**
- 컨테이너(`breatheStyle`) 적용으로 emotion·speaking과 독립 **PASS**
- transform-origin center center **PASS**

### §8.2.3 깜빡임
- `Math.random() * 5000 + 5000` = 5~10 s 랜덤 **PASS**
- opacity 1 → 0.6 (75 ms 후) → 1 = 150 ms 왕복 **PASS**
- unmount useEffect cleanup에서 `clearTimeout` **PASS**

### §8.2.4 말하기 펄스
- `@keyframes saessagi-speaking-opacity` 1.0↔0.85, 200 ms infinite **PASS**
- `@keyframes saessagi-speaking-shake` rotate ±0.5°, 400 ms infinite **PASS**
- speaking=false 시 overlay의 `animation` 속성이 사라지고 `opacity:1 / transform:'rotate(0deg)'` 인라인 복원 → CSS animation 해제 즉시 원위치 **PASS**
- transform-origin center center **PASS**

### §8.2.5 study 감정
- study emotion 수신 시 `study.png` 렌더 (VALID_EMOTIONS 포함) **PASS**
- speaking=true일 때도 overlay animation이 전체 이미지에 적용 **PASS**

### §8.3 에러·누락 정책
| 상황 | 구현 | 판정 |
|---|---|---|
| 8종 외 emotion → neutral + onError(invalid_emotion) + console.warn 1회 | `resolveEmotion` (L82~L92) | PASS |
| 특정 PNG 실패 → neutral 2차 폴백 + onError(asset_missing) | `resolveAsset` (L95~L106) | PASS |
| neutral 실패 → 투명 1px placeholder + onError(mount_failed) + toast | toast·mount_failed emit PASS, **placeholder 렌더링은 리렌더 트리거 부재로 실제 표시 안 될 수 있음** | 부분 FAIL |
| mount 전 setEmotion → 버퍼링 후 immediate 적용 | `pendingEmotion` + preload.then 내 `applyEmotion(..., true)` | PASS |

## 3. 결함 목록

### [CRITICAL] — 0건

### [MAJOR] — 2건

1. **[MAJOR] neutral조차 실패 시 placeholder 리렌더 누락**
   - 파일: `src/renderer/src/components/avatar/SpriteAvatarRenderer.tsx:132-140, 320-331`
   - 결함: `allFailedRef.current = true` 설정은 useRef 쓰기이므로 리렌더를 트리거하지 않음. preload 완료 후 pendingEmotion가 없으면 setLayerA/setLayerB가 호출되지 않아 state update가 전혀 발생하지 않음 → 렌더 함수의 `if (allFailedRef.current)` 체크가 **다시 실행되지 않음** → 사용자는 broken image 아이콘을 본다.
   - 스펙 §8.3 "neutral조차 실패 → 투명 1px placeholder + 에러 토스트 '아바타 로딩 실패'"의 placeholder 표시 보장 실패.
   - 권고 조치: `allFailedRef`를 `useState`로 변경하거나, preload.then에서 강제 리렌더용 더미 state update 추가. 테스트에 DOM `<img[width="1"]>` assertion 추가.

2. **[MAJOR] WS `avatar-state` 수신 시 crossfade_ms 범위 검증 부재 (store 오염)**
   - 파일: `src/renderer/src/services/websocket-handler.tsx:290`
   - 결함: `const crossfadeMs = message.crossfade_ms ?? 250;` — 범위 [200, 300] 밖 값도 그대로 store에 저장됨. SpriteAvatarRenderer가 해당 값으로 applyEmotion을 호출해 에러만 내고 전환은 스킵하지만, store의 `crossfadeMs`는 잘못된 값으로 계속 남아 CSS `transition: opacity 150ms`와 같이 반영되어 **숨쉬기·후속 전환의 duration이 오염**된다.
   - 스펙 §7.2 "crossfade_ms 범위 밖(< 200 or > 300)이면 에러 로깅 후 **무시**"의 "무시" 의미 위반.
   - 권고 조치: WS 핸들러에서 범위 검증을 1차로 수행하고, 범위 밖이면 `console.warn` 후 store 갱신을 생략(또는 speaking/emotion만 갱신하고 crossfade_ms는 이전값 유지).

### [MINOR] — 4건

1. **[MINOR] §13.1 N-1 기대 URL `/assets/character/saessagi/happy.png` vs 구현 `/character/saessagi/happy.png` 경로 표기 불일치**
   - 파일: `src/renderer/src/components/avatar/SpriteAvatarRenderer.tsx:23`
   - Vite `public/` 자동 서빙 관례상 기술적으로는 맞지만, 스펙 §8.1/§13.1에 `assets/` prefix가 명시되어 있음. E2E·단위 테스트 assertion이 스펙 문자열과 다를 경우 향후 Critic이 혼선.
   - 권고 조치: 스펙 §8.1 경로 표기를 "Vite public 루트" 관례에 맞춰 `/character/saessagi/`로 갱신하거나, 빌드 시 rewrite rule 추가. 어느 쪽이든 스펙·구현 단일화 필요.

2. **[MINOR] handle.setSpeaking(on) 호출이 zustand store와 내부 speakingState 불일치 유발**
   - 파일: `src/renderer/src/components/avatar/SpriteAvatarRenderer.tsx:299-301`
   - handle.setSpeaking(false)는 `setSpeakingState(false)`만 호출하고 `useAvatarStore.setState({speaking:false})`는 하지 않음. 이후 WS가 같은 true를 반복 전송하면 store useEffect가 `storeSpeaking`(true) 변경 없음으로 판단해 무시 → overlay가 복원된 채 유지. 실제 사용자 경로는 store 경유이므로 발생 가능성 낮으나 스펙 §5.1 AvatarRenderer 독립 호출 계약 위반 가능.
   - 권고 조치: handle.setSpeaking에서 `useAvatarStore.setState({speaking: on})`을 함께 호출하거나 내부 state를 store로 통일.

3. **[MINOR] dispose() 후 store 구독 해제 부재**
   - 파일: `src/renderer/src/components/avatar/SpriteAvatarRenderer.tsx:309-312`
   - `dispose()`는 blinkTimer·errorListeners만 정리. zustand store useEffect 구독은 React unmount 시 자동 해제되지만, dispose만 호출하고 컴포넌트는 살아 있는 경우 state update가 계속 발생. 스펙 §5.1 "이후 호출은 모두 no-op"는 handle 메서드 한정이라는 해석도 가능하지만 명확치 않음.
   - 권고 조치: dispose에 플래그 추가해 이후 setLayerA/B 호출 차단.

4. **[MINOR] crossfade 중 같은 레이어에 덮어쓰기 경쟁 상태**
   - 파일: `src/renderer/src/components/avatar/SpriteAvatarRenderer.tsx:218-253`
   - 진행 중인 setTimeout 만료 전에 새 setEmotion이 오면 비활성 레이어를 덮어써서 시각적 플리커 가능. 스펙 §8.2.1 명시는 없으나 방어적 설계 부재.
   - 권고 조치: fadingIn이 true일 때 새 호출을 대기열에 넣거나 진행 중 타이머를 clearTimeout.

## 4. 스펙 vs 구현 매핑

| 스펙 항목 | 구현 위치 | 상태 |
|---|---|---|
| §5.1 Emotion 8종 Literal | `components/avatar/types.ts:3-11`, `store/avatar-store.ts:3-11` | OK (중복 정의 2곳 존재) |
| §5.1 preload() | `SpriteAvatarRenderer.tsx:302-304` + handle exposure | OK |
| §5.1 setEmotion(emotion, crossfadeMs) | L290-298 | OK |
| §5.1 setSpeaking(on) | L299-301 | OK |
| §5.1 onError(cb): unsubscribe | L305-308 | OK |
| §5.1 dispose() | L309-312 | 부분 (구독 해제 안 함 — MINOR #3) |
| §5.1 mount() | **구현 없음** (React JSX 자동 마운트 설계) | 설계 변경 선언됨 (L2~L5 주석) |
| §7.2 avatar-state 2차 방어 | `websocket-handler.tsx:286-293` | 부분 (crossfade_ms 검증 누락 — MAJOR #2) |
| §8.1 8종 PNG preload | `SpriteAvatarRenderer.tsx:111-143` | OK |
| §8.2.1 crossfade [200, 300] 범위 검증 | L232-237 | OK |
| §8.2.2 breathe animation | L155-159 | OK |
| §8.2.3 blink 5~10s 랜덤, 150ms 왕복 | L190-205 | OK |
| §8.2.4 speaking opacity·shake | L160-170, L343-358 | OK |
| §8.3 neutral 실패 → placeholder | L320-331 | 부분 (리렌더 트리거 없음 — MAJOR #1) |
| §8.3 mount 전 버퍼링 | L272-278, L258-267 | OK |

## 5. 테스트 커버 검증

| 스펙 테스트 케이스 | 구현된 테스트 | 상태 |
|---|---|---|
| N-1 mount 후 neutral 렌더 | TC-01 | OK |
| N-1 setEmotion('happy',250) | TC-02 | OK |
| N-2 speaking 펄스 토글 | TC-05 | OK |
| E-1 invalid emotion | TC-03 | OK |
| E-2 crossfade_ms 범위 밖 | TC-04 (150), TC-06 (300 경계) | OK |
| mount 전 버퍼링 | TC-07 | OK |
| dispose 후 unmount 안전 | TC-08 | OK |
| all assets failed → toast | TC-09 | 부분 (placeholder DOM 검증 없음) |
| 적대적 (A-1 악성 JSON, A-4 CSP 위반 등) | **없음** | 스코프 외 (§13.3은 M_12 전체 DoD, P2 한정 아님) |

- 정상 ≥5: TC-01/02/03/04/05 = 5건 OK (TC-03/04는 에러 경로지만 정상 API 호출 시 기대 동작이므로 "정상 케이스"로 계수 가능)
- 엣지 ≥5: TC-06/07/08/09 = 4건. **§15 DoD 기준 1건 부족하나 P2 세부 범위 이므로 M_12 전체 DoD 시점에 E2E·적대적 테스트 추가 예정**
- 적대적 ≥3: **현재 0건** (P2 scope는 핵심 렌더 로직, 적대적은 P5 E2E에서 다뤄질 것으로 추정)

## 6. 검토하지 못한 영역

- Electron production 빌드에서 `public/character/` 자산이 `resources/` 또는 dist로 실제 복사되는지 (scope P5).
- Windows 실기기에서 CSS animation GPU 가속 여부·FPS 실측 (scope P5).
- WSL + Windows Electron의 transparent window 렌더링 시 PNG 알파 블렌딩 정확성 (scope P3).
- 8종 PNG의 실제 해상도 일치 여부 (V1 스펙 §8.1은 검증 배제 명시).

## 7. 최종 판정

**FAIL — MAJOR 2건**

- 심각 결함 (CRITICAL): 0
- 중대 결함 (MAJOR): 2 (MAJOR #1 placeholder 리렌더 누락, MAJOR #2 WS crossfade_ms 검증 누락)
- 경미 결함 (MINOR): 4

### 권고 조치 우선순위
1. MAJOR #1 — `allFailedRef`를 `useState`로 전환하거나 preload.then에서 강제 리렌더. 테스트에 placeholder DOM assertion 추가.
2. MAJOR #2 — `websocket-handler.tsx`의 `avatar-state` 케이스에서 crossfade_ms 범위 [200, 300] 검증. 범위 밖이면 store 갱신 스킵 + console.warn.
3. MINOR #1 — 스펙 §8.1/§13.1 경로 표기 `/assets/` prefix 제거 또는 Vite publicDir 설정 조정. 스펙·구현 단일화.
4. MINOR #2~#4 — 후속 PR에서 함께 정리 가능.

### 통과 요건
위 MAJOR 2건 수정 + 해당 커버리지 테스트(placeholder DOM, WS 범위 검증) 각 1건 이상 추가 후 fresh Critic 재검수.

---

*검토 시각*: 2026-04-21
*검토자*: Critic (opus, fresh session)
*참조 문서*: `specs/M_12_Frontend_SPEC.md` §5.1·§8·§19.2, `specs/M_08_AvatarState_SPEC.md` §4.1·§6.3·§7, `docs/CHARACTER_SAESSAGI.md` L5~L53
