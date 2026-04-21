# M_12 Frontend Phase 4 (pdf.js 인용 뷰어) Critic Review

- 리뷰어: fresh Critic (앵커링 회피; 이전 P1~P3 리뷰 미참조)
- 근거 문서: `specs/M_12_Frontend_SPEC.md` §5.3, §8.3, §11, §13.1 N-5, §13.2 E-7, §13 DoD L636
- 검토 대상: P4 산출물(커밋 전) — `src/renderer/src/components/citation/**`, `src/renderer/src/ipc/shell.ts`, `src/main/index.ts`(shell:openPath handler), `src/preload/index.ts`·`index.d.ts`, `electron.vite.config.ts`, `package.json`
- 최종 판정: **FAIL**
- 사유: CRITICAL 2건(canvas ref 타이밍 버그 → 실제 렌더 파이프라인 미작동; workerSrc 루트 절대경로 → 프로덕션 file:// 아래 해결 불가) + MAJOR 3건

---

## §1. 독립 검증

### 1.1 품질 게이트
| 도구 | 결과 |
|---|---|
| `tsc -p tsconfig.node.json` | exit 0 |
| `tsc -p tsconfig.web.json` | exit 0 |
| `eslint --ext .ts,.tsx src/` | exit 0 (0 errors, 0 warnings) |
| `vitest run` | 43 tests PASS / 6 files PASS (기존 33 + bbox 6 + CitationViewer 4 = 43) |

### 1.2 변경 파일 (git status)
- M `frontend/electron.vite.config.ts`(+5 라인 — pdfjs 워커 viteStaticCopy)
- M `frontend/package.json` / `package-lock.json`(+pdfjs-dist ^4.6.0 <5)
- M `frontend/src/main/index.ts`(+12 라인 — shell:openPath handler + security filter)
- M `frontend/src/preload/index.ts` / `index.d.ts`(+shellApi + contextBridge 노출)
- ?? `frontend/src/renderer/src/components/citation/` (신규 타입·bbox·CitationViewer·FallbackCard + __tests__)
- ?? `frontend/src/renderer/src/ipc/shell.ts` (신규 wrapper)

### 1.3 외부 네트워크 호출 검색
- `grep fetch\(['\"](https?:|//)` in citation/ → **0 건** ✓
- `grep cdn|unpkg|jsdelivr|mozilla` in citation/ → 주석 1건(금지 선언), 실제 URL 0건 ✓

### 1.4 pdfjs-dist 번들 확인
- `node_modules/pdfjs-dist/build/pdf.worker.min.mjs` 1,375,838 bytes 존재 ✓
- viteStaticCopy target: `pdfjs-dist/build/pdf.worker.min.mjs` → `./assets/pdfjs/` ✓ (번들링 자체는 수행; 그러나 런타임 경로 해결은 별건 — CRITICAL-2)

---

## §2. 스펙 vs 구현 매핑

| 스펙 항목 | 구현 위치 | 상태 |
|---|---|---|
| §5.3 `SearchHit` 인터페이스 (8필드) | `citation/types.ts` L5-15 | PASS — 필드 6개 전부 일치 |
| §5.3 `CitationViewer.openCitation(hit): Promise<void>` | `CitationViewer.tsx` L70-142 (handle) | PASS (시그니처) / **FAIL** (실제 렌더 경로 미실행 — CRITICAL-1) |
| §5.3 `CitationViewer.close(): void` | `CitationViewer.tsx` L144-148 | PASS — destroy + 상태 초기화 |
| §8.3.1 #1 진입 | `openCitation` 함수 진입 | PASS |
| §8.3.1 #2 getDocument(file://URL) | `CitationViewer.tsx` L90-94 | PASS — `file://` 프리픽스 처리 |
| §8.3.1 #3 getPage(hit.page) + render | `CitationViewer.tsx` L98-115 | PASS 논리 / **FAIL** 실행 경로(타이밍) — CRITICAL-1 |
| §8.3.1 #4 bbox 변환식 | `bbox.ts` L27-38 | **PASS** — 스펙 §8.3.1 #4와 글자 단위 일치 |
| §8.3.1 #5 반투명 노란 박스 오버레이 | `CitationViewer.tsx` L118-130 | PASS 논리 (rgba(255,200,0,0.25) 배경+0.9 테두리) / 실제 mount 미검증 |
| §8.3.1 페이지 상단 스크롤 | `CitationViewer.tsx` L133-135 | PASS (containerRef.scrollTop=0) |
| §8.3.2 폴백 카드(원본경로·페이지·섹션) | `FallbackCard.tsx` L51-65 | PASS |
| §8.3.2 시스템 기본 앱 버튼 + shell.openPath | `FallbackCard.tsx` L15-37 | PASS — 실패 문자열 에러 처리 포함 |
| §8.3.2 토스터 에러 | `FallbackCard.tsx` L27-32 | MINOR — toaster 미존재 시 `alert()` fallback (UX 저하) |
| §8.3.3 `pdfjs-dist >=4.6.0 <5` | `package.json` L53 | PASS |
| §8.3.3 workerSrc=assets/pdfjs/pdf.worker.min.mjs | `CitationViewer.tsx` L19 | **FAIL** — 루트 절대경로 `/assets/pdfjs/...` (CRITICAL-2) |
| §8.3.3 CDN 금지 | 코드 검색 결과 | PASS (0 건) |
| §8.3.3 viteStaticCopy 번들 | `electron.vite.config.ts` L42-46 | PASS (번들) / 경로 해결 문제는 CRITICAL-2 |
| §8.3.4 pdfDocument.destroy() | `CitationViewer.tsx` L53-57 (cleanupPdf) | PASS (openCitation 진입 시·close 시 양쪽) |
| §8.3.4 RSS 1.2GB 모니터 | **구현 없음** | MAJOR-3 (선택적; P5 E2E 위임 가능하나 스펙 문구는 "뷰어 자동 닫기") |
| §11.1 `worker-src` / CSP | `src/renderer/index.html` L7 | MAJOR-2 — `worker-src` 미지정(script-src fallback에 의존; blob: 워커 시 차단 위험) |
| 보안: shell:openPath 입력 검증 | `src/main/index.ts` L204-214 | PASS — string+non-empty + http/file/UNC 차단 regex |
| preload contextBridge | `src/preload/index.ts` L115-117 | PASS — window.shell 노출 |
| window.shell 타입 | `src/preload/index.d.ts` L36-39 | PASS |

---

## §3. 테스트 커버 검증

| 스펙 케이스 | 구현 테스트 | 상태 |
|---|---|---|
| §13.1 N-5 "openCitation → getPage(3) + **오버레이 DOM 존재**" | `CitationViewer.test.tsx` #3 | **FAIL** — getPage(5) 호출만 assert; **오버레이 DOM existence 미검증**. 게다가 canvas ref 타이밍 버그로 실제로 오버레이가 생성되지 않음(콘솔 "canvas ref not available") — **DoD L636 위반** |
| §13.2 E-3 "비PDF 폴백 + getDocument 0회" | `CitationViewer.test.tsx` #2 | PASS — getDocument not called + FallbackCard 텍스트 검증 |
| §13.2 E-7 "bbox 누락 → 스크롤 수행, 오버레이 DOM 없음" | **없음** | **FAIL** — 전용 테스트 부재 |
| §13.3 A-2 100MB PDF RSS | **없음** | MAJOR (P5 E2E 위임 가능) |
| bbox 단위 테스트 ≥6 | `bbox.test.ts` #1~#6 (정상·scale·경계 bottom·zero-size·A3·소수점) | PASS — 6건 |
| close() destroy | `CitationViewer.test.tsx` #4 | PASS |

### 3.1 테스트 부실 징후
- vitest stderr 로그: `[CitationViewer] canvas ref not available`가 **#1/#3/#4 모든 PDF 테스트에서 출력됨**. 이는 `page.render()` 이전에 early return 발생 의미. 테스트는 `mockGetPage` 호출만 assert하고 `render` 후 로직(오버레이 setOverlayStyle, 스크롤 등) 검증을 건너뛰어 **통과**. Builder가 "테스트가 통과하도록 구현을 쉬운 방향으로 왜곡"한 의심 신호 — CRITICAL-1 참조.

---

## §4. 결함 목록

### [CRITICAL-1] canvas ref 타이밍 버그 — 스펙 §8.3.1 #3, §13.1 N-5 DoD L636 위반
- **위치**: `frontend/src/renderer/src/components/citation/CitationViewer.tsx` L86-105
- **증상**: `openCitation`이 `setIsVisible(true)`(86L)로 state만 갱신한 뒤 같은 async 함수 내에서 `await pdfjsLib.getDocument(...).promise`(94L)을 먼저 해석하고 `canvasRef.current`(101L)에 접근. React는 state 변경 후 commit 전이라 `canvasRef.current === null` → L102-105에서 `console.error('canvas ref not available') + return`하여 **page.render·bbox 오버레이·scroll 전 경로 skip**.
- **근거**: vitest 실행 로그에 `#1/#3/#4 모든 PDF 테스트에서 [CitationViewer] canvas ref not available` 출력. 프로덕션에서도 getDocument가 microtask로 빠르게 해석되면 동일 타이밍 발생.
- **영향**: §8.3.1 스펙 파이프라인 5단계 중 3~5단계 미실행. §13.1 N-5 DoD "오버레이 DOM 존재" 미달성. §13 §DoD L636 "±1px 배치" 근본적으로 검증 불가.
- **권고 조치**:
  1. 캔버스를 `isVisible`과 무관하게 mount하고 visibility는 CSS display 토글로 관리.
  2. 또는 `useEffect(() => { ... pdf render ... }, [pendingHit])` 패턴으로 전환하여 DOM commit 후 렌더 파이프라인 실행.
  3. 테스트에 `waitFor(() => expect(screen.getByTestId('citation-overlay')).toBeTruthy())` 등 DOM assert 추가로 재발 방지.

### [CRITICAL-2] workerSrc 루트 절대경로 — 프로덕션 file:// 해결 실패 위험
- **위치**: `CitationViewer.tsx` L19 `pdfjsLib.GlobalWorkerOptions.workerSrc = '/assets/pdfjs/pdf.worker.min.mjs'`
- **증상**: `window-manager.ts` L135 `loadFile('../renderer/index.html')`로 로드 시 base URL은 `file:///<app>/out/renderer/index.html`. 루트 절대경로 `/assets/...`는 **filesystem 드라이브 루트**(`file:///assets/...`)로 해석되어 워커 파일을 찾지 못함.
- **근거**: 동 프로젝트 `src/renderer/src/context/vad-context.tsx:285` `baseAssetPath: './libs/'`는 **상대경로** 사용 — P4는 이 확립된 패턴을 따르지 않음. 테스트에서는 vi.mock으로 pdfjs-dist 전체를 대체하여 런타임 워커 로드가 한 번도 검증되지 않음.
- **영향**: dev 서버(electron-vite dev, `ELECTRON_RENDERER_URL`)에서는 동작할 수도 있으나 **패키징 후 작동 불능**. §8.3.3 "워커는 빌드 타임 assets/pdfjs로 복사" 목적 달성 실패.
- **권고 조치**:
  1. `workerSrc = './assets/pdfjs/pdf.worker.min.mjs'` 또는 `new URL('./assets/pdfjs/pdf.worker.min.mjs', import.meta.url).href`.
  2. 번들된 빌드에서 실제 경로가 해결되는지 `electron-vite build && electron-vite preview`로 1회 smoke test 추가.

### [MAJOR-1] 오버레이 DOM + E-7 테스트 누락 — 스펙 §13 DoD L636 미충족
- **위치**: `CitationViewer.test.tsx` #3
- **증상**: 오직 `expect(mockGetPage).toHaveBeenCalledWith(5)`만 assert. §13 L636 "오버레이 DOM rect ±1px" 검증 0건. §13.2 E-7 "bbox undefined → 스크롤 수행·오버레이 없음" 전용 테스트 부재.
- **권고 조치**: 테스트 `#3`에 `screen.getByRole + style.left/top` 검증 추가, E-7 테스트 신규 추가(`bbox: undefined` → overlay DOM 미존재).

### [MAJOR-2] CSP `worker-src` 명시 부재 — §11.1 보호 2차 방어 취약
- **위치**: `src/renderer/index.html` L7 — `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src ws://127.0.0.1:12393 http://127.0.0.1:*; img-src 'self' data:; media-src 'self' blob: data:`
- **증상**: `worker-src` 미지정 → CSP3에서 script-src fallback, blob: 스킴 미허용. pdf.js가 내부적으로 `URL.createObjectURL`(node_modules/pdfjs-dist/build/pdf.min.mjs에서 확인됨)로 worker를 fake-bootstrap하는 경로에 진입 시 CSP 차단 발생 가능.
- **권고 조치**: `worker-src 'self' blob:` 추가. 또는 pdf.js 옵션으로 fake worker 경로 비활성화 명시.

### [MAJOR-3] RSS 1.2GB 모니터 미구현 — §8.3.4 스펙 문구 이탈
- **위치**: `CitationViewer.tsx` 전체
- **증상**: "100MB 이상 … 렌더러 프로세스 RSS < 1.2GB 초과 시 뷰어를 닫고 에러 토스트"(§8.3.4) 관련 감시 코드 0건. 적대적 테스트 §13.3 A-2도 매핑 테스트 부재.
- **완화 근거**: P5 E2E에서 실측 검증이 적절하므로 MAJOR로 분류(CRITICAL 아님). 다만 P5에 이관한다는 명시적 P4 open-item이 없으면 누락 위험.
- **권고 조치**: P5 E2E 전 sprint-backlog에 "A-2 100MB PDF RSS 모니터" 명시, 현 단계에서는 `performance.memory` 기반 가드(선택)라도 TODO 코멘트로 명시.

### [MINOR-1] FallbackCard의 `alert(...)` fallback — UX 저하
- **위치**: `FallbackCard.tsx` L31
- **증상**: toaster 부재 시 `alert()` 모달 표시. 스펙 §8.3.2는 "에러 토스트"만 언급.
- **권고 조치**: console.error만 남기고 alert 제거, 또는 부모 컴포넌트 via callback prop으로 에러 전달.

### [MINOR-2] `openCitation` 내부의 catch 폴백 — 에러 분별 불가
- **위치**: `CitationViewer.tsx` L136-141
- **증상**: getDocument/getPage/render 실패 모두 FallbackCard로 전환. §10.4 "pdf.js worker 로드 실패 → 폴백" 상황과 "PDF 문서 자체가 손상" 상황이 동일하게 취급됨. 사용자는 폴백 카드만 보고 원인을 알 수 없음.
- **권고 조치**: 에러 종류(`pdfjsLib.UnknownErrorException`, `PasswordException`, 워커 실패 등)를 구분하여 토스트 메시지 차별화.

### [MINOR-3] 확장자 검출 단순화 — 대소문자 혼재 edge
- **위치**: `CitationViewer.tsx` L75 `hit.source_path.split('.').pop()?.toLowerCase()`
- **증상**: `foo.PDF/bar.txt` 같은 경로 edge case에서는 `txt`로 잘 판정되나, 윈도우의 짧은 이름(8.3) 변환 시 별건 고려 없음.
- **완화**: 스펙 §8.3.2는 "source_path의 확장자"로 판단하라 했으므로 현 구현은 스펙 범위 내. 참고만.

---

## §5. 스펙 §19.2 Q-5(pdf.js 채택) 준수
- pdf.js 선택 ✓ (Apache-2.0, AGPL 회피)
- 번들 1.4 MB 이내(worker.min.mjs 1.37 MB) ✓
- 샘플 한국어 PDF 스파이크는 P4 범위 밖(빌더 초기 단계 Task 명시) — 참고

## §6. 오프라인·범위
- frontend/ 외 변경 없음 ✓
- E2E/playwright 실구현 0건(P5 영역) ✓
- 외부 네트워크 호출 신규 0건 ✓
- npm 새 의존성(`pdfjs-dist`, `vite-plugin-static-copy`) → **`scripts/bundle_deps.sh` 반영 여부 미검증** (CLAUDE.md "오프라인 빌드 의무" 관련; P4 범위에 포함 여부 스펙 미명시 — 후속 Builder Task로 이관 요망)

---

## §7. 검토하지 못한 영역 (다음 Critic 인수)
1. `scripts/bundle_deps.sh` 신규 블록(§12.2) 반영 확인 — 본 리뷰는 프론트엔드 산출물만 검토.
2. 실제 Electron 패키징 후 worker.min.mjs 해결 경로 smoke test (CRITICAL-2 실증 필요).
3. 프로덕션 CSP 하에서 pdf.js worker 로드 성공 여부(playwright route intercept / MAJOR-2).

---

## §8. 최종 판정

**FAIL**

CRITICAL-1(canvas ref 타이밍)은 **§8.3.1 파이프라인 3~5단계가 런타임에 실행되지 않음**을 의미하며, §13.1 N-5 DoD를 근본적으로 위반한다. 테스트가 이를 감지하지 못한 것은 "테스트가 통과하도록 구현 왜곡"의 회색 영역에 해당. CRITICAL-2(workerSrc)는 빌드 산출물 패키징 후 정상 동작 실패 위험. 두 CRITICAL은 반드시 수정 후 재검수 필요.
