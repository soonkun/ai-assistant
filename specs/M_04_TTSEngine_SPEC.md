# M_04 TTSEngine — 스펙

## 목적과 범위

### 목적
한국어 여성 음성을 1차로 합성하는 오프라인 TTS 엔진을 제공한다. V1 기본값은 **MeloTTS(한국어 `KR` 화자)** 이며, 사용자가 명시적으로 옵트인한 경우에만 **XTTS v2(Coqui, 화자 클로닝)** 로 전환한다. upstream `TTSInterface`의 계약(`generate_audio`, `async_generate_audio`)을 준수하는 두 개의 독립적인 구현체를 신규로 작성하고, XTTS v2 용도로 **화자 참조 WAV 업로드 HTTP 엔드포인트 1종**을 M_01 FastAPI 라우터에 추가한다.

### 범위 (In-Scope)
1. `MeloTTSEngine` 구현 — `melo.api.TTS`를 얇게 래핑. 한국어(`KR` 화자/`KR` 언어) 전용 초기화, 속도·샘플레이트 파라미터 노출, 출력 WAV 파일 경로 반환.
2. `XttsV2Engine` 구현 — Coqui `TTS.api.TTS`(model_name `"tts_models/multilingual/multi-dataset/xtts_v2"`)를 로컬 디렉토리에서 로드. 화자 참조 WAV 3~6초 필수, 언어 코드 `"ko"`.
3. 공통 예외 정의: `TTSInitError`, `TTSRuntimeError`.
4. 빌더 `build_tts_engine(app_config)` — `AppConfig.tts`(신규 서브스키마)를 읽어 `MeloTTSEngine` 또는 `XttsV2Engine` 인스턴스를 반환.
5. 화자 참조 WAV 업로드 HTTP 엔드포인트 설계 명세 — 구현 자체는 M_01 AppCore가 라우터 추가 시 본 스펙을 따른다(실제 라우터 등록 함수는 본 모듈 `src/tts/upload.py`에서 제공하고 M_01이 주입).
6. WAV 파일 유효성 검증 유틸(`validate_speaker_wav`) — 채널 수·샘플레이트·길이·포맷 검사.
7. 네트워크 차단 정책 — `melo`의 NLTK/HuggingFace 다운로드 경로와 Coqui `TTS`의 모델 자동 다운로드·EULA prompt 경로를 전부 차단.
8. 단위 테스트 (정상 ≥5, 엣지 ≥5, 적대적 ≥3; 두 엔진 모두 커버).
9. 오프라인 번들 항목(`scripts/bundle_deps.sh` 업데이트, `assets/models/melotts-ko/`, `assets/models/xtts_v2/`).

### 범위 외 (Out-of-Scope, 명시적 제외)
- **스트리밍 TTS(청크 단위 WAV 방출)**. V1은 `async_generate_audio`가 한 번에 완성된 WAV 파일 경로를 반환한다. 스트리밍은 V2 후보 — REQUIREMENTS.md §9 "스트리밍 TTS 첫 청크" SLA는 upstream `TTSManager`가 담당하며, 본 모듈은 upstream의 문장 분할 후 문장 단위로 반복 호출되는 구조를 유지한다.
- **upstream TTS 백엔드들(`piper_tts`, `azure_tts`, `edge_tts`, `coqui_tts`, `x_tts`, `bark_tts`, `gpt_sovits_tts`, 그 외)의 사용·수정·팩토리 확장**. 본 프로젝트는 upstream `TTSFactory`를 **수정하지 않는다**. `service_context.init_tts()`가 팩토리를 호출하는 경로는 M_01 `AppServiceContext.load_from_config`에서 덮어써(§배선 참조) 본 모듈의 엔진을 직접 주입한다.
- **음성 전처리·후처리(한자→한글 변환, 숫자 읽기 규칙 등)**. upstream `tts_preprocessor_config`가 담당. 본 모듈은 `text` 인자를 그대로 합성한다.
- **TTS 번역(입력과 다른 언어로 발화)**. upstream `translate_engine` 영역. 본 모듈은 `translate_audio: false` 전제.
- **화자 클로닝 학습·파인튜닝**. XTTS v2의 zero-shot 경로만 사용.
- **립싱크 데이터(viseme 시퀀스) 생성**. M_08 AvatarState에서 opacity 펄스로 처리.
- **오디오 재생**. 본 모듈은 WAV 파일 절대경로만 반환. 재생(`audio-payload` WebSocket 메시지 생성)은 upstream `TTSManager`·`WebSocketHandler` 영역.
- **화자 참조 WAV 레지스트리 UI**. M_12 Frontend 범위.
- **MeloTTS 추가 언어(EN/ZH/JP/FR/ES)**. V1은 한국어 단독. 추가 언어 요청은 `CHANGE_REQUESTS.md` 경유.
- **GPU 스케줄링·다중 엔진 동시 실행**. 단일 엔진 인스턴스 가정.

---

## 요구사항 연결

