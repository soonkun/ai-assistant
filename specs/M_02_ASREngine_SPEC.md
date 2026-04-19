# M_02 ASREngine — 스펙

## 목적과 범위

### 목적
한국어를 1차 언어, 영어를 2차 언어로 인식하는 STT 엔진을 제공한다. upstream `ASRInterface`의 계약과 `faster_whisper_asr.VoiceRecognition` 구현을 기반으로, 본 프로젝트에서 요구하는 **large-v3 + int8** 설정과 에러 정책만 좁게 교체·확장한다. 모델 자체(faster-whisper)는 upstream과 동일한 라이브러리를 사용한다.

### 범위 (In-Scope)
1. `KoreanWhisperASR` 클래스 구현 — upstream `ASRInterface`를 상속하되, `faster_whisper_asr.VoiceRecognition`의 `transcribe_np` 알고리즘은 그대로 가져와 init/에러 처리/0길이 가드만 강화한다.
2. 초기화 시점의 모델 경로 존재 검증, 디바이스 자동 판별(`device="auto"` → CUDA 사용 가능하면 `cuda`, 아니면 `cpu`).
3. 빈/초단시간 오디오에 대한 공짜 경로(조기 반환) 처리.
4. 본 프로젝트 고유 예외 `ASRInitError`, `ASRRuntimeError` 정의.
5. `conf.yaml`의 `character_config.asr_config.faster_whisper` 섹션을 upstream 경로로 읽어 전달하는 배선을 확정(upstream `ASRFactory`는 그대로 REUSE하고, **본 프로젝트는 팩토리에 손대지 않는다** — 대신 설정값을 우리 구현이 호환되는 형태로 둔다).
6. 단위 테스트 (정상 ≥5, 엣지 ≥5, 적대적 ≥3).

### 범위 외 (Out-of-Scope, 명시적 제외)
- 마이크 캡처·WebSocket 오디오 디코딩. 오디오 프레임 수신·집계는 upstream `WebSocketHandler._handle_audio_data`(M_01 REUSE).
- VAD 분기(`<|PAUSE|>`/`<|RESUME|>`) — M_03 VADEngine과 upstream이 담당.
- 발화 인터럽트 처리 — M_05 LLMAgent가 담당.
- 스트리밍 STT(청크 단위 실시간 자막). V1은 발화 종료 후 1회 transcribe. 스트리밍은 V2 후보.
- 다른 ASR 백엔드(`whisper_cpp`, `sherpa_onnx`, Azure 등) — 본 프로젝트는 `faster_whisper` 외 사용 안 함.
- 번역 기능 — upstream `translate_engine`은 `translate_audio: false`로 비활성(M_01).
- 모델 파일 다운로드·버전 관리. 오프라인 번들에 사전 배치만 허용(§오프라인 빌드 메모).

---

## 요구사항 연결

| REQUIREMENTS.md 항목 | M_02 기여 |
|---|---|
| §0 오프라인 / Windows 10/11 | 모델 파일은 `assets/models/whisper-large-v3-int8/`에 사전 배치. HuggingFace 런타임 다운로드 금지 |
| §1.1 STT 한국어/영어 | `language="ko"` 기본, `language=None`으로 자동 감지 허용(엣지 케이스) |
| §1.1 VAD로 발화 구간만 전송 | 본 모듈은 VAD가 추출한 numpy float32 버퍼를 입력으로 받는다. VAD 자체는 M_03 |
| §8 STT 모델: faster-whisper large-v3 | `model_path="assets/models/whisper-large-v3-int8"`, `compute_type="int8"` |
| §9 응답 지연(발화 끝 → 첫 음성 GPU 2s / CPU 6s) | ARCHITECTURE.md §6.2 예산표: large-v3 GPU 0.6s / CPU 2.5s. 본 모듈 단독 SLA는 §성능 표 참조 |
| §9 메모리 프로파일 | MIN: medium(~600 MB), RECOMMENDED: large-v3(~1.6 GB). `profile` 분기로 모델 경로 선택(§설정 구조) |
| §9 외부 네트워크 호출 금지 | `WhisperModel` 생성 시 `download_root`를 지정하지 않고, 모델 경로가 로컬 파일시스템에 존재하지 않으면 **즉시** `ASRInitError`로 실패(네트워크 풀링 시도 차단) |

---

## upstream 재사용 분석

### 분류: EXTEND

upstream에 이미 `faster_whisper` 백엔드가 존재한다. **교체가 아니라 설정 재조정 + 안전가드 추가**다. 그러나 업스트림의 `VoiceRecognition` 생성자는 다음과 같은 약점을 가지므로 본 프로젝트는 별도 서브클래스를 둔다.

- 모델 경로 존재 검증이 없다(잘못된 경로 주입 시 런타임 지연 후 내부 에러).
- 0길이 오디오 가드가 없다(빈 배열을 `WhisperModel.transcribe`에 넣으면 `NaN`/`0 segments` 동작이 백엔드 버전에 따라 갈린다).
- `device="auto"`가 실제로 CUDA 가용성 체크를 수행하지 않는다(`faster-whisper` 내부 auto는 사용 가능하나, 실패 메시지가 불친절).
- 예외 타입이 일반 `RuntimeError`로 올라와 상위 에러 정책과 맞지 않는다.

