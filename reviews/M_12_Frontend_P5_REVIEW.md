# M_12 Frontend P5 (통합·E2E·빌드·DoD) — Critic Review (적대적, M_12 최종 완결 판정)

- 검수자: fresh Critic (Opus 4.7, 1M ctx) — Builder/Validator/기존 Critic 컨텍스트 무관
- 대상: P5 통합 산출물 및 M_12 전체의 §15 DoD 완결 여부
- 날짜: 2026-04-21
- 이전 리뷰: `reviews/M_12_Frontend_P{1,2,3,4}_REVIEW*.md` (P1~P4 각 R2 PASS)

---

## 1) 독립 검증

### 1.1 품질 게이트
| 게이트 | 결과 |
|---|---|
| `tsc --noEmit -p tsconfig.node.json` | exit 0 |
| `tsc --noEmit -p tsconfig.web.json` | exit 0 |
| `eslint src/` | exit 0 |
| `eslint e2e/` | exit 0 (단, 현 프로젝트 `.eslintrc.js`가 `react-recommended`만 사용해 TS 해결 오류를 린트에서 보지 않음) |
| `vitest run` | **52 tests / 7 files PASS** (3.16s) |
| `npm run build` | **미실행** (WSL 환경 제약 — Electron packager 필요) |
| `npm run e2e` | **실행 불가** (Playwright 미설치·WSL 디스플레이 없음) |

### 1.2 변경 범위 (P5)
```
M docs/MODULES.md                                               (M_12 ✅ DONE 갱신)
M frontend/electron-builder.yml                                 (appId/productName/ko_KR/mac 주석)
M frontend/package.json                                         (@playwright/test devDep + e2e script)
M frontend/src/renderer/src/components/avatar/__tests__/validators.test.ts (A-1a/A-1b 추가)
M frontend/src/renderer/src/components/citation/CitationViewer.tsx        (rss-guard 통합)
M frontend/src/renderer/src/components/citation/__tests__/CitationViewer.test.tsx (#6 RSS)
M frontend/vitest.config.ts                                     (e2e/ exclude)
?? frontend/e2e/ (basic.spec.ts, pet-mode.spec.ts, citation.spec.ts, playwright.config.ts)
?? frontend/src/renderer/src/components/citation/rss-guard.ts   (RSS 감시)
?? frontend/src/renderer/src/components/citation/__tests__/rss-guard.test.ts (5건)
?? reviews/M_12_Frontend_P5_DOD.md
```

### 1.3 RSS 감시 통합 검증
- `rss-guard.ts` L6 `RSS_LIMIT_BYTES = 1.2 * 1024 * 1024 * 1024`(§13.3 A-2).
- `CitationViewer.tsx` L19 import, L101 `shouldAbortPdfRender(readRendererRSS())` 분기 + toaster error + 폴백 전환(L110 `setRenderError`).
- **스펙 §8.3.4와 정합**: "렌더러 RSS < 1.2GB 넘기면 뷰어를 **닫고** 에러 토스트".

### 1.4 MODULES.md
- L420·L456 모두 `✅ DONE`. 본문에 P1~P5 경로 명시.

---

## 2) §13 테스트 매트릭스 심사

### 2.1 카운트 (vitest 52건 중 해당)
| 구분 | 건수 | 대표 ID |
|---|---|---|
| 정상 | **≥ 20** | TC-01, TC-02, TC-05 (SpriteAvatar), TC-E1~E3, TC-C1, TC-C3 (validators), bbox #1 #2 #5 #6, CitationViewer #1 #2 #3 #4 #5, TC-P1 TC-P2 (pet-window), TC-V2 TC-V5 (clampToVirtualScreen) |
| 엣지 | **≥ 15** | TC-06 TC-07 TC-08 TC-09 (SpriteAvatar), TC-V1 TC-V3 TC-V4 TC-V6 (clampToVirtualScreen), bbox #3 #4, CitationViewer #5, TC-P3 TC-P4 TC-P5 TC-P6, rss-guard #3 #4 |
| 적대 | **≥ 8 (vitest) + 2 skeleton** | A-1a A-1b (validators XSS), TC-04 (crossfade 범위 밖), TC-V7 (NaN/Infinity), rss-guard #1 #2 #5, CitationViewer #6 (RSS 초과); playwright skeleton A-3 A-4 (test.skip) |

