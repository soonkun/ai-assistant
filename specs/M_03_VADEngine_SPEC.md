# M_03 VADEngine — 스펙

## 목적과 범위

### 목적
음성 대화에서 "사용자가 지금 말하고 있는가"를 판정하고, 말하기 시작·끝 신호(`<|PAUSE|>`·`<|RESUME|>`)와 발화 구간 오디오 바이트를 상위 레이어로 넘긴다. 본 프로젝트는 upstream `vad/silero.py`(Silero VAD + 자체 StateMachine)를 **무수정** 재사용한다. 본 모듈이 하는 일은 다음 세 가지뿐이다.

1. `conf.yaml`의 `character_config.vad_config`를 upstream `VADFactory.get_vad_engine("silero_vad", **kwargs)`가 수용하는 형태로 배선한다.
2. upstream 엔진의 즉시 로드(생성자 시점 `load_silero_vad()` 호출)와 네트워크 의존성을 파악해 **오프라인 번들**이 제대로 작동함을 검증한다.
3. M_01 `AppServiceContext.vad_engine` 슬롯에 upstream 팩토리 산출물(`SileroVADEngine`)을 그대로 주입한다.

### 범위 (In-Scope)
1. `conf.yaml` VAD 섹션의 **실제 키 이름**을 확정하고 문서화(`prob_threshold`, `db_threshold`, `required_hits`, `required_misses`, `smoothing_window`, `orig_sr`, `target_sr`).
2. `vad_model: "silero_vad"` 활성화(M_01 기본 설정의 M_03 활성화 플래그를 `null` → `"silero_vad"`로 전환).
3. Silero VAD 모델 파일(`silero_vad.onnx` 또는 torch.jit `silero_vad.jit`)의 **오프라인 번들 배치 경로 확정**과 런타임 로드 경로 재지정(네트워크 차단 환경에서 `silero_vad` 파이썬 패키지가 모델을 찾게 하는 설정).
4. M_01 `AppServiceContext.load_from_config`가 upstream `init_vad()`를 **그대로** 호출해 `self.vad_engine`에 `SileroVADEngine`을 넣는지 확인(배선 회귀 방지 테스트).
5. upstream 파일 **무수정** 보증(파일 해시 회귀 테스트).
6. 최소한의 회귀·배선 테스트 (정상 ≥5, 엣지 ≥5, 적대적 ≥3). upstream 내부 StateMachine 로직 자체는 재검증하지 않는다.

### 범위 외 (Out-of-Scope, 명시적 제외)
- **upstream `silero.py` 파일 수정**. 어떤 이유에서도 금지. 필요시 `docs/CHANGE_REQUESTS.md` 경유.
- **자체 VAD 엔진 구현**(WebRTC VAD, py-webrtcvad 등). 본 프로젝트는 Silero VAD만 사용.
- **VAD→ASR 파이프라이닝 · `<|PAUSE|>`/`<|RESUME|>` 라우팅**. upstream `websocket_handler.py` L478~L511의 오디오 핸들러가 담당(M_01 REUSE).
- **인터럽트 처리 자체**. M_05 LLMAgent·`conversation_handler`가 담당. 본 모듈은 이벤트 신호만 생성한다.
- **스트리밍 오디오 디코딩·16k 리샘플링**. upstream 오디오 파이프라인이 이미 16kHz float32 배열을 공급한다고 가정. 리샘플링 책임은 M_03 밖.
- **튜닝 파라미터의 한국어·화자 최적화**. upstream 기본값(`prob_threshold=0.4`, `db_threshold=60`, `required_hits=3`, `required_misses=24`, `smoothing_window=5`)을 V1 기본값으로 채택한다. 향후 조정은 `CHANGE_REQUESTS.md`.
- **VAD 비활성화 모드**. V1은 `vad_model: "silero_vad"` 고정. `null`은 개발용 디버그 전용으로만 허용하고 프로덕션 프로파일에서는 금지.

---

## 요구사항 연결

| REQUIREMENTS.md 항목 | M_03 기여 |
|---|---|
| §0 완전 오프라인 / Windows 10/11 | Silero VAD ONNX(또는 JIT) 가중치를 `assets/models/silero-vad/`에 사전 배치. `silero_vad` 파이썬 패키지의 런타임 네트워크 호출 경로가 없는지 검증 |
| §1.1 VAD로 발화 구간만 전송 | upstream `SileroVADEngine.detect_speech`가 `<|PAUSE|>`·`<|RESUME|>` 바이트 마커와 누적 발화 바이트를 yield. 본 모듈은 이 엔진이 `AppServiceContext.vad_engine`에 제대로 배선됐는지 보증 |
| §1.1 전이중(Full Duplex) | `<|PAUSE|>` 마커가 발화 시작 시 즉시 방출되므로 upstream 인터럽트 파이프라인이 TTS 중단 신호를 상위로 전달 가능. 본 모듈은 이 동작을 **변경하지 않는다** |
| §9 메모리: VAD ~40 MB | ARCHITECTURE.md §6.1 예산표. 가중치 ~1.8MB + onnxruntime/torch 상주 오버헤드 |
| §9 외부 네트워크 호출 금지 | `silero_vad.load_silero_vad`는 **기본적으로 로컬 캐시 또는 패키지 번들 경로에서 가중치를 로드**한다(후술). 빌드 머신에서 `silero_vad` wheel을 `pip download`로 수집하며, 첫 호출 시 사내 PC에서 인터넷을 찾지 않도록 사전 로드 검증 스크립트(`scripts/verify_offline.ps1`)를 확장 |
| §9 기동 시간 15초 | upstream `SileroVADEngine.__init__`은 `load_silero_vad()`를 **즉시** 호출한다. 측정치: ≤ 300 ms (로컬 파일, NVMe). 전체 기동 예산 내 |