### REUSE (무수정 호출)

| upstream 경로 | 심볼 | 사용 방식 |
|---|---|---|
| `src/open_llm_vtuber/asr/asr_interface.py` | `ASRInterface` (abstract) | **베이스 클래스**로 상속. `SAMPLE_RATE=16000`, `NUM_CHANNELS=1`, `SAMPLE_WIDTH=2` 상수 상속. `async_transcribe_np`(부모 기본 구현: `asyncio.to_thread(self.transcribe_np, audio)`)를 그대로 사용. `nparray_to_audio_file`도 상속 |
| `src/open_llm_vtuber/asr/faster_whisper_asr.py` | `VoiceRecognition.transcribe_np` 알고리즘 | **함수 본문 로직만 참조·재구현**(복사 아님. import도 하지 않는다). `segments, info = self.model.transcribe(audio, beam_size=5, language=self.LANG, condition_on_previous_text=False, initial_prompt=self.prompt)` 동일 파라미터 유지. Upstream 클래스 자체를 import하지 않는 이유: (a) 우리 서브클래스가 더 엄격한 검증을 수행, (b) upstream 생성자가 `download_root`를 받는 등 외부 다운로드 여지가 있어 오프라인 규칙과 충돌 가능 |
| `src/open_llm_vtuber/asr/asr_factory.py` | `ASRFactory.get_asr_system` | 본 프로젝트는 **upstream 팩토리를 수정하지 않는다**. 대신 `asr_factory.py`는 `asr_model="faster_whisper"` 문자열을 받으면 upstream `VoiceRecognition`을 반환한다. 본 프로젝트는 `service_context.init_asr()` 이후 교체 훅을 사용하거나, `AppServiceContext`에서 **asr_engine만 직접 구성**하여 주입한다(§배선). upstream `asr_factory.py` 파일은 건드리지 않음 |
| `src/open_llm_vtuber/config_manager/asr.py` | `FasterWhisperConfig` (pydantic) | `model_path`, `language`, `device`, `compute_type`, `prompt`, `download_root`를 그대로 수용. **upstream 스키마 변경 금지**. 본 프로젝트는 `download_root`를 명시적으로 `""`(빈 문자열) 또는 로컬 assets 경로로 설정하는 것으로 네트워크 의존을 끊는다 |

### EXTEND (상속·래핑)

| 베이스 | 신규 서브클래스 | 확장 내용 |
|---|---|---|
| `ASRInterface` | `KoreanWhisperASR` (`src/asr/korean_whisper_asr.py`) | 생성자에서 모델 경로 검증, 디바이스 결정, `WhisperModel` 로드. `transcribe_np` 구현에 0길이 가드와 예외 변환 추가 |

### DROP

- `faster_whisper_asr.VoiceRecognition` 자체는 **직접 사용하지 않는다**. upstream 팩토리가 반환하는 이 클래스는 본 프로젝트의 배선(`AppServiceContext.init_asr` 오버라이드 또는 주입 훅)에 의해 `KoreanWhisperASR`로 **덮어쓴다**.
- 나머지 ASR 백엔드(Azure/Groq/WhisperCPP/Sherpa/Fun) — 본 프로젝트 오프라인 규칙과 언어 프로파일에 맞지 않음.

### 배선 정책

upstream `service_context.py` L323~L333의 `init_asr(asr_config)`는 `ASRFactory.get_asr_system(asr_config.asr_model, ...)`를 호출해 `self.asr_engine`을 세팅한다. **upstream 파일을 수정할 수 없으므로**, 본 프로젝트는 다음 중 한 경로를 택한다.

1. **권장**: `AppServiceContext.load_from_config`(M_01 §Service Context)에서 부모 `load_from_config`를 호출한 뒤, `self.asr_engine`을 본 모듈의 `KoreanWhisperASR` 인스턴스로 **재할당**한다. 이 재할당은 upstream 내부 호출 순서와 무관하게 동작하며, upstream 팩토리가 한 번 인스턴스를 만드는 것은 허용되지만 즉시 폐기된다. 폐기 전에 `WhisperModel` 로드가 발생하므로 **낭비를 피하려면** `asr_config.asr_model`을 일시적으로 팩토리에 없는 값(`"faster_whisper"`) 대신 우리가 임의로 주입한 값으로 치환하는 방식은 **사용하지 않는다**(설정 스키마 위반). 대신 아래 대안을 쓴다.
2. **채택**: `AppServiceContext.__init__`에서 `self.asr_engine = None`으로 초기화되어 있음을 확인하고, `AppServiceContext.load_from_config`를 오버라이드하여 `init_asr`를 **직접 우리 구현으로 호출**한다. 즉 `super().load_from_config(config)`을 호출하기 **전에** `self.asr_engine = KoreanWhisperASR(...)`를 세팅하고, upstream `init_asr`의 `if not self.asr_engine` 가드 덕분에 재초기화가 스킵되도록 유도한다.

