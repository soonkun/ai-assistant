# M_08 AvatarState — 스펙

> 분류: **NEW** (+ **부분 REUSE**: upstream `Live2dModel.extract_emotion` 의 bracket 스캔 알고리즘만 이식).
>
> 작성 근거: `REQUIREMENTS.md` §3.1~§3.3/§9, `docs/CHARACTER_SAESSAGI.md` "감정 태그 프로토콜"/표정표, `docs/MODULES.md` M_08(L281~L304)·M_01(L44~L63)·M_12(L389~L408), `docs/MILESTONES.md` M_08(L120~L127), `specs/M_01_AppCore_SPEC.md` §"WebSocket 메시지 타입 — C. 신규 송신 타입"(L466~L474), `upstream/Open-LLM-VTuber/src/open_llm_vtuber/live2d_model.py` L146~L194, `upstream/Open-LLM-VTuber/src/open_llm_vtuber/agent/transformers.py` L58~L100, `upstream/Open-LLM-VTuber/src/open_llm_vtuber/conversations/types.py` L8, `src/tool_router/screenshot.py` L17(`SendTextCallback` 컨벤션).

---

## 1. 목적과 범위

### 1.1 목적

LLM(Gemma 4 E4B)이 스트리밍 출력하는 응답 텍스트에서 본 프로젝트 고유 태그 문법 `[emotion:<key>]`을 **파싱·제거**하고, 현재 아바타 표정 상태(8종 감정 중 LLM 발화용 7종)를 WebSocket 프론트엔드(M_12)로 **이벤트 1건**으로 송신하는 **순수 백엔드 상태 계층**을 제공한다. 추가로 백엔드 장기 작업(RAG 인제스트 등) 중 표시용 **시스템 상태 감정** `study` 1종을 타입 수준에서 허용한다.

본 모듈은 **PNG 렌더·crossfade·opacity 펄스를 직접 수행하지 않는다**. 그것은 M_12 `AvatarRenderer`의 책임이다. M_08은 "어떤 감정이 선택되었는가" + "그 감정을 몇 ms 페이드로 그려라"라는 **명령 이벤트**만 내보낸다.

### 1.2 In-Scope

1. `AvatarState` 클래스 — `extract_emotion(text) -> (clean_text, Emotion | None)` 동기 메서드와 `push_event(event, send_text) -> None` async 메서드 2종.
2. `AvatarEvent` dataclass — `emotion`/`crossfade_ms`/`speaking` 3필드. **frozen=True**.
3. `Emotion` Literal — **8종**(`neutral`, `happy`, `surprised`, `sad`, `worried`, `thinking`, `sleepy`, `study`).
4. `[emotion:<key>]` 태그 파싱(본 프로젝트 정식 문법).
5. WebSocket 송신 페이로드 스키마 `{"type":"avatar-state","emotion":...,"crossfade_ms":...,"speaking":...}`.
6. **LLM 발화 감정 파싱 집합(`_SPOKEN_EMOTIONS`)과 유효 Emotion 타입 집합(`_VALID_EMOTIONS`)의 명시적 분리**. `study`는 후자에만 포함(§4.1, §6.3 D-6).
7. 미지 감정 키 폴백 정책(`neutral` + `logger.warning`). `extract_emotion`이 `[emotion:study]`를 받으면 **미지 키와 동일 취급**(D-6).
8. 동시 `push_event` 호출 시 **전송 순서 직렬화**(`asyncio.Lock` 1개).
9. 단위 테스트(정상 ≥5, 엣지 ≥5, 적대적 ≥3).
10. `AppServiceContext.avatar_state` 슬롯 배선(`load_app_services` 1줄 추가).

### 1.3 Out-of-Scope (명시적 제외)

1. **스트리밍 중간 버퍼링**: `[emotion:` 까지만 들어오고 `happy]`가 아직 안 온 상태를 본 모듈이 자체 저장하지 않는다. `extract_emotion`은 **완결된 문자열**을 기대한다. 버퍼링은 호출자(M_05 `GemmaChatAgent` 또는 upstream `SentenceDivider` 후단)의 책임(§5.2, §13).
2. **PNG 파일 로드·crossfade·opacity 펄스 애니메이션**: M_12 프론트엔드 `AvatarRenderer` 책임.
3. **에셋 유무 검증**(`assets/character/saessagi/<emotion>.png` 존재 체크): 본 모듈은 8종 감정을 **모두 유효**한 것으로 가정하고 그대로 송신. 미보유 에셋에 대한 `neutral` 2차 폴백은 **프론트 단독 책임**이며, 백엔드는 이중 폴백을 금지한다(§6.3 결정 사항 D-3).
4. **감정 태그 자동 삽입**: LLM 프롬프트 튜닝·system prompt 엔지니어링은 M_05/M_01 담당. 본 모듈은 **추출만**.
5. **upstream `[<key>]` 단일 키 문법**(예: `[happy]`, `[joy]`) 지원. 본 프로젝트는 `[emotion:<key>]` 접두 스키마만 정식이며 단일 키 문법은 V1 **비지원**(§6.3 결정 사항 D-1, §18).
6. **다중 감정 동시 재생·보간**: `AvatarEvent.emotion`은 단일 값. 응답 내 복수 태그가 등장해도 스펙상 **첫 번째 1건**만 유의미(§6.3 결정 사항 D-2).
7. **립싱크 음성 타이밍 계산**: `speaking` 플래그는 단순 boolean. 발화 시작/종료 시점 결정은 TTS 재생 관리자(M_04/M_12) 책임.
8. **WebSocket 재시도·버퍼링**: `push_event`는 `send_text`가 던지는 예외를 **재전송 시도 없이 전파**한다(§8).
9. **다중 클라이언트 브로드캐스트**: 단일 사용자 전제(REQUIREMENTS.md §10). `send_text`는 호출 시점의 클라이언트 1개에만 전송.
10. **히스토리/세션 저장**: 본 모듈은 상태를 **메모리에만** 유지(`_last_emotion`, `_last_speaking`). 재시작 시 `default="neutral"`로 초기화.
11. **`study` 감정을 발화 경로(`extract_emotion`)에서 수용하는 것**: D-6에 따라 `study`는 백엔드 emitter(M_06 등)가 `push_event`를 통해 **직접** 송신하는 채널만 유효. LLM 응답 문자열에서 `[emotion:study]`가 등장하면 미지 키 취급 → `neutral` 폴백(§5.1, §10 N-8/E-8).

---

## 2. 요구사항 연결

| REQUIREMENTS.md / 설계 문서 항목 | M_08 기여 |
|---|---|
| §3.1 캐릭터 | "새싹이" 감정 **8종**(`neutral, happy, surprised, sad, worried, thinking, sleepy, study`)을 유일한 유효 값으로 고정(§4.1). 이 중 7종은 LLM 발화 감정, 1종(`study`)은 시스템 상태 감정. |
| §3.3 표현 — `[emotion:happy]` 태그로 표정 전환 | `extract_emotion`이 해당 문법을 파싱 + 제거(§5) |
| §3.3 표현 — 200~300ms crossfade | `AvatarEvent.crossfade_ms` 기본 250, 허용 범위 [200,300] 검증(§4.2, §8) |
| §3.3 표현 — 립싱크 opacity 펄스 | `AvatarEvent.speaking` boolean. 본 모듈은 토글 값 전달만, 펄스 실행은 M_12 |
| §3.2 렌더러 추상화 / 스프라이트 스왑 | 본 모듈은 렌더러가 아니며, 송신 메시지 타입만 정의(M_12가 구독) |
| §9 외부 네트워크 호출 금지 | 새 의존성 0. 표준 라이브러리(`re`, `dataclasses`, `asyncio`, `logging`)만 사용 |
| §9 성능 — 응답 지연 목표 | `extract_emotion` 1KB 입력 ≤ 1 ms, `push_event`는 `send_text` 호출 외 오버헤드 < 0.1 ms(§9) |
| §10 다중 사용자 동시 접속 안 함 | 단일 `AvatarState` 인스턴스 + 단일 `asyncio.Lock`으로 충분 |
| docs/MODULES.md M_01 | `AppServiceContext.avatar_state` 필드에 주입(§13) |
| docs/MILESTONES.md M_08 DoD | §11 체크리스트에 그대로 매핑 |

