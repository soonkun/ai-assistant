# tests/tts/test_speaker_wav.py
"""validate_speaker_wav 단위 테스트."""

from __future__ import annotations

import wave
from pathlib import Path

import pytest

from tts.speaker_wav import SpeakerWavInfo, validate_speaker_wav


def create_wav(
    path: Path,
    duration_sec: float = 4.0,
    sample_rate: int = 24000,
    channels: int = 1,
    sampwidth: int = 2,
) -> Path:
    """테스트용 WAV 파일 생성 헬퍼."""
    n_frames = int(duration_sec * sample_rate)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00" * (n_frames * channels * sampwidth))
    return path


# ---------------------------------------------------------------------------
# 정상 케이스
# ---------------------------------------------------------------------------


class TestValidateSpeakerWavNormal:
    """N-6: 정상 검증 통과."""

    def test_valid_4s_24k_mono_pcm16(self, tmp_path: Path) -> None:
        """N-6: 4초 mono 24kHz PCM16 WAV — 정상 통과."""
        p = create_wav(tmp_path / "ok.wav", duration_sec=4.0, sample_rate=24000)
        info = validate_speaker_wav(str(p))
        assert isinstance(info, SpeakerWavInfo)
        assert info.channels == 1
        assert info.sample_rate == 24000
        assert info.bit_depth == 16
        assert abs(info.duration_sec - 4.0) < 0.01
        assert len(info.sha256) == 64

    def test_valid_min_duration(self, tmp_path: Path) -> None:
        """min_sec 경계: 3.0초 정확히."""
        p = create_wav(tmp_path / "min.wav", duration_sec=3.0, sample_rate=24000)
        info = validate_speaker_wav(str(p), min_sec=3.0)
        assert info.duration_sec >= 3.0

    def test_valid_22050hz(self, tmp_path: Path) -> None:
        """22050Hz WAV 정상 통과."""
        p = create_wav(tmp_path / "22k.wav", duration_sec=4.0, sample_rate=22050)
        info = validate_speaker_wav(str(p))
        assert info.sample_rate == 22050

    def test_valid_16000hz(self, tmp_path: Path) -> None:
        """16000Hz WAV 정상 통과."""
        p = create_wav(tmp_path / "16k.wav", duration_sec=4.0, sample_rate=16000)
        info = validate_speaker_wav(str(p))
        assert info.sample_rate == 16000

    def test_sha256_consistency(self, tmp_path: Path) -> None:
        """동일 파일은 같은 sha256을 반환한다."""
        p = create_wav(tmp_path / "sha.wav", duration_sec=4.0)
        info1 = validate_speaker_wav(str(p))
        info2 = validate_speaker_wav(str(p))
        assert info1.sha256 == info2.sha256


# ---------------------------------------------------------------------------
# 에러 케이스
# ---------------------------------------------------------------------------


class TestValidateSpeakerWavErrors:
    """유효성 검증 실패 케이스."""

    def test_file_not_found(self, tmp_path: Path) -> None:
        """존재하지 않는 파일 → FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            validate_speaker_wav(str(tmp_path / "missing.wav"))

    def test_wrong_extension(self, tmp_path: Path) -> None:
        """확장자가 .wav가 아닌 경우 → ValueError."""
        p = tmp_path / "audio.mp3"
        p.write_bytes(b"\x00" * 1024)
        with pytest.raises(ValueError, match="extension"):
            validate_speaker_wav(str(p))

    def test_stereo_wav_raises(self, tmp_path: Path) -> None:
        """2채널 WAV → ValueError, 메시지에 'channels'."""
        p = create_wav(tmp_path / "stereo.wav", channels=2)
        with pytest.raises(ValueError, match="channels"):
            validate_speaker_wav(str(p))

    def test_too_short(self, tmp_path: Path) -> None:
        """1.5초 WAV → ValueError, 메시지에 'duration'."""
        p = create_wav(tmp_path / "short.wav", duration_sec=1.5)
        with pytest.raises(ValueError, match="duration"):
            validate_speaker_wav(str(p), min_sec=3.0)

    def test_too_long(self, tmp_path: Path) -> None:
        """35초 WAV → ValueError, 메시지에 'duration'."""
        p = create_wav(tmp_path / "long.wav", duration_sec=35.0)
        with pytest.raises(ValueError, match="duration"):
            validate_speaker_wav(str(p), max_sec=30.0)

    def test_invalid_sample_rate(self, tmp_path: Path) -> None:
        """지원되지 않는 샘플레이트(8000) → ValueError."""
        p = create_wav(tmp_path / "8k.wav", duration_sec=4.0, sample_rate=8000)
        with pytest.raises(ValueError, match="sample_rate"):
            validate_speaker_wav(str(p))

    def test_8bit_wav_raises(self, tmp_path: Path) -> None:
        """8-bit PCM WAV → ValueError, 메시지에 'bit_depth'."""
        p = create_wav(tmp_path / "8bit.wav", duration_sec=4.0, sampwidth=1)
        with pytest.raises(ValueError, match="bit_depth"):
            validate_speaker_wav(str(p))

    def test_oversized_file(self, tmp_path: Path) -> None:
        """파일 크기 > 10MB → ValueError."""
        from tts.speaker_wav import MAX_SPEAKER_WAV_BYTES

        p = create_wav(tmp_path / "big.wav", duration_sec=4.0)
        # 파일을 인위적으로 크게 만듦 (헤더는 유지, 데이터만 덧붙임)
        with p.open("ab") as f:
            f.write(b"\x00" * (MAX_SPEAKER_WAV_BYTES + 1))
        with pytest.raises(ValueError, match="file size"):
            validate_speaker_wav(str(p))

    def test_invalid_riff_header(self, tmp_path: Path) -> None:
        """유효하지 않은 RIFF 헤더 → ValueError."""
        p = tmp_path / "fake.wav"
        p.write_bytes(b"FAKE" + b"\x00" * 100)
        with pytest.raises(ValueError, match="RIFF"):
            validate_speaker_wav(str(p))