실제로 `service_context.py` L324의 조건은 `if not self.asr_engine or (self.character_config.asr_config != asr_config):`이므로, 두 번째 조건을 충족시키기 위해 `self.character_config.asr_config = asr_config`도 함께 선세팅한다. 본 세부는 M_01의 `AppServiceContext.load_from_config`에 반영한다. **M_02는 `KoreanWhisperASR` 클래스와 그 팩토리 함수(`build_asr_engine(app_config)`)만 제공**한다.

---

## 공개 API

> Python 3.12 타입 힌트. `async def`는 부모 인터페이스 동작을 그대로 상속.

### 예외 타입

```python
# src/asr/errors.py
class ASRInitError(Exception):
    """모델 로드·경로 검증·디바이스 초기화 실패."""

class ASRRuntimeError(Exception):
    """transcribe 도중의 복구 불가능한 에러 (백엔드 예외 전파)."""
```

### 메인 클래스

```python
# src/asr/korean_whisper_asr.py
import numpy as np
from pathlib import Path
from open_llm_vtuber.asr.asr_interface import ASRInterface  # upstream

class KoreanWhisperASR(ASRInterface):
    """한국어·영어 faster-whisper large-v3 int8 전용 STT.

    upstream ASRInterface를 상속하므로 async_transcribe_np는 부모 기본 구현을 사용한다
    (asyncio.to_thread(self.transcribe_np, audio)).
    """

    # 모델 로드 후 외부 코드에서 읽을 수 있는 메타
    model_path: str
    language: str | None
    compute_type: str
    device: str
    resolved_device: str   # "cuda" | "cpu" (auto 해석 결과)

    def __init__(
        self,
        model_path: str,
        language: str | None = "ko",
        compute_type: str = "int8",
        device: str = "auto",
        beam_size: int = 5,
        initial_prompt: str | None = None,
        min_audio_seconds: float = 0.2,
        download_root: str = "",  # 빈 문자열 = 네트워크 금지(경로 부재 시 즉시 실패)
    ) -> None:
        """모델을 즉시 로드한다(지연 로드 아님 — 첫 발화 지연 방지).

        Raises:
            ASRInitError:
              - model_path가 존재하지 않음
              - model_path 디렉토리가 비어 있음(CT2 가중치 파일 없음)
              - language가 지원 세트 외('ko', 'en', None 외 값 — 본 모듈은 이 2개만 허용)
              - compute_type이 'int8','float16','float32' 외
              - device가 'auto','cpu','cuda' 외
              - WhisperModel 생성자가 예외 발생
        """

    def transcribe_np(self, audio: np.ndarray) -> str:
        """동기 전사. 부모의 async_transcribe_np가 스레드로 래핑해 호출한다.

        동작:
          1) audio가 None이거나 ndim != 1이면 ASRRuntimeError.
          2) audio.dtype != float32면 float32로 캐스트(부모 async_transcribe_np도 캐스트하지만 동기 경로 단독 호출 대비).
          3) len(audio) / SAMPLE_RATE < min_audio_seconds 이면 "" 즉시 반환(로그 debug).
          4) NaN/Inf 샘플 포함 시 np.nan_to_num으로 치환(로그 warn).
          5) self.model.transcribe(audio, beam_size, language, condition_on_previous_text=False,
                                    initial_prompt) 호출.
          6) 세그먼트 없음 → "" 반환.
          7) "".join(seg.text for seg in segments) 반환. 양끝 공백 strip.

        Raises:
            ASRRuntimeError: 백엔드(faster-whisper) 내부 예외를 래핑.
        """

    # 상속되는 공개 멤버:
    #   async_transcribe_np(self, audio) -> str  (부모 구현, 오버라이드 안 함)
    #   nparray_to_audio_file(self, audio, sample_rate, file_path) -> None  (부모 구현)
    #   SAMPLE_RATE = 16000, NUM_CHANNELS = 1, SAMPLE_WIDTH = 2
```

### 팩토리/빌더

```python
# src/asr/builder.py
from src.app.config import AppConfig  # M_01
from src.asr.korean_whisper_asr import KoreanWhisperASR

def resolve_model_path(profile: str, asset_root: str = "assets/models") -> str:
    """profile에 따른 whisper 모델 디렉토리 절대 경로 반환.
      - profile == "min" -> <asset_root>/whisper-medium-int8
      - profile == "recommended" -> <asset_root>/whisper-large-v3-int8
    디렉토리 존재 여부는 KoreanWhisperASR 생성자가 검증한다.
    """

def build_asr_engine(app_config: AppConfig,
                     asset_root: str = "assets/models") -> KoreanWhisperASR:
    """AppConfig.profile + AppConfig.paths에서 경로를 유도해 KoreanWhisperASR 인스턴스를 만든다.
    language='ko' 고정, compute_type='int8', device='auto'.
    """
```

### 상수

```python
SUPPORTED_LANGUAGES: frozenset[str | None] = frozenset({"ko", "en", None})
SUPPORTED_COMPUTE_TYPES: frozenset[str] = frozenset({"int8", "float16", "float32"})
SUPPORTED_DEVICES: frozenset[str] = frozenset({"auto", "cpu", "cuda"})
```

---

## 설정 구조 (conf.yaml)

본 모듈은 upstream 스키마(`character_config.asr_config.faster_whisper`)를 그대로 사용한다. 추가로 `app.profile`에 따라 모델 경로 기본값이 달라진다(§성능·메모리).