---

## 3. upstream 재사용 분석

### 3.1 REUSE (알고리즘 이식만, import 하지 않음)

| upstream 심볼 | 이식 방식 |
|---|---|
| `Live2dModel.extract_emotion` (`live2d_model.py` L146~L172) | 좌측 브래킷 스캔 + 키 테이블 매칭 **알고리즘만** 새 구현체(`AvatarState.extract_emotion`)에 이식. 단, upstream은 `[<key>]`, 본 모듈은 `[emotion:<key>]` 접두형으로 **문법 교체**. `str_to_check.lower()` 정규화 전략은 계승(§5.1). |
| `Live2dModel.remove_emotion_keywords` (L174~L194) | "원본 대소문자 보존 + lower 사본으로 위치 탐색" 트릭을 계승. 본 모듈의 `_strip_tag`는 `re.sub`로 대체되지만, 공백 보존 정책은 동일(§5.1, §6.4). |

**import 하지 않는 이유**: upstream `Live2dModel` 생성자는 `model_dict_path`/`model_info`/`emo_map` 등 Live2D 전용 상태를 요구하므로 스프라이트 기반 본 프로젝트에 부적합. `AppServiceContext.live2d_model = None`(M_01 D-06). 따라서 알고리즘만 복사해 `src/avatar_state/tag_parser.py`에 신규 구현.

### 3.2 DROP (사용 안 함)

| upstream 심볼 | 이유 |
|---|---|
| `Live2dModel._lookup_model_info`, `_load_file_content`, `set_model` | Live2D `.model3.json` 로드 경로. 본 프로젝트는 PNG 스프라이트 사용으로 교체. |
| `Actions.expressions: list[int\|str]` (`output_types.py` L10) | upstream은 감정을 audio payload의 `actions` 서브필드에 실어 보냄(`prepare_audio_payload`, `stream_audio.py` L77). 본 프로젝트는 **독립 메시지 타입** `avatar-state`로 분리(§6.1 결정 사항 D-4). |
| `agent/transformers.py::actions_extractor` 데코레이터 | 감정 추출을 SentenceDivider 파이프라인에 박아 넣는 구조. 본 프로젝트는 M_05 `GemmaChatAgent`가 문장 단위로 `extract_emotion`을 호출하고 결과를 별도 `push_event`로 송신하는 **명시적** 호출 구조를 취한다(§13). |

### 3.3 메시지 타입 충돌 점검

`specs/M_01_AppCore_SPEC.md` §"신규 송신 타입" L471: `avatar-state` 타입은 이미 M_01에서 **예약**되었고, 필드 목록도 `{emotion, crossfade_ms, speaking}`로 일치. 본 스펙은 M_01 예약을 **확정**한다. upstream 기존 송신 타입 21종(`audio`, `full-text`, `control`, `group-update`, `history-list` 등, M_01 §"A. upstream 기존 타입" 참조)과 **문자열 충돌 없음**(rg로 확인: upstream 트리에 `avatar-state` 0건).

---

## 4. 공개 API

> Python 3.12 타입 힌트. `dataclass(frozen=True)`로 불변 이벤트. `async def`는 실제 I/O가 발생하는 `push_event` 1개만.

### 4.1 `Emotion` Literal과 유효 키 테이블 — 두 집합의 분리

본 모듈은 **두 개의 서로 다른 감정 집합**을 정의한다. 이 분리는 §6.3 결정 사항 D-6의 핵심 계약이다.

```python
# src/avatar_state/types.py
from typing import Literal

# (1) 유효 Emotion 타입 — AvatarEvent.emotion 에 들어갈 수 있는 전체 집합(8종).
#     push_event 경로(백엔드 emitter 직접 호출)에서 타입 검증에 사용.
Emotion = Literal[
    "neutral", "happy", "surprised", "sad",
    "worried", "thinking", "sleepy", "study",
]

_VALID_EMOTIONS: frozenset[str] = frozenset({
    "neutral", "happy", "surprised", "sad",
    "worried", "thinking", "sleepy", "study",
})

# (2) LLM 발화 파싱 집합 — extract_emotion 이 [emotion:<key>] 에서 유효로 간주할 키(7종).
#     study 는 의도적으로 제외. LLM 이 발화 중 study 를 쓰면 안 되기 때문(§6.3 D-6).
_SPOKEN_EMOTIONS: frozenset[str] = frozenset({
    "neutral", "happy", "surprised", "sad",
    "worried", "thinking", "sleepy",
})

# 불변식 (테스트 고정):
#   _SPOKEN_EMOTIONS ⊂ _VALID_EMOTIONS
#   _VALID_EMOTIONS - _SPOKEN_EMOTIONS == {"study"}
```

**결정 사항 D-1 (§6.3)**: 전체 8종은 `docs/CHARACTER_SAESSAGI.md` 표(neutral~sleepy + study)와 완전 일치. 순서도 해당 문서 순으로 고정하여 로그·테스트 가독성 향상.

**결정 사항 D-6 (§6.3)**: `_SPOKEN_EMOTIONS` 와 `_VALID_EMOTIONS` 의 **명시적 분리**. `study` 는 백엔드 장기 작업 표시용 시스템 상태이며 LLM 발화 감정이 아니다. 자세한 근거는 §6.3 참조.

### 4.2 `AvatarEvent`

```python
# src/avatar_state/types.py
from dataclasses import dataclass

CROSSFADE_MIN_MS: int = 200
CROSSFADE_MAX_MS: int = 300
CROSSFADE_DEFAULT_MS: int = 250

@dataclass(frozen=True, slots=True)
class AvatarEvent:
    """아바타 상태 이벤트. `push_event`의 입력 단위.

    Fields:
        emotion: 8종 Emotion Literal 중 하나. Literal 범위 위반 시 파이썬
            런타임이 직접 잡지는 않으므로, 본 dataclass의 __post_init__에서
            _VALID_EMOTIONS 집합으로 방어적 검증 수행. study 포함.
        crossfade_ms: 페이드 전환 시간. REQUIREMENTS.md §3.3은 200~300ms
            범위. 범위 밖이면 ValueError(§8 에러 정책).
        speaking: 립싱크 opacity 펄스 ON/OFF 토글. 단순 boolean.
            study 시스템 상태는 통상 False 로 emit (발화 아님).

    Raises:
        ValueError: emotion이 8종 외 또는 crossfade_ms가 [200,300] 범위 밖.
    """
    emotion: Emotion
    crossfade_ms: int = CROSSFADE_DEFAULT_MS
    speaking: bool = False

    def __post_init__(self) -> None: ...
```

**결정 사항 D-5 (§6.3)**: `crossfade_ms`가 범위 밖일 때 **clamp 하지 않고 `ValueError`** 를 던진다. 근거: (a) REQUIREMENTS.md §3.3이 "200~300ms"를 명시적 범위로 고정, (b) 호출자 실수를 조용히 덮지 않고 빠르게 노출, (c) `AvatarState` 내부가 생성하는 이벤트는 항상 기본값 250을 사용하므로 외부 생성 이벤트(테스트·M_11 등)만 검증 대상. clamp 정책은 "잘못된 입력을 정상 출력처럼 보이게 해" 디버깅을 방해한다(§18 부록 근거).

### 4.3 `AvatarState`

