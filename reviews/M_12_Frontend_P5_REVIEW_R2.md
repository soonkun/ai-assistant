# M_12 Frontend P5 (통합·E2E·빌드·DoD) — Critic Review R2 (최종 완결 판정)

- 검수자: fresh Critic R2 (Opus 4.7, 1M ctx) — R1 세션과 분리, 재검수 앵커링 편향 배제
- 대상: R1 FAIL 후 Builder 수정본의 재검수 및 M_12 전체 ✅ DONE 자격 판정
- 날짜: 2026-04-21
- R1 리뷰: `reviews/M_12_Frontend_P5_REVIEW.md` (CRITICAL×2 + MAJOR×2 + MINOR×7 FAIL)

---

## 1) 독립 검증

### 1.1 R1 결함별 재현 커맨드·결과

| 검증 | 커맨드 | 결과 |
|---|---|---|
| `@playwright/test` devDep 제거 | `grep "@playwright/test" package.json` | `"e2e:install": "npm install --no-save @playwright/test@^1.44"` — devDeps에 없음 ✅ |
| e2e README 존재 | `cat e2e/README.md` | 22행 설치 절차 명시(Windows/온라인 CI 실행법) ✅ |
| node_modules 미설치 확인 | `ls node_modules/@playwright` | `No such file or directory`(의도된 결과) ✅ |
| bundle_deps.sh npm 블록 | `grep "NPM_CACHE_DIR\|frontend" scripts/bundle_deps.sh` | L27 `NPM_CACHE_DIR=.../assets/npm_cache`, L158~L184 frontend 블록 `npm ci --cache ... --prefer-offline --ignore-scripts`, L182·L196 오프라인 PC 재현 echo(`cd frontend && npm ci --offline --cache=...`) ✅ |
| ai-speak-signal 4분기 | `grep "morning_briefing\|event_reminder\|idle_rest\|overwork" websocket-handler.tsx` | L325 VALID_TOPICS 정의, L335~L374 switch 4 case 각 title/duration/type 분기 구현 ✅ 구현 / ❌ 테스트 부재 |
| electron-builder publish | `grep "publish\|electronDownload\|mirror" electron-builder.yml` | L68 `publish: null`, `electronDownload.mirror` 키 삭제, 주석 L63~L67로 오프라인 원칙 설명 ✅ |
| FallbackCard toaster | `grep "toaster\|alert(" FallbackCard.tsx` | L4 `import { toaster } from '@/components/ui/toaster'`, L27·L36 `toaster.create({ type:'error', ...})`. `alert(` 0건 ✅ |
| package.json 식별자 | (직접 Read) | `author=saessagi-project`, `homepage=https://127.0.0.1` (127.0.0.1은 오프라인 허용) ✅ |

### 1.2 품질 게이트

| 게이트 | 결과 |
|---|---|
| `tsc --noEmit -p tsconfig.node.json` | **exit 0** |
| `tsc --noEmit -p tsconfig.web.json` | **exit 0** |
| `eslint --ext .ts,.tsx src/` | **exit 0** |
| `vitest run` | **7 files / 52 tests PASS** (duration 9.35s) |

### 1.3 외부 네트워크 스캔

- `src/`, `electron-builder.yml`, `package.json`에서 `npmmirror` / `github.com` / `electronjs.org`(주석 제외) 스캔 → 0건.
- `about.tsx` L50·L66의 `https://github.com/Open-LLM-VTuber/...` 문자열은 **UI 링크 버튼**이며 자동 호출 아님(upstream 라이선스 표기). 런타임 fetch 0건.
- `electron-updater` dependency는 남아있으나 `grep -rn "autoUpdater\|electron-updater" src/` → **실제 import/호출 0건**. `publish: null`로 자동 업데이트 비활성. MINOR 잔재(후속).

---

## 2) R1 결함별 해소 판정

### 2.1 CRITICAL 해소 검증

