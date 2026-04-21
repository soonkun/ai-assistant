# M_01 AppCore — CR-11 proactive-notification 제거 리뷰 (R2)

- 리뷰어: Critic (fresh, R2)
- R1 판정: FAIL (reviews/M_01_AppCore_CR11_REVIEW.md)
- 범위: R1 지적사항 해소 재검수
- 판정: **PASS**
- 날짜: 2026-04-21

---

## 1. 독립 검증

### 1.1 변경 범위
`git status --porcelain` + `git diff --stat HEAD`:

```
 M specs/M_01_AppCore_SPEC.md     |  5 +++--
 M specs/M_08_AvatarState_SPEC.md |  4 ++--
 M specs/M_10_IdleMonitor_SPEC.md |  4 ++--
 M specs/M_12_Frontend_SPEC.md    | 19 ++++++++++---------
```

편집 파일 4개(M_01/M_08/M_10/M_12) 한정. `src/`·`tests/`·`upstream/` 변경 0건(`git diff HEAD -- src/ tests/ upstream/` 무출력). 임시 파일 `specs/M_01_AppCore_SPEC.md.tmp_patch` 존재하지 않음.

### 1.2 전역 grep(`proactive-notification`)

```
specs/M_12_Frontend_SPEC.md:742  ← §19 Q-11 제목 (허용)
specs/M_12_Frontend_SPEC.md:743  ← §19 Q-11 본문 (허용)
specs/M_12_Frontend_SPEC.md:745  ← §19 Q-11 선택지 B 본문 (허용)
specs/M_12_Frontend_SPEC.md:818  ← §19 결정표 Q-11 행 (허용)
specs/M_12_Frontend_SPEC.md:830  ← §19.2 결정 반영 지점 (허용)
docs/CHANGE_REQUESTS.md:759,764,771,774,782  ← CR-11 본문 (허용)
reviews/M_01_AppCore_CR11_REVIEW.md:*  ← R1 리뷰 보존본 (허용)
```

**§19 외부 잔존: 0건.** `docs/ARCHITECTURE.md`·`docs/MODULES.md`·`docs/research/frontend_structure.md` 모두 0건.

### 1.3 회귀 테스트
- `pytest tests/app/` → **130 passed**
- `pytest tests/proactive/` → **59 passed**

---

## 2. R1 지적사항별 해소 여부

### R1 지적 1: `specs/M_12_Frontend_SPEC.md` L11 근거 인용부
- **R1 문제**: "신규 송신 3종(continuous-capture-state·avatar-state·**proactive-notification**)"
- **현재 상태(L11)**: "신규 수신 **4종**(screenshot-trigger·start-continuous-capture·stop-continuous-capture·**set-dnd**) + 신규 송신 3종(continuous-capture-state·avatar-state·**dnd-state**), L411~L504 payload 계약. **CR-10·CR-11 반영 완료**."
- **해소**: ✅ CR-11(proactive-notification 제거) + CR-10(set-dnd / dnd-state 편입) 모두 반영. M_01 §C(SPEC L496~L506)의 현재 3종과 **일치**.

### R1 지적 2: `specs/M_12_Frontend_SPEC.md` L78 핸들러 나열
- **R1 문제**: "신규 3종 송신/수신 타입(...avatar-state, proactive-notification, continuous-capture-state)"
- **현재 상태(L78)**: "WebSocket 이벤트 dispatcher — 신규 타입 핸들러 추가. 수신(클라→서버) 4종(screenshot-trigger, start-continuous-capture, stop-continuous-capture, **set-dnd**) + 송신(서버→클라) 3종(avatar-state, continuous-capture-state, **dnd-state**). CR-10·CR-11 반영."
- **해소**: ✅ proactive-notification 제거, dnd-state / set-dnd 편입, 수신·송신 방향 괄호 명시로 가독성도 개선.

### R1 지적 3: `specs/M_12_Frontend_SPEC.md` L261 §7.2 표 행
- **R1 문제**: `proactive-notification` 행이 §7.2 WS 송신 타입 표에 존재
- **현재 상태(§7.2 L256~L264)**: 표 4행 = `avatar-state` / `continuous-capture-state` / `dnd-state` / `ai-speak-signal`. `proactive-notification` 행 **완전 삭제**. 표 헤더 L256은 "upstream 19종 + 본 프로젝트 신규 3종(CR-10 `dnd-state` 반영. CR-11로 예약 해제된 타입은 §19 Q-11 참조)"로 갱신.
- **추가 확인**: `ai-speak-signal` 행(L264)이 "프로액티브 토스트 경로는 이 타입 **단일**로 통일됨(CR-11). M_11은 본 타입만 사용(§7.3, specs/M_11_ProactiveDispatcher_SPEC.md §7.3)."을 명시 — 경로 단일화 근거를 표 내부에 박아넣어 후속 독자가 Q-11까지 들어가지 않아도 결론을 본다. ✅
- **해소**: ✅