```python
# src/avatar_state/service.py
from collections.abc import Awaitable, Callable
from typing import Any
import asyncio

SendTextCallback = Callable[[dict[str, Any]], Awaitable[None]]
# src/tool_router/screenshot.py L17 과 동일 타입 alias.
# upstream WebSocketSend(=Callable[[str], Awaitable[None]])는 JSON 직렬화를
# 호출자에 맡기지만, 본 프로젝트는 dict를 받아 내부에서 json.dumps 하는
# 컨벤션으로 통일되어 있다(src/tool_router/screenshot.py L31 참조).

class AvatarState:
    """아바타 감정 상태 추출 + 이벤트 송신 서비스 (stateless 파싱 + 최소 상태 저장).

    Attributes:
        _default: 초기 감정. 프로세스 재시작 시 복귀 지점.
        _last_emotion: 마지막으로 확정된 감정. 동일 감정 연속 push_event 시
            로그 소음 감소 판단에 사용되며, 외부에는 노출하지 않음(디버깅용).
        _last_speaking: 마지막 speaking 플래그.
        _send_lock: push_event 호출 직렬화용 asyncio.Lock.
    """

    def __init__(self, default: Emotion = "neutral") -> None:
        """
        Args:
            default: 초기 감정. 기본값 "neutral". 8종 Emotion 중 어느 것이든 가능.
        Raises:
            ValueError: default가 8종 외.
        """
        ...

    def extract_emotion(self, text: str) -> tuple[str, Emotion | None]:
        """완결된 응답 문자열에서 `[emotion:<key>]` 태그를 추출·제거한다.

        Args:
            text: 파싱할 텍스트. **완결된** 스트림 청크(문장 또는 턴 단위)
                여야 한다(§5.2 스트리밍 비보장). 빈 문자열 허용.

        Returns:
            (clean_text, emotion):
              - clean_text: 모든 매치된 `[emotion:<key>]` 토큰이 제거된 텍스트.
                텍스트 앞뒤 공백은 **보존**한다(§6.4).
              - emotion: 첫 번째로 등장한 `_SPOKEN_EMOTIONS` 소속 키(§6.3 D-2).
                유효 발화 키가 없고 알 수 없는 키만 있으면 "neutral"로 폴백.
                `[emotion:study]` 는 `_SPOKEN_EMOTIONS` 에 포함되지 않으므로
                미지 키와 동일하게 처리된다(§6.3 D-6). 태그 자체가 없으면 None.

        복잡도: O(len(text) × |_SPOKEN_EMOTIONS|). `_SPOKEN_EMOTIONS`는 상수
            크기 7이므로 실질 O(n).

        Raises:
            TypeError: text가 str이 아닐 때. 본 모듈은 bytes/None을 수용하지
                않는다(§8).
        """
        ...

    async def push_event(
        self,
        event: AvatarEvent,
        send_text: SendTextCallback,
    ) -> None:
        """WebSocket으로 아바타 상태 이벤트를 송신한다.

        송신 페이로드:
            {
                "type": "avatar-state",
                "emotion": event.emotion,
                "crossfade_ms": event.crossfade_ms,
                "speaking": event.speaking,
            }

        동작:
          (1) self._send_lock 획득(동시 호출 순서 보장, §9 동시성).
          (2) send_text(payload) await.
          (3) 성공 시 self._last_emotion, self._last_speaking 갱신.
          (4) 락 해제.

        이 경로는 `_VALID_EMOTIONS` 집합(8종, study 포함) 기준으로 검증된
        AvatarEvent를 받는다. 즉 백엔드 emitter(M_06 DocumentIngest 등)는
        `AvatarEvent(emotion="study", ...)` 를 직접 만들어 전달할 수 있다(D-6).

        Args:
            event: AvatarEvent. 생성자에서 이미 검증됨(§4.2).
            send_text: dict 페이로드를 받아 비동기 전송하는 콜백.
                WebSocket 핸들러(AppWebSocketHandler)가 per-client로 주입.

        Raises:
            send_text가 던지는 모든 예외를 **그대로 전파**한다(재시도 없음).
            TypeError: event가 AvatarEvent가 아닐 때.
            asyncio.CancelledError: 전파 허용.
        """
        ...

    # 공개 헬퍼 (테스트 및 M_11 ProactiveDispatcher 편의용)
    @property
    def current_emotion(self) -> Emotion:
        """마지막으로 송신 성공한 감정. 한 번도 송신 안 됐으면 default."""
        ...

    @property
    def is_speaking(self) -> bool:
        """마지막으로 송신 성공한 speaking 플래그."""
        ...

    def make_event(
        self,
        emotion: Emotion,
        *,
        crossfade_ms: int = CROSSFADE_DEFAULT_MS,
        speaking: bool = False,
    ) -> AvatarEvent:
        """AvatarEvent 생성 편의 메서드. __post_init__ 검증 경로 재사용.
        호출자가 `AvatarEvent(...)`를 직접 써도 동등."""
        ...
```

**결정 사항 D-7 (§6.3)**: `current_emotion`/`is_speaking` property는 M_11 `ProactiveDispatcher`가 아침 브리핑 직전 "이미 happy 상태면 별도 이벤트 안 보냄" 같은 최적화에 사용 가능하도록 **공개**. 외부 쓰기 금지(read-only property).

---

## 5. 태그 파싱 알고리즘

### 5.1 `extract_emotion` 의사코드

입력 예: `"오늘 [emotion:happy] 기분 좋아, [emotion:sad] 하지만..."`

**판정 원칙**: 본 루틴은 **첫 매칭만 판정한다** — 유효 키든 미지 키든 첫 `[emotion:...]` 발견 시 루프 종료(§6.3 D-3 "첫 등장 기준, 덮어쓰지 않음"; §10.3 A-1 회귀 방지; `src/avatar_state/tag_parser.py` L56~L67).

```text
1. 입력 검증:
   if not isinstance(text, str): raise TypeError
   if text == "": return ("", None)

2. 정규식 컴파일 (모듈 로드 시 1회):
   _TAG_RE = re.compile(r"\[emotion:([a-zA-Z_]+)\]", re.IGNORECASE)
   # 캡처 그룹 1 = key (대소문자 무관, 밑줄 허용)
   # 의도적으로 ASCII만 허용: 한글·숫자 키는 없음(§6.3 D-1)
   # `[emotion:<script>]` 같은 기호는 매치 실패 → 태그 제거도 안 됨(§8 적대적)

3. 전체 매치 목록 수집:
   matches = list(_TAG_RE.finditer(text))

4. 첫 매치로 감정 결정 (첫 등장 기준, §6.3 D-3; §10.3 A-1):
   first_emotion: Emotion | None = None
   for m in matches:
       key = m.group(1).lower()
       if key in _SPOKEN_EMOTIONS:         # <-- study 제외 집합 (D-6)
           first_emotion = key             # 타입 좁힘 (cast 또는 assert)
           break                           # 유효 키 채택 후 즉시 종료
       else:
           logger.warning("unknown emotion tag: %r", m.group(0))
           first_emotion = "neutral"       # 미지 키 → neutral 폴백 (§6.3 D-3)
           break                           # 미지/비발화 키가 먼저 등장하면
           # 뒤의 유효 키는 무시한다(D-3 첫 등장 기준, §10.3 A-1).
           # study 도 동일 경로(D-6): _SPOKEN_EMOTIONS 비소속이므로 이 분기.

5. 모든 태그 제거:
   clean = _TAG_RE.sub("", text)   # 공백은 보존 (§6.4)
   # 주: [emotion:study] 매치는 "미지 키" 로 판정되지만, 정규식 매치 자체는
   # 성공하므로 clean_text 에서는 **제거된다**. 프론트로 원문 [emotion:study]
   # 가 흘러가지 않도록 보장(D-6 안전장치). 5단계는 매치 목록 전체를 지우므로
   # 4단계가 첫 매치에서 조기 종료해도 제거 범위에는 영향이 없다.

6. return (clean, first_emotion)
```

