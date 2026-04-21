# M_12 E2E 테스트 (playwright-electron)

## 현황

- 스펙: `specs/M_12_Frontend_SPEC.md` §13.3 A-3 / A-4 / §14 E2E 매핑.
- 실행 환경 제약: **WSL에는 Electron용 디스플레이 서버가 없어 이 폴더의 `.spec.ts`는
  WSL에서 실행 불가**. 모든 테스트는 현재 `test.skip(...)` 상태다.
- `@playwright/test`는 오프라인 빌드 원칙(`CLAUDE.md`)에 따라 기본 `devDependencies`에서 제외했다.
  Windows 또는 온라인 CI에서 **실행 직전**에 아래 절차로 설치한다.

## 실행 절차 (Windows 또는 온라인 CI)

```powershell
# 1) @playwright/test 설치 (devDependency로 저장하지 않음 — 오프라인 번들에 포함되면 커짐)
npm run e2e:install

# 2) playwright 브라우저 바이너리 — Electron용은 별도 필요 없음.
#    (필요 시) `npx playwright install chromium`

# 3) 앱 빌드 (E2E는 빌드된 앱을 기동)
npm run build

# 4) E2E 실행
npm run e2e
```

## 시나리오

| 파일 | 매핑 | 설명 |
|---|---|---|
| `basic.spec.ts` | §14 N-2 정상 | 앱 기동 + 기본 창 뜨는지 smoke test |
| `pet-mode.spec.ts` | §13.3 A-3 | 펫 모드 click-through 중 합성 click 100회 → 버튼 미반응 |
| `citation.spec.ts` | §13.3 A-4 | 외부 이미지 로드 시도 → CSP 차단 로그 |

## 오프라인 번들과의 관계

- E2E 실행은 **사내 배포 전 QA 단계**에서 수행한다. 최종 사용자 PC에서 실행하지 않는다.
- 따라서 `@playwright/test` 바이너리는 `scripts/bundle_deps.sh` 오프라인 번들 **대상에서 제외**한다.