### 보너스 — §7.1 수신 표 `set-dnd` 행 편입
- §19.2 L829 "§7.1 WS 수신 타입 표에 `set-dnd` 예정 추가 — CR-10 PASS 시 편입"이 §7.1 본문(L246~L254)에 `set-dnd` 행으로 편입됨. 페이로드 `{type, enabled:bool}`가 M_01 §B-4와 일치. 트리거 설명이 "성공 시 서버가 dnd-state 응답을 송신하여 UI가 그 응답 기준으로 최종 상태를 반영(SSoT)"로 SSoT 원칙도 명시. ✅

---

## 3. 체크리스트

### 제거 완전성
- [x] `src/`·`tests/`·`upstream/` 잔존 0건.
- [x] `specs/` 잔존은 `M_12_Frontend_SPEC.md` §19(L742, L743, L745, L818, L830) **5건 모두 §19 내부**. §1~§18 및 §부록 0건.
- [x] `docs/` 잔존은 `CHANGE_REQUESTS.md` CR-11 본문 5건만.
- [x] `ARCHITECTURE.md`·`MODULES.md`·`research/frontend_structure.md` 0건.

### 스펙 정합성
- [x] `M_01_AppCore_SPEC.md` §C(L496~L506) 송신 타입 표 **정확히 3종**(continuous-capture-state · avatar-state · dnd-state). L506에 "CR-11 승인(2026-04-21)으로 제거" 각주.
- [x] `M_12` §7.1 수신 4종(+set-dnd). `{type, enabled:bool}` 스키마 M_01 §B-4와 일치.
- [x] `M_12` §7.2 송신 3종(dnd-state 포함, proactive-notification 제외).
- [x] `ai-speak-signal` 행이 "프로액티브 토스트 경로는 이 타입 **단일**로 통일됨(CR-11)" 문구 명시.
- [x] L11 근거 인용 · L78 §3 핸들러 리스트 모두 CR-10/CR-11 반영 후 상태와 일치.

### 부산물·범위
- [x] `M_01_AppCore_SPEC.md.tmp_patch` 없음.
- [x] 편집 파일 4개(M_01/M_08/M_10/M_12) 한정. src/·tests/·upstream/ 0건.

### 계약 불변
- [x] M_08 diff는 §6.3 D-4 본문 문구 갱신 + §13 note #7 표현 갱신. 공개 API·Emotion Literal·페이로드·에러 정책 불변.
- [x] M_10 diff는 §1.3 #3 Out-of-Scope 설명 + §7.1 콜백 페이로드 주석만. 공개 API·IdleEvent Literal·상태 머신 불변.

### 회귀
- [x] `pytest tests/app/` 130 passed.
- [x] `pytest tests/proactive/` 59 passed.

---

## 4. 결함

### CRITICAL
없음.

### MAJOR
없음.

### MINOR
1. **[MINOR]** `specs/M_12_Frontend_SPEC.md:225` — "upstream 채널을 그대로 쓰되 신규 메시지 타입 **6종**만 추가한다"는 산문이 본 CR 전후로 재집계되지 않았다. 현 §7.1(4종)+§7.2(3종)=7종이며, `ai-speak-signal`이 upstream 기존 타입의 서버→클라이언트 방향 재사용인 점을 감안하면 "신규 6종"이 여전히 성립할 수 있으나 독자가 카운트 근거를 재구성해야 한다. CR-11 범위 **밖**(R1도 비지적). 별도 CR 또는 본 CR의 말미 정리에서 다룰 것을 권고.
2. **[MINOR]** `specs/M_12_Frontend_SPEC.md:757`의 `ai-speak-signal` 행 처리 설명이 "프로액티브 토스트 경로는 이 타입 **단일**로 통일됨(CR-11)"로 CR 번호를 적시한 것은 좋으나, 표 헤더(L257)는 "CR-11로 **예약 해제**"라는 표현을 쓴다. "예약 해제"와 "제거"가 본 스펙 내에서 혼용된다. 독자에게 혼동을 주지 않는 범위이므로 MINOR.

### 결함 없음 확인 영역
- M_01 §C 송신 표의 3종 일치.
- M_08 §6.3 D-4 치환 후에도 "(a)·(b)·(c)" 3축의 독립 타입 정당화 논리 보존.
- M_10 §1.3 #3 및 §7.1 콜백 페이로드 주석 모두 "M_11이 단일 WS 송신 타입 ai-speak-signal로 변환"으로 일관.
- §19 Q-11 본문·결정표·§19.2 반영 지점은 결정 히스토리로서 보존되어야 하는 "발자국"이며 R2 체크리스트에서 허용 범주.

---

## 5. 최종 판정

**PASS**

R1이 지적한 3건(M_12 L11/L78/L261)은 모두 surgical하게 해소됐다. 제거는 완전하고(§19 외부 0건), 부수 문서(§19.2 CR-10·CR-11 편입 예정 항목)도 본문에 **실제 편입**까지 완수됐다. 회귀 테스트 130+59 건 PASS. src/·tests/·upstream/ 계약 변경 0건. M_08·M_10 diff는 문구 치환만이며 공개 계약 불변.

발견된 MINOR 2건은 CR-11 범위 밖 문서 산술·표현 일관성 이슈로, 본 재검수에서 PASS를 막는 사유로 보지 않는다.
