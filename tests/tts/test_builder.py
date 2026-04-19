# tests/tts/test_builder.py
"""build_tts_engine 단위 테스트."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.config import AppConfig, MeloTtsSubConfig, TtsConfig, TtsEngineKind, XttsV2SubConfig
from tts.builder import build_tts_engine
from tts.errors import TTSInitError
from tts.melo_tts_engine import MeloTTSEngine
from tts.xtts_v2_engine import XttsV2Engine


def _make_melo_mock() -> MagicMock:
    m = MagicMock()
    m.hps.data.spk2id = {"KR": 0}
    return m


def _make_coqui_mock() -> MagicMock:
    m = MagicMock()
    m.to.return_value = m
    return m


# ---------------------------------------------------------------------------
# 정상 케이스 N-5
# ---------------------------------------------------------------------------


class TestBuildTtsEngine:
    def test_build_melo_engine(self, tmp_model_dir: Path, tmp_path: Path) -> None:
        """N-5A: engine="melo" → MeloTTSEngine 반환."""
        melo_mock = _make_melo_mock()
        mock_melo_module = MagicMock()
        mock_melo_module.TTS = MagicMock(return_value=melo_mock)

        app_config = AppConfig(
            tts=TtsConfig(
                engine=TtsEngineKind.MELO,
                melo=MeloTtsSubConfig(model_dir=str(tmp_model_dir)),
            )
        )

        with (
            patch("tts._device._check_cuda_available", return_value=False),
            patch("tts.melo_tts_engine._set_offline_env_vars"),
            patch.dict(sys.modules, {"melo": MagicMock(), "melo.api": mock_melo_module}),
        ):
            engine = build_tts_engine(app_config)

        assert isinstance(engine, MeloTTSEngine)

    def test_build_xtts_engine(
        self, tmp_xtts_dir: Path, tmp_valid_wav: Path, tmp_path: Path
    ) -> None:
        """N-5B: engine="xtts_v2" + valid speaker_wav → XttsV2Engine 반환."""
        coqui_mock = _make_coqui_mock()
        mock_tts_module = MagicMock()
        mock_tts_module.TTS = MagicMock(return_value=coqui_mock)

        app_config = AppConfig(
            tts=TtsConfig(
                engine=TtsEngineKind.XTTS_V2,
                xtts=XttsV2SubConfig(
                    model_dir=str(tmp_xtts_dir),
                    speaker_wav=str(tmp_valid_wav),
                ),
            )
        )

        with (
            patch("tts._device._check_cuda_available", return_value=False),
            patch("tts.xtts_v2_engine._set_xtts_env_vars"),
            patch.dict(sys.modules, {"TTS": MagicMock(), "TTS.api": mock_tts_module}),
        ):
            engine = build_tts_engine(app_config)

        assert isinstance(engine, XttsV2Engine)

    def test_melo_config_ignores_xtts_fields(self, tmp_model_dir: Path, tmp_path: Path) -> None:
        """N-5: Melo 경로에서 xtts 필드는 무시된다 (speaker_wav=None이어도 OK)."""
        melo_mock = _make_melo_mock()
        mock_melo_module = MagicMock()
        mock_melo_module.TTS = MagicMock(return_value=melo_mock)

        app_config = AppConfig(
            tts=TtsConfig(
                engine=TtsEngineKind.MELO,
                melo=MeloTtsSubConfig(model_dir=str(tmp_model_dir)),
                xtts=XttsV2SubConfig(speaker_wav=None),
            )
        )

        with (
            patch("tts._device._check_cuda_available", return_value=False),
            patch("tts.melo_tts_engine._set_offline_env_vars"),
            patch.dict(sys.modules, {"melo": MagicMock(), "melo.api": mock_melo_module}),
        ):
            engine = build_tts_engine(app_config)

        assert isinstance(engine, MeloTTSEngine)


# ---------------------------------------------------------------------------
# 엣지 케이스 E-8
# ---------------------------------------------------------------------------


class TestBuildTtsEngineEdge:
    def test_xtts_without_speaker_wav_raises(self, tmp_xtts_dir: Path) -> None:
        """E-8: engine="xtts_v2" + speaker_wav=None → TTSInitError."""
        app_config = AppConfig(
            tts=TtsConfig(
                engine=TtsEngineKind.XTTS_V2,
                xtts=XttsV2SubConfig(
                    model_dir=str(tmp_xtts_dir),
                    speaker_wav=None,
                ),
            )
        )

        with pytest.raises(TTSInitError, match="speaker_wav required for xtts_v2"):
            build_tts_engine(app_config)