**미지 키 폴백 정교화 (§6.3 D-3)**: "첫 번째로 등장한 키"가 미지 키일 때만 `neutral` 폴백을 적용. 첫 유효 키가 나오기 전에 미지 키가 먼저 나오면 `neutral`로 결정하고, **이후 매치는 — 유효 키든 아니든 — 평가하지 않는다**(루프 조기 종료, 위 4단계 `break` 2회). 이유: 프론트는 "처음 감정"을 먼저 그리기 시작하므로 미지 키를 만나면 즉시 합리적 기본값으로 대체해야 어색한 지연이 없고, 첫 결정을 뒤따르는 태그가 번복하면 프론트 crossfade 연쇄가 발생해 UX 가 깨진다. 유효 키와 미지 키가 섞인 경우의 구체 사례는 §10 테스트 N-4/A-1 에서 고정.

**`study` 특례 (§6.3 D-6)**: `_SPOKEN_EMOTIONS` 집합 검사가 `_VALID_EMOTIONS` 대신 사용되기 때문에, `[emotion:study]` 입력은 루프 4단계에서 `else` 분기로 떨어진다. 따라서 `logger.warning("unknown emotion tag: '[emotion:study]'")` 이 발생하고, 첫 등장이면 `neutral` 폴백이 적용된 뒤 루프가 종료된다. `[emotion:joy]` 와 완전히 같은 궤적.

### 5.2 스트리밍 버퍼링 비보장 (계약)

`extract_emotion`은 **완결된 문자열**을 입력으로 기대한다. 다음 입력은 **지원하지 않으며** 호출자가 버퍼링해야 한다:

- `"지금 [emotion:"` → 매치 실패 → `(원문, None)` 반환. 태그 제거도 안 됨.
- `"happy] 기분 좋아"` → 매치 실패 → 원문 그대로 반환.

호출자(M_05 `GemmaChatAgent`)는 upstream `SentenceDivider`가 **문장 단위**로 쪼갠 청크에 대해 `extract_emotion`을 호출하거나, 턴 종료 시(`EndOfTurn`) 누적 버퍼에 대해 호출하는 경로를 취한다. 부분 매칭 상태 관리 책임을 본 모듈에 넘기지 않는다. 근거:

- **성능**: 본 모듈이 stateful 파서가 되면 인스턴스당 lock + 버퍼 필요 → ≤1ms 목표 위반 가능.
- **재진입성**: stateless 파서는 동시 호출에 안전. 테스트 단순.
- **upstream 선례**: upstream `Live2dModel.extract_emotion`도 완결된 문장 입력을 전제로 `sentence_divider → actions_extractor` 파이프라인에서 호출됨(`transformers.py` L86).

---

## 6. 내부 데이터 구조와 결정 사항

### 6.1 파일 배치

```
src/avatar_state/
├── __init__.py          # AvatarState, AvatarEvent, Emotion re-export
├── types.py             # Emotion Literal, _VALID_EMOTIONS, _SPOKEN_EMOTIONS, AvatarEvent, 상수
├── tag_parser.py        # _TAG_RE, extract_emotion 함수(클래스 밖에도 호출 가능하도록 분리)
├── service.py           # AvatarState 클래스 본체, push_event
└── errors.py            # (선택) 본 모듈 고유 예외 현재 없음. 파일도 생성 안 함.
```

`__init__.py`가 공개 심볼 `{AvatarState, AvatarEvent, Emotion, CROSSFADE_DEFAULT_MS, CROSSFADE_MIN_MS, CROSSFADE_MAX_MS, SendTextCallback}`을 re-export. `_SPOKEN_EMOTIONS`·`_VALID_EMOTIONS` 는 **모듈 내부 심볼**이며 밑줄 접두사로 비공개 표시. 외부는 `from avatar_state import AvatarState`만 사용.

### 6.2 내부 상태

```python
class AvatarState:
    _default: Emotion
    _last_emotion: Emotion
    _last_speaking: bool
    _send_lock: asyncio.Lock
```

- `_last_*`는 송신 **성공 후**에만 갱신. 실패 시 변경 없음. 근거: 실패한 이벤트를 "현재 상태"로 간주하면 프론트와 상태 불일치.
- `_send_lock`은 `asyncio.Lock()`. 초기화는 `__init__`이 아니라 `__init__`에서 바로 생성(현재 이벤트 루프가 있든 없든 Lock 자체는 생성 가능; Python 3.10+).

### 6.3 결정 사항 요약

| ID | 결정 | 근거 |
|---|---|---|
| D-1 | **`[emotion:<key>]` 단일 문법만 지원.** upstream `[<key>]`는 V1 비지원. | 본 프로젝트는 접두형 스키마로 사용자 정의 태그(예: `[gesture:...]`)와 네임스페이스 분리. `docs/CHARACTER_SAESSAGI.md` L57이 `[emotion:happy]`로 고정 예시. |
| D-2 | **다중 태그 중 "첫 번째" 채택.** `Emotion \| None` 단일 반환. | 프론트 `AvatarRenderer.setEmotion()`은 단일 감정을 받음(docs/MODULES.md L401). 스트리밍 중 문장 단위 호출이므로 "한 문장 = 하나의 감정"이 UX와 일치. 마지막 채택 시 LLM이 후행 토큰을 뱉기 전까지 전환이 지연되어 립싱크와 mismatch. |
| D-3 | **미지 감정 키 → `neutral` 폴백 + `logger.warning`.** 2차 폴백은 프론트가 하지 않음. | REQUIREMENTS.md §3.3 + `docs/CHARACTER_SAESSAGI.md` "감정 태그 프로토콜" 명시. 백엔드가 1차 폴백을 끝내면 프론트는 "서버가 준 키를 그대로 그린다"만 책임. 에셋 미보유(기타 감정)는 프론트 `AvatarRenderer`가 독자적으로 `neutral.png` 대체(§1.3 Out-of-Scope 3). |
| D-4 | **WebSocket 메시지 타입: `avatar-state` 독립.** upstream `actions.expressions`에 얹지 않음. | 스프라이트 기반은 오디오와 감정 동기화 제약이 Live2D보다 약함. 독립 타입이 (a) `proactive-notification` 경로에서도 재사용 가능(`push_event` 만으로 감정 변경), (b) 메시지 페이로드 작아 네트워크 효율적, (c) M_12가 단순 switch 처리 가능. |
| D-5 | **`crossfade_ms` 범위 밖 → `ValueError`.** clamp 하지 않음. | "조용한 실패"를 피하고 호출자 버그를 조기 노출. 기본값 사용 시에는 절대 발생하지 않음. |
| D-6 | **`_SPOKEN_EMOTIONS`(7종)과 `_VALID_EMOTIONS`(8종, +study) 분리.** `study` 는 시스템 상태 감정이며 LLM 발화 경로에서는 미지 키 취급. | (1) `study` 는 M_06 DocumentIngest 등 **백엔드 장기 작업** 중 "처리 중" 시각 피드백 전용. 실제 자산(`assets/character/saessagi/study.png`, 책 펼친 새싹이)이 제작·배치된 상태. (2) LLM 이 응답 스트림에 `[emotion:study]` 를 섞으면 UX 가 망가진다(발화 중 "공부 중" 표시). 따라서 파싱 집합에서 의도적으로 **제외**. (3) 한편 `push_event` 타입 검증은 8종 전체를 허용해야 M_06 가 `AvatarEvent(emotion="study", ...)` 로 직접 emit 할 수 있다. (4) 단일 집합(`_VALID_EMOTIONS`)만 두고 "study는 LLM이 쓰지 마세요"를 프롬프트로만 막으면 프롬프트 드리프트 발생 시 방어 불가. **두 집합 분리가 코드 수준 보장**을 제공한다. |
| D-7 | `current_emotion`·`is_speaking` **공개 property**. | M_11 `ProactiveDispatcher`의 동일-이벤트 중복 방지 최적화에 필요. Read-only. (구 D-6 을 리넘버링; 신설 D-6 에 "study 분리"를 부여.) |
| D-8 | **정규식 `[a-zA-Z_]+` (ASCII 알파벳+밑줄) 키만 허용.** | 감정 8종 모두 ASCII. `[emotion:<script>]` 같은 XSS·특수문자 페이로드는 정규식 단계에서 **매치 실패** → 태그 제거도 되지 않고 원문 그대로 반환. 이는 클라이언트 표시 시 escape로 방어(M_12 책임)하는 이중 방어 구조. (구 D-7 을 리넘버링.) |
| D-9 | **`send_text` 예외 시 재시도 없음 + `_last_*` 미갱신.** | 상위 레이어(`AppWebSocketHandler`의 `_route_message`)가 WebSocket 연결 끊김 등을 처리. 본 모듈이 재시도하면 락 장시간 점유로 다른 이벤트 stale. (구 D-8 을 리넘버링.) |