```yaml
character_config:
  asr_config:
    asr_model: "faster_whisper"         # 고정
    faster_whisper:
      model_path: "assets/models/whisper-large-v3-int8"   # profile=recommended 기본
      download_root: ""                  # 네트워크 금지 — 빈 값 유지
      language: "ko"                     # 한국어 1차. 자동감지는 null
      compute_type: "int8"               # 고정
      device: "auto"                     # auto | cpu | cuda
      prompt: null                       # 선택. 한국어 도메인 어휘 힌트
```

본 모듈이 읽는 키 목록(`KoreanWhisperASR.__init__` 인자와 1:1 대응):

| 키 경로 | 타입 | 기본값 | 범위/검증 |
|---|---|---|---|
| `character_config.asr_config.faster_whisper.model_path` | str | 프로파일별(§성능) | 존재하는 디렉토리. CT2 포맷 가중치(`model.bin` 등) 포함 |
| `character_config.asr_config.faster_whisper.language` | str \| null | `"ko"` | `"ko"` / `"en"` / `null` 셋 중 하나 |
| `character_config.asr_config.faster_whisper.compute_type` | str | `"int8"` | `int8` / `float16` / `float32` |
| `character_config.asr_config.faster_whisper.device` | str | `"auto"` | `auto` / `cpu` / `cuda` |
| `character_config.asr_config.faster_whisper.prompt` | str \| null | `null` | 길이 ≤ 200자(더 길면 `ASRInitError`) |
| `character_config.asr_config.faster_whisper.download_root` | str | `""` | **빈 값 또는 기존 로컬 디렉토리만 허용**. 비어있지 않고 존재하지 않으면 `ASRInitError` |

### 프로파일 분기(AppConfig.profile)

M_01 `AppConfig.profile`과 연동. `build_asr_engine()`이 `conf.yaml`의 `model_path`가 기본값과 동일하거나 누락일 때 프로파일 기반으로 치환.

| profile | model_path 기본 | 예상 RAM | 근거 |
|---|---|---|---|
| `min` | `assets/models/whisper-medium-int8` | ≈ 600 MB | ARCHITECTURE.md §6.1 MIN 프로파일 |
| `recommended` | `assets/models/whisper-large-v3-int8` | ≈ 1.6 GB | ARCHITECTURE.md §6.1 REC 프로파일 |

사용자가 `conf.yaml`에 `model_path`를 명시적으로 기록하면 그 값을 우선한다(명시 > 프로파일 기본 > 하드코드 기본).

---

## 에러 처리 정책

| 상황 | 반응 | 예외 타입 | 로그 레벨 |
|---|---|---|---|
| `model_path` 디렉토리 부재 | 즉시 실패, 앱 기동 중단 | `ASRInitError("model_path not found: <path>")` | ERROR |
| `model_path` 디렉토리는 있으나 CT2 가중치 파일 없음(`model.bin`·`config.json` 부재) | 즉시 실패 | `ASRInitError("model weights missing in: <path>")` | ERROR |
| `download_root`가 비어있지 않고 존재하지 않음 | 즉시 실패(네트워크 풀링 방지) | `ASRInitError("download_root must be empty or an existing directory")` | ERROR |
| `language`가 지원 세트 외 | 즉시 실패 | `ASRInitError("unsupported language: <v>")` | ERROR |
| `compute_type` 지원 외 | 즉시 실패 | `ASRInitError(...)` | ERROR |
| `device="cuda"` 요청 but CUDA 미가용 | 즉시 실패(사용자 의도 명시적 거부) | `ASRInitError("cuda requested but not available")` | ERROR |
| `device="auto"` + CUDA 가용 판별 실패 | `cpu`로 폴백, 경고 로그 | (예외 없음) | WARNING |
| `WhisperModel` 생성자 예외 | 래핑 | `ASRInitError(str(e)) from e` | ERROR |
| 오디오가 None/ndim≠1 | 즉시 실패 | `ASRRuntimeError("invalid audio shape")` | ERROR |
| 오디오 길이 < `min_audio_seconds` (기본 0.2초) | 빈 문자열 반환, 로그 debug | (예외 없음) | DEBUG |
| 오디오 길이 == 0 | 빈 문자열 반환 | (예외 없음) | DEBUG |
| 오디오 dtype ≠ float32 | float32 캐스트, 경고 없음 | (예외 없음) | — |
| 오디오에 NaN/Inf | `np.nan_to_num`으로 치환, 로그 warn 1회 | (예외 없음) | WARNING |
| `WhisperModel.transcribe` 예외 | 래핑, **한 번 재시도 없음**(요청 단위) | `ASRRuntimeError(str(e)) from e` | ERROR |
| 반환 세그먼트 수 0 | `""` 반환 | (예외 없음) | DEBUG |
| `info.language`가 요청 `language`와 불일치(auto 감지) | 인식 결과는 유지하고 warn 로그(한국어 요청인데 영어 감지 등) | (예외 없음) | WARNING |