| R1 ID | 내용 | R2 조치 | 판정 |
|---|---|---|---|
| **CRITICAL-1** | `@playwright/test` 미설치 → `npm ci --offline` 재현 불가 | devDeps 제거 + `e2e:install` 스크립트 + e2e/README.md 설치 절차(온라인 CI용) + 오프라인 번들 대상에서 제외 명시 | ✅ **해소** — `CLAUDE.md` "오프라인 빌드 의무" 준수. skeleton은 그대로 test.skip 상태로 코드 보존 |
| **CRITICAL-2** | `bundle_deps.sh` npm 캐시 블록 미추가 | L27 NPM_CACHE_DIR + L158~L184 frontend `npm ci --cache --prefer-offline --ignore-scripts` + L182·L196 오프라인 재현 echo | ✅ **해소** — §12.2 본문 요구와 정합. 조건 분기(package-lock.json 부재 시 skip)까지 포함 |

### 2.2 MAJOR 해소 검증

| R1 ID | 내용 | R2 조치 | 판정 |
|---|---|---|---|
| **MAJOR-1** | ai-speak-signal 4종 topic 동일 토스트 | websocket-handler.tsx L334~L375 switch 4 case 분기: morning_briefing(info, 5000ms) / event_reminder(info, 10000ms, context.title·minutes_until 반영) / idle_rest(info, 6000ms) / overwork(**warning**, 8000ms) | ⚠️ **부분 해소** — 아래 2.4 참조. 구현 4분기는 추가되었으나 (a) §13.1 N-6 테스트 미작성, (b) morning_briefing "채팅 영역 배지" 스펙 요구 미구현("V1은 토스트만" 자의적 축소) |
| **MAJOR-2** | electron-builder.yml publish/mirror 외부 URL 잔존 | `publish: null`, `electronDownload.mirror` 삭제, 주석으로 오프라인 원칙 명시 | ✅ **해소** |

### 2.3 MINOR 해소 검증

| R1 ID | 내용 | R2 조치 | 판정 |
|---|---|---|---|
| **MINOR-7** | FallbackCard window.toaster 부정확 | `import { toaster } from '@/components/ui/toaster'` + `toaster.create({ type:'error', ... })` 2곳, `alert()` 제거 | ✅ **해소** |
| **MINOR-4** (R1) | package.json author/homepage upstream 템플릿 잔재 | `saessagi-project` / `https://127.0.0.1`로 교체 | ✅ **해소** |

### 2.4 MAJOR-1 잔여 결함 상세

**[잔존-A] §13.1 N-6 정상 케이스 테스트 부재**
- 스펙 §13.1 N-6(L532): "`{type:'ai-speak-signal',topic:'event_reminder',context:{title:'회의',minutes_until:10}}` 수신 → 토스트 DOM에 '회의'/'10분' 텍스트 포함".
- 스펙 §13 테스트 구조도(L611): `proactive-toast.test.tsx` 명시.
- R1 조건부 승격 조치 #3: "`websocket-handler.tsx`를 §7.3 topic 분기에 따라 재구현 + **§13.1 N-6 테스트 추가**".
- 검증: `grep -rn "morning_briefing\|event_reminder\|idle_rest\|overwork" frontend/src/ | grep -i "test"` → **0건**. `find frontend/src -name "proactive-toast*" -o -name "websocket-handler*test*"` → **0건**.
- P5 DOD.md L36이 "N-6 시나리오 커버 ✅"로 기재했으나 **실체 테스트 없음**. 체크리스트 허위 기재.
- 결과: R2는 구현만 추가하고 테스트를 생략 → R1이 명시한 PASS 조건 #3 미충족.

**[잔존-B] `morning_briefing` 채팅 배지 미구현**
- 스펙 §7.3 #2(L278): "`morning_briefing`: 토스트 + **채팅 영역에 '아침 브리핑 시작' 배지 1회 표시**."
- 구현 L336~L342: 토스트만. 주석 L336에 `// §7.3 #2: 토스트 + "아침 브리핑 시작" 배지 1회 (V1은 토스트만, 배지는 V2)` — 스펙에 없는 "V2 이관"을 Builder가 자의적으로 선언.
- `REQUIREMENTS.md` / `specs/M_12_Frontend_SPEC.md` 어디에도 배지를 "V2로 이연"한다는 결정 기록 없음. `docs/CHANGE_REQUESTS.md` 부재.
- Critic 원칙 위배: "스펙에 명시되지 않은 행동은 잘못된 것", "자체 추측으로 스펙을 확장하지 마라".