---

## upstream 재사용 분석

### 분류: REUSE (무수정)

**결정 근거**: `docs/ARCHITECTURE.md` §4 표에서 "VAD (`vad/silero.py`) | REUSE (무수정) | 설정만 튜닝"로 이미 확정됨. upstream 구현은 (a) 발화 시작·끝 마커를 바이트로 방출해 `websocket_handler.py`의 `b"<|PAUSE|>"`/`b"<|RESUME|>"` 비교에 맞게 이미 호환되고, (b) 한국어/영어/다언어 구분 없이 동작하며, (c) ONNX/JIT 어느 쪽으로도 동작해 CPU-only 환경에도 적합하기 때문이다. 재구현 동기 0.

### REUSE (무수정 호출)

| upstream 경로 | 심볼 | 사용 방식 |
|---|---|---|
| `src/open_llm_vtuber/vad/vad_interface.py` | `VADInterface` (abstract, `detect_speech(audio_data: bytes) -> Iterable[bytes]`) | 본 프로젝트는 인터페이스를 **import하지 않는다**. upstream 내부에서만 쓰임. `AppServiceContext.vad_engine` 필드 타입 힌트는 upstream과 동일하게 `VADInterface \| None`(M_01 스펙 유지) |
| `src/open_llm_vtuber/vad/silero.py` | `VADEngine` (= `SileroVADEngine`), `SileroVADConfig` (pydantic, **class 내부용**), `StateMachine`, `State` | upstream `VADFactory.get_vad_engine("silero_vad", **kwargs)`가 반환하는 `SileroVADEngine` 인스턴스가 그대로 `AppServiceContext.vad_engine`이 된다. 본 모듈은 이 클래스를 **import·서브클래싱 하지 않는다** |
| `src/open_llm_vtuber/vad/vad_factory.py` | `VADFactory.get_vad_engine(engine_type, **kwargs)` | `engine_type="silero_vad"` 분기를 그대로 사용. upstream `service_context.init_vad()`가 호출 경로 — 본 모듈은 이 호출 경로를 **오버라이드하지 않는다** |
| `src/open_llm_vtuber/config_manager/vad.py` | `VADConfig`, `SileroVADConfig` (pydantic, **설정 스키마**) | `conf.yaml`의 `character_config.vad_config` 파싱에 사용. 필드명과 타입은 **고정**(변경 금지) |
| `src/open_llm_vtuber/service_context.py` L347~L362 | `init_vad(vad_config: VADConfig)` | upstream 구현을 그대로 타게. 본 프로젝트는 이 메서드를 오버라이드하지 않는다. `AppServiceContext.load_from_config` 흐름에서 `super().load_from_config(config)`가 `init_vad`를 호출하므로 자동 배선 |
| `src/open_llm_vtuber/websocket_handler.py` L478~L511 | `_handle_audio_data`·`_handle_raw_audio_data` | VAD가 yield한 `b"<|PAUSE|>"`/`b"<|RESUME|>"` 마커를 인터럽트 신호로 변환. 본 모듈은 이 핸들러를 변경하지 않는다 |

### EXTEND

**없음.** 확장·상속 금지.

### NEW

본 모듈이 **새로 만드는 것**은 파이썬 코드가 아니라 다음 문서·설정·스크립트 항목뿐이다.

1. `conf.yaml` 템플릿의 `vad_config` 섹션을 M_01 기본값(현재 `vad_model: "silero_vad"` + `threshold/min_silence_duration_ms`)에서 **upstream 실제 스키마**(`prob_threshold`, `db_threshold`, `required_hits`, `required_misses`, `smoothing_window`, `orig_sr`, `target_sr`)로 보정. M_01 스펙의 예시 YAML에 혼선이 있으므로 본 스펙이 **최종 키 목록**을 확정한다(§설정 구조).
2. `scripts/bundle_deps.sh`에 `silero-vad` wheel과 모델 가중치(`silero_vad.onnx` 또는 `silero_vad.jit`) 수집 스텝 추가.
3. `scripts/verify_offline.ps1`에 VAD 첫 초기화 후 외부 네트워크 호출 없음을 Windows 방화벽 로그로 확인하는 단계 추가.
4. `tests/vad/` — 배선·회귀 테스트(§테스트 케이스).

### DROP

- upstream `vad/silero.py`의 `vad_main()` 엔트리와 `if __name__ == "__main__":` 블록은 **본 프로젝트에서 호출하지 않는다**(websocket 단독 실행 모드). `websockets` 패키지에 직접 의존하는 경로가 없도록 유지.

### 배선 정책

upstream `service_context.py` L277~L278의 `load_from_config` 흐름에서 `self.init_vad(config.character_config.vad_config)`가 자동 호출된다. `init_vad` 내부 로직(L347~L362)은 다음과 같다.

1. `vad_config.vad_model is None` → `self.vad_engine = None` (VAD 비활성).
2. 그 외 → `VADFactory.get_vad_engine(vad_config.vad_model, **getattr(vad_config, vad_config.vad_model.lower()).model_dump())` 결과를 `self.vad_engine`에 저장.

본 프로젝트 M_01 `AppServiceContext.load_from_config`는 `super().load_from_config(config)`를 호출만 하면 되며, **VAD 배선은 별도 코드 없이 upstream 흐름에 위임**한다. 본 M_03 스펙은 이 흐름이 `conf.yaml`의 우리 설정과 호환됨을 테스트로 보증한다.

---

## 공개 API