§13.1 정상 ≥5, §13.2 엣지 ≥5, §13.3 적대 ≥3 모두 **충족**.

### 2.2 §13.3 A-1~A-4 매핑
| ID | 스펙 기대 | 구현 위치 | 판정 |
|---|---|---|---|
| **A-1 악성 JSON(emotion/crossfade_ms)** | emotion 문자열 DOM 삽입 안 되고 neutral 폴백, crossfade_ms 비숫자는 무시 | `validators.ts` + `validators.test.ts` A-1a/A-1b + WS 핸들러(`websocket-handler.tsx` L285~L294에서 두 헬퍼 경유) | ✅ 완전 커버 |
| **A-2 100MB PDF RSS 1.2GB 초과** | 뷰어 자동 닫힘 + 에러 토스트 | `rss-guard.ts` + `CitationViewer.tsx` L101~L112 + `CitationViewer.test.tsx #6` | ✅ 유닛 테스트 커버(실PDF는 QA 위임) |
| **A-3 hit-region 우회(펫 모드)** | 합성 click 100회에도 button 미반응 | `pet-mode.spec.ts` test.skip skeleton | ⚠ skeleton — 현 시점 실행 불가 (Windows QA 위임 명시) |
| **A-4 CSP 위반 차단** | `new Image().src = https://evil...` 거부 로그 + 네트워크 0건 | `citation.spec.ts` test.skip + `index.html` CSP 메타 태그 | ⚠ skeleton + CSP 헤더 존재. 실행은 Windows CI |

A-1·A-2는 테스트 실체, A-3·A-4는 skeleton. §13.3 "적대 ≥3"은 실체만 세도 **≥3 충족**.

---

## 3) §15 DoD 심사

### 3.1 §15.1 공통
| 항목 | 상태 | 근거/비고 |
|---|---|---|
| 스펙 사용자 승인 (Q-1~Q-15) | ✅ | `specs/M_12_Frontend_SPEC.md` §19 결정 기록 |
| `frontend/src/`·`frontend/main/` 구현 | ✅ | SpriteAvatarRenderer, PetWindow, CitationViewer, rss-guard, WS 핸들러 |
| 테스트 매트릭스(정상≥5·엣지≥5·적대≥3) | ✅ | §2.1 참조 |
| `npm run lint` PASS | ✅ | exit 0 |
| `npm run typecheck` PASS | ✅ | node+web exit 0 |
| `npm run test` PASS | ✅ | 52/52 |
| `npm run build` | ⚠ | WSL 환경 제약. P5 DOD.md에 "Windows QA 위임" 기록됨 |
| `reviews/M_12_Frontend_REVIEW.md` PASS | ⚠ | P1~P4 R2 PASS 존재. 본 P5 리뷰(본 문서)로 M_12 전체 최종 판정 |
| `docs/MODULES.md` ✅ DONE | ✅ | L420·L456 갱신 |

