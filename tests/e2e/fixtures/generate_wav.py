#!/usr/bin/env python3
# tests/e2e/fixtures/generate_wav.py
"""테스트용 WAV 파일 생성 스크립트.

실제 한국어 음성 파일이 없을 때 사용할 수 있는 더미 WAV 생성기.
E2E-02/21 테스트용:
  - silence_2s.wav: 2초 무음 (전부 0)
  - greeting_ko.wav: 간단한 440Hz 사인파 (ASR이 음성으로 인식할 수 있을 정도)

실제 E2E-02는 실제 한국어 음성이 필요하므로, 이 스크립트로 생성된 파일은
ASR skip 로직 테스트(무음)에만 유효하다.
"""

from __future__ import annotations

import struct
import wave
from pathlib import Path


FIXTURES_AUDIO_DIR = Path(__file__).parent / "audio"


def _write_wav(path: Path, frames: bytes, sample_rate: int = 16000, channels: int = 1) -> None:
    """PCM16 WAV 파일 기록."""
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(frames)


def generate_silence(duration_sec: float = 2.0, sample_rate: int = 16000) -> None:
    """무음 WAV 생성."""
    path = FIXTURES_AUDIO_DIR / "silence_2s.wav"
    n_samples = int(sample_rate * duration_sec)
    frames = b"\x00\x00" * n_samples
    _write_wav(path, frames, sample_rate)
    print(f"Generated: {path} ({n_samples} samples, {duration_sec}s silence)")


def generate_tone(
    duration_sec: float = 3.0,
    freq_hz: float = 440.0,
    sample_rate: int = 16000,
    amplitude: float = 0.3,
) -> None:
    """사인파 WAV 생성 (greeting_ko.wav 대체용)."""
    import math

    path = FIXTURES_AUDIO_DIR / "greeting_ko.wav"
    n_samples = int(sample_rate * duration_sec)
    frames = b""
    for i in range(n_samples):
        t = i / sample_rate
        sample = amplitude * math.sin(2 * math.pi * freq_hz * t)
        # float → int16
        sample_int = int(max(-32768, min(32767, sample * 32767)))
        frames += struct.pack("<h", sample_int)
    _write_wav(path, frames, sample_rate)
    print(f"Generated: {path} ({n_samples} samples, {duration_sec}s tone)")


if __name__ == "__main__":
    FIXTURES_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    generate_silence()
    generate_tone()
    print("Done.")
