# M_01 AppCore — CR-11 proactive-notification 제거 리뷰

- 리뷰어: Critic (fresh)
- 범위: CR-11 (M_01/M_08/M_10 스펙 정리)
- 판정: FAIL
- 날짜: 2026-04-21

---

## 1. 독립 검증 결과

### 1.1 변경 범위 (git status/diff --stat)

```
 M specs/M_01_AppCore_SPEC.md      5 +++++--
 M specs/M_08_AvatarState_SPEC.md  4 ++--
 M specs/M_10_IdleMonitor_SPEC.md  4 ++--
 3 files changed, 7 insertions(+), 6 deletions(-)
```

- 편집 파일 3개로 한정(M_01/M_08/M_10 스펙). `src/`·`tests/`·`upstream/` **완전 불변**(`git diff HEAD -- src/ tests/ upstream/` 비어 있음).
- `specs/M_01_AppCore_SPEC.md.tmp_patch` 부산물 **없음**(확인됨: "No such file or directory").

### 1.2 전역 grep(`proactive-notification`)

- `src/`·`tests/`·`upstream/` 결과 **0건**. ✅
- `docs/` 결과: `docs/CHANGE_REQUESTS.md` 5건(CR-11 본문·DoD 내부). 체크리스트 허용 범주. ✅
- `specs/` 결과: `specs/M_12_Frontend_SPEC.md` **8건**, M_01/M_08/M_10 **0건**. ⚠️

  M_12 잔존 위치:
  1. L11(스펙 상단 "작성 근거" — M_01 §C를 "신규 송신 3종: continuous-capture-state·avatar-state·**proactive-notification**"로 기술)
  2. L78(§3.2 포크 수정 파일 — "신규 3종 송신/수신 타입" 나열에 포함)
  3. L261(§7.2 서버→클라 WS 송신 타입 표의 **행**)
  4. L741·L742·L744(§19 Q-11 본문)
  5. L817(§19.1 결정 표 Q-11 행 — "CR-11 발행" 기록)
  6. L829(§19.2 "CR-11 PASS 시 편입" 예고)

### 1.3 M_01 §C 송신 타입 표 현재 상태

```
| continuous-capture-state | 송신 | {running: bool, interval_sec?: int} |
| avatar-state             | 송신 | M_08에서 발송. M_01은 타입만 예약 ... |
| dnd-state                | 송신 | {enabled: bool}. set-dnd ... (CR-10) |
```
→ 3종 확인, 주석 "**이 세 타입을 프론트가 수신 가능한 것으로 문서화**"로 변경 확인, CR-11 각주(§C 하단, `specs/M_12_Frontend_SPEC.md §19 Q-11` 및 `specs/M_11_ProactiveDispatcher_SPEC.md §7.3` 정확 참조) 확인. ✅

### 1.4 회귀 테스트

- `pytest tests/app/ -q` → **130 passed, 6 warnings**(warnings는 upstream pydantic deprecation, 본 변경과 무관).
- `pytest tests/proactive tests/avatar_state tests/idle_monitor -q` → **160 passed, 1 skipped**.
- 문서 prose만 변경되어 회귀 없음. ✅

---

## 2. 체크리스트 심사

### 제거 완전성

- [x] `src/`·`tests/`·`upstream/` **0건**.
- [ ] **`specs/` 잔존 언급 범주 위반.** 체크리스트 명시: "specs/에 남은 언급이 (a) `specs/M_12_Frontend_SPEC.md` §19 Q-11 결정 히스토리, (b) M_01 §C CR-11 각주 — 이 두 경우로만 한정되는가? **다른 스펙에 제거되지 않은 언급이 있으면 FAIL.**"
  - §19에 해당하는 L741~L829는 허용 범주.
  - **L11·L78·L261 — 허용 범주 밖.** 이 3건은 "M_01 §C에 proactive-notification이 **존재한다**"는 현재 상태 기술/WS 송신 타입 표 행으로, CR-11 적용 후의 M_01 §C와 직접 모순.
- [x] `docs/` 잔존 = CHANGE_REQUESTS.md CR-11 본문 하나 범주. `docs/ARCHITECTURE.md`·`docs/MODULES.md`·`docs/research/frontend_structure.md` 0건.

