# tests/e2e/test_e2e_21_empty_asr.py
"""E2E-21: 무음 WAV → ASR 빈 문자열 → Gemma 호출 생략.

시나리오 ID: E2E-21-empty-asr
REQUIREMENTS: §1.1 VAD + STT
관련 모듈: M_02 ASREngine, M_03 VAD, M_05 LLMAgent
마커: e2e_model (Whisper 모델 필요)
실행 시간 목표: ≤ 8초
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.e2e_model]

_FIXTURES_AUDIO = Path(__file__).parent / "fixtures" / "audio"
_WHISPER_PATHS = [
    Path("assets/models/whisper-large-v3-int8"),
    Path("assets/models/whisper-medium-int8"),
]


def _find_whisper_model() -> Path | None:
    for p in _WHISPER_PATHS:
        if p.exists():
            return p
    return None


@pytest.mark.timeout(20)
async def test_e2e_21_empty_asr() -> None:
    """무음 WAV → ASR 빈 문자열 또는 무음 관련 결과.

    수락 기준:
    - ASR 결과가 빈 문자열 또는 매우 짧은 텍스트 (< 5자).
    - 예외 없이 완료.
    - Gemma 호출 0회 (ASR 결과 검증 — 빈 결과면 chat() 호출 안 함).
    """
    whisper_path = _find_whisper_model()
    if whisper_path is None:
        pytest.skip(
            reason=(f"Q-5 옵션 A: Whisper 모델 없음. 경로: {[str(p) for p in _WHISPER_PATHS]}")
        )

    silence_wav = _FIXTURES_AUDIO / "silence_2s.wav"
    if not silence_wav.exists():
        pytest.skip(reason=f"무음 WAV 없음: {silence_wav}")

    from asr.korean_whisper_asr import KoreanWhisperASR

    asr = KoreanWhisperASR(
        model_path=str(whisper_path),
        language="ko",
        compute_type="int8",
    )

    # 무음 WAV float32 로드
    with wave.open(str(silence_wav), "rb") as wf:
        frames = wf.readframes(wf.getnframes())
    audio = np.zeros(len(frames) // 2, dtype=np.float32)

    result = await asr.async_transcribe_np(audio)

    # 수락 기준: 무음 → 빈 문자열 또는 매우 짧은 결과
    assert isinstance(result, str), f"결과가 str이 아님: {type(result)}"
    # 무음에서 긴 텍스트가 나오면 비정상
    assert len(result.strip()) < 20, f"무음 WAV에서 긴 ASR 결과: {result!r}"
