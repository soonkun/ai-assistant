# M_12 Frontend P3 Critic Review R2 (2026-04-21)

Fresh Critic R2 session. R1 FAIL 후 수정본 재검수. 앵커링 편향 방지를 위해 스펙·코드를 처음 보는 관점으로 재검토.

## 1. 독립 검증 결과

| 명령 | 결과 |
|---|---|
| `grep 'pet-mode:\|pet:'` (main+preload) | `pet-mode:` 잔존 **0건**. `pet:` 7종 (`enable/disable/setClickThrough/setAlwaysOnTop/dragStart/dragMove/dragEnd`) 확인 |
| `grep clientX\|nativeEvent.offset` (PetDragHandle) | `e.clientX, e.clientY` 사용. `nativeEvent.offset*` **0건** |
| `grep isBool\|isFiniteNumber\|throw new Error` (main/index.ts) | 4개 핸들러 (setClickThrough·setAlwaysOnTop·dragStart·dragMove) 모두 검증 + `throw new Error` |
| `grep clampToVirtualScreen` | `pet-ipc-validators.ts`에 정의. `pet:enable` 복원 setTimeout 콜백에서 `currentDisplayBounds()`와 함께 호출, null 시 `logger.warn` + 복원 skip |
| 스펙 §5.2 `dragMove`·`dragEnd` | spec L202~L207에 추가됨. L210에 P3 확장 근거(Q-9 B안) 주석 |
| 스펙 §9.4 채널 목록 | L404에 7종 명시 |
| payload 키 `{x, y}` 정합 | preload L25·d.ts L29·wrapper pet-mode.ts L7~L11·PetDragHandle L52 모두 일관 |
| `e.preventDefault()` | PetDragHandle L46 추가 |
| `logger.warn` (dragMove without dragStart) | main/index.ts L192 `[PetMode] dragMove called without dragStart; no-op` |
| tsc.node.json | exit 0 |
| tsc.web.json | exit 0 |
| ESLint | 0 errors |
| vitest 전체 | **33/33 PASS** (pet-ipc-validators 11 + pet-window-persistence 6 + validators 7 + SpriteAvatarRenderer 9) |
| 외부 네트워크 호출 신규 | 없음 (grep 0 matches) |
| pdf.js / playwright | 없음 (grep 0 matches) |
| window-manager 보안 | `sandbox: true, contextIsolation: true, nodeIntegration: false` 유지 |

## 2. R1 결함별 해소 여부

| # | 결함 | 해소 근거 | 상태 |
|---|---|---|---|
| MAJOR-1 | mousedown이 `offsetX/Y`(20x20 핸들 상대좌표) 전달 → 창 점프 | `PetDragHandle.tsx` L52 `petMode.dragStart({ x: e.clientX, y: e.clientY })`. clientX/Y는 창 viewport 기준이므로 main에서 `screenX - clientX = win.screenX` 로 정확히 원래 창 위치 유지 | ✅ 해소 |
| MAJOR-2 | IPC 핸들러 입력값 검증 0건 | `pet-ipc-validators.ts`에 `isBool`·`isFiniteNumber` 추가. main/index.ts L138/L154/L165/L181 네 핸들러 모두 실패 시 `logger.warn` + `throw new Error(...)` → renderer에 reject 전파 | ✅ 해소 |
| MAJOR-3 | 채널명 `pet-mode:*` 스펙 §9.4 위반 | main+preload 모두 `pet:` 7종으로 통일. grep 확인 결과 `pet-mode:` 잔존 0건 | ✅ 해소 |
| MAJOR-4 | 저장 (x,y)가 현재 virtual screen 밖이면 창 실종 | `clampToVirtualScreen(x, y, displays)` 정의. `pet:enable` 복원 콜백(L115~L128)이 `currentDisplayBounds()` 실시간 조회 후 clamp. null이면 warn + 복원 skip → 디폴트 위치로 표시 | ✅ 해소 |
| MAJOR-5 | `dragMove`·`dragEnd`가 스펙 §5.2 미존재 (CR 없이 추가) | spec L202~L207에 dragMove/dragEnd 추가 + L210 P3 확장 근거 주석(Q-9 B안). §9.4 L404에 7종 1:1 매핑 명시 | ✅ 해소 |
| MINOR-1 | dragStart payload 키 `{offsetX,offsetY}` vs 스펙 `{x,y}` | 전 계층 `{x, y}` 통일 (PetDragHandle·preload·d.ts·wrapper·main) | ✅ 해소 |
| MINOR-4 | dragMove without dragStart silently return | main L191~L194 `logger.warn('[PetMode] dragMove called without dragStart; no-op')` | ✅ 해소 |
| MINOR-6 | mousedown에서 preventDefault 미호출 | PetDragHandle L46 `e.preventDefault()` | ✅ 해소 |