### 스펙 정합성

- [x] M_01 §C 표 3종(`continuous-capture-state`, `avatar-state`, `dnd-state`) + "**세 타입**" 주석 일치.
- [x] M_01 CR-11 각주가 §C 하단 추가, M_12 §19 Q-11·M_11 §7.3 정확 참조.
- [x] M_08 §6.3 D-4 치환이 "`avatar-state` 독립 타입의 정당화" 논리를 보존. 원문의 "(a) proactive-notification 경로에서도 재사용"을 "(a) 백엔드 emitter 경로(`push_event`)와 LLM 발화 경로 양쪽에서 재사용 가능(M_06·M_11 등 어떤 호출자든 동일 타입으로 감정만 갱신)"으로 일반화. 오히려 호출자 예시가 늘어 D-4의 **독립 타입 재사용성** 논지가 더 명시적이 됨. 의도 왜곡 없음.
- [x] M_08 §14 Out-of-Scope 7번 치환이 "상호 순서 보장은 M_11 책임" 원칙을 보존하면서 "단일 WS 송신 타입 ai-speak-signal"로 구체화. ✅
- [x] M_10 §1.3 #3 치환이 "페이로드 변환은 M_11 책임" 원칙 보존. `ai-speak-signal` 단일화로 문언 단순화. ✅
- [x] M_10 §8 페이로드 규약 문단 치환 동일. ✅

### 부산물·위생

- [x] tmp_patch 파일 없음.
- [x] 섹션 앵커 정상(§C 헤더 1건, §6.3 결정 사항 요약 존재, D-4 행 존재, §1.3 Out-of-Scope 존재, §8 송신 페이로드 규약 존재).

### 회귀

- [x] tests/app 130 passed, tests/{proactive,avatar_state,idle_monitor} 160 passed +1 skipped. 0 failures.

### 범위 초과 방지

- [x] 편집 파일 M_01/M_08/M_10 3개로 한정. M_11·M_12 소스 불변(M_12는 아직 DONE 아님이므로 본 CR 범위 외에서 Builder가 편입 예정).
- [x] 공개 API 시그니처·타입·에러 정책 변경 0건(문서 prose 수정만).

---

## 3. 결함 목록

### [CRITICAL] C-1. `specs/M_12_Frontend_SPEC.md` L11·L78·L261 잔존 — 체크리스트 규정 직접 위반

- **파일:라인**:
  - `specs/M_12_Frontend_SPEC.md:11` — 본문 시작 "작성 근거" 인용부. "신규 송신 3종(`continuous-capture-state`·`avatar-state`·`proactive-notification`)"이라고 기술. CR-11 적용 후 M_01 §C에서는 `dnd-state`로 대체되었으므로 **현재 M_01과 직접 모순**.
  - `specs/M_12_Frontend_SPEC.md:78` — §3.2 포크 수정 대상 나열에 `proactive-notification` 핸들러 포함. "실제로 송신 주체 없음"이라는 CR-11의 전제와 모순(핸들러를 추가할 이유가 없어짐).
  - `specs/M_12_Frontend_SPEC.md:261` — §7.2 서버→클라 WS 송신 타입 **표 행**으로 존재. "백엔드 M_11이 이 타입을 **실제로는 송신하지 않고** `ai-speak-signal`로 통일"이라는 자조적 주석이 달려 있어 CR-11 취지를 사실상 이 표에서도 **제거**하는 것이 합리적.

