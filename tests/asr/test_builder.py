# tests/asr/test_builder.py
"""빌더 테스트 — N-6, profile 분기, resolve_model_path."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from asr.builder import build_asr_engine, resolve_model_path
from asr.errors import ASRInitError
from asr.korean_whisper_asr import KoreanWhisperASR
from app.config import AppConfig, HardwareProfile


class MockInfo:
    def __init__(self, language: str = "ko") -> None:
        self.language = language


# ──────────────────────────────────────────────
# resolve_model_path 테스트
# ──────────────────────────────────────────────


def test_resolve_model_path_min() -> None:
    """profile=min → whisper-medium-int8 경로."""
    result = resolve_model_path("min", "assets/models")
    assert result == "assets/models/whisper-medium-int8"


def test_resolve_model_path_recommended() -> None:
    """profile=recommended → whisper-large-v3-int8 경로."""
    result = resolve_model_path("recommended", "assets/models")
    assert result == "assets/models/whisper-large-v3-int8"


def test_resolve_model_path_unknown_raises() -> None:
    """알 수 없는 profile → ValueError."""
    with pytest.raises(ValueError, match="unknown profile: ultra"):
        resolve_model_path("ultra")


def test_resolve_model_path_custom_asset_root() -> None:
    """사용자 지정 asset_root가 반영된다."""
    result = resolve_model_path("min", "/custom/models")
    assert result == "/custom/models/whisper-medium-int8"


# ──────────────────────────────────────────────
# N-6. build_asr_engine 프로파일 경로 해석
# ──────────────────────────────────────────────


def test_n6_build_asr_engine_min_profile(tmp_path: Path) -> None:
    """N-6: AppConfig(profile=min) → whisper-medium-int8 경로로 인스턴스 생성."""
    # tmp_asset_root/whisper-medium-int8/ 디렉토리와 필수 파일 생성
    model_dir = tmp_path / "whisper-medium-int8"
    model_dir.mkdir(parents=True)
    (model_dir / "model.bin").touch()
    (model_dir / "config.json").touch()

    app_config = AppConfig(profile=HardwareProfile.MIN)

    mock_cls = MagicMock()
    mock_instance = MagicMock()
    mock_instance.transcribe.return_value = ([], MockInfo("ko"))
    mock_cls.return_value = mock_instance

    with patch("faster_whisper.WhisperModel", mock_cls):
        asr = build_asr_engine(app_config, asset_root=str(tmp_path))

    assert isinstance(asr, KoreanWhisperASR)
    assert asr.model_path.endswith("whisper-medium-int8")


def test_n6_build_asr_engine_recommended_profile(tmp_path: Path) -> None:
    """N-6 변형: AppConfig(profile=recommended) → whisper-large-v3-int8 경로."""
    model_dir = tmp_path / "whisper-large-v3-int8"
    model_dir.mkdir(parents=True)
    (model_dir / "model.bin").touch()
    (model_dir / "config.json").touch()

    app_config = AppConfig(profile=HardwareProfile.RECOMMENDED)

    mock_cls = MagicMock()
    mock_instance = MagicMock()
    mock_instance.transcribe.return_value = ([], MockInfo("ko"))
    mock_cls.return_value = mock_instance

    with patch("faster_whisper.WhisperModel", mock_cls):
        asr = build_asr_engine(app_config, asset_root=str(tmp_path))

    assert isinstance(asr, KoreanWhisperASR)
    assert asr.model_path.endswith("whisper-large-v3-int8")


def test_build_asr_engine_missing_model_raises(tmp_path: Path) -> None:
    """모델 경로가 없으면 ASRInitError 전파."""
    app_config = AppConfig(profile=HardwareProfile.MIN)

    # 디렉토리를 생성하지 않음
    mock_cls = MagicMock()

    with patch("faster_whisper.WhisperModel", mock_cls):
        with pytest.raises(ASRInitError, match="model_path not found"):
            build_asr_engine(app_config, asset_root=str(tmp_path))


def test_build_asr_engine_fixed_language_ko(tmp_path: Path) -> None:
    """build_asr_engine은 항상 language='ko'로 설정한다."""
    model_dir = tmp_path / "whisper-medium-int8"
    model_dir.mkdir(parents=True)
    (model_dir / "model.bin").touch()
    (model_dir / "config.json").touch()

    app_config = AppConfig(profile=HardwareProfile.MIN)

    mock_cls = MagicMock()
    mock_cls.return_value = MagicMock()

    with patch("faster_whisper.WhisperModel", mock_cls):
        asr = build_asr_engine(app_config, asset_root=str(tmp_path))

    assert asr.language == "ko"
    assert asr.compute_type == "int8"
    assert asr.device == "auto"


# ──────────────────────────────────────────────
# PathsConfig.asr_model_path 오버라이드 테스트 (Fix C-11)
# ──────────────────────────────────────────────


def test_asr_model_path_takes_precedence_over_profile(tmp_path: Path) -> None:
    """PathsConfig.asr_model_path가 설정되면 profile 기반 경로보다 우선한다.

    profile=recommended이면 기본적으로 whisper-large-v3-int8을 사용해야 하지만,
    paths.asr_model_path에 custom-model 경로가 설정되면 그 경로가 사용되어야 한다.
    """
    # 커스텀 모델 디렉토리 생성 (profile 기본 경로와 다른 이름)
    custom_model_dir = tmp_path / "custom-model"
    custom_model_dir.mkdir(parents=True)
    (custom_model_dir / "model.bin").touch()
    (custom_model_dir / "config.json").touch()

    # profile=RECOMMENDED이지만 asr_model_path를 명시적으로 설정
    from app.config import PathsConfig

    app_config = AppConfig(
        profile=HardwareProfile.RECOMMENDED,
        paths=PathsConfig(asr_model_path=str(custom_model_dir)),
    )

    mock_cls = MagicMock()
    mock_cls.return_value = MagicMock()

    with patch("faster_whisper.WhisperModel", mock_cls):
        # asset_root는 profile 기본 경로를 생성할 때 사용되지만,
        # asr_model_path가 우선하므로 실제로는 사용되지 않는다
        asr = build_asr_engine(app_config, asset_root=str(tmp_path))

    # profile=RECOMMENDED의 기본 경로(whisper-large-v3-int8)가 아닌
    # 명시적으로 설정한 custom-model 경로가 사용되어야 한다
    assert asr.model_path == str(custom_model_dir), (
        f"asr_model_path 오버라이드가 우선해야 한다. "
        f"기대: {custom_model_dir}, 실제: {asr.model_path}"
    )


def test_asr_model_path_none_falls_back_to_profile(tmp_path: Path) -> None:
    """PathsConfig.asr_model_path가 None이면 profile 기반 경로를 사용한다."""
    from app.config import PathsConfig

    model_dir = tmp_path / "whisper-medium-int8"
    model_dir.mkdir(parents=True)
    (model_dir / "model.bin").touch()
    (model_dir / "config.json").touch()

    # asr_model_path=None (기본값)
    app_config = AppConfig(
        profile=HardwareProfile.MIN,
        paths=PathsConfig(asr_model_path=None),
    )

    mock_cls = MagicMock()
    mock_cls.return_value = MagicMock()

    with patch("faster_whisper.WhisperModel", mock_cls):
        asr = build_asr_engine(app_config, asset_root=str(tmp_path))

    assert asr.model_path.endswith("whisper-medium-int8")


def test_build_asr_engine_passes_initial_prompt(tmp_path: Path) -> None:
    """build_asr_engine에 initial_prompt를 전달하면 KoreanWhisperASR에 반영된다."""
    model_dir = tmp_path / "whisper-medium-int8"
    model_dir.mkdir(parents=True)
    (model_dir / "model.bin").touch()
    (model_dir / "config.json").touch()

    app_config = AppConfig(profile=HardwareProfile.MIN)

    mock_cls = MagicMock()
    mock_instance = MagicMock()
    mock_instance.transcribe.return_value = ([], MockInfo("ko"))
    mock_cls.return_value = mock_instance

    prompt = "사내 회의 기술 용어"

    with patch("faster_whisper.WhisperModel", mock_cls):
        asr = build_asr_engine(
            app_config,
            asset_root=str(tmp_path),
            initial_prompt=prompt,
        )

    assert asr.initial_prompt == prompt
