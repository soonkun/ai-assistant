# PROJECT_PLAN — 실행 계획서

이 문서는 **처음부터 끝까지 한 번 읽고** 시작한다. 10분이면 된다.

## 1. 우리가 만드는 것

사내 인트라넷 Windows PC에서 **완전 오프라인**으로 동작하는 멀티모달 AI 비서. 캐릭터는 **새싹이(Saessagi)**. 기능은:

- 음성·텍스트 대화 (한국어 우선)
- 사내 문서 RAG — **페이지 단위 인용 포함**
- 새싹이 아바타 (펫 모드·표정·립싱크)
- 자연어 일정 등록 + 10분 전 알림
- 유휴 감지 시 휴식 권고
- 화면 공유 → 멀티모달 이해

상세 명세: `REQUIREMENTS.md`.

## 2. 기술 스택

- **LLM**: Gemma 4 E4B (Ollama `gemma4:e4b`) — 멀티모달 + 함수 호출 + 131K 컨텍스트.
- **STT**: faster-whisper large-v3.
- **TTS**: Piper (한국어) 기본, CosyVoice 2 업그레이드 옵션.
- **임베딩**: BGE-M3 (다국어).
- **벡터DB**: LanceDB (임베드 가능, 외부 프로세스 불필요).
- **PDF 파싱**: Docling + PyMuPDF — 페이지·섹션·바운딩 박스 메타데이터 보존.
- **아바타**: 스프라이트 스왑(V1) → 이후 Live2D(V2 옵션).
- **UI**: Open-LLM-VTuber 포크 + 커스텀 모듈.
- **스케줄러**: APScheduler + SQLite.

## 3. 개발 환경

- Windows 10/11.
- Python 3.11 이상, Node.js 20 이상, uv, ffmpeg, Ollama, Claude Code.
- RAM 16GB 이상, 디스크 여유 30GB 이상.
- GPU 없어도 동작 (있으면 가속).

점검·설치: `scripts\preflight.ps1`, `scripts\bootstrap.ps1`.

## 4. 작업 방식 — 멀티에이전트 파이프라인

단일 에이전트가 모든 걸 짜면 편향과 결함이 쌓인다. 역할을 분리한다:

| 에이전트 | 모델 | 역할 |
|---|---|---|
| **planner** | Opus | 아키텍처·모듈 스펙 |
| **researcher** | Sonnet | 코드베이스·라이브러리 조사 |
| **builder** | Sonnet | 실제 구현 (TDD) |
| **validator** | Haiku | 린트·타입·테스트 독립 실행 |
| **critic** | Opus | 적대적 스펙 검수 (반드시 별도 세션) |
| **integrator** | Sonnet | 모듈 통합·E2E |

### 핵심 규칙

1. **Builder가 만든 코드는 반드시 fresh critic이 검수.** Builder 세션의 컨텍스트 없이 스펙과 코드만 보고 판정.
2. **스펙 없이 구현 금지.** Planner가 `specs/M_NN_*.md`를 만들기 전에 Builder를 부르지 않는다.
3. **외부 네트워크 호출 금지.** REQUIREMENTS §0 위반은 자동 빌드 실패.
4. **모델 라우팅**: 단순 검색·읽기는 Haiku, 일반 구현은 Sonnet, 기획·검수는 Opus. 토큰 비용 50% 이상 절감 가능.

## 5. 단계별 실행 흐름

```
┌──────────────────────────────────────────────────────────┐
│ Phase 0 · GAP 분석 (researcher)                          │
│   upstream 코드 분석 → REUSE/EXTEND/NEW 분류             │
│   산출: docs/GAP_ANALYSIS.md                             │
└──────────────────────────────────────────────────────────┘
                          ↓ 사용자 승인
┌──────────────────────────────────────────────────────────┐
│ Phase 1 · 아키텍처 (planner)                             │
│   전체 설계, 모듈 분해, 마일스톤, 리스크                │
│   산출: docs/ARCHITECTURE.md, MODULES.md, MILESTONES.md,│
│         RISKS.md                                         │
└──────────────────────────────────────────────────────────┘
                          ↓ 사용자 승인
┌──────────────────────────────────────────────────────────┐
│ Phase 2 · 모듈 반복 루프 (10~12회)                       │
│   모듈마다:                                              │
│     ① planner  → specs/M_NN_*.md                         │
│     ② 사용자 승인                                        │
│     ③ builder  → src/<module>/, tests/<module>/          │
│     ④ validator → 테스트·린트 독립 실행                  │
│     ⑤ critic (fresh) → reviews/M_NN_*.md                 │
│     ⑥ PASS면 docs/MODULES.md 업데이트 · commit          │
│     ⑦ FAIL이면 builder로 되돌아감 (critic은 매번 새로) │
└──────────────────────────────────────────────────────────┘
                          ↓ 모든 모듈 DONE
┌──────────────────────────────────────────────────────────┐
│ Phase 3 · 통합 (integrator)                              │
│   E2E 시나리오 15개+ 작성·실행                           │
│   산출: tests/e2e/, docs/ACCEPTANCE.md                  │
└──────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────┐
│ Phase 4 · 오프라인 배포 번들 (선택)                      │
│   휠·npm·모델 한 번에 묶기                               │
└──────────────────────────────────────────────────────────┘
```