- **근거**: 리뷰 지시문 체크리스트 "제거 완전성" 제2항: "specs/에 남은 언급이 (a) §19 Q-11 결정 히스토리, (b) M_01 §C CR-11 각주 — 이 두 경우로만 한정되는가? **다른 스펙에 제거되지 않은 언급이 있으면 FAIL.**" L11·L78·L261은 §19 내부가 아님.
- **현실 영향**: CR-11 DoD(`docs/CHANGE_REQUESTS.md` L771~L782)는 "M_01 스펙만 편집"으로 좁게 정의되었으나, 본 리뷰의 체크리스트는 **specs/ 전역에서 §19 Q-11 결정 히스토리 외 잔존을 금지**하므로 평가 기준이 더 엄격. 사용자 지시 우선.
- **권고 조치**:
  1. L11을 "신규 송신 3종(`continuous-capture-state`·`avatar-state`·`dnd-state`)"으로 치환. CR-11 참조 각주 추가.
  2. L78의 `proactive-notification`을 제거하고 `set-dnd`/`dnd-state`로 갱신(§19.2 L828 "§7.1 WS 수신 타입 표에 `set-dnd` 예정 추가 — CR-10 PASS 시 편입"과 일관). 또는 §19.2 L829("§7.2 WS 송신 타입 표에서 `proactive-notification` 제거 예정 — CR-11 PASS 시 편입")의 본문 편입을 **이번에 동시에** 수행.
  3. L261 행을 삭제하고 §19.2 L829의 예고를 본문에 반영. `dnd-state` 행을 추가해 M_01 §C와 맞춘다(§19.2 L828 CR-10 편입과 묶어 처리 권장).
  4. 만약 M_12 편집을 "본 CR 범위 외"로 고수하려면 — CR-11을 부분 완료로 닫고 **후속 CR**(예: CR-12 "M_12 M_01 §C/§19.2 편입 반영")을 발행해 추적한다. 편집 순서·범위 결정은 사용자 판단이 필요.

### [MAJOR] M-1. CR-11 각주의 일관성 — M_12와의 참조 동기화 누락

- **파일:라인**: `specs/M_01_AppCore_SPEC.md:506` ("CR-11 승인(2026-04-21)으로 제거. 사유: specs/M_12_Frontend_SPEC.md §19 Q-11. …")
- **문제**: 각주는 M_12 §19 Q-11을 인용하지만, 정작 M_12 본문 L11·L78·L261은 CR-11 적용 전 상태로 남아 있다. 독자가 각주 경유로 M_12를 열면 `proactive-notification`을 여전히 발견해 "정말 제거됐나?"라는 의문을 품는다. **링크 일관성 문제**.
- **권고 조치**: C-1 해소 시 자연스럽게 해결. 또는 각주에 "M_12 §19.2 L829 편입은 M_12 본문 갱신 시 반영 예정" 유보 문구 추가.

### [MINOR] m-1. CR-11 각주의 들여쓰기·시각 분리

- **파일:라인**: `specs/M_01_AppCore_SPEC.md:506`
- **문제**: §C 하단 블록쿼트(`>`) 두 줄이 연속인데 **앞의 "세 타입" 설명**과 **CR-11 각주**가 같은 블록쿼트 들여쓰기에 평행으로 놓여 있어, 주 설명과 각주의 위계가 시각적으로 구분되지 않는다. 각주임을 명시하려면 `> **각주 (CR-11)**: ...` 등 라벨이 있으면 가독성 향상.
- **권고 조치**: 라벨 추가 또는 구분선 삽입. 필수 아님.

---

## 4. 최종 판정

**FAIL.**

- **핵심 사유**: `specs/M_12_Frontend_SPEC.md` L11·L78·L261에 `proactive-notification`이 "현재 상태 기술"로 잔존. 리뷰 지시문 체크리스트 "제거 완전성" 제2항이 명시적으로 "§19 Q-11 결정 히스토리 외 잔존 시 FAIL"로 규정.
- **긍정 요소**:
  - `src/`·`tests/`·`upstream/` 불변성 완벽(0건).
  - M_01 §C 표·주석·CR-11 각주 정확.
  - M_08 D-4·§14, M_10 §1.3·§8 치환이 원문 의도를 보존하거나 강화.
  - 회귀 테스트 0 failure(tests/app 130 passed, proactive+avatar+idle 160 passed +1 skipped).
  - tmp_patch 등 부산물 없음.
- **재리뷰 조건**: Builder/Planner가 M_12 L11·L78·L261을 CR-11 취지에 맞게 갱신(또는 사용자 승인 하에 CR-11 범위를 M_01/M_08/M_10 3개로 공식 축소하고 후속 CR로 M_12 분리)한 후 fresh Critic 재검수.