> 리넘버링 주의: D-1~D-5 는 기존 의미·번호 그대로 보존. 신설은 D-6(study 분리) 1건이며, 구 D-6/D-7/D-8 은 각각 D-7/D-8/D-9 로 밀렸다. 테스트·리뷰 문서에서 "D-5 회귀" 같은 표현은 불변.

### 6.4 공백 보존 정책

`re.sub("", text)`로 태그만 제거하므로 **태그 전후의 공백은 보존**한다.

- 입력: `"오늘 [emotion:happy] 기분 좋아"` → 출력 clean: `"오늘  기분 좋아"` (공백 2개, 정상).
- 입력: `"[emotion:happy]안녕"` → 출력 clean: `"안녕"` (공백 없음).

공백 정규화(연속 공백 축약 등)는 **수행하지 않는다**. 근거: TTS(M_04)가 수신 전 자체 정규화 파이프라인을 가지며, 본 모듈이 공백 정규화를 시작하면 원문-표시 텍스트 길이가 달라져 립싱크 타이밍 오차를 일으킨다.

---

## 7. 송신 페이로드 스키마 (JSON)

`push_event`가 `send_text`에 전달하는 dict:

```json
{
  "type": "avatar-state",
  "emotion": "happy",
  "crossfade_ms": 250,
  "speaking": true
}
```

- `type`: 고정 문자열 `"avatar-state"`. 다른 값 금지.
- `emotion`: **8종** 중 하나(neutral/happy/surprised/sad/worried/thinking/sleepy/study). 프론트는 이 값을 그대로 `AvatarRenderer.setEmotion()`에 전달.
- `crossfade_ms`: 200~300 정수.
- `speaking`: boolean. `study` 이벤트에서는 관례상 `false` 로 emit 하되, 본 스펙은 강제하지 않는다(M_12 는 `speaking` 이 true 여도 study 이미지에 펄스를 적용하면 됨).

**M_12 수신 핸들러와의 계약**: 프론트는 이 네 키만 신뢰하고, 추가 키가 있으면 무시한다. 본 스펙은 향후 확장 시 키 추가만 허용하며 **기존 키 의미 변경·제거는 브레이킹 체인지**로 취급한다.

`specs/M_01_AppCore_SPEC.md` §C(L471)의 "타입만 예약" 상태를 본 스펙이 확정. M_01 수정은 필요 없다(§13 배선 참조).

---

## 8. 에러 처리 정책

| 상황 | 반응 | 호출자 가시성 |
|---|---|---|
| `extract_emotion(text=None)` | `TypeError("text must be str")` | 테스트에서만 검증. 프로덕션 호출 경로(M_05)는 str 전달 보장 |
| `extract_emotion(text="")` | `("", None)` 반환. 에러 없음 | 정상 |
| `extract_emotion` 매치 키가 `_SPOKEN_EMOTIONS` 외 (study 포함) | 첫 등장 시 `logger.warning("unknown emotion tag: %r", raw_tag)` + `neutral`로 폴백(§5.1, D-6) | 로그 |
| `extract_emotion` 태그 자체 없음 | `(text, None)` 반환. 로그 없음 | 정상 |
| `AvatarEvent(emotion="joy")` | `__post_init__`에서 `ValueError(f"emotion must be one of {_VALID_EMOTIONS}, got 'joy'")` | 호출자 예외 |
| `AvatarEvent(emotion="study")` | **정상 생성**. push_event 경로는 study 허용 (D-6) | 정상 |
| `AvatarEvent(crossfade_ms=150)` | `ValueError(f"crossfade_ms must be in [200,300], got 150")` | 호출자 예외 |
| `AvatarEvent(crossfade_ms=350)` | 동일 `ValueError` | 호출자 예외 |
| `AvatarEvent(speaking="yes")` | 타입 힌트 위반이나 런타임 검증은 **하지 않음**(truthy 평가). mypy로 사전 차단 | mypy 단계 |
| `AvatarState.__init__(default="joy")` | `ValueError` | 호출자 예외 |
| `AvatarState.__init__(default="study")` | **정상**. 생성 후 current_emotion == "study" | 정상 (테스트로만 의미 있음; 통상 "neutral" 권장) |
| `push_event(event=None)` | `TypeError("event must be AvatarEvent")` | 호출자 예외 |
| `push_event` 내 `send_text` 예외 (예: WebSocket 끊김) | 예외 **전파**. `_last_*` 미갱신. 로그는 `logger.error` 1회 | 상위 핸들러가 처리 |
| `push_event` 내 `asyncio.CancelledError` | 전파. 락은 `finally`에서 해제(§9) | 정상 |
| 매우 긴 입력(10KB 이상) | 정상 처리. regex는 linear. 로그 없음 | §9 성능 |

**원칙**: 태그 파싱은 **방어적**으로(사용자 입력이 아니라 LLM 출력이지만 신뢰 경계로 취급), 이벤트 전송은 **failure-fast**로. 조용한 실패는 안 만든다.

---

## 9. 성능·메모리·동시성 요구사항

### 9.1 성능

| 지표 | 요구 | 근거 |
|---|---|---|
| `extract_emotion` 1KB 입력 | ≤ 1 ms (median, p95 ≤ 2 ms) | REQUIREMENTS.md §9 응답 지연. `re.finditer` + `sub`는 text 길이에 linear |
| `extract_emotion` 10KB 입력 | ≤ 10 ms | 동일 근거. 벤치마크 기준점 |
| `push_event` 자체 오버헤드 | < 0.1 ms (send_text 호출 제외) | dict 생성 + lock acquire/release만 |
| 모듈 import 시간 | < 50 ms | re.compile 1회, 동시 lock 생성 없음 |

### 9.2 메모리

- `AvatarState` 인스턴스 오버헤드: **≤ 1 KB**. `_last_emotion`/`_last_speaking`/`_default`/Lock 객체만.
- `AvatarEvent` 인스턴스: **≤ 200 B** (slots=True).
- `_TAG_RE`: 모듈 전역, ≤ 2 KB.

### 9.3 동시성

- `push_event`는 `asyncio.Lock`으로 직렬화. 동시 N건 호출 시 전송 순서 = 호출 순서.
- `extract_emotion`은 **순수 함수**(상태 read 없음) → 락 없음, 재진입 안전.
- `current_emotion`/`is_speaking` 읽기는 GIL 하 단일 bool/str read → 락 없음(race 있어도 한 값은 보장).

**결정**: 내부 `asyncio.Lock`은 `__init__`에서 `asyncio.Lock()`으로 즉시 생성. 이벤트 루프에 바인딩되는 시점은 첫 `acquire()` 호출이므로 테스트에서 `AvatarState()`를 sync fixture로 생성해도 문제 없다.

---

## 10. 테스트 케이스

경로: `tests/avatar_state/test_*.py`. pytest + `pytest-asyncio`. 합계 **정상 7 + 엣지 7 + 적대적 4 = 18건**(M_08 DoD 하한: 정상 ≥5, 엣지 ≥5, 적대적 ≥3 충족).

### 10.1 정상 케이스 (≥5)

**N-1. 단일 태그 정상 추출**
- 입력: `"[emotion:happy] 안녕하세요"`.
- 기대: `clean == " 안녕하세요"`, `emotion == "happy"`.

**N-2. 태그 없음 / 평범한 텍스트**
- 입력: `"오늘 날씨 좋아요"`.
- 기대: `clean == "오늘 날씨 좋아요"`, `emotion is None`.