## 6. 예상 모듈 구성 (Phase 1에서 Planner가 확정)

의존성 순서 예시 — 최종 결정은 Planner가:

1. **M_01 LLM 클라이언트** — Ollama Gemma 4 E4B 래퍼, 스트리밍, 함수 호출.
2. **M_02 STT·TTS 오케스트레이터** — faster-whisper + Piper, VAD, 전이중 인터럽션.
3. **M_03 RAG 파이프라인** — Docling 파싱, BGE-M3 임베딩, LanceDB, 페이지 인용 생성.
4. **M_04 아바타 뷰** — 새싹이 스프라이트 렌더, 감정 태그 매핑, 펫 모드.
5. **M_05 스케줄러·다이어리** — SQLite, 자연어 파싱, 10분 전 알림.
6. **M_06 유휴 감지기** — Windows 입력 이벤트 훅, 임계값, 휴식 권고 생성.
7. **M_07 스크린 비전** — `mss` 캡처, Gemma 멀티모달 입력, 토큰 예산 관리.
8. **M_08 오케스트레이터** — 의도 라우팅, 컨텍스트·메모리, 에이전트 루프.
9. **M_09 UI 쉘** — 채팅 UI, 문서 업로드, 설정.
10. **M_10 부팅 시퀀스** — 오늘의 브리핑, 헬스체크, 모델 프리로드.

## 7. 실행 순서 (이 프로젝트 시작부터 끝까지)

1. **지금**: `scripts\preflight.ps1` 실행 → 필요한 도구 설치.
2. `scripts\bootstrap.ps1` 실행 → upstream clone, 모델 pull, venv, git init.
3. 새싹이 표정 6장 추가 제작 지시 (디자이너 또는 본인) — 개발과 병렬 진행.
4. 이 폴더에서 Claude Code 실행 (`claude`).
5. `prompts\00_kickoff.md` 프롬프트를 Claude Code에 붙여넣기.
6. 이후 Claude Code가 Phase 0 → 1 → 2(반복) → 3 순으로 안내.
7. 각 Phase 끝에서 사용자 승인이 요구되면 내용 확인 후 승인.
8. Phase 2 모듈 루프에서 Critic PASS를 받으면 git commit + 다음 모듈.

## 8. 멈춰야 할 때

다음 상황에서는 일단 멈춘다:

- Critic이 같은 모듈에서 3회 연속 FAIL → Planner에게 스펙 재검토 의뢰.
- Builder가 "스펙이 모호하다"며 질문 → 절대 추측하지 말고 Planner 수정.
- Validator의 테스트 커버리지가 70% 미만 → Builder에 테스트 추가 지시.
- 외부 네트워크 호출이 코드에 발견 → 즉시 FAIL, 사유 기록 후 재작업.

## 9. 참조 문서

- `REQUIREMENTS.md` — 요구사항 정전(canonical)
- `CLAUDE.md` — Claude Code 자동 로딩 규칙
- `docs/CHARACTER_SAESSAGI.md` — 캐릭터 에셋 가이드
- `docs/YOUTUBE_REFERENCE.md` — 착수 당시 시장·기술 참조 요약
- `.claude/agents/*.md` — 에이전트별 행동 규약
- `prompts/*.md` — Phase별 실행 프롬프트

## 10. 성공 기준 (Definition of Done — 프로젝트 전체)

- [ ] REQUIREMENTS.md의 §1~§8 모든 항목이 E2E 테스트로 검증됨.
- [ ] 사내 PC에서 인터넷 완전 차단 상태로 모든 기능 동작 확인.
- [ ] 새싹이가 7가지 표정을 상황에 맞게 전환하며 펫 모드로 동작.
- [ ] 문서 업로드 → 질의 시 페이지 번호·섹션까지 정확한 인용.
- [ ] 음성 발화 끝에서 첫 응답 음성까지 2초 이내.
- [ ] 오프라인 인스톨러 번들이 깨끗한 VM에서 원클릭 설치됨.