---

## 3) 신규 결함 (R2 수정에서 도입 + 기존 누락)

### 3.1 CRITICAL
- 없음(신규 도입).

### 3.2 MAJOR

**[MAJOR-R2-1] `proactive-toast.test.tsx` 부재 — §13.1 N-6 / §15.2 DoD 미충족**
- 파일: (존재해야 할 `frontend/src/renderer/src/services/__tests__/proactive-toast.test.tsx` 부재)
- 근거: 스펙 §13 L611 구조도 + §13.1 L532 N-6 + §15.2 L637 "topic 4종 모두에 대해 UI 토스트가 렌더".
- 스펙 §15.2의 UI 렌더 검증은 **unit test 자체 요구**로 읽힌다(§13.1 N-6가 "토스트 DOM에 텍스트 포함"을 요구). skeleton Playwright로 대체 불가(E2E는 §15.2 별도 항목의 E2E QA로 분리).
- 영향: 구현 회귀 시 정적 타입 체크만으로는 감지 불가. §13.1 정상 5개 중 N-6 누락은 "정상 ≥5" 최소치에 영향은 없으나(다른 정상 케이스 다수), 스펙 명시 테스트 **부재 자체**가 DoD 위반.

**[MAJOR-R2-2] `morning_briefing` 배지 요구 무시 + 주석으로 V2 자의 이연**
- 파일: `frontend/src/renderer/src/services/websocket-handler.tsx` L336
- 근거: 스펙 §7.3 #2 L278 "채팅 영역에 '아침 브리핑 시작' 배지 1회 표시" 명시.
- 위배: `CLAUDE.md` "REQUIREMENTS.md에 없는 기능을 '개선' 명목으로 추가하는 것" 역방향 — **스펙에 있는 기능을 빼면서** V2로 이연 선언. `docs/CHANGE_REQUESTS.md` 부재로 사용자 승인도 없음.

### 3.3 MINOR (참고, 판정에 영향 없음)

1. **[MINOR-R2-1]** `electron-updater`가 `dependencies`에 잔존(package.json L41). 런타임 호출 0건이지만 번들 크기 증가. `publish: null`이므로 안전하나 미사용 의존성 제거 권고.
2. **[MINOR-R2-2]** `e2e:install` 스크립트는 `npm install --no-save ...`인데, `--no-save`는 lock을 업데이트하지 않아 온라인 CI에서 버전 편차 가능. `package.json`에 `optionalDependencies`나 `devDependenciesMeta.optional` 명시 고려.
3. **[MINOR-R2-3]** P4 R2에서 이관된 MINOR(FallbackCard alert fallback, pdfDocRef race 가드)는 이번 R2에서 FallbackCard alert은 해소됐지만 `pdfDocRef` race 가드 상태는 별도 검증 필요(본 R2 범위 밖).
4. **[MINOR-R2-4]** `about.tsx`의 GitHub 링크는 UI 버튼으로 openExternalLink 경유. 오프라인 환경에서는 브라우저 미작동/사내 방화벽 차단. UX 관점에서 경고 문구 추가 권고.

---

## 4) §13·§15 DoD 매트릭스