**N-3. 다중 태그 — 첫 번째 채택 (§6.3 D-2 회귀 방지)**
- 입력: `"[emotion:happy] 좋다 [emotion:sad] 슬프다"`.
- 기대: `clean == " 좋다  슬프다"`, `emotion == "happy"`.

**N-4. 대소문자 혼용 (`re.IGNORECASE`)**
- 입력: `"[EMOTION:Happy] 안녕 [Emotion:SLEEPY]"`.
- 기대: `clean == " 안녕 "`, `emotion == "happy"` (lower 정규화). 7종 모두 통과.

**N-5. `push_event` 정상 송신 + 상태 갱신**
- 준비: `AsyncMock()` send_text.
- 입력: `AvatarState().push_event(AvatarEvent("happy", speaking=True), send_text)`.
- 기대:
  - send_text가 정확히 1회 호출됨.
  - 인자 == `{"type":"avatar-state","emotion":"happy","crossfade_ms":250,"speaking":True}`.
  - `state.current_emotion == "happy"`, `state.is_speaking is True`.

**N-6. `make_event` 편의 메서드 기본값**
- `AvatarState().make_event("sleepy")` → `AvatarEvent(emotion="sleepy", crossfade_ms=250, speaking=False)`.

**N-7. 동시 `push_event` 순서 보장 (§9.3 회귀 방지)**
- `asyncio.gather(push_event(happy), push_event(sad), push_event(neutral))` 순차 호출 → send_text 호출 순서가 반드시 `happy → sad → neutral`(락으로 직렬화). 테스트는 mock에 도착한 인자 시퀀스를 검증.

**N-8. `push_event` 로 `study` 시스템 상태 직접 emit (§6.3 D-6 회귀 방지)**
- 준비: `AsyncMock()` send_text.
- 입력: `AvatarState().push_event(AvatarEvent("study", crossfade_ms=250, speaking=False), send_text)`.
- 기대:
  - `AvatarEvent("study", ...)` 생성이 `ValueError` 없이 성공.
  - send_text 가 1회 호출되고 페이로드 `emotion` 필드가 `"study"` 문자열.
  - `state.current_emotion == "study"`, `state.is_speaking is False`.
  - `_VALID_EMOTIONS` 가 `study` 를 포함함을 단언.

### 10.2 엣지 케이스 (≥5)

**E-1. 빈 문자열**
- 입력: `""`.
- 기대: `("", None)`. 에러 없음.

**E-2. 태그만 있는 문자열**
- 입력: `"[emotion:happy]"`.
- 기대: `clean == ""`, `emotion == "happy"`.

**E-3. 중첩 브래킷 `[[emotion:happy]]`**
- 입력: `"[[emotion:happy]]"`.
- 기대: 내부 `[emotion:happy]`만 제거 → `clean == "[]"`, `emotion == "happy"`. 외부 브래킷은 남는다(정규식 non-greedy + 고정 문법).

**E-4. 미완결 태그 `[emotion:ha`**
- 입력: `"안녕 [emotion:ha 기분"`.
- 기대: 매치 실패 → `clean == "안녕 [emotion:ha 기분"` (원문 그대로), `emotion is None`. 로그 없음.

**E-5. 한글 사이 삽입**
- 입력: `"안녕[emotion:happy]하세요"`.
- 기대: `clean == "안녕하세요"`, `emotion == "happy"`. 공백 보존 정책 검증(태그 양쪽 공백 없음).

**E-6. `crossfade_ms` 경계값**
- `AvatarEvent("happy", crossfade_ms=200)` 생성 성공.
- `AvatarEvent("happy", crossfade_ms=300)` 생성 성공.
- `AvatarEvent("happy", crossfade_ms=199)` → `ValueError`.
- `AvatarEvent("happy", crossfade_ms=301)` → `ValueError`.

**E-7. `push_event` 실패 시 상태 불변**
- send_text가 `ConnectionError` 발생.
- 기대: `push_event`가 `ConnectionError` 전파, `state.current_emotion`이 호출 전 값 유지.

**E-8. `extract_emotion("[emotion:study] 하이")` 는 미지 키 취급 (§6.3 D-6 회귀 방지)**
- 입력: `"[emotion:study] 하이"`.
- 기대:
  - 반환 `(clean, emotion) == (" 하이", "neutral")`. 즉 `emotion` 필드는 **None 이 아니라 "neutral"** — 첫 등장 미지 키 폴백(D-3)과 동일 규칙.
  - `caplog` 에 `WARNING` 레벨 1건이 기록되며 메시지에 `"[emotion:study]"` 문자열 포함.
  - `clean_text` 에서 `[emotion:study]` 토큰은 **제거됨**(정규식은 매치, 의미만 미지 키로 취급).
- 추가 서브케이스: `extract_emotion("[emotion:study]")` → `("", "neutral")`, 같은 WARNING 1건.

### 10.3 적대적 케이스 (≥3)

**A-1. 알 수 없는 감정 키 + `neutral` 폴백 (§6.3 D-3 회귀 방지)**
- 입력: `"[emotion:joy] 기분 좋아"` (joy는 upstream 키지만 본 프로젝트 비지원).
- 기대: `clean == " 기분 좋아"`, `emotion == "neutral"`. `logger.warning`가 1회 발생하며 `"joy"` 문자열 포함.
- 추가: `"[emotion:joy] [emotion:happy]"` → `emotion == "neutral"` (첫 등장 기준 D-3, 유효 키가 뒤에 있어도 덮어쓰지 않음). 로그 1회.

**A-2. XSS 시도 `[emotion:<script>]`**
- 입력: `"[emotion:<script>alert(1)</script>] 안녕"`.
- 기대: 정규식 `[a-zA-Z_]+` 매치 실패 → 태그가 **제거되지 않고 원문 그대로** 반환. `emotion is None`. 로그 없음(매치 없었으므로 미지 키도 아님).
- 추가: 이 결과가 프론트에 도달해도 M_12의 HTML escape가 2차 방어(본 모듈 책임 아님). 본 케이스는 "정규식이 악성 키로 넓어지지 않았는지"만 검증.

**A-3. 매우 긴 입력 (10 KB 이상, 태그 100개)**
- 입력: `("[emotion:happy] 문장 " * 500)` (약 10 KB, 태그 500개).
- 기대: `extract_emotion` 완료 시간 ≤ 20 ms (로컬 CI 기준, `time.perf_counter`로 측정). `emotion == "happy"`. 프로세스 메모리 증가 < 5 MB.

**A-4. 비-문자열 입력**
- 입력: `extract_emotion(None)`, `extract_emotion(b"[emotion:happy]")`, `extract_emotion(123)`.
- 기대: 각각 `TypeError`. 메시지에 "text must be str" 포함.

### 10.4 테스트 지원 도구

- `pytest-asyncio`의 `@pytest.mark.asyncio` 사용.
- `send_text`는 `unittest.mock.AsyncMock()`로 대체.
- 로깅 검증은 `caplog` fixture로 `WARNING` 레벨 메시지 캡처.
- 성능 테스트(A-3)는 `pytest.mark.slow` 마커로 분리, 기본 CI에서만 실행.

---

## 11. Definition of Done

### 11.1 공통 (CLAUDE.md "산출물 체크리스트")

- [ ] `specs/M_08_AvatarState_SPEC.md` (본 문서) 사용자 승인.
- [ ] `src/avatar_state/` 하위 4개 파일(`__init__.py`, `types.py`, `tag_parser.py`, `service.py`) 구현.
- [ ] `tests/avatar_state/test_*.py` 테스트 통과: 정상 ≥5, 엣지 ≥5, 적대적 ≥3 (실제 18건, study 케이스 N-8/E-8 포함).
- [ ] `ruff format .`, `ruff check .`, `mypy src/`, `pytest tests/avatar_state/ -v` 모두 통과.
- [ ] 테스트 커버리지 ≥ 70% (본 모듈 파일 한정).
- [ ] `reviews/M_08_AvatarState_REVIEW.md`에 Critic PASS 기록.
- [ ] `docs/MODULES.md` M_08 행 상태가 `✅ DONE`으로 갱신.

