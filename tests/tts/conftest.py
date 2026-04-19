# tests/tts/conftest.py
"""TTS 테스트 공통 픽스처 및 mock 등록."""

from __future__ import annotations

import sys
import wave
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# melo / TTS (Coqui) mock — import 전에 sys.modules에 등록
# ---------------------------------------------------------------------------


def _make_mock_package(name: str) -> MagicMock:
    mock = MagicMock()
    mock.__name__ = name
    mock.__package__ = name
    mock.__path__ = []
    mock.__spec__ = None
    return mock


_MELO_MOCK_PACKAGES = [
    "melo",
    "melo.api",
    "TTS",
    "TTS.api",
]
for _pkg in _MELO_MOCK_PACKAGES:
    if _pkg not in sys.modules:
        sys.modules[_pkg] = _make_mock_package(_pkg)  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# 유틸: 유효한 WAV 파일 생성
# ---------------------------------------------------------------------------


def create_wav_file(
    path: Path,
    duration_sec: float = 4.0,
    sample_rate: int = 24000,
    channels: int = 1,
    sampwidth: int = 2,
) -> Path:
    """테스트용 WAV 파일을 생성한다."""
    n_frames = int(duration_sec * sample_rate)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(sample_rate)
        # 무음 데이터(모두 0)
        wf.writeframes(b"\x00" * (n_frames * channels * sampwidth))
    return path


# ---------------------------------------------------------------------------
# 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_model_dir(tmp_path: Path) -> Path:
    """MeloTTS 모델 stub 디렉토리."""
    d = tmp_path / "melotts-ko"
    d.mkdir()
    # stub 파일 생성
    (d / "config.json").write_text("{}")
    (d / "checkpoint.pth").write_bytes(b"\x00" * 8)
    (d / "tokenizer.json").write_text("{}")
    return d


@pytest.fixture()
def tmp_xtts_dir(tmp_path: Path) -> Path:
    """XTTS v2 모델 stub 디렉토리."""
    d = tmp_path / "xtts_v2"
    d.mkdir()
    for fname in [
        "config.json",
        "model.pth",
        "vocab.json",
        "dvae.pth",
        "mel_stats.pth",
        "speakers_xtts.pth",
    ]:
        (d / fname).write_bytes(b"\x00" * 8)
    return d


@pytest.fixture()
def tmp_valid_wav(tmp_path: Path) -> Path:
    """유효한 4초 mono 24kHz PCM16 WAV 파일."""
    p = tmp_path / "speaker.wav"
    return create_wav_file(p, duration_sec=4.0, sample_rate=24000, channels=1, sampwidth=2)


@pytest.fixture()
def tmp_valid_wav_22050(tmp_path: Path) -> Path:
    """유효한 3초 mono 22050Hz PCM16 WAV 파일 (E-5 경계값)."""
    p = tmp_path / "speaker_22050.wav"
    return create_wav_file(p, duration_sec=3.0, sample_rate=22050, channels=1, sampwidth=2)


@pytest.fixture()
def tmp_stereo_wav(tmp_path: Path) -> Path:
    """stereo(2채널) WAV — 유효성 실패 케이스."""
    p = tmp_path / "stereo.wav"
    return create_wav_file(p, duration_sec=4.0, sample_rate=24000, channels=2, sampwidth=2)


@pytest.fixture()
def tmp_short_wav(tmp_path: Path) -> Path:
    """1.5초 WAV — 너무 짧음."""
    p = tmp_path / "short.wav"
    return create_wav_file(p, duration_sec=1.5, sample_rate=24000, channels=1, sampwidth=2)


@pytest.fixture()
def tmp_35s_wav(tmp_path: Path) -> Path:
    """3.5초 WAV — 경계값 (E-4)."""
    p = tmp_path / "speaker_35s.wav"
    return create_wav_file(p, duration_sec=3.5, sample_rate=24000, channels=1, sampwidth=2)


@pytest.fixture()
def mock_melo_tts() -> MagicMock:
    """melo.api.TTS mock 인스턴스."""
    mock = MagicMock()
    mock.hps.data.spk2id = {"KR": 0}
    return mock


@pytest.fixture()
def mock_coqui_tts() -> MagicMock:
    """TTS.api.TTS mock 인스턴스."""
    mock = MagicMock()
    mock.to.return_value = mock
    return mock