### 3.2 §15.2 M_12 고유
| 항목 | 상태 | 비고 |
|---|---|---|
| upstream Live2D 의존 제거 (package.json에 pixi/live2d 없음) | ✅ | `dependencies` 블록 grep 결과 pixi/live2d 0건 |
| AvatarRenderer §5.1 정의 + SpriteAvatarRenderer 6종 메서드 | ✅ | P2 R2 PASS에서 실증 |
| 8종 PNG 프리로드 unit test | ✅ | SpriteAvatarRenderer TC-01 |
| PetWindowController.enable() 투명/frame=false/alwaysOnTop | ⚠ | WSL 제약, P5 DOD.md 위임 기록 |
| click-through hover + 드래그 B안 | ⚠ | 구현됨(`pet-ipc-validators.test.ts` TC-V1~V7 포함 11건), E2E 실기 검증은 Windows QA |
| CitationViewer bbox ±1px | ✅ | `CitationViewer.test.tsx #3` + `bbox.test.ts 6건` |
| ai-speak-signal topic 4종 UI 토스트 | ⚠ MAJOR | `websocket-handler.tsx` L322~L339: topic별 분기 **없음**. 단일 `프로액티브 [${topic}]` 3초 토스트. `event_reminder`의 context.title/10초 요구(§7.3 #2) 미충족. morning_briefing 배지 미구현. |
| CSP `index.html` + Electron session | ⚠ | HTML meta는 존재. Electron session 레벨 설정은 P5 DOD.md에 "citation.spec.ts Windows QA 위임" |
| `scripts/bundle_deps.sh` npm 캐시 블록 | ❌ CRITICAL | **미추가**. `scripts/bundle_deps.sh`에 "M_12"/"npm"/"NPM_CACHE_DIR" 0건. 스펙 §12.2·§15.2의 명시적 요구 |
| 렌더러 RSS 350MB·펫 모드 CPU 2% 벤치마크 | ⚠ | WSL 제약, P5 DOD.md 위임 |

---

## 4) 신규 결함

### 4.1 CRITICAL

**[CRITICAL-1] `@playwright/test`가 실제 설치되지 않음 — 오프라인 빌드 블로커**
- 파일: `frontend/package.json` L79, `frontend/node_modules/@playwright/` 부재
- 검증: `ls node_modules/@playwright` → `No such file or directory`. `grep -c "@playwright/test" package-lock.json` → `0`.
- 영향: `npm run e2e` 즉시 실패. `npm ci --offline` 재현 불가(lock에 해당 패키지 없음). Windows CI로 위임한다 해도, 캐시 없이 인터넷 필요 → `CLAUDE.md` 오프라인 빌드 의무 위배.
- 권고: (a) 인터넷 단말에서 `npm install @playwright/test@^1.44 --save-dev` → lock 재생성 → `assets/npm_cache` 수집, 또는 (b) `@playwright/test`를 devDep에서 제거하고 E2E skeleton을 별도 브랜치로 이동.

**[CRITICAL-2] `scripts/bundle_deps.sh` npm 캐시 블록 미추가 — §15.2 DoD 명시 요구 미충족**
- 파일: `scripts/bundle_deps.sh`
- 검증: `grep -c "M_12\|npm\|frontend" scripts/bundle_deps.sh` → `0`. `wc -l` = 160줄, 전부 기존 Python wheel/HF 모델 번들링만.
- 근거: `specs/M_12_Frontend_SPEC.md` §3.4, §12.2, §15.2 (마지막 세 번째 줄: "`scripts/bundle_deps.sh`에 npm 캐시 수집 블록이 추가되고, 오프라인 PC에서 `npm ci --offline` 재현").
- P5 DOD.md는 이를 "P5 scope 밖"이라 기술하나 스펙 §15.2 DoD 체크리스트에 **M_12 고유 항목**으로 명시되므로 "밖"이라는 해석은 자의적 축소다.
- 권고: §12.2 스펙 본문에 기술된 블록을 그대로 반영하여 PR.

### 4.2 MAJOR

**[MAJOR-1] `ai-speak-signal` topic별 UI 미구현 — §7.3 DoD 미충족**
- 파일: `frontend/src/renderer/src/services/websocket-handler.tsx` L322~L339
- 현 구현: `toaster.create({ title: \`프로액티브 [${topic}]\`, type: 'info', duration: 3000 })` — 4종 모두 동일 스타일.
- 스펙 §7.3 #2: `morning_briefing` 토스트 + 채팅 영역 배지 1회; `event_reminder` 토스트(title=`context.title`, body=`"N분 뒤 시작"`) + 10초 유지; `idle_rest`/`overwork` 토스트만.
- 미구현: (a) `morning_briefing` 배지, (b) `event_reminder` title/body/duration 분기, (c) §13.1 N-6 테스트 자체 미존재(정상 케이스 #6도 테스트 부재).
- 이 결함은 P1부터 존재하지만, P5가 "§15 DoD 완결"을 선언하는 단계이므로 여기서 집계한다. P1 R2 Critic이 이 분기 요구를 놓쳤다.

**[MAJOR-2] `electron-builder.yml` 외부 URL/publish 설정 잔존 — 오프라인 원칙 위반 잠재**
- 파일: `frontend/electron-builder.yml` L63~L68
- 내용: `publish.provider: github` + `electronDownload.mirror: https://npmmirror.com/mirrors/electron/`
- 근거: `specs/M_12_Frontend_SPEC.md` §4.2 #10 "자체 업데이트 채널 금지". §11.1 "외부 CDN/폰트 금지". 
- 현재 런타임 코드가 electron-updater를 import하지는 않음(`grep` 0건). 그러나 설정만으로도 `electron-builder --publish` 플래그 실수 시 외부 호출 위험. mirror URL은 빌드 타임에만 사용되나 사내망 오프라인에서 접근 불가.
- 권고: `publish: null` 또는 `provider: generic` + 로컬 URL. `electronDownload.mirror` 삭제(기본 캐시 경로 사용) 또는 사내 미러로 교체.

### 4.3 MINOR

1. **[MINOR-1] P4 R2 이관 항목 미처리 — MINOR-1(FallbackCard alert fallback), MINOR-2(pdf.js 에러 종류 분별), MINOR-R2-2(pdfDocRef race 가드)**. P5 DOD.md에 이 세 항목에 대한 처리 결과 기록 없음. `FallbackCard.tsx` L31 `alert()` 여전히 존재.
2. **[MINOR-2] CitationViewer race 가드 추가 미반영**. `openCitation`을 연속 호출하면 이전 async의 `pdfDocRef.current = pdfDoc` 할당 타이밍에 따라 이전 doc이 누수될 수 있다(`cleanupPdf`가 pdfDocRef=null일 때 실행되면 놓침). P4 R2에서 지적된 MINOR-R2-2 그대로 잔존.
3. **[MINOR-3] 스펙 §5.3 `CitationViewer` 인터페이스 이름 불일치**. 스펙은 `interface CitationViewer`로 요구, 구현은 `CitationViewerHandle`. 기능 동일, 이름만 불일치.
4. **[MINOR-4] `package.json.author="example.com"` / `homepage="https://electron-vite.org"` — upstream 템플릿 잔재**. 프로젝트 식별 정보로 부적절.
5. **[MINOR-5] playwright.config.ts가 use.headless=false로 설정됨**. CI 환경에서는 headless=true가 표준. `playwright install` 없이 바로 기동 시도 시 실패.
6. **[MINOR-6] `e2e/*.spec.ts`가 tsconfig include에서 제외**되어 typecheck 게이트를 빠져나감. 실제 `@playwright/test` 미설치 상태에서 TS 오류가 잡히지 않은 근본 원인.
7. **[MINOR-7] `FallbackCard.tsx` — toaster 접근 방식 부정확**. `(window as { toaster? })` 패턴은 실제 Chakra toaster 사용법과 맞지 않는다. 현 Citation Viewer 본체는 `@/components/ui/toaster`를 정상 import하지만 FallbackCard는 window 글로벌에서 찾으므로 에러 처리가 항상 alert()로 폴백.

---

## 5) 스펙 vs 구현 매핑 요약

| §13 케이스 | 구현 테스트 | 상태 |
|---|---|---|
| N-1 emotion 수신 → DOM 전환 | SpriteAvatarRenderer TC-01/02 | ✅ |
| N-2 speaking 펄스 | TC-05 | ✅ |
| N-3 펫 모드 on/off | — | ⚠ Skeleton (Windows QA) |
| N-4 드래그 | pet-ipc-validators 11건 + pet-mode.spec.ts skeleton | ⚠ 부분 |
| N-5 PDF 열기 | CitationViewer #1 #3 | ✅ |
| N-6 프로액티브 토스트 context.title | **없음** | ❌ (MAJOR-1) |
| N-7 continuous-capture 동기화 | (WS 핸들러 L302~L312에 수신 반영, 테스트 없음) | ⚠ |
| E-1 알 수 없는 emotion | TC-03 | ✅ |
| E-2 crossfade 범위 밖 | TC-04, TC-C2 | ✅ |
| E-3 비PDF 인용 | #2 | ✅ |
| E-4 WS 단절 | — | ❌ (P1 원 범위, 미커버) |
| E-5 마이크 권한 | — | ❌ (미커버) |
| E-6 study 감정 | — | 부분(validators에서 study 유효로 통과) |
| E-7 bbox 누락 | #5 | ✅ |
| A-1 | A-1a/A-1b + WS 통합 | ✅ |
| A-2 | rss-guard 5 + #6 | ✅ |
| A-3 | pet-mode.spec.ts skeleton | ⚠ Windows QA |
| A-4 | citation.spec.ts skeleton | ⚠ Windows QA |
| A-5 preload 우회 | — | ❌ (스펙 §13.3 #5 커버 없음) |

---

## 6) 검토하지 못한 영역

- 프로덕션 Electron 패키징(`electron-vite build` + `electron-builder`) 실제 빌드 산출물 검증 (WSL 제약).
- pdf.js worker의 file:// 프로덕션 경로 실증 (P4 R2 CRITICAL-2 회귀 확인 — P5 이관 명시 항목).
- CSP blob: worker-src가 런타임에 실제 pdf.js 워커를 로드하는지 검증 (P4 R2 MAJOR-2 회귀).
- Playwright 브라우저 바이너리 오프라인 번들 정책 (§12.2 블록에 포함 예정이었으나 블록 자체가 미추가).
- upstream 커밋 d176e7d 이후의 회귀 확인 (UPSTREAM_COMMIT.md 고정 여부 미확인).

---

## 7) 최종 판정

### **FAIL — M_12 ✅ DONE 자격 보류**

**근거 요약**
- [CRITICAL-1] `@playwright/test` 미설치 → `npm run e2e` 블로커 + 오프라인 재현 불가.
- [CRITICAL-2] `scripts/bundle_deps.sh` npm 캐시 블록 미추가 → §15.2 DoD 고유 항목 **명시적 미충족**.
- [MAJOR-1] `ai-speak-signal` topic별 UI 분기 미구현 → §7.3·§15.2 "UI 토스트 4종" 표면적 통과하나 스펙 요구 내용 미충족.
- [MAJOR-2] `electron-builder.yml` 외부 URL/publish 설정 잔존 → 오프라인 원칙 위배 잠재.

**조건부 승격 조건(PASS로 이행하기 위한 최소 조치)**
1. `@playwright/test` 실제 설치 + `package-lock.json` 갱신 + `assets/npm_cache` 갱신 (CRITICAL-1).
2. `scripts/bundle_deps.sh`에 §12.2 블록 추가 + 오프라인 `npm ci --offline` 동작 검증 로그 추가 (CRITICAL-2).
3. `websocket-handler.tsx` L322~L339를 §7.3 topic 분기에 따라 재구현 + §13.1 N-6 테스트 추가 (MAJOR-1).
4. `electron-builder.yml`에서 `publish` 블록을 `null` 또는 `generic` 로컬 URL로, `electronDownload.mirror`를 삭제 또는 사내 미러로 변경 (MAJOR-2).
5. P5 DOD.md에 위 조치 결과와 P4 R2 이관 항목(MINOR-1/2/R2-2) 처리 상태를 명시적으로 기록.

**PASS 가능 시기**: 위 4개 CRITICAL+MAJOR가 수정되고 P5-R2 fresh Critic 재검수가 진행된 시점.