본 모듈은 **새 Python 심볼을 export하지 않는다.** 외부에 노출되는 것은 `AppServiceContext.vad_engine: VADInterface | None`(M_01 소유) 한 개이며, 이 필드의 실제 런타임 타입은 upstream `open_llm_vtuber.vad.silero.VADEngine`(= `SileroVADEngine`)이다.

### 상위 레이어가 의존하는 계약(upstream 그대로)

```python
# upstream/Open-LLM-VTuber/src/open_llm_vtuber/vad/vad_interface.py
class VADInterface(ABC):
    @abstractmethod
    def detect_speech(self, audio_data):  # upstream 타입 힌트 없음
        """
        입력: float 리스트(silero.py 기준 np.float32로 캐스트). bytes 타입 힌트는
              인터페이스 주석과 실제 silero 구현 간 불일치가 있으나 upstream 상태 유지.
        반환: generator. yield되는 bytes는 다음 세 종류 중 하나:
              - b"<|PAUSE|>"       : 발화 시작(ACTIVE 전이)
              - b"<|RESUME|>"      : 발화 종료(IDLE 복귀)
              - <audio_chunk bytes>: 발화 종료 시점에 누적된 int16 PCM 바이트
        """
```

### 상위 레이어가 의존하는 메서드(실체)

```python
# upstream/Open-LLM-VTuber/src/open_llm_vtuber/vad/silero.py 의 VADEngine
class VADEngine(VADInterface):
    def __init__(self, orig_sr=16000, target_sr=16000,
                 prob_threshold=0.4, db_threshold=60,
                 required_hits=3, required_misses=24,
                 smoothing_window=5): ...
    def load_vad_model(self): ...  # silero_vad.load_silero_vad() 호출
    def detect_speech(self, audio_data: list[float]): ...  # 제너레이터
```

### M_03가 export 하는 심볼

**없음.** `src/vad/`에는 `__init__.py`만 둔다(빈 패키지). 본 스펙은 **파이썬 모듈이 아니라 문서·테스트 산출물**이다.

---

## 설정 구조 (conf.yaml)

`conf.yaml`의 `character_config.vad_config`는 upstream `config_manager/vad.py`의 `VADConfig` pydantic 스키마와 **정확히 일치**해야 한다. 본 프로젝트 키 목록을 다음과 같이 확정한다.

```yaml
character_config:
  vad_config:
    vad_model: "silero_vad"        # null(비활성) | "silero_vad"
    silero_vad:
      orig_sr: 16000               # int. 입력 오디오 샘플레이트
      target_sr: 16000             # int. Silero VAD 처리 샘플레이트(16000 권장)
      prob_threshold: 0.4          # float [0.0~1.0]. 발화 확률 컷오프
      db_threshold: 60             # int. dBFS 절대값 기준(음성 에너지 최소)
      required_hits: 3             # int ≥1. 연속 hit로 ACTIVE 전이(3 * 32ms = 96ms)
      required_misses: 24          # int ≥1. 연속 miss로 IDLE 복귀(24 * 32ms = 768ms)
      smoothing_window: 5          # int ≥1. prob/db moving average 윈도우
```

### 키 명칭 혼선 해결

M_01 `specs/M_01_AppCore_SPEC.md` L445~L449의 예시 YAML에는 `threshold: 0.5`, `min_silence_duration_ms: 700` 키가 등장하나, **이는 upstream 스키마에 존재하지 않는다**. 두 키를 그대로 쓰면 pydantic `VADConfig.silero_vad` 파싱이 실패한다. 본 M_03 스펙이 **최종 진실**이며, M_01 예시 YAML은 구현 단계에서 본 스펙의 7개 키로 교체한다. 개념상의 매핑(사용자가 UI 언어로 "임계값", "최소 무음 시간"을 기대할 수 있음):

| 사용자 기대(M_01 예시) | 실제 upstream 키 | 근사 변환 |
|---|---|---|
| `threshold: 0.5` | `prob_threshold: 0.5` | 의미 동일(0.0~1.0 확률) |
| `min_silence_duration_ms: 700` | `required_misses: 22` | 700ms / 32ms(= 청크 길이) ≈ 21.875 → 22. 본 프로젝트 V1 기본값은 **upstream 기본(`required_misses=24` = 768ms)** 을 유지 |

**V1 기본값 확정**: upstream 기본값(`prob_threshold=0.4`, `db_threshold=60`, `required_hits=3`, `required_misses=24`, `smoothing_window=5`, `orig_sr=16000`, `target_sr=16000`)을 **그대로 사용**한다. 한국어 화자 튜닝 근거 데이터가 없는 상태에서 임의 조정 금지(§범위 외).

### 키 검증 요구

| 키 | 허용 범위 | 허용 밖일 때 |
|---|---|---|
| `vad_model` | `"silero_vad"` 또는 `null` | pydantic `Literal` 검증 실패 → `AppConfig` 로드 실패 |
| `orig_sr`, `target_sr` | int > 0. 실용 범위 8000/16000/24000/48000 | upstream은 범위 체크 없음. 본 프로젝트는 **16000 외 값은 로그 경고**만(회귀 테스트로 확인)후 그대로 전달 |
| `prob_threshold` | float. 상식 범위 [0.0, 1.0] | upstream은 범위 체크 없음. 경고 없이 전달(엣지 케이스 E-4 참조) |
| `db_threshold` | int. 상식 범위 [0, 120] | 동일 |
| `required_hits`, `required_misses` | int ≥ 1 | upstream은 0을 허용하면 `>=` 비교로 즉시 전이가 되는 버그성 동작이 발생 가능. 본 프로젝트는 `AppConfig` 로드 단계에서 **1 미만 값은 거부**(M_01 `AppConfig` 검증 레이어 추가 권장, §의존) |
| `smoothing_window` | int ≥ 1 | 0이면 `deque(maxlen=0)`가 되어 나눗셈 결과가 NaN. **거부** |