### 11.2 M_08 고유 (docs/MILESTONES.md L120~L127 기준)

- [ ] `extract_emotion("오늘 [emotion:happy] 기분 좋아")` → `("오늘  기분 좋아", "happy")` (공백 2개 보존).
- [ ] 8종 감정(`neutral, happy, surprised, sad, worried, thinking, sleepy, study`) 외 값 → `__post_init__`에서 `ValueError`.
- [ ] **`_SPOKEN_EMOTIONS` 외 키(= `study` 또는 기타) → `"neutral"` 폴백 + `logger.warning` 1회**(D-6 회귀 방지).
- [ ] `extract_emotion("[emotion:study]")` 의 `emotion` 반환값이 `"neutral"` 이며 `"study"` 가 **아님**을 단언.
- [ ] `push_event(AvatarEvent(emotion="study", ...))` 가 예외 없이 동작하고 페이로드 `emotion` 필드 == `"study"`.
- [ ] `push_event` 호출 시 송신 페이로드가 §7 스키마와 정확히 일치(`{type, emotion, crossfade_ms, speaking}` 4키, 추가/누락 없음).
- [ ] `push_event` 연속 호출 시 내부 `asyncio.Lock`으로 전송 순서 = 호출 순서(N-7 테스트).
- [ ] `AvatarEvent.crossfade_ms` 범위 밖 → `ValueError` (clamp 하지 않음, D-5 회귀 방지 테스트).
- [ ] upstream `[<key>]` 단일 키 문법이 **매치되지 않음**을 테스트로 증명(`"[happy]"` → `(원문, None)`).
- [ ] `AppServiceContext.avatar_state` 주입 경로가 `src/app/service_context.py::load_app_services`에 1줄 추가되며, M_01 공개 API 시그니처는 **변경 없음**(§13).

---

## 12. 의존성

### 12.1 Python 패키지

| 패키지 | 버전 | 용도 | 추가 여부 |
|---|---|---|---|
| (표준) `re` | — | 태그 정규식 | 기존 |
| (표준) `dataclasses` | — | `AvatarEvent`, slots | 기존 |
| (표준) `asyncio` | — | `Lock`, async 시그니처 | 기존 |
| (표준) `logging` | — | warn/error 로깅 (loguru와 호환: M_01 init_logging이 stdlib logging도 intercept) | 기존 |
| (표준) `typing` | — | `Literal`, `Callable`, `Awaitable` | 기존 |
| `pytest-asyncio` (test-only) | 기존 | async 테스트 | 기존(M_07/M_09에서 이미 사용) |

**새 의존성 0**. `pyproject.toml` 수정 없음. `scripts/bundle_deps.sh` 수정 없음.

### 12.2 내부 모듈 의존

- 런타임: **없음**. M_01/M_05/M_06/M_11 중 어느 모듈도 M_08을 import하지 않은 상태에서도 독립 실행 가능.
- 역의존: M_01(`AppServiceContext.avatar_state` 필드 배선, §13), M_05(`GemmaChatAgent.chat`이 `extract_emotion` 호출 — M_05 SPEC에서 이미 문서화되어 있다고 가정), **M_06 DocumentIngest(`study` 상태 emitter — 아래 §12.3 연동 노트)**, M_11(`ProactiveDispatcher`가 특정 프로액티브 토픽에서 감정 힌트를 추가 송신할 때 선택적으로 호출).

### 12.3 M_06 DocumentIngest 연동 노트 (비고)

M_06 DocumentIngest 는 HWPX/PDF/MD 파싱·청킹·임베딩이 수초~수분 걸리는 장기 작업이다. UX 관점에서 "처리 중" 시각 피드백이 필요하며, 본 모듈의 `study` 감정이 그 용도다. M_06 구현 시 예상 경로:

```
# (의사코드, 실제 배선은 M_06 단계)
await avatar_state.push_event(
    AvatarEvent(emotion="study", crossfade_ms=250, speaking=False),
    send_text,
)
try:
    await ingest_pipeline.run(document_paths)
finally:
    await avatar_state.push_event(
        AvatarEvent(emotion="neutral", crossfade_ms=250, speaking=False),
        send_text,
    )
```

- 인제스트 시작 시 `study` 이벤트 1건을 emit 해 프론트가 책 펼친 새싹이(`study.png`) 로 전환하도록 지시한다.
- 종료(성공/실패 무관)에는 `neutral` 로 복귀한다. 실패 로그·토스트는 M_06 자체 책임이며 M_08 과 무관.
- **실제 배선·라이프사이클 관리(취소 처리, 중첩 인제스트 큐잉, 진행률 표시 등)는 M_06 단계에서 수행하며 M_08 범위 밖.** 본 모듈은 `study` 를 타입 수준에서 허용하고 파싱 경로에서 차단하는 두 축만 보장한다.

---

## 13. 배선 범위 결정 (AppServiceContext 연결)

### 13.1 결정: M_08 단독 구현 범위에 포함

M_01 `AppServiceContext.avatar_state: AvatarState | None` **필드 슬롯은 이미 존재**(`specs/M_01_AppCore_SPEC.md` §"서비스 컨텍스트" L196). M_01을 수정할 필요는 없고, 단지 `load_app_services` 메서드 내부에서 `None` 대신 `AvatarState(default="neutral")`을 할당하는 **1줄 추가**만 수행한다.

**M_09 CalendarService 선례**와 동일 패턴:

```python
# src/app/service_context.py::load_app_services (기존)
async def load_app_services(self, app_config: AppConfig) -> None:
    ...
    self.calendar_service = CalendarService(
        db_path=app_config.paths.calendar_db_path,
        default_tz=_KST,
    )
    # +++ M_08 추가 1줄 +++
    self.avatar_state = AvatarState(default="neutral")
    ...
```

### 13.2 `send_text` 주입 경로

`AvatarState.push_event(event, send_text)`의 `send_text`는 **호출 시점**에 전달된다. M_01 `AppWebSocketHandler`가 per-client `send_text`를 보유하므로, 호출자(M_05 `GemmaChatAgent` 또는 M_06 DocumentIngest 또는 M_11 `ProactiveDispatcher`)가 핸들러 경유로 전달한다. 본 모듈은 `send_text`를 생성자에서 저장하지 **않는다**(stateless 주입 패턴). 이유:

- 단일 `AvatarState` 인스턴스가 여러 WebSocket 클라이언트에 재사용될 가능성(테스트·향후 확장) 대비.
- 프로액티브 이벤트는 클라이언트 연결 전이라도 큐잉되어야 할 수 있음(M_11이 독자적으로 dropping 결정).

### 13.3 M_08 본 모듈이 수정하지 않는 것

- `specs/M_01_AppCore_SPEC.md` 본문.
- `src/app/service_context.py`의 `AppServiceContext` 필드 선언(이미 존재).
- `src/app/ws_handler.py`.
- `src/tool_router/*` 파일.

**M_08 builder가 수정하는 것**:

1. `src/app/service_context.py::load_app_services` 내 1줄(`self.avatar_state = AvatarState(default="neutral")`).
2. 위 수정에 대한 기존 `test_service_context.py` 업데이트(`avatar_state is not None` 단언 추가). 구현자 판단으로 1~2줄.
3. 신규: `src/avatar_state/**`, `tests/avatar_state/**`.

### 13.4 호출 경로 다이어그램

