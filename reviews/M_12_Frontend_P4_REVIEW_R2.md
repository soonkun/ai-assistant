# M_12 Frontend Phase 4 (pdf.js 인용 뷰어) Critic Review — R2

- 리뷰어: fresh Critic R2 (R1 판정 무관한 새 리뷰어 — 앵커링 회피)
- 근거 문서: `specs/M_12_Frontend_SPEC.md` §5.3, §8.3.1, §8.3.3, §8.3.4, §11.1, §13.1 N-5, §13.2 E-7, §13 DoD L636
- 이전 리뷰: `reviews/M_12_Frontend_P4_REVIEW.md` (R1 FAIL — CRITICAL 2건 + MAJOR 3건 + MINOR 3건)
- 최종 판정: **PASS**
- 사유: CRITICAL 2건 모두 해소, MAJOR-1·MAJOR-2 해소, MAJOR-3은 P5 백로그 이관, 품질 게이트(tsc/eslint/vitest) 전항 통과, vitest "canvas ref not available" 경고 0건, 회귀 0건

---

## §1. 독립 검증 결과

### 1.1 품질 게이트
| 도구 | 결과 |
|---|---|
| `tsc --noEmit -p tsconfig.node.json` | exit 0 |
| `tsc --noEmit -p tsconfig.web.json` | exit 0 |
| `eslint --ext .ts,.tsx src/` | exit 0 (0 errors, 0 warnings) |
| `vitest run` | 44 PASS / 6 files PASS (R1 대비 +1: CitationViewer.test.tsx 4→5) |
| "canvas ref not available" 로그 수 | **0** (R1은 #1/#3/#4 3건 발생) |

### 1.2 변경 파일 (git status, frontend/ 이내)
- M `frontend/electron.vite.config.ts`, `package.json`, `package-lock.json`, `src/main/index.ts`, `src/preload/index.ts`, `src/preload/index.d.ts`, `src/renderer/index.html`
- ?? `frontend/src/renderer/src/components/citation/`, `src/renderer/src/ipc/shell.ts`
- frontend/ 범위 외 변경 0건 ✓

### 1.3 외부 네트워크 호출 / E2E 구현
- `grep fetch\(['\"](https?:|//)` → 0건 ✓
- `grep playwright` → 0건(P5 영역 준수) ✓
- `nodeIntegration: false`, `contextIsolation: true` 유지(`src/main/window-manager.ts:72-73`) ✓

---

## §2. R1 결함별 해소 검증

### [CRITICAL-1] canvas ref 타이밍 버그 → **해소 (PASS)**
- **수정 위치**: `src/renderer/src/components/citation/CitationViewer.tsx` L60, L78-159, L190-192
- **수정 내용**:
  1. `pendingPdfHit` state 신설(L60).
  2. `openCitation`은 `setIsVisible(true) + setPendingPdfHit(hit)`만 호출(L191-192) — 비-PDF는 즉시 `setFallbackHit` + 반환(L181-188).
  3. 실제 pdf.js 파이프라인(getDocument → getPage → render → bbox 오버레이 → scroll)은 `useEffect(() => {...}, [pendingPdfHit, cleanupPdf])` 내부(L79-159)에서 수행. React는 commit 후 useEffect를 실행하므로 canvas DOM mount가 선행 보장됨.
  4. cleanup 함수로 `cancelled = true` 플래그 처리(L156-158) → 연속 호출 race 방어.
- **검증**:
  - `grep "canvas ref not available"` vitest 실행 출력 → 0건 (R1은 3건).
  - 테스트 #3 `expect(container.querySelector('[data-testid="citation-overlay"]')).not.toBeNull()`(test L140-141) PASS — 이전에는 early return으로 overlay 미생성이었음.
  - L103-108의 방어 로그는 "useEffect 후에도 canvas가 null이면 설계 위반"인 경우의 fallback만 담당(실제 테스트에서 발화되지 않음).
- **판정**: **해소 확인**.

### [CRITICAL-2] workerSrc 루트 절대경로 → **해소 (PASS)**
- **수정 위치**: `CitationViewer.tsx` L23-26
- **수정 내용**: `pdfjsLib.GlobalWorkerOptions.workerSrc = new URL('assets/pdfjs/pdf.worker.min.mjs', window.location.href).href`
- **검증**:
  - `grep "/assets/pdfjs" src/` → 주석 1건(L22)만 남음, 실행 문자열 0건.
  - 첫 인수가 앞에 `/` 없는 상대경로 → `file:///<app>/out/renderer/index.html`을 base로 해석되면 `file:///<app>/out/renderer/assets/pdfjs/pdf.worker.min.mjs`로 해결. dev(http://localhost)에서도 정상.
  - viteStaticCopy가 `dist/renderer/assets/pdfjs/pdf.worker.min.mjs`에 복사(`electron.vite.config.ts` 유지, R1 1.4 §1.4에서 확인된 상태) → 경로 해결과 번들 일치.
- **판정**: **해소 확인**. 단, 실제 `electron-vite build` 후 패키징 smoke test는 P5 또는 빌드 검증 단계에서 수행(이 리뷰 범위 아님).

### [MAJOR-1] 오버레이 DOM + E-7 테스트 → **해소 (PASS)**
- **수정 위치**: `CitationViewer.tsx` L229(`data-testid="citation-overlay"`) + `__tests__/CitationViewer.test.tsx` L113-171
- **수정 내용**:
  1. 오버레이 div에 `data-testid="citation-overlay"` 부여(L229).
  2. 테스트 #3 `bbox 있을 때 getPage(N) 호출 + 오버레이 DOM 생성`: `expect(mockGetPage).toHaveBeenCalledWith(5) + expect(overlay).not.toBeNull()`(test L138-141). 이중 await flush로 useEffect 완료 대기.
  3. 테스트 #5 신규 — `bbox 누락 시 스크롤만 수행하고 오버레이 DOM 없음`: bbox 미지정 SearchHit → `expect(overlay).toBeNull()`(test L145-171). §13.2 E-7 DoD 충족.
- **판정**: **해소 확인**. 5/5 테스트 PASS, overlay DOM 양쪽(존재/부재) 모두 검증.

### [MAJOR-2] CSP worker-src 명시 → **해소 (PASS)**
- **수정 위치**: `src/renderer/index.html` L7
- **수정 내용**: CSP meta에 `worker-src 'self' blob:` 추가됨(지문: `img-src 'self' data:; media-src 'self' blob: data:; worker-src 'self' blob:;`).
- **검증**: `grep worker-src src/renderer/index.html` → 1 match. pdf.js fake-worker 경로(blob:)도 허용.
- **판정**: **해소 확인**.

### [MAJOR-3] RSS 1.2GB 모니터 → **P5 백로그 이관 (허용)**
- **현재 상태**: 미구현 유지. R2 수정 주장 §5에 "P5 백로그 이관(이번 R2에서 수정 안 함)" 명시.
- **이관 근거**:
  - §8.3.4 "렌더러 RSS < 1.2GB … 뷰어 자동 닫기"는 실측 없이 단위 테스트로 검증 불가.
  - §13.3 A-2 적대적 케이스는 P5 E2E 범위에 자연스럽게 속함(100MB PDF 실파일 + performance.memory 관측).
  - R2 체크리스트 "P5 백로그로 명시" 요건 충족: 본 리뷰 §4에 P5 이관 목록 명시(아래 참조).
- **판정**: **이번 리뷰 허용, §4 P5 이관 목록에 기록**.

### [MINOR 1-3] → **P5 또는 후속 PR 보류 (허용)**
- FallbackCard alert fallback, catch error 미분별, 확장자 edge case — R2는 건드리지 않음. 판정에 영향 없음.

---

## §3. 신규 결함(R2에서 유입 확인)

### [MINOR-R2-1] openCitation의 Promise<void> 의미
- **위치**: `CitationViewer.tsx` L173-193
- **증상**: `openCitation`이 `Promise<void>` 반환하나 실제 pdf.js 렌더 완료 전에 resolve됨(setPendingPdfHit만 호출 후 return). 호출자는 "열기 완료"로 착각 가능.
- **완화**: §5.3 스펙은 `Promise<void>` 시그니처만 규정, "렌더 완료 대기" 요구 없음 → 스펙 범위 내. 참고용.

### [MINOR-R2-2] Race condition — pdfDocRef 할당 후 연속 openCitation
- **위치**: L94-95 vs L175
- **증상**: `setPendingPdfHit(hit)` 직후 두 번째 `openCitation` 호출이 `cleanupPdf()`로 기존 `pdfDocRef.current.destroy()` 수행. 그러나 첫 useEffect의 (이미 진행 중인) async 블록이 L95에서 방금 destroy된 doc을 `pdfDocRef.current`로 재할당할 가능성. cancelled flag는 L91 이전에 체크하지만 L95 할당 자체를 가드하지는 않음.
- **영향**: 매우 좁은 타이밍 창이며 실제 동작 시 cancelled=true로 즉시 return되므로 실사용 영향은 거의 없음. 참고용 MINOR. 후속 개선 시 `pdfDocRef.current = pdfDoc` 전에도 cancelled 검사 추가 권장.

### [MINOR-R2-3] fallbackHit ↔ renderError useEffect 전이
- **위치**: L162-168
- **증상**: renderError → fallbackHit 전환을 별도 useEffect로 처리. 상태 전이가 `pendingPdfHit → (error) → renderError → fallbackHit + pendingPdfHit=null`로 다단계라 디버깅 시 상태 흐름이 복잡.
- **영향**: 기능상 문제 없음. 가독성/유지보수 MINOR.

**신규 CRITICAL·MAJOR 유입: 0건.**

---

## §4. 체크리스트 R2 판정표

| 항목 | 결과 |
|---|---|
| canvasRef.current 접근이 useEffect 내부? | ✅ L79-159 |
| vitest "canvas ref not available" 경고 0건? | ✅ grep -c → 0 |
| workerSrc가 new URL(..., window.location.href)? | ✅ L23-26 |
| 루트 절대경로 `/assets/pdfjs/...` 실행 문자열 없음? | ✅ 주석 1건만 잔존 |
| `data-testid="citation-overlay"` DOM 요소 존재 (bbox 제공 시)? | ✅ L229 |
| 테스트 #3에 overlay querySelector 검증? | ✅ test L140-141 |
| 테스트 #5 (E-7) bbox 누락 시 overlay null? | ✅ test L145-171 |
| CSP worker-src 'self' blob: 포함? | ✅ index.html L7 |
| MAJOR-3 RSS는 P5 백로그 명시? | ✅ 본 리뷰 §2 / §4 P5 이관 |
| tsc.node + tsc.web exit 0? | ✅ 둘 다 0 |
| eslint 0 errors/warnings? | ✅ |
| vitest ≥44 PASS? | ✅ 정확히 44 (6 files) |
| 기존 테스트 회귀? | ✅ 0건 |
| frontend/ 외 변경? | ✅ 0건 |
| 외부 네트워크 호출 신규? | ✅ 0건 |
| playwright/E2E 실구현? | ✅ 0건(P5 준수) |
| nodeIntegration=false 유지? | ✅ window-manager L73 |
| useEffect cancelled flag 방어 적절? | ✅ L81, 91, 99, 121, 149 다단 체크 |

**전 항목 PASS.**

---

## §5. 스펙 vs 구현 매핑 (핵심 항목 재검증)

| 스펙 항목 | 구현 위치 | R1 | R2 |
|---|---|---|---|
| §8.3.1 #3 getPage(hit.page) + render 실행 경로 | CitationViewer.tsx L97-120 (useEffect 내) | FAIL (타이밍) | **PASS** |
| §8.3.1 #4 bbox 변환식 | bbox.ts L27-38 | PASS | PASS(변동 없음) |
| §8.3.1 #5 반투명 노란 박스 오버레이 DOM 생성 | CitationViewer.tsx L124-142, L228-230 | FAIL(미검증) | **PASS** (DOM 렌더 실증) |
| §8.3.3 workerSrc 로컬 번들 | CitationViewer.tsx L23-26 | FAIL(루트 절대경로) | **PASS** (상대 URL) |
| §11.1 CSP worker-src | index.html L7 | FAIL(미지정) | **PASS** |
| §13.1 N-5 DoD "오버레이 DOM 존재" | test #3 L138-141 | FAIL(assertion 부재) | **PASS** |
| §13.2 E-7 "bbox 누락 → overlay 없음" | test #5 L145-171 | FAIL(테스트 부재) | **PASS** |
| §8.3.4 RSS 1.2GB 모니터 | (미구현) | MAJOR | **P5 이관(허용)** |

---

## §6. 최종 판정

**PASS**

R1이 지적한 CRITICAL 2건(canvas ref 타이밍, workerSrc 경로)은 `pendingPdfHit` + useEffect 패턴과 `new URL(..., window.location.href)` 상대 URL로 각각 해소되어 §8.3.1 파이프라인 3~5단계가 실제로 실행됨을 vitest 로그(경고 0건) 및 DOM assertion 추가로 실증. MAJOR-1·MAJOR-2도 해소, MAJOR-3은 P5 백로그로 명시 이관. 품질 게이트 tsc/eslint/vitest 모두 PASS, 회귀 0건, 새 CRITICAL·MAJOR 유입 0건.

### P5 이관 목록(P5 critic이 인수할 항목)
1. **MAJOR-3 RSS 1.2GB 모니터 + §13.3 A-2 100MB PDF 적대 테스트** — performance.memory 기반 감시 및 뷰어 자동 닫기 로직, E2E 실파일 시나리오.
2. **CRITICAL-2 실증 검증** — `electron-vite build && electron-vite preview` 또는 실제 패키징 smoke test로 file:// 프로덕션 워커 로드 경로 확인. 본 R2는 코드 상 수정만 검증.
3. **MAJOR-2 실증 검증** — 프로덕션 CSP 하에서 pdf.js blob: 워커 경로가 실제로 허용되는지 Electron DevTools 콘솔 확인.
4. **MINOR-1 FallbackCard alert fallback 제거**(UX 개선).
5. **MINOR-2 pdf.js 에러 종류 분별 토스트**(§10.4 정합).
6. **MINOR-R2-2 pdfDocRef 재할당 race 가드 추가**(이중 cancelled 검사).