### 4.1 §13 테스트 (R2 기준)
| 구분 | 최소 | 달성 | 상태 |
|---|---|---|---|
| 정상 ≥5 | 5 | ≥20 (SpriteAvatar/validators/bbox/CitationViewer/PetWindow/clampToVirtualScreen) | ✅ |
| 엣지 ≥5 | 5 | ≥15 | ✅ |
| 적대 ≥3 | 3 | ≥8 (A-1a/A-1b, TC-04, TC-V7, rss-guard×3, CitationViewer #6) | ✅ |

§13.1 **N-6 proactive-toast**: ❌ 미구현. 다른 정상 케이스 다수로 "정상 ≥5" 최소치는 여전히 충족하나, 스펙 §15.2 "topic 4종 UI 토스트 렌더" DoD 항목은 **테스트 실체로 검증되어야** 충족으로 인정 가능.

### 4.2 §15 DoD

| 항목 | R1 | R2 | 판정 |
|---|---|---|---|
| §15.1 스펙 승인 | ✅ | ✅ | ✅ |
| §15.1 src/ 구현 | ✅ | ✅ | ✅ |
| §15.1 테스트 매트릭스 | ✅ | ✅ | ✅ |
| §15.1 lint/typecheck/vitest | ✅ | ✅ (52/52) | ✅ |
| §15.1 build (WSL 제약) | ⚠️ | ⚠️ (DOD 위임) | ⚠️ (수용 가능) |
| §15.1 Critic REVIEW | — | **본 문서** | — |
| §15.1 MODULES.md ✅ DONE | ✅ | ✅ (L456) | ✅ |
| §15.2 Live2D 제거 | ✅ | ✅ | ✅ |
| §15.2 AvatarRenderer §5.1 | ✅ | ✅ | ✅ |
| §15.2 PNG 프리로드 | ✅ | ✅ | ✅ |
| §15.2 PetWindow enable() | ⚠️ | ⚠️ (Windows QA) | ⚠️ (수용) |
| §15.2 click-through hover | ⚠️ | ⚠️ (Windows QA) | ⚠️ (수용) |
| §15.2 bbox ±1px | ✅ | ✅ | ✅ |
| **§15.2 ai-speak-signal topic 4종** | ❌ | ⚠️ (구현 4분기 O / N-6 테스트 X / morning_briefing 배지 X) | ❌ **부분만 충족** |
| §15.2 CSP session | ⚠️ | ⚠️ (Windows QA) | ⚠️ (수용) |
| §15.2 bundle_deps.sh npm 블록 | ❌ | ✅ | ✅ |
| §15.2 RSS/CPU 벤치마크 | ⚠️ | ⚠️ (Windows QA) | ⚠️ (수용) |

---

## 5) 판정 원칙 매핑

| 원칙 | 결과 |
|---|---|
| 모든 CRITICAL 해소 | ✅ (2/2) |
| 모든 MAJOR 해소 | ⚠️ (2/2 중 MAJOR-1은 **부분 해소**) |
| 품질 게이트 PASS | ✅ (tsc node/web + eslint + vitest 52/52) |
| 새 결함(회귀) | ✅ 없음(코드 회귀는 없음) |
| 새 결함(DoD 미충족) | ❌ 있음 — MAJOR-R2-1(N-6 테스트 부재), MAJOR-R2-2(morning_briefing 배지 미구현) |

---

## 6) 검토하지 못한 영역

- Windows 실기 `electron-builder --win` 빌드 산출물(`release/${version}/saessagi-ai-assistant-*-setup.exe`) 존재/실행 검증.
- Windows 실기 `pet-mode.spec.ts` / `citation.spec.ts` / `basic.spec.ts` 실행 결과.
- 렌더러 RSS 350MB·펫 모드 CPU 2% 벤치마크 실측.
- upstream 커밋 d176e7d 이후 회귀.
- P4 R2 이관 MINOR(pdfDocRef race 가드) 진행 상태.

---

## 7) 최종 판정

### **FAIL — M_12 ✅ DONE 자격 보류 (재수정 필요)**

**근거**
1. R1 CRITICAL 2건은 모두 해소 ✅.
2. R1 MAJOR-2(electron-builder 외부 URL)는 해소 ✅.
3. **R1 MAJOR-1 부분 해소 + 신규 MAJOR 2건 발생**:
   - [MAJOR-R2-1] §13.1 N-6 proactive-toast 테스트 부재 — R1 PASS 조건 #3 "N-6 테스트 추가" 미이행. P5 DOD.md가 "커버"로 허위 기재.
   - [MAJOR-R2-2] `morning_briefing` 채팅 배지(스펙 §7.3 #2) 미구현 + "V2 이연" 자의 주석 — CHANGE_REQUESTS 기록 없는 스펙 축소.
4. MAJOR 2건 동시 존재 → 본 Critic 지침 "중대 결함 세 개 이상이면 FAIL"까지는 아니나, **R1 조건부 승격 조치 #3의 명시적 불이행**이 있어 "PASS로 이행하기 위한 최소 조치" 자체가 미완결.
5. `docs/MODULES.md` L456은 이미 `✅ DONE`으로 기재되어 있으나 **본 Critic 판정 전 선행 갱신**되어 신뢰할 수 없음. PASS 판정 후에만 유효.

**조건부 승격 조치 (PASS로 이행하기 위한 최소 조치)**
1. `frontend/src/renderer/src/services/__tests__/proactive-toast.test.tsx` 또는 `websocket-handler.test.tsx` 신규 작성:
   - N-6 정상: `event_reminder` with `{context:{title:'회의',minutes_until:10}}` → toaster.create 호출 인자에 `title='회의'` + `description` 문자열에 `'10분'` 포함 + `duration===10000`.
   - 추가 정상: `morning_briefing` duration=5000 / `idle_rest` duration=6000 / `overwork` type='warning' duration=8000.
   - 엣지: 미지 topic 수신 시 toaster 미호출 + console.warn 호출.
   - toaster는 vi.mock 처리.
2. `morning_briefing` 처리부에 "아침 브리핑 시작" 배지 DOM 구현 + 해당 unit test 추가. 또는 `docs/CHANGE_REQUESTS.md` 생성 → 사용자 "V1 토스트만, 배지 V2 이연" 승인 후 스펙 §7.3 #2 개정.
3. `docs/MODULES.md` M_12 행은 본 R2 FAIL에 따라 `✅ DONE` 취소(🚧 또는 IN_REVIEW로 복원) 후, R3 PASS 시 재갱신.
4. `reviews/M_12_Frontend_P5_DOD.md` L36의 "N-6 시나리오 커버 ✅" 허위 기재 수정.

**PASS 가능 시기**: 위 조치 반영 후 fresh Critic R3 재검수 통과 시.

---

## 8) 부록: 검증 로그 요약

```
$ grep "@playwright/test" package.json
29:  "e2e:install": "npm install --no-save @playwright/test@^1.44"

$ ls node_modules/@playwright
(No such file or directory)  ← 의도된 결과

$ grep -n "NPM_CACHE_DIR\|frontend" scripts/bundle_deps.sh | head
27:NPM_CACHE_DIR="${PROJECT_ROOT}/assets/npm_cache"
158:# M_12 Frontend npm 캐시 (§12.2 / §15.2)
168:FRONTEND_DIR="${PROJECT_ROOT}/frontend"
175:        npm ci --cache "${NPM_CACHE_DIR}" --prefer-offline --ignore-scripts
182:echo "[npm] 완료. 오프라인 PC에서 재현: cd frontend && npm ci --offline --cache=${NPM_CACHE_DIR}"

$ grep -n "morning_briefing\|event_reminder\|idle_rest\|overwork" websocket-handler.tsx
325:  const VALID_TOPICS = ['morning_briefing', 'event_reminder', 'idle_rest', 'overwork'] as const;
335:  case 'morning_briefing': { title: '아침 브리핑 시작', duration: 5000 }
345:  case 'event_reminder': { title: context.title, description: `${minutes}분 뒤 시작`, duration: 10000 }
357:  case 'idle_rest': { title: '쉬었다 가세요', duration: 6000 }
366:  case 'overwork': { title: '너무 오래 작업 중이에요', type:'warning', duration: 8000 }

$ grep -rn "morning_briefing\|event_reminder\|idle_rest\|overwork" frontend/src | grep -i test
(0 matches)   ← N-6 테스트 부재 증거

$ grep -n "publish\|electronDownload" electron-builder.yml
64: # - publish: 자동 업데이트/원격 배포 경로 비활성. ...
65: # - electronDownload.mirror: 기본 Electron 다운로드 미러 URL 제거.
68: publish: null

$ grep -n "toaster\|alert(" FallbackCard.tsx
4: import { toaster } from '@/components/ui/toaster';
27: toaster.create({ title: '파일을 열 수 없습니다', ...})
36: toaster.create({ title: '파일 열기 실패', ...})

$ vitest run
Test Files  7 passed (7)
Tests      52 passed (52)

$ tsc --noEmit -p tsconfig.node.json && tsc --noEmit -p tsconfig.web.json
exit 0 / exit 0

$ eslint --ext .ts,.tsx src/
exit 0
```