### 원칙
- **초기화 실패는 앱 기동을 중단시킨다**(M_01 `create_app()`이 예외를 그대로 전파). 이는 STT가 핵심 기능이기 때문.
- **런타임 실패는 세션 단위로 격리**: 한 번의 transcribe 실패가 다음 발화 처리를 막지 않아야 한다. 상위 `WebSocketHandler`가 `ASRRuntimeError`를 캐치해 프론트에 `error` 메시지를 보내고 대화 루프를 유지한다.
- **외부 네트워크 호출 가능성 0**: `download_root=""` 기본값과 경로 사전검증으로, `WhisperModel`이 HuggingFace에서 풀링을 시도할 기회를 차단한다.

---

## 성능·메모리 요구사항

### 모델별 메모리 · 디스크 예산(참고: ARCHITECTURE.md §6.1)

| 모델 | compute_type | 디스크 | 프로세스 RSS 증가 | 프로파일 |
|---|---|---|---|---|
| Whisper medium | int8 | ~470 MB | ~600 MB | MIN |
| Whisper large-v3 | int8 | ~1.5 GB | ~1.6 GB | RECOMMENDED |
| Whisper large-v3 | float16 (GPU) | ~3 GB | ~3.2 GB | (옵션, 본 V1은 기본 int8 유지) |

### 기동 시간
- `KoreanWhisperASR.__init__`(모델 로드 포함) **≤ 3.0 s** (CPU, large-v3 int8, NVMe SSD 기준).
- MIN 프로파일(medium int8)에서는 **≤ 1.5 s**.
- 본 모듈은 지연 로드가 아니라 **즉시 로드**한다 — 첫 발화에서 사용자가 5~10초 지연을 느끼는 것보다 기동 시간을 소비하는 편이 UX에 유리. REQUIREMENTS.md §9 전체 기동 예산 15초 중 3초 이내로 수용.

### 전사 지연(입력 4초 발화 기준, ARCHITECTURE.md §6.2)
| 환경 | medium int8 | large-v3 int8 |
|---|---|---|
| GPU(RTX 4070급) | 0.4 s | 0.6 s |
| CPU(i7-12700) | 1.0 s | 2.5 s |

본 모듈 SLA: 5초 이하 발화에 대해 CPU i7-12700 + large-v3 int8에서 **≤ 3.0 s** (테스트에서 엄격 적용은 하지 않음; 벤치마크는 별도 스크립트로 기록).

### 메모리 상한
- `KoreanWhisperASR` 인스턴스 + `WhisperModel` 합계 RSS 증가가 아래를 초과하면 문제로 간주:
  - MIN 프로파일: 750 MB
  - RECOMMENDED 프로파일: 1.8 GB
- 초과 확인은 벤치마크 마일스톤에서 수행(테스트 CI에서는 측정하지 않음 — 환경 의존).

### 동시성
- `WhisperModel.transcribe`는 스레드-세이프하지 않다(내부 상태 공유). 본 모듈은 **인스턴스당 동시 1개 transcribe**로 제한한다. 상위 레이어가 동시에 호출하면 asyncio 이벤트 루프 내에서 직렬화된다(부모 `async_transcribe_np`가 `asyncio.to_thread`를 쓰므로 스레드풀은 기본 1 사용 — 구현에서 `asyncio.Lock`으로 추가 보호).

---

## 테스트 케이스

경로: `tests/asr/test_*.py`. pytest + `pytest-asyncio`. `WhisperModel` 자체는 무겁기 때문에 **모든 테스트에서 기본적으로 `faster_whisper.WhisperModel`을 MagicMock으로 대체**한다. 별도의 `@pytest.mark.slow` 마커로 실제 모델 로드 테스트를 1건 포함하고, CI에서는 `pytest -m "not slow"` 기본.

### 정상 케이스 (≥5)

**N-1. 정상 초기화 (mock WhisperModel)**
- 입력: `model_path=tmp_model_dir`(디렉토리 존재, `model.bin`과 `config.json` 빈 파일 생성), `language="ko"`, `compute_type="int8"`, `device="auto"`.
- 검증: 인스턴스 생성 성공. `asr.language == "ko"`, `asr.compute_type == "int8"`, `asr.resolved_device in {"cpu","cuda"}`.

**N-2. 한국어 오디오 전사 (mock segments)**
- 입력: `audio = np.random.rand(16000*2).astype(np.float32)` (2초). mock `WhisperModel.transcribe`가 `[Segment(text="안녕하세요"), Segment(text=" 반갑습니다")]`와 `info(language="ko")` 반환.
- 검증: `asr.transcribe_np(audio) == "안녕하세요 반갑습니다"`. `WhisperModel.transcribe`가 `beam_size=5, language="ko", condition_on_previous_text=False, initial_prompt=None` 인자로 호출됨(`call_args` 확인).

**N-3. async 경로 동작**
- 입력: `await asr.async_transcribe_np(audio)` (mock).
- 검증: 부모 구현이 스레드로 `transcribe_np`를 호출. 반환 문자열이 정상. `asyncio.CancelledError`가 상위로 전파 가능함을 `asyncio.wait_for(..., timeout=0)` 시나리오로 확인.

**N-4. `prompt` 설정 전달**
- 입력: 생성자에 `initial_prompt="사내 회의 기술 용어"`.
- 검증: `transcribe_np` 호출 시 mock의 `call_args.kwargs["initial_prompt"] == "사내 회의 기술 용어"`.

