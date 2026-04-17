# CLAUDE.md — 프로젝트 운영 규칙

이 파일은 Claude Code가 세션 시작 시 자동으로 읽는 프로젝트 지침이다.

## 프로젝트 개요

사내 인트라넷 오프라인 환경에서 동작하는 멀티모달 AI 비서. Open-LLM-VTuber(upstream/)를 베이스로, REQUIREMENTS.md에 명시된 기능을 추가·수정한다.

## 참조 문서

작업 시작 전 반드시 참조:
- `REQUIREMENTS.md` — 기능·비기능 요구사항의 단일 진실 공급원.
- `PROJECT_PLAN.md` — 실행 단계와 흐름.
- `docs/ARCHITECTURE.md` — Phase 1에서 생성, 이후 모든 구현의 근거.
- `docs/MODULES.md` — 모듈 인터페이스 계약.

## 멀티에이전트 규칙 (엄수)

이 프로젝트는 서브에이전트로 역할을 분리해 운영한다.

| 에이전트 | 모델 | 호출 시점 |
|---|---|---|
| `planner` | opus | 아키텍처·모듈 스펙 설계 |
| `researcher` | sonnet | 외부 자료·오픈소스 조사 |
| `builder` | sonnet | 실제 코드 구현 |
| `validator` | haiku | 테스트·린트·빌드 실행 |
| `critic` | opus | 적대적 리뷰 (반드시 builder 세션과 분리) |
| `integrator` | sonnet | 모듈 통합·E2E 테스트 |

### 절대 금지

- **Builder가 자신이 작성한 코드를 Critic 없이 자체 승인하는 것.**
- **Critic이 같은 결함에 대해 두 번 이상 리뷰하는 것.** 재검수는 fresh critic을 띄운다.
- **specs/M_NN_SPEC.md 없이 src/에 파일을 만드는 것.**
- **REQUIREMENTS.md에 없는 기능을 "개선" 명목으로 추가하는 것.** 필요하면 docs/CHANGE_REQUESTS.md를 생성하고 사용자 승인을 먼저 받는다.
- **외부 네트워크 호출 추가.** 코드 내 `fetch`, `http.get`, `requests.get`이 사용자 로컬 주소(`127.0.0.1`, `localhost`) 또는 사내 IP가 아닌 곳을 향하면 즉시 거부.

## 파일 규칙

- 모듈 스펙: `specs/M_NN_<module_name>_SPEC.md`
- 모듈 리뷰: `reviews/M_NN_<module_name>_REVIEW.md`
- 소스 코드: `src/<module_name>/`
- 테스트: `tests/<module_name>/`
- 모든 마크다운 문서는 첫 줄에 `#` 제목.
- 모든 파이썬 파일은 타입 힌트 필수.
- 모든 새 의존성은 `pyproject.toml`에 추가하고 사유를 PR 메시지에 기록.

## 커밋·테스트 명령

```bash
# 파이썬 포매팅
ruff format .

# 린트
ruff check .

# 타입 체크
mypy src/

# 단위 테스트
pytest tests/ -v

# 커버리지
pytest --cov=src tests/
```

Validator는 구현 완료 판정 전에 위 네 가지를 모두 실행한다. 하나라도 실패하면 FAIL.

## 모델 라우팅

- 단순 파일 검색·읽기·요약 → Haiku.
- 일반 구현·디버그 → Sonnet.
- 기획·아키텍처·적대적 리뷰 → Opus.

`/model sonnet`, `/model opus` 명령으로 명시적으로 전환한다. 의심스러우면 Sonnet.

## 산출물 체크리스트

모듈 M_NN을 "완료" 선언하려면:

- [ ] `specs/M_NN_*.md` 작성 및 사용자 승인.
- [ ] `src/<module>/` 구현 완료.
- [ ] `tests/<module>/` 테스트 작성 (정상 ≥5, 엣지 ≥5, 적대적 ≥3).
- [ ] `pytest`, `ruff`, `mypy` 모두 통과.
- [ ] `reviews/M_NN_*.md`에 Critic PASS 기록.
- [ ] `docs/MODULES.md`의 해당 모듈 상태가 `✅ DONE`으로 갱신.

## 오프라인 빌드 의무

- 새 의존성을 추가하면 반드시 `scripts/bundle_deps.sh`에도 반영해 오프라인 번들에 포함되도록 한다.
- 모델 파일(.gguf 등)은 git에 커밋하지 않는다. `.gitignore`에 이미 제외.
- HuggingFace `snapshot_download`를 코드 런타임에 호출하지 않는다. 빌드 타임에 미리 받아 `assets/models/`에 배치.

## 시작 전 확인

새 세션에서 첫 작업 시:
1. `PROJECT_PLAN.md`를 읽고 현재 Phase가 어디인지 확인.
2. `docs/MODULES.md`에서 진행 중인 모듈 확인.
3. 작업할 역할이 무엇인지 사용자에게 확인(planner? builder? critic?).
4. 불확실하면 질문. 추측으로 시작하지 않는다.
