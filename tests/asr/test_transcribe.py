# tests/asr/test_transcribe.py
"""transcribe_np 테스트 — N-2, N-3, N-4, N-5, E-1~E-6, A-5, A-6."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Iterator, NamedTuple
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from asr.errors import ASRRuntimeError
from asr.korean_whisper_asr import KoreanWhisperASR


class MockSegment(NamedTuple):
    text: str


class MockInfo:
    def __init__(self, language: str = "ko") -> None:
        self.language = language


# ──────────────────────────────────────────────
# 픽스처
# ──────────────────────────────────────────────


@pytest.fixture()
def asr(tmp_model_dir: Path) -> Iterator[KoreanWhisperASR]:
    """기본 설정의 KoreanWhisperASR 인스턴스 (mock WhisperModel)."""
    mock_cls = MagicMock()
    mock_instance = MagicMock()
    mock_instance.transcribe.return_value = ([], MockInfo("ko"))
    mock_cls.return_value = mock_instance

    with patch("faster_whisper.WhisperModel", mock_cls):
        instance = KoreanWhisperASR(
            model_path=str(tmp_model_dir),
            language="ko",
            compute_type="int8",
            device="auto",
        )
        yield instance


@pytest.fixture()
def asr_with_mock(tmp_model_dir: Path) -> Iterator[tuple[KoreanWhisperASR, MagicMock]]:
    """asr 인스턴스와 mock 모델을 함께 반환한다."""
    mock_cls = MagicMock()
    mock_instance = MagicMock()
    mock_instance.transcribe.return_value = ([], MockInfo("ko"))
    mock_cls.return_value = mock_instance

    with patch("faster_whisper.WhisperModel", mock_cls):
        instance = KoreanWhisperASR(
            model_path=str(tmp_model_dir),
            language="ko",
            compute_type="int8",
            device="auto",
        )
        yield instance, mock_instance


# ──────────────────────────────────────────────
# N-2. 한국어 오디오 전사
# ──────────────────────────────────────────────


def test_n2_korean_transcription(tmp_model_dir: Path) -> None:
    """N-2: 한국어 mock segments → 올바른 전사 결과 및 call_args 확인."""
    mock_cls = MagicMock()
    mock_instance = MagicMock()
    mock_instance.transcribe.return_value = (
        [MockSegment(text="안녕하세요"), MockSegment(text=" 반갑습니다")],
        MockInfo("ko"),
    )
    mock_cls.return_value = mock_instance

    with patch("faster_whisper.WhisperModel", mock_cls):
        asr = KoreanWhisperASR(
            model_path=str(tmp_model_dir),
            language="ko",
            compute_type="int8",
            device="auto",
        )

    audio = np.random.rand(16000 * 2).astype(np.float32)
    result = asr.transcribe_np(audio)

    assert result == "안녕하세요 반갑습니다"

    call_kwargs = mock_instance.transcribe.call_args.kwargs
    assert call_kwargs["beam_size"] == 5
    assert call_kwargs["language"] == "ko"
    assert call_kwargs["condition_on_previous_text"] is False
    assert call_kwargs["initial_prompt"] is None


# ──────────────────────────────────────────────
# N-3. async 경로 동작
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_n3_async_transcribe(tmp_model_dir: Path) -> None:
    """N-3: async_transcribe_np가 transcribe_np를 스레드로 호출한다."""
    mock_cls = MagicMock()
    mock_instance = MagicMock()
    mock_instance.transcribe.return_value = (
        [MockSegment(text="테스트")],
        MockInfo("ko"),
    )
    mock_cls.return_value = mock_instance

    with patch("faster_whisper.WhisperModel", mock_cls):
        asr = KoreanWhisperASR(
            model_path=str(tmp_model_dir),
            language="ko",
            device="auto",
        )

    audio = np.random.rand(16000 * 2).astype(np.float32)
    result = await asr.async_transcribe_np(audio)
    assert result == "테스트"


@pytest.mark.asyncio
async def test_n3_async_cancel_propagates(tmp_model_dir: Path) -> None:
    """N-3 변형: asyncio.CancelledError가 상위로 전파 가능하다."""
    mock_cls = MagicMock()
    mock_instance = MagicMock()
    mock_instance.transcribe.return_value = ([], MockInfo("ko"))
    mock_cls.return_value = mock_instance

    with patch("faster_whisper.WhisperModel", mock_cls):
        asr = KoreanWhisperASR(
            model_path=str(tmp_model_dir),
            language="ko",
            device="auto",
        )

    audio = np.zeros(16000 * 2, dtype=np.float32)
    # wait_for timeout=0은 즉시 CancelledError를 발생시킨다
    with pytest.raises((asyncio.TimeoutError, asyncio.CancelledError)):
        await asyncio.wait_for(asr.async_transcribe_np(audio), timeout=0)


@pytest.mark.asyncio
async def test_n3_async_dispatches_to_thread(tmp_model_dir: Path) -> None:
    """N-3 스레드 디스패치 검증: async_transcribe_np는 asyncio.to_thread로 transcribe_np를 호출한다.

    asyncio.to_thread를 mock으로 교체하고 첫 번째 인자가 asr.transcribe_np임을 확인한다.
    이것은 부모 ASRInterface의 기본 구현이 스레드풀에 디스패치함을 직접 증명한다.
    """
    mock_cls = MagicMock()
    mock_instance = MagicMock()
    mock_instance.transcribe.return_value = (
        [MockSegment(text="스레드")],
        MockInfo("ko"),
    )
    mock_cls.return_value = mock_instance

    with patch("faster_whisper.WhisperModel", mock_cls):
        asr = KoreanWhisperASR(
            model_path=str(tmp_model_dir),
            language="ko",
            device="auto",
        )

    audio = np.random.rand(16000 * 2).astype(np.float32)

    # asyncio.to_thread를 mock하여 실제로 호출되는지, 첫 인자가 transcribe_np인지 확인
    captured_calls: list[tuple[object, ...]] = []

    async def mock_to_thread(func: object, *args: object, **kwargs: object) -> object:
        captured_calls.append((func, args, kwargs))
        # 실제 스레드 디스패치는 수행하지 않고, 동기로 func을 호출해 결과 반환
        import asyncio

        return await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: func(*args, **kwargs),  # type: ignore[operator]
        )

    with patch("asyncio.to_thread", side_effect=mock_to_thread):
        result = await asr.async_transcribe_np(audio)

    # asyncio.to_thread가 1번 호출되었는지 확인
    assert len(captured_calls) == 1, "asyncio.to_thread가 정확히 1회 호출되어야 한다"

    # 첫 번째 인자가 asr.transcribe_np임을 확인 (스레드 디스패치 증명).
    # Python 바운드 메서드는 접근할 때마다 새 객체가 생성되므로 `is` 대신
    # __func__(언바운드 함수)와 __self__(인스턴스)를 각각 비교한다.
    dispatched_func = captured_calls[0][0]
    assert hasattr(dispatched_func, "__func__"), (
        f"dispatched_func는 바운드 메서드여야 한다. 실제: {dispatched_func!r}"
    )
    assert dispatched_func.__func__ is KoreanWhisperASR.transcribe_np, (
        "to_thread에 전달된 함수는 KoreanWhisperASR.transcribe_np여야 한다. "
        f"실제: {dispatched_func.__func__!r}"
    )
    assert dispatched_func.__self__ is asr, "to_thread에 전달된 메서드의 인스턴스가 asr여야 한다."

    assert result == "스레드"


# ──────────────────────────────────────────────
# N-4. prompt 설정 전달
# ──────────────────────────────────────────────


def test_n4_initial_prompt_passed(tmp_model_dir: Path) -> None:
    """N-4: initial_prompt가 transcribe 호출에 전달된다."""
    mock_cls = MagicMock()
    mock_instance = MagicMock()
    mock_instance.transcribe.return_value = (
        [MockSegment(text="회의 결과")],
        MockInfo("ko"),
    )
    mock_cls.return_value = mock_instance

    with patch("faster_whisper.WhisperModel", mock_cls):
        asr = KoreanWhisperASR(
            model_path=str(tmp_model_dir),
            language="ko",
            initial_prompt="사내 회의 기술 용어",
        )

    audio = np.random.rand(16000 * 2).astype(np.float32)
    asr.transcribe_np(audio)

    assert mock_instance.transcribe.call_args.kwargs["initial_prompt"] == "사내 회의 기술 용어"


# ──────────────────────────────────────────────
# N-5. 영어 자동 전환 (language=None)
# ──────────────────────────────────────────────


def test_n5_language_none_no_warn(tmp_model_dir: Path, caplog: pytest.LogCaptureFixture) -> None:
    """N-5: language=None + info.language=en → 결과 유지, warning 없음."""
    mock_cls = MagicMock()
    mock_instance = MagicMock()
    mock_instance.transcribe.return_value = (
        [MockSegment(text="Hello world")],
        MockInfo("en"),
    )
    mock_cls.return_value = mock_instance

    with patch("faster_whisper.WhisperModel", mock_cls):
        asr = KoreanWhisperASR(
            model_path=str(tmp_model_dir),
            language=None,
        )

    audio = np.random.rand(16000 * 2).astype(np.float32)

    with caplog.at_level(logging.WARNING, logger="asr.korean_whisper_asr"):
        result = asr.transcribe_np(audio)

    assert result == "Hello world"
    # language=None이므로 불일치 경고 없음
    assert not any("언어 불일치" in r.message for r in caplog.records)


# ──────────────────────────────────────────────
# E-1. 0 길이 오디오
# ──────────────────────────────────────────────


def test_e1_zero_length_audio(asr_with_mock: tuple[KoreanWhisperASR, MagicMock]) -> None:
    """E-1: 0 길이 오디오 → 빈 문자열, transcribe 미호출."""
    asr, mock_model = asr_with_mock
    audio = np.zeros(0, dtype=np.float32)

    result = asr.transcribe_np(audio)

    assert result == ""
    mock_model.transcribe.assert_not_called()


# ──────────────────────────────────────────────
# E-2. 초단시간 오디오 (0.1초)
# ──────────────────────────────────────────────


def test_e2_too_short_audio(
    asr_with_mock: tuple[KoreanWhisperASR, MagicMock],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """E-2: 0.1초 오디오 (< min_audio_seconds=0.2) → 빈 문자열, transcribe 미호출, DEBUG 로그."""
    asr, mock_model = asr_with_mock
    audio = np.random.rand(1600).astype(np.float32)  # 0.1초

    with caplog.at_level(logging.DEBUG, logger="asr.korean_whisper_asr"):
        result = asr.transcribe_np(audio)

    assert result == ""
    mock_model.transcribe.assert_not_called()
    assert any(r.levelno == logging.DEBUG for r in caplog.records)


# ──────────────────────────────────────────────
# E-3. dtype 변환 (int16 입력)
# ──────────────────────────────────────────────


def test_e3_int16_input_converted(asr_with_mock: tuple[KoreanWhisperASR, MagicMock]) -> None:
    """E-3: int16 입력 → float32로 캐스트되어 transcribe에 전달된다."""
    asr, mock_model = asr_with_mock
    mock_model.transcribe.return_value = ([MockSegment(text="변환")], MockInfo("ko"))

    audio = (np.random.rand(32000) * 32767).astype(np.int16)
    asr.transcribe_np(audio)

    called_audio = mock_model.transcribe.call_args.args[0]
    assert called_audio.dtype == np.float32


# ──────────────────────────────────────────────
# E-4. NaN/Inf 포함
# ──────────────────────────────────────────────


def test_e4_nan_inf_replaced(
    asr_with_mock: tuple[KoreanWhisperASR, MagicMock],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """E-4: NaN/Inf 포함 오디오 → nan_to_num 치환 후 전달, WARNING 1회."""
    asr, mock_model = asr_with_mock
    mock_model.transcribe.return_value = ([MockSegment(text="ok")], MockInfo("ko"))

    audio = np.array([0.1, np.nan, np.inf, -np.inf, 0.2] * 10000, dtype=np.float32)

    with caplog.at_level(logging.WARNING, logger="asr.korean_whisper_asr"):
        asr.transcribe_np(audio)

    called_audio = mock_model.transcribe.call_args.args[0]
    assert np.isfinite(called_audio).all()

    warn_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warn_records) == 1


# ──────────────────────────────────────────────
# E-5. 세그먼트 수 0
# ──────────────────────────────────────────────


def test_e5_empty_segments(asr_with_mock: tuple[KoreanWhisperASR, MagicMock]) -> None:
    """E-5: mock transcribe가 빈 리스트 반환 → 빈 문자열, 예외 없음."""
    asr, mock_model = asr_with_mock
    mock_model.transcribe.return_value = ([], MockInfo("ko"))

    audio = np.random.rand(16000 * 2).astype(np.float32)
    result = asr.transcribe_np(audio)

    assert result == ""


# ──────────────────────────────────────────────
# E-6. info.language와 요청 언어 불일치
# ──────────────────────────────────────────────


def test_e6_language_mismatch_warns(
    asr_with_mock: tuple[KoreanWhisperASR, MagicMock],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """E-6: language=ko + info.language=en → 결과 유지, WARNING 1건."""
    asr, mock_model = asr_with_mock
    mock_model.transcribe.return_value = (
        [MockSegment(text="Hello")],
        MockInfo("en"),
    )

    audio = np.random.rand(16000 * 2).astype(np.float32)

    with caplog.at_level(logging.WARNING, logger="asr.korean_whisper_asr"):
        result = asr.transcribe_np(audio)

    assert result == "Hello"
    warn_records = [
        r for r in caplog.records if r.levelno == logging.WARNING and "언어 불일치" in r.message
    ]
    assert len(warn_records) == 1


# ──────────────────────────────────────────────
# A-5. 비정상 numpy 배열 (2D)
# ──────────────────────────────────────────────


def test_a5_2d_audio_raises(asr_with_mock: tuple[KoreanWhisperASR, MagicMock]) -> None:
    """A-5: 2D 오디오 배열 → ASRRuntimeError("invalid audio shape")."""
    asr, mock_model = asr_with_mock
    audio = np.zeros((2, 16000), dtype=np.float32)

    with pytest.raises(ASRRuntimeError, match="invalid audio shape"):
        asr.transcribe_np(audio)

    mock_model.transcribe.assert_not_called()


def test_a5_none_audio_raises(asr: KoreanWhisperASR) -> None:
    """A-5 변형: audio=None → ASRRuntimeError("invalid audio shape")."""
    with pytest.raises(ASRRuntimeError, match="invalid audio shape"):
        asr.transcribe_np(None)  # type: ignore[arg-type]


# ──────────────────────────────────────────────
# A-6. 백엔드 예외
# ──────────────────────────────────────────────


def test_a6_backend_exception_wrapped(asr_with_mock: tuple[KoreanWhisperASR, MagicMock]) -> None:
    """A-6: mock transcribe가 RuntimeError → ASRRuntimeError로 래핑, __cause__ 확인."""
    asr, mock_model = asr_with_mock
    original_error = RuntimeError("CUDA OOM")
    mock_model.transcribe.side_effect = original_error

    audio = np.random.rand(16000 * 2).astype(np.float32)

    with pytest.raises(ASRRuntimeError, match="CUDA OOM") as exc_info:
        asr.transcribe_np(audio)

    assert exc_info.value.__cause__ is original_error
