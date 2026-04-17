# AI 비서 프로젝트 스타터 킷

사내 인트라넷 **Windows** PC에서 완전 오프라인으로 동작하는 멀티모달 AI 비서 구축 키트. 캐릭터는 **새싹이(Saessagi)**. 멀티에이전트 파이프라인(기획-구현-적대적 검수)으로 개발한다.

## 빠른 시작

```powershell
# 1. 환경 점검
.\scripts\preflight.ps1

# 2. 부족한 도구 설치 (Git, Python 3.11, Node 20, uv, ffmpeg, Ollama, Claude Code)

# 3. 부트스트랩 (upstream clone, 모델 pull, venv, git init)
.\scripts\bootstrap.ps1

# 4. Claude Code 실행
claude

# 5. prompts\00_kickoff.md 의 프롬프트를 복사해 Claude Code에 붙여넣기
```

## 이 폴더에 뭐가 있나

| 파일/폴더 | 역할 |
|---|---|
| `PROJECT_PLAN.md` | **첫 번째로 읽을 실행 계획서**. |
| `REQUIREMENTS.md` | 기능·비기능 요구사항 정전. |
| `CLAUDE.md` | Claude Code 자동 로딩 규칙. |
| `.claude/agents/` | 6개 서브에이전트 정의. |
| `.claude/settings.json` | Claude Code 권한·상태바 설정. |
| `prompts/` | Phase별 붙여넣기용 프롬프트. |
| `specs/` | (비어있음) Planner가 모듈 스펙 채움. |
| `reviews/` | (비어있음) Critic 리뷰 기록. |
| `docs/` | 산출물 저장소. 유튜브 참조·새싹이 가이드 포함. |
| `assets/character/saessagi/` | 새싹이 PNG (`neutral.png`만 제공). |
| `scripts/` | PowerShell 부트스트랩·프리플라이트. |
| `upstream/` | (비어있음) Open-LLM-VTuber가 bootstrap 시 clone됨. |

## 병렬로 준비해야 할 것

**새싹이 표정 6장 추가 제작**:

`happy.png`, `surprised.png`, `sad.png`, `worried.png`, `thinking.png`, `sleepy.png` 를 `assets/character/saessagi/`에 배치. 상세 사양은 `docs/CHARACTER_SAESSAGI.md`. 디자이너 반나절 작업 분량. 개발과 병렬 처리 가능 — M_04 모듈 구현 전까지만 완성되면 된다.

## 멀티에이전트 규칙 (엄수)

1. **Builder와 Critic은 다른 세션·다른 모델.** Builder 컨텍스트를 Critic이 봐선 안 된다.
2. **스펙 없이 구현 금지.** Planner가 spec을 만들기 전엔 Builder 호출 X.
3. **검수는 거부할 이유를 찾는 역할.** Critic이 "LGTM"만 하고 넘어가면 교체.
4. **외부 네트워크 호출 즉시 거부.** 완전 오프라인이 요구사항이다.

## 다음 단계

`PROJECT_PLAN.md` 읽기 → `scripts\preflight.ps1` 실행.
