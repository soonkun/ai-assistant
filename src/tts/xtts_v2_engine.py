# src/tts/xtts_v2_engine.py
"""XTTS v2 화자 클로닝 TTS 엔진."""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from open_llm_vtuber.tts.tts_interface import TTSInterface  # upstream

from ._device import resolve_device
from .errors import TTSInitError, TTSRuntimeError
from .speaker_wav import validate_speaker_wav

MAX_TEXT_CHARS: int = 1000

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

XTTS_SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"ko"})
SUPPORTED_DEVICES: frozenset[str] = frozenset({"auto", "cpu", "cuda"})

# XTTS v2 필수 파일 목록
XTTS_REQUIRED_FILES: list[str] = [
    "config.json",
    "model.pth",
    "vocab.json",
    "dvae.pth",
    "mel_stats.pth",
    "speakers_xtts.pth",
]


class XttsV2Engine(TTSInterface):  # type: ignore[misc]
    """Coqui XTTS v2 화자 클로닝 엔진. 사용자 옵트인 시에만 활성.

    upstream TTSInterface를 상속. async_generate_audio는 asyncio.Lock + to_thread를 사용.
    """

    model_dir: str
    speaker_wav: str  # 절대 경로
    language: str  # 항상 "ko"
    device: str
    resolved_device: str
    cache_dir: str
    min_speaker_wav_sec: float
    max_speaker_wav_sec: float

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
        """즉시 로드. 모든 유효성 검증은 import 전에 수행.

        Raises:
            TTSInitError: 설정 오류 또는 모델 로드 실패.
        """
        # 1. model_dir 존재 검증
        model_path = Path(model_dir)
        if not model_path.exists() or not model_path.is_dir():
            logger.error("model_dir not found: %s", model_dir)
            raise TTSInitError(f"model_dir not found: {model_dir}")

        # 필수 파일 검증
        missing_files = [f for f in XTTS_REQUIRED_FILES if not (model_path / f).exists()]
        if missing_files:
            logger.error("model weights missing: %s", missing_files)
            raise TTSInitError(f"model weights missing: {missing_files}")

        # 2. speaker_wav 존재 검증
        if not os.path.exists(speaker_wav):
            logger.error("speaker_wav not found: %s", speaker_wav)
            raise TTSInitError(f"speaker_wav not found: {speaker_wav}")

        # 3. speaker_wav 유효성 검증
        try:
            wav_info = validate_speaker_wav(
                speaker_wav,
                min_sec=min_speaker_wav_sec,
                max_sec=max_speaker_wav_sec,
            )
        except (ValueError, FileNotFoundError) as exc:
            logger.error("invalid speaker wav: %s", exc)
            raise TTSInitError(f"invalid speaker wav: {exc}") from exc

        # 4. language 검증
        if language not in XTTS_SUPPORTED_LANGUAGES:
            logger.error("unsupported language: %s", language)
            raise TTSInitError(f"unsupported language: {language!r} (must be 'ko')")

        # 5. device 검증 및 CUDA 체크
        if device not in SUPPORTED_DEVICES:
            logger.error("unsupported device: %s", device)
            raise TTSInitError(
                f"unsupported device: {device!r} (must be one of {SUPPORTED_DEVICES})"
            )

        resolved_device = resolve_device(device)

        # 6. 환경변수 설정 (오프라인 강제 + EULA 동의)
        nltk_data_dir = (
            Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            / "assets"
            / "nltk_data"
        )
        _set_xtts_env_vars(nltk_data_dir=str(nltk_data_dir))

        # 7. Coqui TTS 지연 import + 모델 로드
        try:
            from TTS.api import TTS as CoquiTTS
        except ImportError as exc:
            logger.error("Failed to import TTS: %s", exc)
            raise TTSInitError(f"Failed to import TTS.api.TTS: {exc}") from exc

        try:
            tts = CoquiTTS(
                model_path=str(model_path.resolve()),
                config_path=str(model_path / "config.json"),
                progress_bar=False,
            )
            tts = tts.to(resolved_device)
        except Exception as exc:
            logger.error("CoquiTTS init failed: %s", exc)
            raise TTSInitError(str(exc)) from exc

        # 캐시 디렉토리 생성
        try:
            os.makedirs(cache_dir, exist_ok=True)
        except OSError as exc:
            logger.error("Failed to create cache_dir %s: %s", cache_dir, exc)
            raise TTSInitError(f"cache dir not writable: {cache_dir}") from exc

        # 인스턴스 속성 저장
        self._nltk_data_dir = str(nltk_data_dir)  # = <project_root>/assets/nltk_data
        self.model_dir = str(model_path.resolve())
        self.speaker_wav = wav_info.path  # resolved absolute path
        self.language = language
        self.device = device
        self.resolved_device = resolved_device
        self.cache_dir = cache_dir
        self.min_speaker_wav_sec = min_speaker_wav_sec
        self.max_speaker_wav_sec = max_speaker_wav_sec
        self._tts = tts
        self._lock = asyncio.Lock()
        self._thread_lock = threading.Lock()

        logger.info(
            "XttsV2Engine initialized: language=%s device=%s resolved=%s speaker_wav=%s",
            language,
            device,
            resolved_device,
            self.speaker_wav,
        )

    def generate_audio(
        self,
        text: str,
        file_name_no_ext: str | None = None,
    ) -> str:
        """동기 TTS 합성.

        Args:
            text: 합성할 텍스트.
            file_name_no_ext: 출력 파일명(확장자 제외). None이면 "temp".

        Returns:
            str: 생성된 WAV 파일의 절대 경로.

        Raises:
            TTSRuntimeError: 백엔드 예외 또는 출력 파일 누락.
        """
        # 1. 빈 텍스트 검증
        if not text or not text.strip():
            logger.error("empty text passed to generate_audio")
            raise TTSRuntimeError("empty text")

        # 2. 1000자 초과 절단
        if len(text) > MAX_TEXT_CHARS:
            logger.warning(
                "text length %d exceeds max %d chars; truncating",
                len(text),
                MAX_TEXT_CHARS,
            )
            text = text[:MAX_TEXT_CHARS]

        # 3. 출력 경로 생성 — cache_dir 사용, basename 강제로 path traversal 방지
        _stem = Path(file_name_no_ext).name if file_name_no_ext is not None else "temp"
        if not _stem:
            _stem = "temp"
        output_path: str = str(os.path.abspath(os.path.join(self.cache_dir, f"{_stem}.wav")))

        # 4. 캐시 디렉토리 존재 확인
        output_dir = os.path.dirname(output_path)
        try:
            os.makedirs(output_dir, exist_ok=True)
        except OSError as exc:
            logger.error("cache dir not writable: %s", output_dir)
            raise TTSRuntimeError(f"cache dir not writable: {output_dir}") from exc

        # 5. 합성 실행
        with self._thread_lock:
            try:
                self._tts.tts_to_file(
                    text=text,
                    speaker_wav=self.speaker_wav,
                    language=self.language,
                    file_path=output_path,
                )
            except Exception as exc:
                logger.error("XTTS synthesis failed: %s", exc)
                raise TTSRuntimeError(str(exc)) from exc

        # 6. 출력 파일 존재 확인
        if not os.path.exists(output_path):
            logger.error("output file not written: %s", output_path)
            raise TTSRuntimeError(f"output file not written: {output_path}")

        logger.debug("generate_audio OK: path=%s", output_path)
        return output_path

    async def async_generate_audio(
        self,
        text: str,
        file_name_no_ext: str | None = None,
    ) -> str:
        """비동기 TTS 합성 — asyncio.Lock으로 동시 호출 직렬화."""
        async with self._lock:
            result: str = await asyncio.to_thread(self.generate_audio, text, file_name_no_ext)
            return result


def _set_xtts_env_vars(nltk_data_dir: str = "") -> None:
    """XTTS v2 오프라인 강제 + EULA 동의 환경변수를 설정한다.

    이미 설정된 값은 건드리지 않는다(테스트 환경 재현성 보장).
    """
    if not os.environ.get("COQUI_TOS_AGREED"):
        os.environ["COQUI_TOS_AGREED"] = "1"
    if not os.environ.get("HF_HUB_OFFLINE"):
        os.environ["HF_HUB_OFFLINE"] = "1"
    if not os.environ.get("TRANSFORMERS_OFFLINE"):
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
    if not os.environ.get("NLTK_DATA") and nltk_data_dir:
        os.environ["NLTK_DATA"] = nltk_data_dir
    logger.debug(
        "XTTS env: COQUI_TOS_AGREED=%s HF_HUB_OFFLINE=%s TRANSFORMERS_OFFLINE=%s NLTK_DATA=%s",
        os.environ.get("COQUI_TOS_AGREED"),
        os.environ.get("HF_HUB_OFFLINE"),
        os.environ.get("TRANSFORMERS_OFFLINE"),
        os.environ.get("NLTK_DATA"),
    )
