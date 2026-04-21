# UPSTREAM_COMMIT — frontend 독립 포크 근거

이 디렉토리는 upstream `Open-LLM-VTuber/Open-LLM-VTuber-Web` 소스의 **특정 커밋 스냅샷**을 복사해 만든 독립 포크다.
`specs/M_12_Frontend_SPEC.md` §19 Q-1·Q-15 결정에 따라 서브모듈이 아닌 루트 `frontend/` 디렉토리에 트리를 복사하는 방식을 채택했다.

## 포크 기준

| 항목 | 값 |
|---|---|
| upstream 리포 | `https://github.com/Open-LLM-VTuber/Open-LLM-VTuber-Web` |
| 포크 대상 브랜치 | `main` (소스) |
| 포크 커밋 해시 | `d176e7df2366952e3bacbf12cf9a8b18a4315932` |
| 포크 일자 | 2026-04-21 |
| 참고 — `.gitmodules` 서브모듈 pin | `06a659b114fff788cf0daaa86e484576db4975bf` (`build` 브랜치 — 배포 산출물. 소스 포크에는 부적합이어서 `main` 선택) |

## 브랜치 선택 근거

`.gitmodules`가 가리키는 `build` 브랜치는 Electron 빌드 산출물(44MB, `assets/`·`libs/`만 포함)이다.
M_12 Frontend는 **소스 커스터마이징(스프라이트 렌더러, 펫 모드, PDF 뷰어 신설)**이 필수이므로
실제 Electron+React+TypeScript+Vite 소스가 들어 있는 `main` 브랜치(`d176e7d`)를 포크 기준으로 선택했다.

## 포크 절차 (재현 가능)

```bash
# 1) upstream 서브모듈 초기화(build 브랜치가 pin되어 있으므로 main으로 전환)
git -C upstream/Open-LLM-VTuber submodule update --init frontend
cd upstream/Open-LLM-VTuber/frontend
git checkout main

# 2) 소스 트리를 루트 frontend/로 복사 (.git, .github 제외)
rsync -a --exclude='.git' --exclude='.github' \
  upstream/Open-LLM-VTuber/frontend/ frontend/

# 3) 서브모듈을 원래의 build 커밋으로 복귀 (upstream 히스토리 보존)
git -C upstream/Open-LLM-VTuber submodule update --init frontend
```

## 편집 정책 (CLAUDE.md 및 M_12 §3.3 기반)

- 이 디렉토리의 모든 파일은 **본 프로젝트의 자산**이다. upstream에 PR로 돌려보내지 않는다.
- 수정 diff를 추적하기 쉽도록, 첫 자체 편집 시 해당 파일의 루트에 `// @fork-edit: <요약>` 주석 또는 마크다운 각주를 남긴다.
- upstream이 배포한 원본 디렉토리 구조(`src/main`, `src/preload`, `src/renderer`)는 유지.
- Live2D 관련 경로(`src/renderer/src/components/avatar/` 등)는 M_12 §3.3에 따라 **삭제 또는 치환**(스프라이트 렌더러 교체). 삭제 시 본 문서에 경로를 기록한다.

## upstream 업데이트 절차

upstream에 유의미한 버그 수정·보안 패치가 나오면:
1. `git -C upstream/Open-LLM-VTuber/frontend fetch origin main` 으로 최신 메인 확인.
2. 해당 diff를 본 디렉토리에 수동으로 선별 반영.
3. 본 문서의 "포크 커밋 해시"와 "포크 일자"를 갱신.

## 원본 파일 중 리네임된 항목

- `CLAUDE.md` → `UPSTREAM_CLAUDE.md` (프로젝트 루트의 `CLAUDE.md` 자동 로딩과 혼선 방지).
