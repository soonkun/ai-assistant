# src/tts/speaker_wav.py
"""화자 참조 WAV 유효성 검증 유틸."""

from __future__ import annotations

import hashlib
import logging
import wave
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

ALLOWED_SAMPLE_RATES: frozenset[int] = frozenset({16000, 22050, 24000, 44100, 48000})

MAX_SPEAKER_WAV_BYTES: int = 10 * 1024 * 1024  # 10 MB


@dataclass(frozen=True)
class SpeakerWavInfo:
    """WAV 파일 메타 정보."""

    path: str
    channels: int  # 1만 허용(mono)
    sample_rate: int  # ALLOWED_SAMPLE_RATES 중 하나
    duration_sec: float
    bit_depth: int  # 16만 허용(PCM_16)
    sha256: str  # 중복 업로드 감지용


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

    Args:
        path: WAV 파일 경로.
        min_sec: 최소 재생 시간(초). 기본 3.0.
        max_sec: 최대 재생 시간(초). 기본 30.0.

    Returns:
        SpeakerWavInfo: 검증된 WAV 파일 메타 정보.

    Raises:
        FileNotFoundError: 파일 부재.
        ValueError: 위 조건 중 하나라도 위반. 메시지에 어떤 필드가 실패했는지 명시.
    """
    p = Path(path)

    if not p.exists():
        raise FileNotFoundError(f"speaker_wav not found: {path}")

    if p.suffix.lower() != ".wav":
        raise ValueError(f"extension must be .wav, got: {p.suffix!r}")

    file_size = p.stat().st_size
    if file_size > MAX_SPEAKER_WAV_BYTES:
        raise ValueError(f"file size {file_size} exceeds max {MAX_SPEAKER_WAV_BYTES} bytes")

    # RIFF/WAVE 헤더 검증 및 오디오 속성 확인
    try:
        with wave.open(str(p), "rb") as wf:
            channels = wf.getnchannels()
            sample_rate = wf.getframerate()
            sampwidth = wf.getsampwidth()
            n_frames = wf.getnframes()
    except wave.Error as exc:
        raise ValueError(f"invalid RIFF header or WAV format: {exc}") from exc
    except EOFError as exc:
        raise ValueError(f"invalid RIFF header or WAV format: {exc}") from exc

    if channels != 1:
        raise ValueError(f"channels must be 1 (mono), got: {channels}")

    if sample_rate not in ALLOWED_SAMPLE_RATES:
        raise ValueError(
            f"sample_rate {sample_rate} not in allowed set {sorted(ALLOWED_SAMPLE_RATES)}"
        )

    bit_depth = sampwidth * 8
    if bit_depth != 16:
        raise ValueError(f"bit_depth must be 16 (PCM_16), got: {bit_depth}")

    if sample_rate == 0:
        raise ValueError("sample_rate is 0, cannot compute duration")

    duration_sec = n_frames / sample_rate
    if duration_sec < min_sec:
        raise ValueError(f"duration {duration_sec:.2f}s is shorter than min {min_sec}s")
    if duration_sec > max_sec:
        raise ValueError(f"duration {duration_sec:.2f}s exceeds max {max_sec}s")

    # sha256 계산
    sha256 = _compute_sha256(p)

    logger.debug(
        "validate_speaker_wav OK: path=%s channels=%d sr=%d bit=%d dur=%.2fs",
        path,
        channels,
        sample_rate,
        bit_depth,
        duration_sec,
    )

    return SpeakerWavInfo(
        path=str(p.resolve()),
        channels=channels,
        sample_rate=sample_rate,
        duration_sec=duration_sec,
        bit_depth=bit_depth,
        sha256=sha256,
    )


def _compute_sha256(p: Path) -> str:
    """파일의 sha256 hex digest를 반환한다."""
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