---

## 에러 처리 정책

| 상황 | 반응 | 예외 타입 | 로그 레벨 |
|---|---|---|---|
| `vad_model: null` (V1 프로덕션에서) | `vad_engine = None`. **M_01 부트스트랩이 경고 로그 1회 기록하고 기동 계속**. VAD 없이는 인터럽트·발화 구간 판정 불가 | (예외 없음, 하지만 프로덕션 모드에서는 WARNING) | WARNING |
| `silero_vad` 파이썬 패키지 미설치 | upstream `silero.py` L9의 `from silero_vad import load_silero_vad`가 `ImportError`. M_01 부트스트랩이 이를 `AppStartupError`로 래핑(M_01 책임) | `ImportError` → `AppStartupError` | CRITICAL |
| `load_silero_vad()` 실패 (모델 파일 미존재·권한 오류) | upstream `SileroVADEngine.__init__` 내부에서 예외가 그대로 올라옴. `init_vad()`가 로그만 찍고 예외 전파(upstream 기본 동작). M_01이 기동 실패로 간주 | 원본 예외 전파 | ERROR |
| `load_silero_vad()`가 인터넷 접근 시도(오프라인 실패) | 빌드 단계에서 `scripts/verify_offline.ps1`가 실패 검출. 런타임에는 파일 시스템 접근 실패로 수렴 | (위와 동일) | ERROR |
| `detect_speech` 도중 `torch` 추론 예외 (드문 케이스) | upstream은 잡지 않음. `websocket_handler._handle_audio_data`가 잡아 현재 오디오 청크를 drop. 본 모듈은 **변경하지 않는다** | 상위로 전파 | ERROR |
| 입력 오디오 배열이 `window_size_samples`(512)보다 짧음 | upstream `detect_speech` L57~L58의 `if len(chunk_np) < self.window_size_samples: break` — 정상 처리. 아무 것도 yield 하지 않음 | (예외 없음) | — |
| `pydantic` 스키마 불일치(잘못된 키 이름) | `AppConfig` 로드 단계에서 `ValidationError` → M_01 기동 실패 | `pydantic.ValidationError` | ERROR |
| `prob_threshold` 범위 밖(예: 1.5) | upstream이 수용. 실제 추론에서는 항상 miss로 판정 → 발화 감지 실패. 본 스펙은 M_01 `AppConfig`에 추가 `ge=0.0, le=1.0` 검증을 권장(본 모듈 범위 외, RISKS 등록) | (예외 없음, 기능 미동작) | — |
| `required_hits < 1` 또는 `smoothing_window < 1` | M_01 `AppConfig` 로드 시 거부(§설정 구조) | `pydantic.ValidationError` | ERROR |

### 원칙
- **무수정 원칙**: upstream이 던지는 예외·로그 포맷을 **변환하지 않는다**. M_02 ASREngine처럼 전용 예외 타입(`VADInitError` 등)을 만들지 **않는다**. 이렇게 함으로써 upstream 업데이트 시 회귀 영향 최소.
- **기동 실패 기본**: VAD 초기화 실패는 REQUIREMENTS.md §1.1 "VAD로 발화 구간만 전송"의 전제를 무너뜨리므로 **기동 실패로 간주**. 단, `vad_model: null`(개발·디버그) 경로는 의도적 허용.

---

## 성능·메모리 요구사항

### 메모리 (ARCHITECTURE.md §6.1 예산표)

| 항목 | 크기 | 근거 |
|---|---|---|
| Silero VAD 모델 가중치 | ~1.8 MB (ONNX) | `silero_vad` 공식 배포 파일 |
| `silero_vad` 파이썬 패키지 런타임 오버헤드 | ~10 MB | `import silero_vad`, `torch` 서브모듈 일부 |
| `torch` 상주(upstream 다른 모듈과 공유) | — | 본 모듈 단독 증가분이 아님 |
| `onnxruntime` 상주(공유) | — | M_02, 추후 embedder와 공유 |
| `SileroVADEngine` 파이썬 객체(StateMachine 버퍼 포함) | ~30 MB | `pre_buffer` deque(maxlen=20) × 512 samples × int16 = 20KB. 대부분은 torch 내부 텐서 워크스페이스 |
| **합계 (본 모듈 배타 증가분)** | **~40 MB** | ARCHITECTURE.md §6.1 표와 일치 |

### 레이턴시

| 지표 | 값 | 환경 | 근거 |
|---|---|---|---|
| `SileroVADEngine.__init__` (= `load_silero_vad()` 포함) | ≤ 300 ms | Windows 11, NVMe, i7-12700, CPU-only | silero-vad 0.x 공식 벤치마크 참고치 |
| 단일 청크(512 samples = 32 ms) 처리 | ≤ 3 ms | CPU-only | 16kHz에서 실시간 ×10 마진 |
| `<|PAUSE|>` 마커 방출 지연 | `required_hits * 32 ms` = **96 ms** (기본) | 기본 설정 | StateMachine 정의 |
| `<|RESUME|>` 마커 방출 지연 | `required_misses * 32 ms` = **768 ms** (기본) | 기본 설정 | 발화 종료 후 769ms 뒤에 ASR 시작 |

ARCHITECTURE.md §6.2 예산의 "VAD → ASR 시작 지연 50 ms"는 `<|PAUSE|>` 지연이 아니라 **ASR 트리거 루프의 추가 오버헤드**를 의미한다(혼동 방지). 실제 "발화 종료 → ASR 호출"은 `required_misses * 32 ms` (기본 768 ms)가 우세하며, 이는 상위 레이어가 감내한다.

