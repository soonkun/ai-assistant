# src/tts/__init__.py
"""TTS 모듈 공개 심볼."""

import logging
import os

from .builder import TtsEngine, build_tts_engine, resolve_melotts_dir, resolve_xtts_v2_dir
from .errors import TTSInitError, TTSRuntimeError
from .melo_tts_engine import MeloTTSEngine
from .speaker_wav import ALLOWED_SAMPLE_RATES, SpeakerWavInfo, validate_speaker_wav
from .upload import SpeakerWavListItem, SpeakerWavUploadResponse, create_speaker_upload_router

try:
    from .xtts_v2_engine import XttsV2Engine
except Exception:  # TTS 패키지 미설치(macOS/Python 3.12) 시 skip
    XttsV2Engine = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

# 환경변수 누락 시 WARNING (오프라인 강제 정책)
_REQUIRED_ENV_VARS = [
    "HF_HUB_OFFLINE",
    "TRANSFORMERS_OFFLINE",
    "COQUI_TOS_AGREED",
    "NLTK_DATA",
]


def _warn_missing_env_vars() -> None:
    for _env_var in _REQUIRED_ENV_VARS:
        if not os.environ.get(_env_var):
            logger.warning(
                "TTS module: environment variable %s is not set. "
                "This is required for offline operation. "
                "Set it before importing TTS engines.",
                _env_var,
            )


__all__ = [
    "TTSInitError",
    "TTSRuntimeError",
    "MeloTTSEngine",
    "XttsV2Engine",
    "build_tts_engine",
    "TtsEngine",
    "resolve_melotts_dir",
    "resolve_xtts_v2_dir",
    "validate_speaker_wav",
    "SpeakerWavInfo",
    "ALLOWED_SAMPLE_RATES",
    "create_speaker_upload_router",
    "SpeakerWavUploadResponse",
    "SpeakerWavListItem",
]