## 3. 신규 결함 탐색

### 3.1 CRITICAL — 없음

### 3.2 MAJOR — 없음

### 3.3 MINOR 후보 (참고용)

- **[MINOR-R2-1]** `clampToVirtualScreen`의 maxX/maxY 여유치 100px은 스펙 §10.3에 명시되지 않은 매직 넘버. 주석으로 정책(창 일부만 보여도 드래그 복구 가능)은 설명돼 있지만 스펙 부재. 다만 합리적 디폴트이고 테스트로 동작 고정됨. 보완 권고: 스펙 §10.3에 "저장 위치 복원 시 virtual screen 범위 밖 100px 마진 이상 이탈은 디폴트 폴백" 문장 추가.
- **[MINOR-R2-2]** `PetDragHandle.tsx` L39 `petMode.dragMove(...).catch(() => {})` — 주석("IPC 실패는 무시")은 있으나 완전 침묵. 장시간 drag 중 연속 실패가 있어도 사용자는 원인 불명. 다만 throttle 16ms × 드래그 시간 이므로 콘솔 노이즈 회피가 더 큰 우선순위. 수용 가능.
- **[MINOR-R2-3]** `throttle` 유틸이 trailing edge fire를 수행하지 않아, 드래그 종료 직전 마지막 mousemove가 누락될 수 있음. 다만 mouseup → `dragEnd`에서 `win.getBounds()`로 실제 최종 위치를 영속화하므로 저장 값에는 영향 없음. UX상 1프레임 지연 정도로 무시 가능.

### 3.4 검토한 신규 엣지
- **duplicate dragStart**: mousedown이 2회 연속 호출되면 `dragOffset`이 최신값으로 덮어써짐 — 이는 정상 동작 (멀티 mousedown은 Electron에서 드물지만 덮어쓰기가 올바름).
- **dragEnd without dragStart**: main L204 `pet:dragEnd` 핸들러는 `dragOffset = null` + `savePetWindowState`만 수행. `dragOffset`이 이미 null이어도 안전.
- **window 없음 상황**: `pet:setClickThrough`·`pet:setAlwaysOnTop`·`pet:dragMove`·`pet:dragEnd` 모두 `if (!win) return` 가드 존재.
- **topology 변경 + 저장값 남음**: TC-V6 테스트가 "저장된 듀얼 모니터 좌표(3000,500) → 단일 모니터만 연결" 케이스를 커버 → null 반환 → warn + skip → 창은 디폴트 중앙 span에서 시작.

## 4. 최종 판정

**PASS.**

- MAJOR 5건 모두 해소 (파일·라인 레벨에서 확인).
- MINOR 3건 모두 해소.
- 신규 CRITICAL·MAJOR **0건**. MINOR 후보 3건은 모두 정책 보완 성격.
- 품질 게이트 tsc(node+web)·eslint·vitest 모두 녹색.
- 테스트 33/33 PASS (pet-ipc-validators 11 신규 포함).
- 스펙-구현 정합 (§5.2 PetModeApi 7종, §9.4 채널 7종 1:1).
- 외부 네트워크·보안 설정 위반 없음.

### 검토하지 못한 영역 (다음 단계 고려)
- 실기기 Electron 30.x에서 `setIgnoreMouseEvents(true, {forward:true})` + mousedown 드래그 실제 동작 확인 (E2E 단계).
- 고DPI 멀티 모니터에서 `e.clientX`가 논리 픽셀 vs 물리 픽셀 어느 쪽인지 확인 (Electron은 논리 픽셀 기준이므로 `screen.screenX`와 단위 일치, 정합할 것으로 판단).