### 동시성
- `SileroVADEngine.detect_speech`는 **제너레이터**이며 내부 `StateMachine`은 스레드-세이프하지 않다. 단일 `AppServiceContext`는 단일 WebSocket을 다루므로 본 요구사항은 자연 충족(REQUIREMENTS.md §10 "1인 1PC"). 동시 2개 이상 연결 시 `StateMachine` 상태가 섞이면 정의되지 않은 동작 — 본 프로젝트에서 이 시나리오는 발생하지 않는다(M_01 동시 최대 2 연결 허용은 pet 모드 + 메인 창 동시 연결 시나리오이며, 두 창이 같은 마이크를 공유하지 않는다).

---

## 테스트 케이스

경로: `tests/vad/test_*.py`. pytest + `pytest-asyncio`. **REUSE 모듈이므로 upstream 내부 로직(StateMachine, 확률 스무딩)을 재검증하지 않는다.** 테스트 초점은 다음 4가지다.
(i) upstream `VADFactory`가 본 프로젝트 `conf.yaml`의 키를 올바르게 수용하는가,
(ii) M_01 `AppServiceContext.load_from_config` 후 `vad_engine`이 기대 타입(`SileroVADEngine`)으로 세팅되는가,
(iii) 오프라인 번들에서 Silero 모델 로드가 네트워크 없이 성공하는가,
(iv) upstream VAD 파일이 수정되지 않았는가.

Silero 모델 로드는 무거우므로 **원칙적으로 `silero_vad.load_silero_vad`를 `unittest.mock.patch`로 대체**하고, 1건의 `@pytest.mark.slow` 실제 로드 테스트만 둔다(CI 기본 skip).

### 정상 케이스 (≥5)

**N-1. `VADConfig` pydantic 파싱 — 우리 conf 스키마로 로드 성공**
- 입력: §설정 구조의 YAML 스니펫을 `yaml.safe_load`로 파싱하여 upstream `VADConfig.model_validate` 호출.
- 검증: 예외 없음. `parsed.vad_model == "silero_vad"`, `parsed.silero_vad.prob_threshold == 0.4`, `parsed.silero_vad.required_misses == 24`.

**N-2. `VADFactory.get_vad_engine("silero_vad", **kwargs)` 호출 성공 (mock load)**
- 입력: `silero_vad.load_silero_vad`를 `MagicMock`으로 패치. `VADFactory.get_vad_engine("silero_vad", orig_sr=16000, target_sr=16000, prob_threshold=0.4, db_threshold=60, required_hits=3, required_misses=24, smoothing_window=5)` 호출.
- 검증: 반환 인스턴스가 `open_llm_vtuber.vad.silero.VADEngine` 타입. `instance.config.prob_threshold == 0.4`, `instance.window_size_samples == 512`. `load_silero_vad`가 1회 호출.

**N-3. `AppServiceContext.load_from_config` 후 `vad_engine` 배선**
- 입력: 미니멀 `AppConfig`(§설정 구조 YAML 포함), `silero_vad.load_silero_vad` 패치.
- 검증: `ctx.vad_engine is not None`. `type(ctx.vad_engine).__name__ == "VADEngine"`. `ctx.vad_engine.config.smoothing_window == 5`.

**N-4. `vad_model: null` 경로 — 개발/디버그 모드**
- 입력: `vad_config.vad_model = None`.
- 검증: `AppServiceContext.load_from_config` 후 `ctx.vad_engine is None`. WARNING 로그 1건 (`caplog`).

**N-5. `detect_speech` 제너레이터 프로토콜 확인 (mock model)**
- 입력: `silero_vad.load_silero_vad`가 반환하는 mock model의 `__call__`이 0.8(발화 확률)을 반환하도록 구성. `audio_data = [0.1] * (512 * 10)`.
- 검증: `engine.detect_speech(audio_data)`가 제너레이터. 반복 시 처음 `required_hits(=3)` 청크 이후 `(…, b"<|PAUSE|>")` 튜플을 방출(단, 본 테스트는 upstream의 **구조(yield 여부)만 확인**하고 정확한 state machine 로직은 검증하지 않는다 — upstream 신뢰).

**N-6. upstream 파일 해시 회귀**
- 입력: `upstream/Open-LLM-VTuber/src/open_llm_vtuber/vad/{silero.py,vad_factory.py,vad_interface.py}` 3개 파일의 SHA-256를 `tests/vad/upstream_hashes.json`에 고정.
- 검증: 실행 시 재계산한 해시와 일치. 불일치 시 테스트 실패(업스트림 수정 감지).

### 엣지 케이스 (≥5)

**E-1. `target_sr != 16000` (예: 8000)**
- 입력: `VADFactory.get_vad_engine("silero_vad", orig_sr=8000, target_sr=8000, prob_threshold=0.4, db_threshold=60, required_hits=3, required_misses=24, smoothing_window=5)`.
- 검증: 예외 없음. `instance.window_size_samples == 256` (upstream 분기). 로그 경고 1건(본 프로젝트는 16000만 테스트됨을 알림 — M_01 로더 책임으로 스펙화).

**E-2. 매우 짧은 오디오 입력 (< 512 samples)**
- 입력: `engine.detect_speech([0.0] * 100)`.
- 검증: 제너레이터가 아무것도 yield하지 않고 종료. 예외 없음.

**E-3. 빈 리스트 입력**
- 입력: `engine.detect_speech([])`.
- 검증: 즉시 종료. 예외 없음.

**E-4. `prob_threshold=0.0` — 항상 hit**
- 입력: 인스턴스 생성 시 `prob_threshold=0.0`. mock model이 0.001 반환.
- 검증: 인스턴스 생성 성공. upstream 내부에서 첫 required_hits 청크 후 `<|PAUSE|>` 방출. 본 테스트는 **생성 성공**까지만 확인(내부 로직은 upstream 소유).