```
(LLM 스트리밍)
M_05 GemmaChatAgent.chat()
   └── sentence buffer 완결
         └── AvatarState.extract_emotion(sentence) → (clean, emotion)
              └── if emotion: AvatarState.push_event(AvatarEvent(emotion, speaking=True), ws_send_text)
                     └── send_text({"type":"avatar-state", ...})  ── WebSocket ──▶  M_12 AvatarRenderer.setEmotion()

(시스템 상태 — M_06 DocumentIngest, §12.3)
M_06 DocumentIngest.ingest()
   ├── AvatarState.push_event(AvatarEvent("study", speaking=False), ws_send_text)   # 시작
   ├── (파싱·청킹·임베딩 수 초~수 분)
   └── AvatarState.push_event(AvatarEvent("neutral", speaking=False), ws_send_text) # 종료

(프로액티브)
M_11 ProactiveDispatcher.emit(topic="morning_briefing")
   └── AvatarState.push_event(AvatarEvent("happy", speaking=False), ws_send_text)
```

M_05·M_06·M_11은 자체 SPEC에서 "본 모듈이 M_08을 호출한다"는 구체 API를 다루며, 본 스펙은 **M_08이 호출 가능한 표면만** 고정한다.

---

## 14. 스펙 외 사항 (명시적 제외, 오해 방지용)

본 모듈의 책임이 **아닌** 항목을 열거. 검토자는 이 목록에 해당하는 문제를 M_08의 결함으로 간주하지 않는다.

1. **감정별 PNG 파일 제작·배치**: 일러스트레이터 작업. `docs/CHARACTER_SAESSAGI.md` 지침. 8종(`neutral`, `happy`, `surprised`, `sad`, `worried`, `thinking`, `sleepy`, `study`) 모두 배치됨. 본 모듈은 파일 유무에 영향받지 않는다.
2. **프론트 `AvatarRenderer.setEmotion` 구현**: M_12 담당. crossfade·scaleY 숨쉬기·깜빡임·opacity 펄스는 모두 프론트 책임. `study` 도 예외 없이 단일 PNG 스왑으로 처리.
3. **미보유 감정 PNG에 대한 2차 폴백**: 프론트가 `neutral.png`로 대체. 백엔드는 간섭하지 않음(§1.3 Out-of-Scope 3, D-3 근거).
4. **LLM system prompt에 감정 태그 규칙 주입**(특히 "`study` 는 쓰지 마세요" 지시): M_05 `GemmaChatAgent` 또는 `character_config.persona_prompt`(conf.yaml) 책임. 본 모듈은 프롬프트 지시 없이도 `_SPOKEN_EMOTIONS` 분리로 **코드 수준 방어**를 제공(D-6).
5. **TTS 문장 전처리(태그 제거)**: upstream `tts_preprocessor.tts_filter`가 `ignore_brackets=True` 옵션으로 대괄호를 건너뛰도록 이미 설정됨(M_04 범위). 본 모듈의 `extract_emotion`과는 **독립 경로**. 이중 제거가 되어도 부작용은 "이미 제거된 텍스트에 정규식 매치 0건" 뿐.
6. **히스토리 저장 시 태그 포함 여부**: upstream `chat_history_manager`가 raw 텍스트(태그 포함)를 저장하는지, clean 텍스트를 저장하는지는 본 모듈이 결정하지 않음. M_01/M_05 정책.
7. **proactive-notification 메시지 타입**: `specs/M_01_AppCore_SPEC.md` §C에 예약됨. M_11이 발송. 본 모듈은 `avatar-state`와 `proactive-notification`의 상호 순서를 보장하지 않는다(M_11이 결정).
8. **연속 감정 억제**(같은 감정 반복 호출 시 첫 이벤트만 보내기): 호출자가 `current_emotion` property를 읽어 판단. 본 모듈은 항상 호출 횟수만큼 송신(§6.2).
9. **세션 간 상태 지속**: 프로세스 재시작 시 `_default`로 복귀. 파일/DB 영속화 없음. V1 범위 밖.
10. **감정 변화 애니메이션 곡선**(linear vs ease-in-out): 프론트 CSS `transition-timing-function` 선택. 백엔드는 `crossfade_ms` 시간만 전달.
11. **M_06 DocumentIngest 실제 배선**: §12.3 노트는 **예시**다. 인제스트 시작/종료 콜백, 예외 시 `neutral` 복귀, 중첩 인제스트 큐잉, 취소 처리 등 라이프사이클은 M_06 SPEC 에서 결정하며 M_08 은 관여하지 않는다.

---

## 15. 부록 — upstream 경로·증적

본 스펙 작성 중 `/mnt/c/projects/ai-assistant/upstream/Open-LLM-VTuber/src/open_llm_vtuber/` 아래 다음 파일을 직접 읽어 결정을 정당화했다:

- `live2d_model.py` L146~L172: `Live2dModel.extract_emotion` 의 브래킷 스캔 알고리즘. 본 모듈은 **정규식 기반**으로 재구현해 복잡도와 가독성을 개선(§5.1).
- `live2d_model.py` L174~L194: `remove_emotion_keywords` 의 "lower 사본 위치 탐색" 트릭 — 본 모듈은 단일 정규식으로 대체.
- `agent/transformers.py` L58~L100: `actions_extractor` — SentenceDivider 파이프라인 후단에서 문장 단위로 호출된다는 실재 경로 확인. `extract_emotion`이 **완결된 문장**에 적용된다는 계약(§5.2)의 근거.
- `agent/output_types.py` L6~L17: `Actions.expressions: Optional[List[str] \| List[int]]` — upstream은 감정을 audio payload의 하위 필드로 실음. 본 프로젝트는 독립 `avatar-state` 타입으로 분리(§6.3 D-4 근거).
- `utils/stream_audio.py` L27~L82: `prepare_audio_payload` — upstream의 송신 메시지 타입 `"audio"`와 필드 구조 확인. `avatar-state` 이름이 upstream 기존 타입과 **충돌하지 않음** 재확인.
- `conversations/types.py` L8: `WebSocketSend = Callable[[str], Awaitable[None]]` — upstream은 str을 받지만, 본 프로젝트는 `src/tool_router/screenshot.py` L17의 `SendTextCallback = Callable[[dict[str, Any]], Awaitable[None]]`로 통일(§4.3 주석 근거).
- `websocket_handler.py` L14~L98: upstream 메시지 타입 전수. `avatar-state`가 기존 타입과 겹치지 않음 확인(rg 조회 결과 0건).

본 스펙이 **upstream 파일을 수정하지 않는다**는 CLAUDE.md 규칙을 준수함을 명시한다.

---

## 16. docs/MODULES.md 초안과의 일치·수정 사항

`docs/MODULES.md` L281~L304의 M_08 초안과 본 스펙의 차이점을 명시한다. M_07·M_09 선례에 따라 builder가 구현 완료 후 해당 문서의 **비고**에 각주를 추가한다.

| 항목 | 초안 | 본 스펙 | 수정 근거 |
|---|---|---|---|
| 공개 시그니처 | `Callable`(제네릭 없음) | `SendTextCallback = Callable[[dict[str, Any]], Awaitable[None]]` | `src/tool_router/screenshot.py` L17 기존 컨벤션과 통일 |
| `extract_emotion` 반환 | `Emotion \| None` | 동일 (유지) | 변경 없음 |
| 다중 태그 정책 | 명시 없음 | **첫 번째 채택** 확정 | §6.3 D-2 근거 |
| `crossfade_ms` 검증 | 200~300 (주석) | **ValueError 강제** (clamp 금지) | §6.3 D-5 근거 |
| 감정 키 정규식 | 명시 없음 | `[a-zA-Z_]+` (ASCII만) | §6.3 D-8 근거 |
| 유효 감정 수 | 7종 | **8종 (study 추가, LLM 발화용 7종 + 시스템 상태용 1종)** | §6.3 D-6 근거, `docs/CHARACTER_SAESSAGI.md` 표정표 갱신 |
| 추가 심볼 | — | `current_emotion`, `is_speaking`, `make_event` property/helper | §6.3 D-7 근거 |

**docs/MODULES.md 문서 갱신 의무**: M_08 builder는 구현 완료 후 M_07 선례에 따라 `docs/MODULES.md` 비고란에 "§16 참조" 각주 추가 + 상태 `✅ DONE` 갱신.
