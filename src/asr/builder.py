# src/asr/builder.py
"""ASR 엔진 빌더 — AppConfig에서 KoreanWhisperASR 인스턴스를 구성한다."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .korean_whisper_asr import KoreanWhisperASR

if TYPE_CHECKING:
    from app.config import AppConfig

logger = logging.getLogger(__name__)


def resolve_model_path(profile: str, asset_root: str = "assets/models") -> str:
    """profile에 따른 whisper 모델 디렉토리 경로를 반환한다.

    Args:
        profile: "min" 또는 "recommended".
        asset_root: 모델이 위치한 루트 디렉토리.

    Returns:
        str: 모델 디렉토리 경로.

    Raises:
        ValueError: 알 수 없는 profile 값.
    """
    if profile == "min":
        return f"{asset_root}/whisper-medium-int8"
    elif profile == "recommended":
        return f"{asset_root}/whisper-large-v3-int8"
    else:
        raise ValueError(f"unknown profile: {profile}")


def build_asr_engine(
    app_config: "AppConfig",
    asset_root: str = "assets/models",
    initial_prompt: str | None = None,
) -> KoreanWhisperASR:
    """AppConfig.profile + AppConfig.paths에서 경로를 유도해 KoreanWhisperASR를 만든다.

    language='ko' 고정, compute_type='int8', device='auto'.

    경로 우선순위: app_config.paths.asr_model_path > profile 기반 경로.
    initial_prompt 우선순위: 인자로 전달된 값 (호출자가 upstream FasterWhisperConfig.prompt
    등에서 읽어서 전달).

    Args:
        app_config: 본 프로젝트 AppConfig 인스턴스.
        asset_root: 모델이 위치한 루트 디렉토리. asr_model_path가 설정된 경우 무시.
        initial_prompt: WhisperModel.transcribe에 전달할 초기 프롬프트. None이면 미전달.
            호출자가 upstream FasterWhisperConfig.prompt 값을 여기에 넘긴다.

    Returns:
        KoreanWhisperASR: 초기화된 ASR 엔진 인스턴스.

    Raises:
        ASRInitError: 모델 경로가 없거나 초기화에 실패한 경우.
    """
    # AppConfig.paths.asr_model_path가 명시적으로 설정된 경우 최우선 사용
    # PathsConfig에 asr_model_path 필드가 있으므로 getattr 대신 직접 접근
    paths_model_path: str | None = app_config.paths.asr_model_path

    if paths_model_path:
        model_path: str = paths_model_path
        logger.info(f"ASR 모델 경로: paths.asr_model_path 오버라이드 사용 → {model_path}")
    else:
        # 프로파일 기반 기본 경로
        profile_value: str = (
            app_config.profile.value
            if hasattr(app_config.profile, "value")
            else str(app_config.profile)
        )
        model_path = resolve_model_path(profile_value, asset_root)
        logger.info(f"ASR 엔진 빌드: profile={app_config.profile}, model_path={model_path}")

    return KoreanWhisperASR(
        model_path=model_path,
        language="ko",
        compute_type="int8",
        device="auto",
        initial_prompt=initial_prompt,
    )