**E-5. `prob_threshold=1.5` — 범위 밖 (upstream이 수용, 검증 없음)**
- 입력: `VADConfig(silero_vad={"prob_threshold": 1.5, ...})`.
- 검증: pydantic이 통과(upstream 스키마는 범위 검증 없음). 본 프로젝트의 M_01 `AppConfig` 추가 검증에 `ge=0.0, le=1.0`이 없다면 통과. **RISKS에 등록**하고, 향후 M_01이 검증을 추가할 때 본 테스트가 `ValidationError`를 기대하도록 업데이트.

**E-6. 키 생략 — upstream `SileroVADConfig`는 모든 필드가 `Field(...)` 필수**
- 입력: `VADConfig(silero_vad={"prob_threshold": 0.4})` (`orig_sr` 등 누락).
- 검증: `pydantic.ValidationError`. 필수 필드 누락 메시지에 `orig_sr`, `target_sr`, `db_threshold`, `required_hits`, `required_misses`, `smoothing_window` 6개가 언급됨.

### 적대적 케이스 (≥3)

**A-1. `vad_model: "webrtc_vad"` — 미지원 엔진**
- 입력: `VADConfig(vad_model="webrtc_vad", ...)`.
- 검증: upstream `VADConfig.vad_model`은 `Optional[Literal["silero_vad"]]` → `pydantic.ValidationError`. 본 프로젝트는 다른 엔진을 **절대 지원하지 않는다**.

**A-2. `silero_vad` 패키지 미설치**
- 입력: `sys.modules["silero_vad"]`를 제거 후 `from open_llm_vtuber.vad.silero import VADEngine` 재임포트.
- 검증: `ImportError`. M_01 부트스트랩이 이를 감지해 `AppStartupError`로 변환하는 동작은 M_01 테스트에서 커버되며, 본 모듈 테스트는 **`ImportError`가 발생함**까지만 확인.

**A-3. 네트워크 의존 시도 감지 (정적 검사)**
- 입력: `tests/vad/test_no_network.py`가 upstream `vad/silero.py`를 파일로 읽고 정규식으로 `requests\.|urllib\.|http[s]?://` 패턴을 검색.
- 검증: 매칭 0건. 추가로 `silero_vad` 패키지의 `load_silero_vad` 소스를 `inspect.getsource`로 읽어 동일 패턴을 검색. `silero_vad<5.0` 계열은 모델을 패키지 번들에 포함하므로 매칭 0건이 기대치. 매칭이 1건이라도 있으면 **FAIL** — `silero_vad` 버전 핀(§의존)을 재점검해야 한다는 신호.

**A-4. 잘못된 타입 주입**
- 입력: `VADFactory.get_vad_engine("silero_vad", orig_sr="16000", ...)` (str).
- 검증: upstream은 pydantic 검증을 factory에서 건너뛰므로 `SileroVADConfig(orig_sr="16000", ...)` 내부에서 str→int coerce되거나 `ValidationError`. `pydantic` v2 기본은 coerce. 본 테스트는 **어느 동작이든 프로세스가 죽지 않음**을 확인. (M_01이 `AppConfig` 레벨에서 strict 타입으로 거부하는지는 M_01 테스트 책임.)

**A-5. 중복 `init_vad` 호출 — 동일 설정**
- 입력: `ctx.init_vad(vad_config)`를 두 번 호출.
- 검증: upstream L353 조건 `if not self.vad_engine or (self.character_config.vad_config != vad_config):`에 의해 두 번째 호출이 `load_silero_vad`를 **다시 호출하지 않는다**. mock의 `call_count == 1`.

### Slow 마커 실제 로드 테스트(선택, CI 기본 skip)

**S-1. 실제 `silero_vad.load_silero_vad()` 호출 — 오프라인 모드**
- 전제: `silero-vad` 패키지 설치, 네트워크 차단 환경 시뮬레이션(`requests` 모킹으로 외부 URL 거부).
- 입력: `VADFactory.get_vad_engine("silero_vad", ...)` 기본값.
- 검증: 인스턴스 생성 성공. 외부 HTTP 요청 0건(`requests`·`urllib` 몽키패치로 카운터 확인).

---

## 오프라인 빌드 메모

### 모델 파일 배치

`silero-vad` 파이썬 패키지는 버전에 따라 모델 가중치 배치 방식이 다르다.

| 패키지 버전 | 모델 소스 | 오프라인 준비 |
|---|---|---|
| `silero-vad >=5.0` | 패키지 내 `silero_vad/data/*.jit` 번들 | wheel 설치만으로 충분. 네트워크 호출 없음 |
| `silero-vad 4.x` | `torch.hub.load("snakers4/silero-vad", ...)` 호출 → `torch.hub` 캐시 | 빌드 머신에서 1회 선실행 후 `~/.cache/torch/hub/` 복사 필요 (본 프로젝트는 이 경로를 피하기 위해 5.x 이상 핀) |

**결정**: `silero-vad >=5.0, <6` 핀. 모델 파일은 **패키지 wheel 내부에 포함**되어 사내 PC에는 별도 파일 배치가 불필요하다. 단, 검증을 위해:

- `assets/models/silero-vad/`: **본 프로젝트는 이 디렉토리를 생성하지 않는다**(v5+ 사용 시). ARCHITECTURE.md §7 디렉토리 트리의 `assets/models/silero-vad/*.onnx` 기재는 4.x 계열 가정의 잔재이며, 본 스펙으로 공식 철회. 번들 인스톨러도 이 디렉토리를 만들지 않는다.
- 만약 향후 4.x로 롤백이 필요하면 별도 `CHANGE_REQUESTS.md`.