**N-5. 영어 자동 전환**
- 입력: `language=None`, mock segments가 `info.language="en"`, text `["Hello world"]`.
- 검증: 반환 `"Hello world"`, warn 로그 없음(요청이 None이었으므로 언어 불일치 경고 없음).

**N-6. `build_asr_engine` 프로파일 경로 해석**
- 입력: `AppConfig(profile="min", paths=default)`, `asset_root=tmp_asset_root`. `tmp_asset_root/whisper-medium-int8/` 생성.
- 검증: 반환 인스턴스의 `model_path`가 `<tmp_asset_root>/whisper-medium-int8`로 끝남.

### 엣지 케이스 (≥5)

**E-1. 0 길이 오디오**
- 입력: `audio = np.zeros(0, dtype=np.float32)`.
- 검증: `asr.transcribe_np(audio) == ""`. `WhisperModel.transcribe`가 **호출되지 않음**(`call_count == 0`).

**E-2. 초단시간 오디오(0.1초)**
- 입력: `audio = np.random.rand(1600).astype(np.float32)` (0.1초 < `min_audio_seconds=0.2`).
- 검증: `asr.transcribe_np(audio) == ""`. `call_count == 0`. 로그 레벨 DEBUG 레코드 존재(`caplog`).

**E-3. dtype 변환 (int16 입력)**
- 입력: `audio = (np.random.rand(32000) * 32767).astype(np.int16)` (2초).
- 검증: 호출 직전에 float32 캐스트. mock에 전달된 첫 인자의 `dtype == np.float32`.

**E-4. NaN/Inf 포함**
- 입력: `audio = np.array([0.1, np.nan, np.inf, -np.inf, 0.2] * 10000, dtype=np.float32)`.
- 검증: mock에 전달된 배열에 NaN/Inf 없음(`np.isfinite(...).all() == True`). WARNING 로그 1회.

**E-5. 세그먼트 수 0**
- 입력: mock `transcribe`가 빈 리스트 + `info` 반환.
- 검증: 반환 `""`. 예외 없음.

**E-6. `info.language`와 요청 불일치**
- 입력: `language="ko"`, mock `info.language="en"`, segments `[Segment(text="Hello")]`.
- 검증: 반환 `"Hello"`. WARNING 로그 레코드 1건.

**E-7. `device="auto"` + CUDA 사용 불가**
- 입력: `torch.cuda.is_available`을 False로 mock(또는 `faster_whisper` 내부 CUDA 체크를 mock).
- 검증: `asr.resolved_device == "cpu"`. WARNING 없음(auto의 정상 폴백).

### 적대적 케이스 (≥3)

**A-1. 존재하지 않는 `model_path`**
- 입력: `model_path="/no/such/dir"`.
- 검증: 생성자에서 `ASRInitError`. `WhisperModel` 생성자는 호출되지 않음.

**A-2. `download_root` 네트워크 우회 시도**
- 입력: `model_path="/nonexistent/whisper"`, `download_root="https://huggingface.co/..."`.
- 검증: 생성자에서 `ASRInitError("download_root must be empty or an existing directory")`. `WhisperModel`이 **절대** 인스턴스화되지 않음(mock의 `call_count == 0`).

**A-3. `device="cuda"` 강제 but 불가**
- 입력: `device="cuda"`, CUDA 미가용 환경.
- 검증: `ASRInitError("cuda requested but not available")`. auto 폴백하지 않음(사용자 의도를 존중해 실패).

**A-4. 잘못된 language 주입**
- 입력: `language="xx"`.
- 검증: `ASRInitError("unsupported language: xx")`.

**A-5. 비정상 numpy 배열(2D)**
- 입력: `audio = np.zeros((2, 16000), dtype=np.float32)` (stereo).
- 검증: `ASRRuntimeError("invalid audio shape")`. mock 호출 없음.

**A-6. 백엔드가 예외를 던짐**
- 입력: mock `transcribe`가 `RuntimeError("CUDA OOM")` raise.
- 검증: `ASRRuntimeError("CUDA OOM")`이 상위로 전파. `__cause__`가 원본 `RuntimeError`.

### Slow 마커 실제 로드 테스트(선택, CI 기본 skip)

**S-1. 실제 medium int8 로드 + 샘플 WAV 전사**
- 전제: `assets/models/whisper-medium-int8/` 존재.
- 입력: `tests/asr/fixtures/sample_ko_3s.wav`를 numpy float32로 읽어 전사.
- 검증: 빈 문자열이 아님. 한글 유니코드 범위 문자 1자 이상 포함.

---

## 오프라인 빌드 메모

### 모델 파일 배치
- `assets/models/whisper-large-v3-int8/`: CT2 양자화 가중치. faster-whisper 공식 저장소(`Systran/faster-whisper-large-v3`) 사본을 빌드 머신에서 내려받아 복사.
- `assets/models/whisper-medium-int8/`: 동일(`Systran/faster-whisper-medium`). MIN 프로파일용.
- 각 디렉토리는 최소 `model.bin`, `config.json`, `tokenizer.json`, `vocabulary.txt`(또는 `vocabulary.json`)을 포함해야 한다. 파일 부재 시 본 모듈의 초기화 검증이 실패한다.