| REQUIREMENTS.md 항목 | M_04 기여 |
|---|---|
| §0 오프라인 / Windows 10/11 | 모델 파일은 `assets/models/melotts-ko/`, `assets/models/xtts_v2/`에 사전 배치. melo/Coqui의 런타임 HuggingFace/NLTK 다운로드 경로 차단(환경변수 + 경로 검증) |
| §1.1 TTS: 한국어 여성 목소리 기본 | MeloTTS `language="KR"`, `speaker="KR"` 고정. 검수 결과(R-05)에 따라 음성 결과가 여성 화자임을 QA 체크리스트로 확인 |
| §1.1 음성 클로닝(Voice Clone) 옵션 | XTTS v2 엔진 구현 + 화자 참조 WAV 업로드 API |
| §1.1 전이중(사용자가 AI 발화 중간에 끼어들면 즉시 멈춘다) | 본 모듈은 `async_generate_audio` 취소(`asyncio.CancelledError`) 전파를 허용. 파일이 이미 기록되었으면 호출자가 `remove_file`로 정리 |
| §8 TTS 모델: MeloTTS(한국어) 기본 + XTTS v2 옵션 | 본 스펙 §공개 API |
| §9 응답 지연 (첫 음성까지 GPU 2s / CPU 6s, 스트리밍 첫 청크 기준) | 본 모듈은 문장 단위 합성. ARCHITECTURE.md §6.2의 MeloTTS 첫 청크 GPU 0.4s / CPU 0.8s 예산을 지킨다. 첫 문장 합성 단독 SLA는 §성능 참조 |
| §9 메모리 (MIN 14GB 이하 / REC 20GB 이하) | ARCHITECTURE.md §6.1 기준 MeloTTS 450 MB. XTTS v2는 +1.8 GB, **기본 OFF**. 활성화되었을 때만 로드하여 예산 위반을 회피(동시 적재 금지) |
| §9 외부 네트워크 호출 금지 | melo/Coqui 양측에서 발생 가능한 HuggingFace·NLTK 원격 풀링을 환경변수(`HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `COQUI_TOS_AGREED=1`, `NLTK_DATA=<local>`)와 모델 경로 사전 검증으로 원천 차단 |
| §10 다중 사용자 불가 | 단일 엔진 인스턴스. 동시 `generate_audio` 호출은 `asyncio.Lock`으로 직렬화 |

---

## upstream 재사용 분석

### 분류: **NEW** (upstream `TTSInterface` 계약만 REUSE)

upstream에는 `tts/melo_tts.py`(melo 래퍼, 그러나 EN 기본 + nltk 온라인 의존), `tts/coqui_tts.py`(Coqui `TTS.api` 래퍼, EULA prompt 미차단), `tts/x_tts.py`(별도 HTTP 서버 호출 — 본 프로젝트와 무관), `tts/piper_tts.py`(한국어 모델 없음 → D-03) 등이 있으나, 어느 것도 본 프로젝트의 요구사항(한국어 기본, 오프라인 강제, 화자 참조 업로드 API)을 그대로 만족하지 않는다. 따라서 **본 모듈은 신규 작성**하며, upstream의 `TTSInterface` 계약만 상속한다.

### REUSE (무수정 호출)

| upstream 경로 | 심볼 | 사용 방식 |
|---|---|---|
| `src/open_llm_vtuber/tts/tts_interface.py` | `TTSInterface` (abstract) | **베이스 클래스로 상속**. `async_generate_audio`(기본 구현: `asyncio.to_thread(self.generate_audio, text, file_name_no_ext)`)를 그대로 사용. `remove_file`, `generate_cache_file_name`도 상속 |
| `src/open_llm_vtuber/config_manager/tts.py` | `TTSConfig`, `MeloTTSConfig`, (참고: `CoquiTTSConfig`) | 본 프로젝트는 **upstream `TTSConfig` 스키마를 수정하지 않는다**. `conf.yaml`의 `character_config.tts_config.tts_model`은 `"melo_tts"`로 두고, `melo_tts` 섹션의 필드를 본 모듈이 별도로 읽는다. XTTS v2는 upstream `x_tts`(HTTP)·`coqui_tts` 중 어느 것과도 구조가 다르므로 본 프로젝트 고유 필드(`AppConfig.tts`)에 분리 |

### DROP (사용 안 함)

| upstream 심볼 | 이유 |
|---|---|
| `tts/melo_tts.py` (`TTSEngine`) | EN 기본·nltk `averaged_perceptron_tagger_eng` 자동 다운로드 경로가 온라인 의존. 한국어 전용으로 재작성 필요 |
| `tts/coqui_tts.py` (`TTSEngine`) | EULA 동의 prompt 미차단, device 자동 감지 로직이 `torch.cuda.is_available()` 호출로 GPU 환경에서 의도와 다르게 cuda 선점 가능 |
| `tts/x_tts.py` | 별도 HTTP XTTS 서버(`http://127.0.0.1:8020`)를 전제 — 본 프로젝트는 in-process 실행 |
| `tts/piper_tts.py` | D-03: 한국어 모델 없음 / 대체 모델 라이선스 부적합 |
| `tts_factory.py`의 `"melo_tts"`, `"coqui_tts"`, `"x_tts"` 분기 | upstream 파일 수정 금지. 본 프로젝트는 팩토리를 거치지 않고 직접 주입 |

### 배선 정책

upstream `service_context.py` L335~L343의 `init_tts(tts_config)`는 `TTSFactory.get_tts_engine(tts_config.tts_model, **...)`을 호출해 `self.tts_engine`을 세팅한다. **upstream 파일 수정 금지**이므로 본 프로젝트는 M_02(ASR)와 동일 패턴을 사용한다:

1. M_01 `AppServiceContext.load_from_config`가 `super().load_from_config(config)`를 호출한 **직후**, `self.tts_engine`을 본 모듈 `build_tts_engine(app_config)` 결과로 **재할당**한다.
2. upstream `init_tts`는 한 번 인스턴스를 만들고 폐기되지만, 본 프로젝트는 `conf.yaml`에 `tts_model="melo_tts"`로 두고 `melo_tts` 섹션을 upstream 스키마와 호환되도록 채워 유효성 검증을 통과시킨 뒤, 실제 엔진은 본 모듈이 덮어쓴다. upstream 팩토리가 호출되더라도 **인스턴스는 즉시 GC**되도록 보장(낭비는 있으나 수용 가능 — 모델 로딩 자체는 `MeloTTS` 생성자에서 발생하므로 낭비 비용이 크다. 이를 회피하기 위해 아래 "init_tts 가드" 경로를 채택).
3. **init_tts 가드**: `AppServiceContext.load_from_config` 오버라이드에서 `super().load_from_config(config)`를 호출하기 **전에** `self.tts_engine = build_tts_engine(app_config)` + `self.character_config.tts_config = config.character_config.tts_config`를 선세팅한다. upstream `init_tts`의 `if not self.tts_engine or (self.character_config.tts_config != tts_config):` 가드에 의해 재초기화가 스킵된다. 이 선세팅 로직은 M_01 스펙에 반영(M_02와 동일 패턴).

**M_04의 책임**: `MeloTTSEngine`, `XttsV2Engine`, `build_tts_engine(app_config)`, `validate_speaker_wav`, `create_speaker_upload_router()` 제공. `AppServiceContext` 통합은 M_01.

---

## 공개 API

> Python 3.12 타입 힌트. `async def`는 부모 기본 구현(`asyncio.to_thread`) 상속. 에러는 아래 두 예외로만 발생.

### 예외 타입

```python
# src/tts/errors.py
class TTSInitError(Exception):
    """모델 파일 누락, 라이브러리 로드 실패, 화자 참조 WAV 검증 실패 등 초기화 단계 에러."""

class TTSRuntimeError(Exception):
    """generate_audio 도중의 복구 불가능한 합성 실패."""
```

### MeloTTS 엔진

```python
# src/tts/melo_tts_engine.py
from open_llm_vtuber.tts.tts_interface import TTSInterface  # upstream

class MeloTTSEngine(TTSInterface):
    """한국어(KR) 전용 MeloTTS 엔진.

    upstream TTSInterface를 상속. async_generate_audio는 부모 기본 구현을 사용(asyncio.to_thread).
    """

    # 초기화 후 외부 코드에서 읽을 수 있는 메타
    model_dir: str
    language: str        # 항상 "KR"
    speaker: str         # 항상 "KR" (MeloTTS 한국어 스피커)
    speaker_id: int      # melo 내부에서 해석된 int id
    sample_rate: int     # 기본 24000
    speed: float         # 0.5 ~ 2.0
    device: str          # "auto" | "cpu" | "cuda"
    resolved_device: str # "cuda" | "cpu" (auto 해석 결과)
    cache_dir: str       # 기본 "cache"

    def __init__(
        self,
        model_dir: str,
        speaker: str = "KR",
        language: str = "KR",
        speaker_id: int | None = None,
        sample_rate: int = 24000,
        speed: float = 1.0,
        device: str = "auto",
        cache_dir: str = "cache",
    ) -> None:
        """즉시 로드. 지연 로드 아님(첫 발화 지연 방지).

        Raises:
            TTSInitError:
              - model_dir 미존재 또는 비어 있음(필수 파일 누락)
              - language가 "KR" 이외
              - speaker가 "KR" 이외
              - speed가 0.5~2.0 범위 밖
              - sample_rate가 16000/22050/24000/44100/48000 외
              - device가 {"auto","cpu","cuda"} 외
              - device="cuda" 요청인데 CUDA 미가용
              - `melo.api.TTS` 생성자 예외
              - hps.data.spk2id에 "KR" 부재 또는 speaker_id 범위 초과
        """

    def generate_audio(
        self,
        text: str,
        file_name_no_ext: str | None = None,
    ) -> str:
        """동기 TTS. 부모 async_generate_audio가 스레드로 래핑해 호출.

        동작:
          1) text is None or text.strip() == "" -> TTSRuntimeError("empty text").
          2) len(text) > 1000 -> 1000자에서 절단 + WARNING 로그 1회
             (MeloTTS 한 문장 상한 경험치. upstream TTSManager가 문장 분할 담당).
          3) cache_dir에 "<file_name_no_ext | 'temp'>.wav" 파일명 생성.
          4) self._model.tts_to_file(text, self.speaker_id, output_path, speed=self.speed) 호출.
          5) os.path.exists(output_path) == False -> TTSRuntimeError.
          6) 절대 경로 반환.

        Raises:
            TTSRuntimeError: 백엔드 예외 또는 출력 파일 누락.
        """
```

### XTTS v2 엔진

```python
# src/tts/xtts_v2_engine.py
from open_llm_vtuber.tts.tts_interface import TTSInterface  # upstream

class XttsV2Engine(TTSInterface):
    """Coqui XTTS v2 화자 클로닝 엔진. 사용자 옵트인 시에만 활성.

    upstream TTSInterface를 상속. async_generate_audio는 부모 기본 구현 사용.
    """

    model_dir: str
    speaker_wav: str     # 절대 경로. 3~6초 mono 16k/22k/24k/44.1k/48k WAV
    language: str        # 항상 "ko"
    device: str
    resolved_device: str
    cache_dir: str
    min_speaker_wav_sec: float  # 기본 3.0
    max_speaker_wav_sec: float  # 기본 30.0 (권장은 3~6초지만 상한은 느슨하게)

    def __init__(
        self,
        model_dir: str,
        speaker_wav: str,
        language: str = "ko",
        device: str = "auto",
        cache_dir: str = "cache",
        min_speaker_wav_sec: float = 3.0,
        max_speaker_wav_sec: float = 30.0,
    ) -> None:
        """즉시 로드. 첫 호출에서 xtts_v2 모델 전체가 메모리로 올라가므로 1~3초 소요.

        Raises:
            TTSInitError:
              - model_dir 미존재 또는 필수 파일(config.json, model.pth, vocab.json 등) 누락
              - speaker_wav 파일 미존재
              - validate_speaker_wav 실패(채널 수, 샘플레이트, 길이, 포맷 중 하나라도 위반)
              - language != "ko"
              - device 지원 외 / cuda 요청인데 미가용
              - `TTS.api.TTS` 생성자 예외(EULA 미동의, 모델 파일 손상 등)
        """

    def generate_audio(
        self,
        text: str,
        file_name_no_ext: str | None = None,
    ) -> str:
        """동기 TTS. 부모 async_generate_audio가 스레드로 래핑해 호출.

        동작:
          1) text 검증(§MeloTTS와 동일).
          2) output_path 생성.
          3) self._tts.tts_to_file(
                 text=text,
                 speaker_wav=self.speaker_wav,
                 language=self.language,
                 file_path=output_path
             ) 호출.
          4) 파일 존재 확인 후 절대 경로 반환.

        Raises:
            TTSRuntimeError: 백엔드 예외.
        """
```

### 화자 WAV 검증 유틸

```python
# src/tts/speaker_wav.py
from pathlib import Path

@dataclass(frozen=True)
class SpeakerWavInfo:
    path: str
    channels: int          # 1만 허용(mono)
    sample_rate: int       # {16000, 22050, 24000, 44100, 48000} 중 하나
    duration_sec: float
    bit_depth: int         # 16만 허용(PCM_16)
    sha256: str            # 중복 업로드 감지용

ALLOWED_SAMPLE_RATES: frozenset[int] = frozenset({16000, 22050, 24000, 44100, 48000})

def validate_speaker_wav(
    path: str,
    min_sec: float = 3.0,
    max_sec: float = 30.0,
) -> SpeakerWavInfo:
    """WAV 파일 유효성 검증.

    검증 항목:
      - 파일 존재, 확장자 ".wav"
      - RIFF/WAVE 헤더(표준 라이브러리 `wave` 모듈로 파싱)
      - 채널 수 == 1 (mono)
      - sample_rate ∈ ALLOWED_SAMPLE_RATES
      - bit depth == 16 (PCM_16)
      - duration in [min_sec, max_sec]
      - 전체 파일 크기 ≤ 10 MB (DoS 방지)

    Raises:
        ValueError: 위 조건 중 하나라도 위반. 메시지에 어떤 필드가 실패했는지 명시.
        FileNotFoundError: 파일 부재.
    """
```

### 빌더

```python
# src/tts/builder.py
from src.app.config import AppConfig
from src.tts.melo_tts_engine import MeloTTSEngine
from src.tts.xtts_v2_engine import XttsV2Engine

TtsEngine = MeloTTSEngine | XttsV2Engine

def resolve_melotts_dir(asset_root: str = "assets/models") -> str:
    """<asset_root>/melotts-ko 반환."""

def resolve_xtts_v2_dir(asset_root: str = "assets/models") -> str:
    """<asset_root>/xtts_v2 반환."""

def build_tts_engine(
    app_config: AppConfig,
    asset_root: str = "assets/models",
    cache_dir: str = "cache",
) -> TtsEngine:
    """AppConfig.tts에 따라 엔진을 구성한다.

    - app_config.tts.engine == "melo" -> MeloTTSEngine
    - app_config.tts.engine == "xtts_v2" -> XttsV2Engine
        - app_config.tts.xtts.speaker_wav가 None이면 TTSInitError.
        - 지정된 speaker_wav 파일은 validate_speaker_wav 통과해야 함.

    Raises:
        TTSInitError: 설정 값 위반 또는 모델 로드 실패.
    """
```

### 화자 WAV 업로드 라우터 (M_01에 주입)

```python
# src/tts/upload.py
from fastapi import APIRouter, UploadFile, HTTPException
from pydantic import BaseModel

class SpeakerWavUploadResponse(BaseModel):
    id: str                      # sha256 prefix 16자
    path: str                    # 서버 로컬 저장 절대 경로
    duration_sec: float
    sample_rate: int
    channels: int

class SpeakerWavListItem(BaseModel):
    id: str
    path: str
    duration_sec: float
    sample_rate: int
    created_at: str              # ISO8601

def create_speaker_upload_router(
    storage_dir: str,            # 예: "data/speaker_refs"
    max_bytes: int = 10 * 1024 * 1024,
) -> APIRouter:
    """M_01 FastAPI 앱에 포함될 라우터를 생성한다.

    엔드포인트:
      POST   /api/tts/speaker-refs         (multipart/form-data: file=<wav>)
      GET    /api/tts/speaker-refs         (목록)
      GET    /api/tts/speaker-refs/{id}    (메타 조회)
      DELETE /api/tts/speaker-refs/{id}

    POST 로직:
      1) Content-Length가 max_bytes를 넘으면 413.
      2) UploadFile.filename 확장자 검사(.wav만 허용, 400).
      3) 스트림 저장: <storage_dir>/<timestamp>_<orig_name>.wav
         - 저장 중 누적 바이트가 max_bytes 초과 시 삭제 + 413.
      4) validate_speaker_wav(저장 경로) 실행. 실패 시 400 + 파일 삭제.
      5) sha256 계산. 이미 동일 sha256 존재 시 기존 id 재사용(신규 파일 삭제).
      6) SpeakerWavUploadResponse 반환.

    보안 요건:
      - 업로드 경로는 MIME 판별이 아닌 확장자 + RIFF 헤더로만 판정.
      - Content-Type이 무엇이든 "audio/wav"로 고정 응답.
      - storage_dir는 FastAPI 앱 정적 마운트 대상에서 제외(기본 제외).
      - 인증은 V1 범위 밖(단일 사용자, loopback 전용) — 향후 CR.

    Raises:
        HTTPException(400): 유효성 실패.
        HTTPException(413): 크기 초과.
        HTTPException(404): id 미존재(조회/삭제).
    """
```

### 공통 상수

```python
MELOTTS_SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"KR"})
MELOTTS_SUPPORTED_SAMPLE_RATES: frozenset[int] = frozenset({16000, 22050, 24000, 44100, 48000})
MELOTTS_MIN_SPEED: float = 0.5
MELOTTS_MAX_SPEED: float = 2.0
XTTS_SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"ko"})
SUPPORTED_DEVICES: frozenset[str] = frozenset({"auto", "cpu", "cuda"})
MAX_TEXT_CHARS: int = 1000
MAX_SPEAKER_WAV_BYTES: int = 10 * 1024 * 1024
```

### 모듈 공개 심볼 (`src/tts/__init__.py`)

```python
from .errors import TTSInitError, TTSRuntimeError
from .melo_tts_engine import MeloTTSEngine
from .xtts_v2_engine import XttsV2Engine
from .builder import build_tts_engine, TtsEngine, resolve_melotts_dir, resolve_xtts_v2_dir
from .speaker_wav import validate_speaker_wav, SpeakerWavInfo, ALLOWED_SAMPLE_RATES
from .upload import create_speaker_upload_router, SpeakerWavUploadResponse, SpeakerWavListItem
```

---

## 설정 구조 (conf.yaml)

본 모듈은 **두 개의 설정 경로**를 읽는다.

1. **upstream 스키마** (`character_config.tts_config`) — upstream `init_tts`의 `init_tts` 가드를 통과시키기 위한 호환 필드. 본 모듈이 실제로 값을 읽지는 않음(읽어도 그대로 동작하도록 정합성만 유지).
2. **본 프로젝트 고유 스키마** (`app.tts`) — 실제 엔진 선택과 파라미터. 본 모듈이 읽는 유일한 진실 공급원.

### 본 프로젝트 `AppConfig.tts` 추가 필드

M_01 `src/app/config.py`에 아래 필드를 추가하는 **변경 사항**이 필요하다. 본 스펙이 M_01의 추가 변경을 요청한다(M_01 스펙 갱신 + builder 호출 경로 반영). 변경 범위는 `AppConfig`에 `tts: TtsConfig` 필드 1개 추가.

```python
# src/app/config.py 추가 스키마 (pydantic)
class TtsEngineKind(str, Enum):
    MELO = "melo"
    XTTS_V2 = "xtts_v2"

class MeloTtsSubConfig(BaseModel):
    speaker: str = Field(default="KR")
    language: str = Field(default="KR")
    speaker_id: int | None = Field(default=None)   # None이면 hps.data.spk2id["KR"] 자동
    sample_rate: int = Field(default=24000)
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    device: str = Field(default="auto")            # auto|cpu|cuda
    model_dir: str | None = Field(default=None)    # None이면 asset_root/melotts-ko

class XttsV2SubConfig(BaseModel):
    speaker_wav: str | None = Field(default=None)  # 절대 경로 또는 upload id 기반 경로
    language: str = Field(default="ko")
    device: str = Field(default="auto")
    model_dir: str | None = Field(default=None)    # None이면 asset_root/xtts_v2

class TtsConfig(BaseModel):
    engine: TtsEngineKind = Field(default=TtsEngineKind.MELO)
    cache_dir: str = Field(default="cache")
    speaker_refs_dir: str = Field(default="data/speaker_refs")
    melo: MeloTtsSubConfig = Field(default_factory=MeloTtsSubConfig)
    xtts: XttsV2SubConfig = Field(default_factory=XttsV2SubConfig)
```

### `conf.yaml` 예시

```yaml
# upstream 호환 (값은 본 모듈이 무시하지만 TTSConfig 스키마 검증을 통과해야 함)
character_config:
  tts_config:
    tts_model: "melo_tts"
    melo_tts:
      speaker: "KR"
      language: "KR"
      device: "auto"
      speed: 1.0

# 본 프로젝트 고유 - 실제 엔진 선택의 진실 공급원
app:
  tts:
    engine: "melo"                    # "melo" | "xtts_v2"
    cache_dir: "cache"
    speaker_refs_dir: "data/speaker_refs"
    melo:
      speaker: "KR"
      language: "KR"
      speaker_id: null                # null이면 hps.data.spk2id["KR"] 자동
      sample_rate: 24000
      speed: 1.0
      device: "auto"
      model_dir: null                 # null이면 assets/models/melotts-ko
    xtts:
      speaker_wav: null               # XTTS v2 사용 시 반드시 채움
      language: "ko"
      device: "auto"
      model_dir: null                 # null이면 assets/models/xtts_v2
```

### 필드별 검증 표

| 키 | 타입 | 기본 | 검증 |
|---|---|---|---|
| `app.tts.engine` | str | `"melo"` | `"melo"` / `"xtts_v2"` |
| `app.tts.cache_dir` | str | `"cache"` | 쓰기 가능 디렉토리. 없으면 `os.makedirs`로 생성 |
| `app.tts.speaker_refs_dir` | str | `"data/speaker_refs"` | 쓰기 가능 디렉토리. 업로드 라우터 기준 저장 루트 |
| `app.tts.melo.speaker` | str | `"KR"` | `{"KR"}` 중 하나 |
| `app.tts.melo.language` | str | `"KR"` | `{"KR"}` |
| `app.tts.melo.speaker_id` | int \| null | `null` | null이면 자동 해석. 명시 시 ≥ 0 |
| `app.tts.melo.sample_rate` | int | `24000` | `{16000,22050,24000,44100,48000}` |
| `app.tts.melo.speed` | float | `1.0` | `[0.5, 2.0]` |
| `app.tts.melo.device` | str | `"auto"` | `{"auto","cpu","cuda"}` |
| `app.tts.melo.model_dir` | str \| null | `null` | null이면 `assets/models/melotts-ko`. 지정 시 디렉토리 존재·필수 파일 포함 |
| `app.tts.xtts.speaker_wav` | str \| null | `null` | `engine="xtts_v2"`면 필수. 파일 존재 + `validate_speaker_wav` 통과 |
| `app.tts.xtts.language` | str | `"ko"` | `{"ko"}` |
| `app.tts.xtts.device` | str | `"auto"` | `{"auto","cpu","cuda"}` |
| `app.tts.xtts.model_dir` | str \| null | `null` | null이면 `assets/models/xtts_v2`. 지정 시 디렉토리 존재·필수 파일 포함 |

---

## 에러 처리 정책

| 상황 | 반응 | 예외 타입 | 로그 레벨 |
|---|---|---|---|
| `model_dir` 부재 | 즉시 실패 | `TTSInitError("model_dir not found: <p>")` | ERROR |
| `model_dir`은 존재하나 필수 파일 누락 (melo: `config.json`·`checkpoint.pth`·`tokenizer.json`; xtts: `config.json`·`model.pth`·`vocab.json`·`dvae.pth`·`mel_stats.pth`·`speakers_xtts.pth`) | 즉시 실패 | `TTSInitError("model weights missing: <files>")` | ERROR |
| MeloTTS `language != "KR"` | 즉시 실패 | `TTSInitError("unsupported language")` | ERROR |
| MeloTTS `speaker != "KR"` | 즉시 실패 | `TTSInitError("unsupported speaker")` | ERROR |
| MeloTTS `speed` 범위 밖 | 즉시 실패 | `TTSInitError("speed out of range")` | ERROR |
| MeloTTS `speaker_id`가 `hps.data.spk2id` 범위 밖 | 즉시 실패 | `TTSInitError("speaker_id out of range")` | ERROR |
| XTTS v2 `speaker_wav` 부재 | 즉시 실패 | `TTSInitError("speaker_wav required for xtts_v2")` | ERROR |
| XTTS v2 `validate_speaker_wav` 실패 | 즉시 실패 | `TTSInitError("invalid speaker wav: <reason>")`. `__cause__`에 `ValueError` | ERROR |
| `device="cuda"` but CUDA 미가용 | 즉시 실패(의도 존중) | `TTSInitError("cuda requested but not available")` | ERROR |
| `device="auto"` + CUDA 미가용 | `cpu`로 폴백 | (예외 없음) | INFO |
| 백엔드(`melo.api.TTS` / `TTS.api.TTS`) 생성자 예외 | 래핑 | `TTSInitError(str(e)) from e` | ERROR |
| Coqui EULA prompt 발생(`COQUI_TOS_AGREED` 미설정) | 환경변수 사전 설정으로 차단. 미설정 상태에서 잡히면 즉시 실패 | `TTSInitError("COQUI_TOS_AGREED=1 required")` | ERROR |
| `generate_audio(text="")` 또는 `text` None | 즉시 실패 | `TTSRuntimeError("empty text")` | ERROR |
| `text` > 1000자 | 1000자에서 절단하고 합성 계속 | (예외 없음) | WARNING (1회) |
| 합성 도중 백엔드 예외 | 래핑, 재시도 없음 | `TTSRuntimeError(str(e)) from e` | ERROR |
| 합성은 성공했는데 출력 파일 누락 | 즉시 실패 | `TTSRuntimeError("output file not written")` | ERROR |
| cache_dir 쓰기 실패(권한) | 즉시 실패 | `TTSRuntimeError("cache dir not writable: <p>")` | ERROR |
| 업로드 파일 크기 초과 | HTTP 413 | (예외 아닌 HTTPException) | WARNING |
| 업로드 WAV 유효성 실패 | HTTP 400 | HTTPException + 저장 파일 삭제 | WARNING |
| `asyncio.CancelledError` | 상위 전파(이미 기록된 부분 WAV는 호출자가 `remove_file`로 정리) | (예외 없음) | DEBUG |

### 원칙
- **초기화 실패는 앱 기동을 중단시키지 않는다**(ASR과 달리 TTS는 선택적 — 텍스트 채팅은 계속 가능). M_01 `AppServiceContext.load_app_services`는 `TTSInitError`를 캐치해 `self.tts_engine = None`으로 두고 사용자에게 UI 배지로 알린다. (ARCHITECTURE.md §6.1의 "XTTS 기본 OFF" 정책과 정합)
- **런타임 실패는 단일 발화 단위로 격리**. 상위 `TTSManager`가 `TTSRuntimeError`를 캐치해 해당 문장만 스킵(혹은 텍스트 자막만 전송).
- **네트워크 0건 보장**: 엔진 초기화 직전에 `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `COQUI_TOS_AGREED=1`, `NLTK_DATA=<local>`을 환경변수로 설정한다. 이미 설정되어 있으면 건드리지 않음(테스트 환경 재현성). 추가로 모델 디렉토리 사전 검증 + `model_dir`이 없으면 즉시 실패 → 백엔드가 HF로 풀링할 기회를 차단.

---

## 성능·메모리 요구사항

### 메모리 · 디스크 예산 (ARCHITECTURE.md §6.1 근거)

| 엔진 | 프로세스 RSS 증가 | 디스크 | 활성 조건 |
|---|---|---|---|
| MeloTTS(KR, ONNX or PyTorch float32) | ≈ 450 MB | ~300~500 MB | 기본 ON (`engine="melo"`) |
| XTTS v2 | ≈ 1.8 GB | ~1.9 GB | 사용자 옵트인 시만 (`engine="xtts_v2"`) |

**동시 적재 금지**: 두 엔진을 동시에 로드하지 않는다. `build_tts_engine`이 한 번에 하나만 생성한다. 엔진 전환은 재기동(V1) 또는 재초기화(V2 후보).

### 기동·로드 시간

| 엔진 | 환경 | 초기화 시간 (모델 로드 포함) |
|---|---|---|
| MeloTTSEngine | CPU (i7-12700, NVMe SSD) | ≤ 2.5 s |
| MeloTTSEngine | GPU (RTX 4070) | ≤ 1.5 s |
| XttsV2Engine | CPU | ≤ 6.0 s |
| XttsV2Engine | GPU | ≤ 3.0 s |

전체 앱 기동 예산 15초(REQUIREMENTS.md §9) 중, MIN 프로파일에서 MeloTTS 2.5초를 소비한다. XTTS v2 옵트인 시 6초까지 허용하되 UI에서 로딩 인디케이터 표출(M_01 책임).

### 합성 지연 (단문 기준)

입력: 한국어 30~50자 문장(`"안녕하세요. 오늘 일정을 안내해드릴게요."` 급).

| 엔진 | 환경 | 합성 시간 | ARCHITECTURE.md §6.2 예산 |
|---|---|---|---|
| MeloTTS | GPU | ≤ 0.4 s | 첫 청크 0.4 s |
| MeloTTS | CPU | ≤ 0.8 s | 첫 청크 0.8 s |
| XTTS v2 | GPU | ≤ 0.8 s | 기본 경로 아님 |
| XTTS v2 | CPU | ≤ 3.0 s | 기본 경로 아님 |

본 모듈 단독 SLA: **MeloTTS CPU 단문 0.8 s 이하**. 실측은 벤치마크 마일스톤에서 별도 스크립트로 기록(CI 테스트는 환경 의존이 커 엄격히 강제하지 않는다).

### 동시성

- `melo.api.TTS`와 `TTS.api.TTS` 모두 스레드-세이프하지 않다(내부 상태 공유).
- 본 모듈은 **인스턴스당 동시 1개 합성**으로 제한한다. `generate_audio` 내부에 `threading.Lock`을, `async_generate_audio` 경로에는 `asyncio.Lock`을 둔다(이중 안전).
- upstream `TTSManager`가 문장 단위로 순차 호출하는 것이 기본 전제.

### 품질 QA (R-05 연계)

M_04 DoD에 다음 **주관 평가 체크리스트**를 포함:

| 평가 항목 | 표본 | 기준 |
|---|---|---|
| 회사 고유명사 10종 | `["OO팀", "XX프로젝트", ...]` | 10건 중 ≥ 7건 원어 정확 발음 |
| 숫자·단위 5건 | `["3월 15일", "오후 2시 30분", "5,000원", "1.5배", "3개월"]` | 5건 중 ≥ 4건 자연스러움 |
| 한자 혼용 1문장 | `"회의실(會議室) 예약"` 등 3건 | 3건 중 ≥ 2건 한글만 읽음(한자 스킵) |
| 일반 한국어 5문장 | 일상 문장 | 5건 중 ≥ 4건 자연스러움(5점 척도 ≥ 3점) |

평균 점수 3점 미만이면 R-05의 CR 발행 절차(XTTS v2 기본 승격 또는 CosyVoice 2 재검토).

---

## 화자 참조 WAV 업로드 API

### 설계 원칙
- **로컬 loopback에서만 제공**. M_01 FastAPI 앱의 바인드 주소는 `127.0.0.1`(또는 설정된 사설 IP). 외부 노출 금지.
- **파일만 받고 모델 파인튜닝은 안 한다**. XTTS v2는 zero-shot이므로 3~6초 WAV 하나로 충분.
- **V1은 인증 없음**. 단일 사용자 전제(REQUIREMENTS.md §10).
- **중복 파일은 동일 id 재사용**(sha256 기반).

### 엔드포인트 상세

#### POST `/api/tts/speaker-refs`
- **Content-Type**: `multipart/form-data`
- **필드**: `file` (필수, `.wav` 확장자)
- **최대 크기**: 10 MB (Content-Length 선검사 + 스트림 누적 검사)
- **검증**: 확장자 `.wav` + RIFF/WAVE 헤더 + mono + 샘플레이트 `{16k,22k,24k,44.1k,48k}` + bit depth 16 + 길이 3~30초
- **저장 경로**: `{speaker_refs_dir}/{sha256[:16]}_{origname}.wav` (경로 조작 방지: 원본 파일명은 `pathlib.Path(...).name`만 유지)
- **응답 200**:
  ```json
  {
    "id": "a1b2c3d4e5f6789a",
    "path": "data/speaker_refs/a1b2c3d4e5f6789a_voice.wav",
    "duration_sec": 4.35,
    "sample_rate": 24000,
    "channels": 1
  }
  ```
- **에러**:
  - 400: 확장자·헤더·포맷 위반. 본문 `{"detail": "<reason>"}`
  - 413: 크기 초과
  - 422: `file` 필드 없음

#### GET `/api/tts/speaker-refs`
- **응답 200**: `list[SpeakerWavListItem]` — 저장된 파일 메타 목록(디렉토리 스캔, 수정 시각 내림차순)

#### GET `/api/tts/speaker-refs/{id}`
- **응답 200**: `SpeakerWavListItem`
- **에러 404**: id 미존재

#### DELETE `/api/tts/speaker-refs/{id}`
- **응답 204**
- **에러 404**: id 미존재
- **부작용**: 현재 활성 XTTS v2 엔진의 `speaker_wav`가 삭제 대상이면 **거부 409 + 본문 `{"detail": "speaker ref is currently active"}`**. 스펙상 현재 활성화 여부는 `AppServiceContext.tts_engine.speaker_wav`와 비교(M_01이 주입).

### M_01 통합

- M_01 `AppWebSocketServer.create_app`에서 `app.include_router(create_speaker_upload_router(storage_dir=app_config.tts.speaker_refs_dir))`를 호출한다.
- 활성 XTTS v2 엔진의 `speaker_wav` 참조 검사는 M_01 `AppServiceContext`가 라우터 생성 시 콜백으로 주입(`is_active_callback: Callable[[str], bool]`).

### 보안 메모
- 업로드된 파일은 **정적 마운트에서 제외**. 즉 `/api/tts/speaker-refs/<id>`는 메타만 반환하고, 실제 WAV 바이너리를 HTTP로 다시 내려주지 않는다(V1). 필요하면 V2 CR.
- 경로 조작 방지: 파일명에서 `..`, `/`, `\\` 제거.
- 디렉토리 존재하지 않으면 `os.makedirs(storage_dir, exist_ok=True, mode=0o700)`.

---

## 테스트 케이스

경로: `tests/tts/test_*.py`. pytest + `pytest-asyncio`. `melo.api.TTS`와 `TTS.api.TTS`는 모두 무겁기 때문에 **모든 테스트에서 MagicMock으로 대체**한다. 실제 모델 로드 테스트는 `@pytest.mark.slow`로 1건씩만 포함하고 CI에서는 `pytest -m "not slow"` 기본.

### 정상 케이스 (≥5)

**N-1. MeloTTSEngine 정상 초기화 (mock)**
- 입력: `model_dir=tmp_model_dir`(필수 파일 빈 stub 생성), `speaker="KR"`, `language="KR"`, `speed=1.0`, `sample_rate=24000`, `device="auto"`.
- mock: `melo.api.TTS` 생성자가 객체 반환, `.hps.data.spk2id = {"KR": 0}`.
- 검증: 인스턴스 생성 성공, `engine.speaker == "KR"`, `engine.speaker_id == 0`, `engine.resolved_device in {"cpu","cuda"}`.

**N-2. MeloTTSEngine `generate_audio` 정상 합성 (mock)**
- 입력: `text="안녕하세요 새싹이입니다"`, `file_name_no_ext="greet"`.
- mock: `tts_to_file`이 `cache/greet.wav`를 실제로 생성(테스트 헬퍼로 1KB zero 파일 write).
- 검증: 반환값이 `cache/greet.wav` 절대 경로. mock `.tts_to_file.call_args.kwargs["speed"] == 1.0`, 첫 인자가 입력 text.

**N-3. MeloTTSEngine async 경로**
- 입력: `await engine.async_generate_audio("반갑습니다")`.
- 검증: 부모 구현이 스레드로 동기 `generate_audio`를 호출. 결과 파일 경로 반환. `asyncio.CancelledError`가 `asyncio.wait_for(..., timeout=0)`에서 정상 전파됨을 확인.

**N-4. XttsV2Engine 정상 초기화 (mock)**
- 입력: `model_dir=tmp_xtts_dir`(필수 파일 stub), `speaker_wav=tmp_valid_wav(4.0s, 1ch, 24k, PCM16)`, `language="ko"`.
- mock: `TTS.api.TTS` 생성자가 객체 반환.
- 검증: 인스턴스 생성 성공, `engine.language == "ko"`, `engine.speaker_wav`가 절대 경로.

**N-5. `build_tts_engine` 선택 분기**
- 입력 A: `AppConfig(tts=TtsConfig(engine="melo"))` → MeloTTSEngine 반환.
- 입력 B: `AppConfig(tts=TtsConfig(engine="xtts_v2", xtts=XttsV2SubConfig(speaker_wav=<유효 WAV>)))` → XttsV2Engine 반환.
- 검증: 각 타입이 기대와 일치. Melo 경로에서 `xtts` 서브 필드가 무시됨. 반대도 동일.

**N-6. `validate_speaker_wav` 정상 통과**
- 입력: 4초 mono 24kHz PCM16 WAV 파일(`wave` 모듈로 생성).
- 검증: `SpeakerWavInfo(duration_sec≈4.0, sample_rate=24000, channels=1, bit_depth=16)` 반환.

**N-7. 업로드 엔드포인트 정상 경로**
- 클라이언트: TestClient가 4초 mono 24k PCM16 WAV를 `file` 필드로 POST.
- 검증: 200 응답, `id` 16자, 저장 파일 존재, 두 번째 동일 파일 업로드 시 동일 `id` 반환(중복 감지).

### 엣지 케이스 (≥5)

**E-1. MeloTTS 빈 문자열 입력**
- 입력: `engine.generate_audio("")`.
- 검증: `TTSRuntimeError("empty text")`. `tts_to_file` 호출되지 않음.

**E-2. MeloTTS `text` 1000자 초과 → 절단**
- 입력: `text="가"*1500`.
- 검증: mock에 전달된 text 길이가 1000. WARNING 로그 1회(`caplog`).

**E-3. MeloTTS `device="auto"` + CUDA 미가용**
- mock: `torch.cuda.is_available` → False(또는 `melo` 내부 체크를 mock).
- 검증: `engine.resolved_device == "cpu"`. 예외 없음.

**E-4. XttsV2Engine `speaker_wav`가 3.5초 경계값**
- 입력: 3.5초 WAV. `min_speaker_wav_sec=3.0`.
- 검증: `validate_speaker_wav`와 `XttsV2Engine` 모두 통과.

**E-5. 업로드 경계 샘플레이트**
- 입력: 22050 Hz WAV 3초.
- 검증: 200 응답. `sample_rate == 22050`.

**E-6. `file_name_no_ext`가 슬래시 포함 (MeloTTS)**
- 입력: `file_name_no_ext="subdir/name"`.
- 검증: 부모 `generate_cache_file_name` 동작에 따라 `cache/subdir/name.wav` 경로가 생성되는지 확인. 상위 디렉토리 생성이 실패하면 `TTSRuntimeError`.

**E-7. 중복 업로드 sha256 재사용**
- 입력: 동일 WAV 파일을 두 번 POST.
- 검증: 두 응답의 `id` 동일, 서버 디스크에 1개 파일만 존재(두 번째는 저장 스킵).

**E-8. `build_tts_engine`에서 `xtts` 엔진 선택 but `speaker_wav=None`**
- 검증: `TTSInitError("speaker_wav required for xtts_v2")`. 모델 로드 시도 없음.

### 적대적 케이스 (≥3)

**A-1. MeloTTS `model_dir` 부재**
- 입력: `model_dir="/no/such/dir"`.
- 검증: `TTSInitError("model_dir not found")`. `melo.api.TTS` 호출 없음.

**A-2. MeloTTS `device="cuda"` 강제 but 미가용**
- 입력: `device="cuda"`, CUDA 미가용 환경.
- 검증: `TTSInitError("cuda requested but not available")`. auto 폴백 없음.

**A-3. XTTS v2 `speaker_wav` 포맷 위반 (stereo)**
- 입력: 2채널 WAV.
- 검증: `TTSInitError` with `__cause__ is ValueError`, 메시지에 "channels" 포함. `TTS.api.TTS` 호출 없음.

**A-4. XTTS v2 `speaker_wav` 너무 짧음 (1.5초)**
- 입력: 1.5초 WAV.
- 검증: `TTSInitError` + "duration". 호출 없음.

**A-5. 업로드 크기 초과**
- 입력: 12 MB 더미 파일 POST.
- 검증: HTTP 413. 서버 디스크에 파일 없음(누적 검사가 중단 시 삭제).

**A-6. 업로드 확장자 위조 (`.mp3.wav`·헤더 불일치)**
- 입력: MP3 바이트에 `.wav` 확장자만 바꿔 POST.
- 검증: HTTP 400 "invalid RIFF header". 서버 디스크에 파일 없음.

**A-7. 업로드 경로 조작 시도 (`../../etc/passwd.wav`)**
- 입력: `filename="../../etc/passwd.wav"` 헤더로 WAV 바이트 POST.
- 검증: 저장 파일명에 `..`·슬래시 없음. `pathlib.Path.name`만 사용됨을 테스트에서 파일시스템 스캔으로 확인.

**A-8. 백엔드가 예외를 던짐 (MeloTTS)**
- mock: `tts_to_file`이 `RuntimeError("cuda OOM")` raise.
- 검증: `TTSRuntimeError("cuda OOM")`. `__cause__`가 원본 `RuntimeError`.

### Slow 마커 실제 로드 테스트 (CI 기본 skip)

**S-1. 실제 MeloTTS KR 모델 로드 + 단문 합성**
- 전제: `assets/models/melotts-ko/` 존재.
- 입력: `text="안녕하세요"`.
- 검증: 반환 파일이 WAV 헤더를 가지며 길이 ≥ 0.5초.

**S-2. 실제 XTTS v2 모델 로드 + 단문 합성**
- 전제: `assets/models/xtts_v2/` 존재, 샘플 WAV 4초.
- 입력: `text="반갑습니다"`.
- 검증: 반환 파일 헤더 유효, 길이 ≥ 0.5초.

---

## 오프라인 빌드 메모

### 모델 파일 배치

- **`assets/models/melotts-ko/`**
  - 필수 파일: `config.json`, `checkpoint.pth`, `tokenizer.json`, `bert/`(한국어 BERT 가중치 디렉토리 — melo 내부에서 language-specific prepro 시 요구) 또는 melo 버전에 따른 등가 파일.
  - 출처: `myshell-ai/MeloTTS` HuggingFace 저장소 중 한국어 산출물. MIT 라이선스.

- **`assets/models/xtts_v2/`**
  - 필수 파일: `config.json`, `model.pth`, `vocab.json`, `dvae.pth`, `mel_stats.pth`, `speakers_xtts.pth`.
  - 출처: `coqui/XTTS-v2` HuggingFace. **Coqui Public Model License (CPML)** — 비상업 무료. 사내 내부 사용은 법무 검토 후 번들에 포함(R-09 연계, `docs/LICENSES.md`에 명시).

- **`assets/nltk_data/`** (MeloTTS 의존)
  - MeloTTS가 영어 텍스트 처리에서 `averaged_perceptron_tagger` 등을 요구하더라도, 본 프로젝트는 한국어 전용이므로 실제로 호출되지 않아야 한다. 그럼에도 부작용 호출 방지를 위해 빈 stub 디렉토리 + `NLTK_DATA` 환경변수 지정.

### `.gitignore`
- `assets/models/` 전체 제외 유지(기존 규칙).
- `data/speaker_refs/` 제외 추가.
- `cache/` 제외 추가(이미 있으면 유지).

### `scripts/bundle_deps.sh` 추가 항목

1. Python 패키지
   - `melotts-korean==<최신 안정>` 또는 `melotts` 공식 wheel(빌드 머신에서 `pip download` 수집). 한국어 지원이 포함된 버전 핀.
   - `TTS>=0.22,<1` (Coqui). XTTS v2 지원 버전.
   - `torch>=2.1,<3` (CPU wheel + CUDA wheel 별도 — 프로파일에 따라 선택).
   - `soundfile>=0.12,<1` (WAV I/O 보조).
   - `pydub`은 **사용 금지** (ffmpeg 런타임 의존). 표준 `wave` 모듈만 사용.

2. 모델 아티팩트 다운로드 블록 (빌드 머신 전용):
   ```bash
   # MeloTTS 한국어
   huggingface-cli download myshell-ai/MeloTTS-Korean \
       --local-dir assets/models/melotts-ko --local-dir-use-symlinks False
   # XTTS v2
   huggingface-cli download coqui/XTTS-v2 \
       --local-dir assets/models/xtts_v2 --local-dir-use-symlinks False
   ```

3. 번들 포함 항목:
   - `assets/models/melotts-ko/` 전체
   - `assets/models/xtts_v2/` 전체 (CPML 동의 + 법무 승인 후)
   - 각 디렉토리에 `LICENSE.txt` 파일 동봉 (MIT / CPML)

### 환경변수 설정 (런타임 진입점에서)

`src/app/main.py`(M_01)가 TTS 모듈 import 전에 아래를 설정:

```
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1
COQUI_TOS_AGREED=1
NLTK_DATA=<project_root>/assets/nltk_data
```

본 모듈 `__init__.py`는 import 시 위 환경변수가 설정되어 있는지 확인하고, 누락이면 WARNING 로그(테스트에서는 fixture로 세팅).

### 네트워크 검증
- `scripts/verify_offline.ps1`가 TTS 초기화 직후에도 외부 DNS·HTTP 요청이 발생하지 않았음을 Windows 방화벽 로그로 확인. `download_root`/`model_dir` 사전 검증 + 환경변수 조합으로 백엔드의 원격 풀링은 원천 차단.

### pyproject.toml 변경 예
```toml
[project.dependencies]
melotts-korean = ">=0.1,<1"   # 또는 공식 패키지 이름/핀 확정 필요 (CHANGE: build 단계에서 확정)
TTS = ">=0.22,<1"             # Coqui
torch = ">=2.1,<3"
soundfile = ">=0.12,<1"
```

> melo 공식 PyPI 패키지 이름·버전 핀은 오프라인 번들 확정 시 M_04 구현자가 최종 결정해 PR 메시지에 근거 기록.

---

## Definition of Done

### 공통 (CLAUDE.md "산출물 체크리스트")
- [ ] `specs/M_04_TTSEngine_SPEC.md` (본 문서) 사용자 승인.
- [ ] `src/tts/` 전체 구현 (`melo_tts_engine.py`, `xtts_v2_engine.py`, `speaker_wav.py`, `upload.py`, `builder.py`, `errors.py`, `__init__.py`).
- [ ] `tests/tts/` 테스트: 정상 ≥5, 엣지 ≥5, 적대적 ≥3 (본 스펙의 N/E/A 케이스 전량).
- [ ] `ruff format .`, `ruff check .`, `mypy src/tts/`, `pytest tests/tts/ -v` 모두 통과.
- [ ] `reviews/M_04_TTSEngine_REVIEW.md` Critic PASS.
- [ ] `docs/MODULES.md`의 M_04 상태가 ✅ DONE으로 갱신.

### M_04 고유

- [ ] `MeloTTSEngine`와 `XttsV2Engine`이 upstream `TTSInterface`를 상속하고 `generate_audio`를 구현한다.
- [ ] 두 엔진 모두 초기화 시 `model_dir` 존재성과 필수 파일 목록 검증이 동작한다.
- [ ] `validate_speaker_wav`가 채널·샘플레이트·bit depth·길이·크기 5가지 항목을 모두 검사하며, 각 위반에 대해 서로 다른 에러 메시지를 반환한다.
- [ ] `build_tts_engine(app_config)`가 `engine` 키에 따라 올바른 클래스를 반환하고, xtts 경로에서 `speaker_wav=None`이면 `TTSInitError`로 거부한다.
- [ ] `create_speaker_upload_router`가 반환하는 `APIRouter`가 POST/GET/GET{id}/DELETE 4개 엔드포인트를 모두 노출하고, 413·400·404·409 응답을 모두 커버한다.
- [ ] 업로드 저장 파일명에서 `..`, `/`, `\\`가 제거됨을 테스트로 확인한다.
- [ ] 동일 sha256 파일 중복 업로드 시 동일 `id`가 반환되고 디스크에 1개 파일만 존재한다.
- [ ] `device="cuda"` 요청 + CUDA 미가용 시 `TTSInitError`로 실패하며 auto 폴백하지 않는다.
- [ ] `device="auto"` + CUDA 미가용 시 `cpu`로 폴백하며 예외 없이 동작한다.
- [ ] 두 엔진 모두 `text=""` 또는 `None`에 대해 `TTSRuntimeError("empty text")`를 발생시키며 백엔드 호출 없음.
- [ ] `text` 1000자 초과는 절단 + WARNING 로그 1회.
- [ ] `asyncio.CancelledError`가 `async_generate_audio`에서 상위로 전파된다(테스트로 확인).
- [ ] `upstream/Open-LLM-VTuber/src/open_llm_vtuber/tts/*` 파일이 수정되지 않았음을 git diff로 확인.
- [ ] `melotts-korean`, `TTS`, `torch`, `soundfile`이 `pyproject.toml`과 `scripts/bundle_deps.sh` 양쪽에 반영됨.
- [ ] `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `COQUI_TOS_AGREED=1`, `NLTK_DATA` 4개 환경변수가 M_01 `main.py`의 import 전 단계에 설정됨(M_01 스펙 연동 변경 요청 포함).
- [ ] R-05 품질 QA 체크리스트 결과(≥ 4/5점 평균)가 `docs/research/melotts_korean_qa.md`에 기록됨. 3점 미만이면 CHANGE_REQUEST 발행 조건 명시.

---

## 의존성

### Python 패키지 (pyproject.toml 추가)

| 패키지 | 버전 핀 | 용도 | 사유 |
|---|---|---|---|
| `melotts-korean` (또는 확정된 melo 패키지명) | `>=0.1,<1` | MeloTTS 한국어 합성 | D-03. MIT 라이선스 |
| `TTS` (Coqui) | `>=0.22,<1` | XTTS v2 엔진 | D-03. CPML |
| `torch` | `>=2.1,<3` | 두 엔진의 딥러닝 런타임 | CPU wheel만 번들, GPU는 별도 설치 옵션 |
| `soundfile` | `>=0.12,<1` | WAV I/O 보조(libsndfile 기반) | 표준 `wave`와 조합 사용 |

`numpy`, `fastapi`, `pydantic`은 이미 upstream에서 추가됨. `onnxruntime`은 M_03 VAD에서 추가됨.

### 런타임 전제

- Python 3.12 이상.
- upstream 소스 트리가 `upstream/Open-LLM-VTuber/src`에 존재하고 `sys.path`에 포함(M_01 설정과 동일).
- `assets/models/melotts-ko/` 디렉토리 사전 배치. XTTS v2 옵트인 시 `assets/models/xtts_v2/` 추가.
- `data/speaker_refs/` 디렉토리 쓰기 권한(최초 업로드 시 자동 생성, 권한 0o700).
- `cache/` 디렉토리 쓰기 권한(부모 `generate_cache_file_name`이 자동 생성).
- 환경변수 4종(§오프라인 빌드 메모) 설정 필수.

### 모듈 의존

| 대상 | 관계 |
|---|---|
| M_01 AppCore | `AppConfig.tts` 구조 추가 요청. `AppServiceContext.load_from_config`에서 `build_tts_engine()` 호출 및 `init_tts` 가드 선세팅. `create_speaker_upload_router()`를 FastAPI 앱에 포함 |
| upstream `TTSInterface` | 상속 |
| upstream `TTSConfig` / `MeloTTSConfig` | `tts_model="melo_tts"` 호환 검증 통과용(내용은 본 모듈이 무시) |

**M_04는 M_02(ASR)·M_03(VAD)·M_05(LLM)에 의존하지 않는다.** 상위 `TTSManager`가 문장 단위로 본 모듈의 `async_generate_audio`를 호출한다.

---

## 디렉토리 구조

```
src/tts/
├── __init__.py              # 공개 심볼
├── errors.py                # TTSInitError, TTSRuntimeError
├── melo_tts_engine.py       # MeloTTSEngine
├── xtts_v2_engine.py        # XttsV2Engine
├── speaker_wav.py           # validate_speaker_wav, SpeakerWavInfo
├── upload.py                # create_speaker_upload_router
└── builder.py               # build_tts_engine, resolve_*_dir

tests/tts/
├── __init__.py
├── conftest.py              # mock MeloTTS/TTS fixtures, tmp_model_dir, tmp_valid_wav, FastAPI TestClient
├── test_melo_engine.py      # N-1~N-3, E-1~E-3, E-6, A-1, A-2, A-8
├── test_xtts_engine.py      # N-4, E-4, A-3, A-4
├── test_builder.py          # N-5, E-8
├── test_speaker_wav.py      # N-6, 검증 실패 세부
├── test_upload_router.py    # N-7, E-5, E-7, A-5, A-6, A-7
└── fixtures/
    ├── speaker_3s.wav       # slow 마커용(선택)
    └── speaker_invalid_stereo.wav
```

---

## 스펙 외 사항 (명시적 제외)

본 모듈의 책임이 **아닌** 항목:

1. **스트리밍 TTS**: 청크 단위 WAV 방출은 V2. 본 모듈은 완성된 WAV 파일 경로만 반환.
2. **문장 분할(sentence splitting)**: upstream `TTSManager` 책임. 본 모듈은 받은 `text`를 그대로 합성.
3. **텍스트 전처리**: 한자→한글, 숫자 읽기, 기호 제거 등. upstream `tts_preprocessor_config` 책임.
4. **오디오 재생·WebSocket 송신**: upstream `WebSocketHandler`·프론트엔드 책임.
5. **립싱크 viseme 생성**: M_08 AvatarState의 opacity 펄스로 대체(V1).
6. **TTS 번역(입력 언어와 다른 언어로 발화)**: `translate_audio=false` 전제.
7. **다른 TTS 백엔드 지원(Piper, Edge, Azure, GPT-SoVITS 등)**: upstream `TTSFactory`에 있으나 본 프로젝트는 사용 안 함. 추가 필요 시 `CHANGE_REQUESTS.md` 경유.
8. **MeloTTS 다른 언어(EN/ZH/JP/FR/ES)**: V1은 `KR` 단독.
9. **XTTS v2 파인튜닝·학습**: zero-shot 화자 클로닝만.
10. **화자 WAV 동적 교체(재기동 없이 speaker_wav 스왑)**: V1은 기동 시 고정. V2 후보.
11. **업로드 인증·인가·권한 관리**: 단일 사용자 + loopback 전제. V2 CR.
12. **GPU 메모리 공유·모델 오프로드**: 단일 인스턴스 상주. Ollama `keep_alive`와 같은 언로드 스케줄링은 V2 후보.
13. **upstream `TTSFactory` 확장**: 팩토리 수정 금지. 본 프로젝트는 M_01 `load_from_config`에서 직접 주입.

---

## 부록: upstream 경로·심볼 인덱스 (실재 확인)

본 스펙 작성 중 `/mnt/c/projects/ai-assistant/upstream/Open-LLM-VTuber/src/open_llm_vtuber/` 하의 실제 파일을 읽어 시그니처를 확정했다:

- `tts/tts_interface.py` L1~L82: `TTSInterface` abstract. `async_generate_audio` 기본 구현은 `asyncio.to_thread(self.generate_audio, text, file_name_no_ext)`. `generate_audio` abstract. `remove_file`, `generate_cache_file_name`은 구현 제공(캐시 루트 `"cache"` 하드코드).
- `tts/melo_tts.py` L1~L74: 참고용. `from melo.api import TTS`, `TTS(language=language, device=device)`, `self.model.hps.data.spk2id[speaker]`로 speaker_id 해석, `tts_to_file(text, speaker_id, output_path, speed=speed)` 호출. `nltk` 런타임 다운로드 fallback 존재(본 프로젝트에서는 차단).
- `tts/coqui_tts.py` L1~L129: 참고용. `from TTS.api import TTS`, `TTS(model_name=...).to(device)`, `tts_to_file(text, speaker_wav, language, file_path)` 호출.
- `tts/x_tts.py` L1~L44: HTTP 클라이언트 — 본 프로젝트와 무관.
- `tts/piper_tts.py` L1~L117: 참고용 (D-03으로 DROP).
- `tts/tts_factory.py` L1~L227: `TTSFactory.get_tts_engine(engine_type, **kwargs)` 분기. 수정 금지.
- `config_manager/tts.py` L235~L256: `MeloTTSConfig` — `speaker`, `language`, `device`(default "auto"), `speed`(default 1.0). upstream `tts_model="melo_tts"` 선택 시 이 스키마가 유효성 검증됨.
- `config_manager/tts.py` L683~L816: `TTSConfig` — `tts_model` Literal 후보에 `melo_tts` 포함. 본 프로젝트는 이 값으로 고정.
- `service_context.py` L335~L343: `init_tts(tts_config)` 동작 — 조건부 재초기화. 본 프로젝트는 M_01 `AppServiceContext.load_from_config`에서 `self.tts_engine` 선세팅 + `self.character_config.tts_config = tts_config`로 재초기화를 스킵한다.