### `.gitignore`
- 변경 없음. `silero-vad` wheel은 빌드 단계에서만 수집되고, 사내 PC에는 venv 내부에 설치된다.

### `scripts/bundle_deps.sh` 추가 항목

```bash
# Python 패키지 휠 수집 (빌드 머신에서 실행)
pip download silero-vad>=5.0,<6 \
    --platform win_amd64 --python-version 3.12 --only-binary=:all: \
    --dest dist/wheels/
# silero-vad는 순수 Python 패키지로 모델 가중치(*.jit)를 wheel에 번들한다
```

onnxruntime / torch는 upstream과 공유되며 M_02·M_07 번들 수집 단계에서 이미 수집된다. 본 모듈이 추가로 요구하는 것은 `silero-vad` 하나.

### 네트워크 검증

`scripts/verify_offline.ps1`에 다음 추가:

```powershell
# 오프라인 모드에서 서버 기동 후 WebSocket에 "mic-audio-data"를 1개 청크 전송
# silero_vad.load_silero_vad()가 외부 HTTP·DNS 요청을 발생시키지 않는지
# Windows Defender Firewall 로그(pfirewall.log)에서 외부 IP 대상 허용/차단 로그 0건 확인
```

### `pyproject.toml` 추가 예 (PR 메시지 기록 대상)

```toml
[project.dependencies]
silero-vad = ">=5.0,<6"    # upstream vad/silero.py가 import하는 공식 패키지
# torch, onnxruntime은 M_02·M_07과 공유 이미 선언
```

---

## Definition of Done

### 공통 (CLAUDE.md "산출물 체크리스트")

- [ ] `specs/M_03_VADEngine_SPEC.md` (본 문서) 사용자 승인.
- [ ] `src/vad/__init__.py`만 생성(빈 패키지). 파이썬 구현 파일은 **추가하지 않는다**.
- [ ] `tests/vad/` 테스트: 정상 ≥5, 엣지 ≥5, 적대적 ≥3 (본 스펙의 N/E/A 케이스 전량).
- [ ] `ruff format .`, `ruff check .`, `mypy src/vad/`(빈 패키지도 통과), `pytest tests/vad/ -v` 모두 통과.
- [ ] `reviews/M_03_VADEngine_REVIEW.md`에 Critic PASS.
- [ ] `docs/MODULES.md`의 M_03 상태가 ✅ DONE으로 갱신.

### M_03 고유

- [ ] `conf.yaml` 템플릿의 `vad_config.silero_vad` 섹션이 upstream `SileroVADConfig`의 7개 필수 키를 **모두** 포함한다.
- [ ] `AppServiceContext.load_from_config(config)` 실행 후 `ctx.vad_engine`이 `open_llm_vtuber.vad.silero.VADEngine` 인스턴스임이 테스트로 확인된다.
- [ ] `vad_model: null` 경로가 정상 동작(VAD 비활성, WARNING 로그 1건)함이 테스트로 확인된다.
- [ ] upstream `vad/silero.py`, `vad/vad_factory.py`, `vad/vad_interface.py` 3개 파일의 SHA-256 해시가 `tests/vad/upstream_hashes.json`에 기록되고 회귀 테스트가 통과한다.
- [ ] `silero-vad >=5.0,<6` 버전 핀이 `pyproject.toml`과 `scripts/bundle_deps.sh`에 반영된다.
- [ ] `load_silero_vad` 호출 경로가 외부 네트워크 요청을 유발하지 않음을 정적(패턴 검색) + 동적(몽키패치 카운터)으로 확인한다.
- [ ] M_01 `specs/M_01_AppCore_SPEC.md`의 YAML 예시에 등장한 `threshold`/`min_silence_duration_ms` 키 이름 혼선이 본 스펙의 7개 키로 구현 단계에서 교체됨을 M_01 통합 테스트에서 확인한다(M_01 기동이 `silero_vad` 블록을 올바르게 파싱).

---

## 의존성

### Python 패키지 (pyproject.toml 추가)

| 패키지 | 버전 핀 | 용도 | 사유 |
|---|---|---|---|
| `silero-vad` | `>=5.0,<6` | Silero VAD 모델 로드 + 추론 | upstream `vad/silero.py`의 `from silero_vad import load_silero_vad`. v5.x는 모델 가중치를 wheel에 번들 |
| `torch` | upstream 핀 따름 (`>=2.6.0`) | silero_vad 추론 런타임 | upstream이 이미 요구 |
| `onnxruntime` | M_02와 공유 (`>=1.17,<2`) | silero-vad 5.x의 일부 로드 경로 | 공유 의존 |
| `numpy` | upstream 공유 | `detect_speech` 내부 float32 배열 | 공유 |
| `pydantic` | upstream 공유 | `VADConfig` 스키마 | 공유 |

### 런타임 전제
- Python 3.12 이상.
- upstream 소스 트리가 `upstream/Open-LLM-VTuber/src`에 존재하고 `sys.path`에 포함(M_01 설정).
- `silero-vad` wheel이 venv 내부에 설치되어 있음(모델 가중치 포함).

### 모듈 의존

| 대상 | 관계 |
|---|---|
| M_01 AppCore | `AppServiceContext.vad_engine` 슬롯 제공. `load_from_config`에서 upstream `init_vad` 호출 경로. **M_01이 본 모듈에 설정 전달, 본 모듈은 M_01에 코드 요구 0** |
| upstream `vad/silero.py` | **무수정 REUSE** |
| upstream `vad/vad_factory.py` | **무수정 REUSE** |
| upstream `config_manager/vad.py` | **스키마 REUSE** |