### `.gitignore`
- `assets/models/` 전체 제외 유지(CLAUDE.md 기존 규칙).

### `scripts/bundle_deps.sh` 추가 항목
1. Python 패키지
   - `faster-whisper>=1.0,<2` — upstream과 동일 버전 핀 유지.
   - `ctranslate2>=4.4,<5` (faster-whisper 전이 의존).
   - `av>=11,<14` (오디오 디코딩 보조. upstream이 이미 사용 중이면 변경 없음).
   - `onnxruntime>=1.17,<2`는 VAD(M_03)와 공유.
2. 모델 아티팩트 다운로드 블록:
   ```bash
   # 빌드 머신에서만 실행. 사내 PC에서는 절대 실행 금지.
   huggingface-cli download Systran/faster-whisper-large-v3 \
       --local-dir assets/models/whisper-large-v3-int8 --local-dir-use-symlinks False
   huggingface-cli download Systran/faster-whisper-medium \
       --local-dir assets/models/whisper-medium-int8 --local-dir-use-symlinks False
   ```
3. 번들 인스톨러 포함 시 `assets/models/whisper-*/` 디렉토리 통째로 복사.

### 네트워크 검증
- `scripts/verify_offline.ps1`(M_01 연계)가 `KoreanWhisperASR` 초기화 직후에도 외부 DNS 조회·HTTP 요청이 발생하지 않았는지 Windows 방화벽 로그로 확인한다. 본 모듈의 `download_root=""` 정책으로 인해 `WhisperModel`의 내부 HF 풀링은 원천 차단된다.

### pyproject.toml 추가 예(PR 메시지 기록 대상)
```toml
[project.dependencies]
faster-whisper = ">=1.0,<2"
ctranslate2 = ">=4.4,<5"
```

---

## Definition of Done

### 공통 (CLAUDE.md "산출물 체크리스트")
- [ ] `specs/M_02_ASREngine_SPEC.md` (본 문서) 사용자 승인.
- [ ] `src/asr/` 전체 파일 구현(`korean_whisper_asr.py`, `builder.py`, `errors.py`, `__init__.py`).
- [ ] `tests/asr/` 테스트: 정상 ≥5, 엣지 ≥5, 적대적 ≥3 (본 스펙의 N/E/A 케이스 전량).
- [ ] `ruff format .`, `ruff check .`, `mypy src/asr/`, `pytest tests/asr/ -v` 모두 통과.
- [ ] `reviews/M_02_ASREngine_REVIEW.md`에 Critic PASS.
- [ ] `docs/MODULES.md`의 M_02 상태가 ✅ DONE으로 갱신.

### M_02 고유
- [ ] `KoreanWhisperASR`가 upstream `ASRInterface`를 상속하고 `transcribe_np`를 구현한다.
- [ ] 생성자에서 `model_path` 존재성·필수 파일(`model.bin`, `config.json`) 확인 로직이 동작한다.
- [ ] `download_root=""` 기본값이 유지되며, 비어있지 않고 존재하지 않는 경로는 거부된다.
- [ ] `language` 허용 세트 `{"ko","en",None}` 외 값은 `ASRInitError`를 발생시킨다.
- [ ] `device="auto"`는 CUDA 가용 시 `"cuda"`, 아니면 `"cpu"`로 해석되어 `resolved_device`에 기록된다.
- [ ] `device="cuda"` 요청에 CUDA가 없으면 auto 폴백 없이 `ASRInitError`로 실패한다.
- [ ] 0 길이·0.1초 오디오가 빈 문자열을 반환하며 `WhisperModel.transcribe`를 호출하지 않는다.
- [ ] NaN/Inf 오디오 샘플은 `np.nan_to_num`으로 치환되며 WARNING 로그가 정확히 1회 발생한다.
- [ ] `build_asr_engine(app_config)`가 `profile`에 따라 올바른 모델 디렉토리 경로를 선택한다.
- [ ] `upstream/Open-LLM-VTuber/src/open_llm_vtuber/asr/*` 파일이 **수정되지 않았음**을 파일 해시 또는 `git diff` 검사로 확인한다(M_01과 동일 검사 공유).
- [ ] `faster-whisper`, `ctranslate2`가 `pyproject.toml`과 `scripts/bundle_deps.sh` 양쪽에 반영됨.

---

## 의존성

### Python 패키지 (pyproject.toml 추가)

| 패키지 | 버전 핀 | 용도 | 사유 |
|---|---|---|---|
| `faster-whisper` | `>=1.0,<2` | STT 백엔드 | upstream과 동일. large-v3 int8 지원 |
| `ctranslate2` | `>=4.4,<5` | CT2 런타임(faster-whisper 전이 의존) | int8 양자화 모델 실행기 |
| `numpy` | `>=1.26,<3` | 오디오 배열 | upstream 이미 사용 |

`onnxruntime`은 M_03 VADEngine과 공유이므로 본 모듈에서 추가하지 않는다.

### 런타임 전제
- Python 3.12 이상.
- upstream 소스 트리가 `upstream/Open-LLM-VTuber/src`에 존재하고 `sys.path`에 포함(M_01 설정과 동일).
- 모델 디렉토리가 `assets/models/whisper-*-int8/`에 사전 배치(오프라인 번들 빌드 책임).

### 모듈 의존
| 대상 | 관계 |
|---|---|
| M_01 AppCore | `AppConfig.profile`, `AppConfig.paths`를 주입받음. `AppServiceContext.load_from_config`에서 `KoreanWhisperASR` 인스턴스를 `asr_engine`에 할당 |
| upstream `ASRInterface` | 상속 |
| upstream `FasterWhisperConfig` | 설정 스키마 REUSE |

**M_02는 M_03(VAD)·M_05(LLM)·M_04(TTS)에 의존하지 않는다.** 상위 레이어(conversation orchestrator, upstream REUSE)가 VAD 결과 numpy 버퍼를 본 모듈에 전달한다.

---

## 디렉토리 구조

```
src/asr/
├── __init__.py              # 공개 심볼: KoreanWhisperASR, build_asr_engine, ASRInitError, ASRRuntimeError
├── korean_whisper_asr.py    # KoreanWhisperASR 본체
├── builder.py               # resolve_model_path, build_asr_engine
└── errors.py                # ASRInitError, ASRRuntimeError

tests/asr/
├── __init__.py
├── conftest.py              # mock WhisperModel fixture, tmp_model_dir fixture
├── test_init.py             # N-1, A-1~A-4, E-7
├── test_transcribe.py       # N-2~N-5, E-1~E-6, A-5, A-6
├── test_builder.py          # N-6, profile 분기
└── fixtures/
    └── sample_ko_3s.wav     # slow 마커 테스트용 (선택)
```

---

## 스펙 외 사항 (명시적 제외)

본 모듈의 책임이 **아닌** 항목:

1. **VAD (Voice Activity Detection)**: M_03 VADEngine이 담당. 본 모듈은 이미 잘라진 float32 발화 버퍼만 입력으로 받는다.
2. **마이크 캡처·WebSocket 오디오 수신·포맷 변환**: upstream `WebSocketHandler._handle_audio_data`·`_handle_raw_audio_data`(M_01 REUSE) 책임.
3. **스트리밍 전사(부분 결과 방출)**: V1은 발화 종료 후 1회 전사. 스트리밍은 범위 외.
4. **다국어 자동감지 로직 개선**: upstream faster-whisper의 자동감지를 그대로 사용한다. 본 모듈은 감지 결과를 로그로 기록만 한다.
5. **번역(STT 결과를 다른 언어로)**: upstream `translate_engine`·`tts_preprocessor_config` 담당, 기본 OFF.
6. **발화 인터럽트 (`<|PAUSE|>`·`<|RESUME|>` 처리)**: M_05 LLMAgent·upstream `conversation_handler`가 담당.
7. **화자 분리(diarization)**: 범위 외. 단일 사용자 전제(REQUIREMENTS.md §10).
8. **백엔드 교체 가능한 팩토리 확장**: upstream `ASRFactory`는 그대로 두되, 본 프로젝트는 항상 `KoreanWhisperASR`만 쓴다. 다른 백엔드가 필요하면 `CHANGE_REQUESTS.md` 경유.
9. **모델 파일 다운로드·버전 관리 자동화**: 오프라인 번들 빌드 스크립트 책임. 런타임은 파일 존재만 검증.
10. **GPU 메모리 관리·다중 인스턴스**: 단일 인스턴스만 사용. 동시 transcribe는 `asyncio.Lock`으로 직렬화.

---

## 부록: upstream 경로·심볼 인덱스 (실재 확인)

본 스펙 작성 중 `/mnt/c/projects/ai-assistant/upstream/Open-LLM-VTuber/src/open_llm_vtuber/` 하의 실제 파일을 읽어 시그니처를 확정했다:

- `asr/asr_interface.py` L1~L57: `ASRInterface` (abstract), `SAMPLE_RATE=16000`, `NUM_CHANNELS=1`, `SAMPLE_WIDTH=2`, `async_transcribe_np` 기본 구현(`asyncio.to_thread` + float32 캐스트), `transcribe_np` (abstract), `nparray_to_audio_file`.
- `asr/faster_whisper_asr.py` L1~L50: `VoiceRecognition(ASRInterface)`, 생성자 시그니처 `(model_path, download_root, language, device, compute_type, prompt)`, `transcribe_np`는 `WhisperModel.transcribe(audio, beam_size=5, language, condition_on_previous_text=False, initial_prompt)` 호출.
- `asr/asr_factory.py` L7~L62: `ASRFactory.get_asr_system` 분기. `"faster_whisper"` 지원.
- `config_manager/asr.py` L28~L62: `FasterWhisperConfig` — `model_path, download_root, language(Optional), device(default "auto"), compute_type(Literal int8/float16/float32), prompt(Optional)`.
- `config_manager/asr.py` L310~L375: `ASRConfig` — `asr_model` Literal 후보에 `faster_whisper` 포함.
- `service_context.py` L323~L333: `init_asr(asr_config)` 동작 — 조건부 재초기화. 본 프로젝트는 이를 M_01 `AppServiceContext.load_from_config`에서 우회하여 `KoreanWhisperASR`로 교체한다(§배선).