**M_03은 M_02·M_04·M_05·M_07에 의존하지 않는다.**

---

## 디렉토리 구조

```
src/vad/
└── __init__.py              # 빈 파일. 본 모듈은 파이썬 심볼을 export하지 않는다

tests/vad/
├── __init__.py
├── conftest.py              # mock silero_vad.load_silero_vad fixture
├── test_config.py           # N-1, E-5, E-6, A-1, A-4 (VADConfig 스키마)
├── test_factory.py          # N-2, E-1~E-4 (VADFactory 호출)
├── test_wiring.py           # N-3, N-4, A-5 (AppServiceContext 배선)
├── test_upstream_integrity.py # N-6 (파일 해시 회귀), A-3 (네트워크 패턴)
├── test_import.py           # A-2 (silero_vad ImportError)
├── test_slow.py             # S-1 (@pytest.mark.slow, 실제 load_silero_vad)
└── upstream_hashes.json     # {"silero.py": "sha256:...", "vad_factory.py": "...", "vad_interface.py": "..."}
```

**주의**: `src/vad/`에는 `korean_*.py` 같은 래퍼를 만들지 **않는다**. 본 모듈은 "코드 없음, 배선·검증만"을 엄격히 지킨다. 이는 REUSE 분류의 본질이다.

---

## 스펙 외 사항 (명시적 제외)

본 모듈의 책임이 **아닌** 항목:

1. **VAD 알고리즘 자체**: Silero VAD 또는 `StateMachine` 로직의 수정·튜닝. upstream 소유.
2. **오디오 캡처·리샘플링·포맷 변환**: upstream `websocket_handler._handle_audio_data`가 16kHz float32 배열을 공급한다고 가정. 이 전처리 단계는 M_01(upstream REUSE) 담당.
3. **발화 바이트 → ASR 호출 트리거**: upstream `conversation_handler`가 `<|RESUME|>` 수신 시 ASR 파이프라인을 킥오프. M_02·M_05·conversation 레이어 담당.
4. **인터럽트 신호 처리**: `<|PAUSE|>`를 받은 상위 레이어가 TTS 스트림을 취소하고 agent에 `handle_interrupt`를 호출. M_05 LLMAgent·upstream `conversation_handler` 담당.
5. **VAD 파라미터의 한국어 화자 튜닝**: 데이터 수집 후 별도 마일스톤. 현재는 upstream 기본값.
6. **다중 VAD 엔진(WebRTC, Picovoice 등)**: V1·V2 모두 범위 밖. Silero VAD만 사용.
7. **VAD 없이 수동 push-to-talk 모드**: 프론트엔드 UI 기능(M_12)으로 고려 가능하나 본 모듈은 관여하지 않는다.
8. **VAD 메트릭·관측성(발화 수, 평균 발화 길이 등)**: V1 범위 밖. 필요 시 `CHANGE_REQUESTS.md`.
9. **모델 자체 오프라인 번들 (`assets/models/silero-vad/`) 디렉토리 생성**: `silero-vad >=5.0` 선택으로 불필요.
10. **upstream 파일 수정**: 어떤 조건에서도 금지.

---

## 부록: upstream 경로·심볼 인덱스 (실재 확인)

본 스펙 작성 중 `/mnt/c/projects/ai-assistant/upstream/Open-LLM-VTuber/src/open_llm_vtuber/` 하의 실제 파일을 읽어 시그니처를 확정했다.

- `vad/vad_interface.py` L1~L13: `VADInterface` (ABC), `detect_speech(self, audio_data)` abstract. 주석상 입력 타입은 `bytes`로 기재되나 실제 구현은 `list[float]`를 수용.
- `vad/silero.py` L14~L22: `SileroVADConfig(BaseModel)` — `orig_sr`, `target_sr`, `prob_threshold`, `db_threshold`, `required_hits`, `required_misses`, `smoothing_window` 7개 필드.
- `vad/silero.py` L24~L75: `VADEngine(VADInterface)` — 생성자 7개 키워드 인자, `load_vad_model()`이 `load_silero_vad()` 호출, `detect_speech`는 제너레이터.
- `vad/silero.py` L85~L189: `StateMachine` — IDLE/ACTIVE/INACTIVE 3상태, `b"<|PAUSE|>"`·`b"<|RESUME|>"` 마커 yield.
- `vad/silero.py` L191~L227: `vad_main()` 엔트리 (본 프로젝트 미사용).
- `vad/vad_factory.py` L5~L21: `VADFactory.get_vad_engine(engine_type, **kwargs)` — `"silero_vad"` 분기만 구현.
- `config_manager/vad.py` L7~L38: `SileroVADConfig(I18nMixin)` — 모든 필드 `Field(...)` 필수.
- `config_manager/vad.py` L41~L64: `VADConfig(I18nMixin)` — `vad_model: Optional[Literal["silero_vad"]]`.
- `service_context.py` L347~L362: `init_vad(vad_config)` — `vad_model is None`이면 비활성, 그 외 `VADFactory.get_vad_engine` 호출.
- `service_context.py` L277~L278: `load_from_config` 흐름에서 `self.init_vad(config.character_config.vad_config)` 자동 호출.
- `websocket_handler.py` L478~L511: `_handle_audio_data`·`_handle_raw_audio_data` — VAD yield된 `b"<|PAUSE|>"`·`b"<|RESUME|>"` 마커를 인터럽트 신호로 변환(본 모듈 무수정 REUSE 대상).
- `config_templates/conf.default.yaml` L458~L467: `vad_config.silero_vad` 기본값 — 본 스펙 §설정 구조의 V1 기본값과 일치.
