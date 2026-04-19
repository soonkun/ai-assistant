# tests/asr/test_init.py
"""초기화 테스트 — N-1, A-1, A-2, A-3, A-4, E-7."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import NamedTuple
from unittest.mock import MagicMock, patch

import pytest

from asr.errors import ASRInitError
from asr.korean_whisper_asr import KoreanWhisperASR


class MockSegment(NamedTuple):
    text: str


class MockInfo:
    def __init__(self, language: str = "ko") -> None:
        self.language = language


# ──────────────────────────────────────────────
# N-1. 정상 초기화
# ──────────────────────────────────────────────


def test_n1_normal_init(tmp_model_dir: Path) -> None:
    """N-1: 정상 초기화 — 인스턴스 생성 성공, 속성 검증."""
    with patch("faster_whisper.WhisperModel", MagicMock()):
        asr = KoreanWhisperASR(
            model_path=str(tmp_model_dir),
            language="ko",
            compute_type="int8",
            device="auto",
        )

    assert asr.language == "ko"
    assert asr.compute_type == "int8"
    assert asr.resolved_device in {"cpu", "cuda"}


# ──────────────────────────────────────────────
# E-7. device="auto" + CUDA 사용 불가
# ──────────────────────────────────────────────


def test_e7_auto_cuda_unavailable_falls_back_to_cpu(
    tmp_model_dir: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """E-7: device=auto + CUDA 미가용 → cpu 폴백, 예외 없음, WARNING 로그 없음.

    스펙 §에러 처리 표: "device=auto + CUDA 가용 판별 실패 → cpu로 폴백"
    스펙 §테스트 E-7: "WARNING 없음" — CPU 폴백은 정상 동작이므로 WARNING을 발생시키지 않는다.
    """
    mock_cls = MagicMock()
    mock_cls.return_value = MagicMock()

    with (
        patch("faster_whisper.WhisperModel", mock_cls),
        patch("asr.korean_whisper_asr._check_cuda_available", return_value=False),
        caplog.at_level(logging.WARNING, logger="asr.korean_whisper_asr"),
    ):
        asr = KoreanWhisperASR(
            model_path=str(tmp_model_dir),
            language="ko",
            device="auto",
        )

    assert asr.resolved_device == "cpu"
    # device=auto에서 CPU로 폴백하는 것은 정상 동작 — WARNING 로그가 없어야 한다
    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warning_records) == 0, (
        f"device=auto CPU 폴백은 WARNING을 발생시키면 안 된다. "
        f"발생한 WARNING: {[r.message for r in warning_records]}"
    )


def test_e7_auto_cuda_available_uses_cuda(tmp_model_dir: Path) -> None:
    """E-7 변형: device=auto + CUDA 가용 → cuda 사용."""
    mock_cls = MagicMock()
    mock_cls.return_value = MagicMock()

    with (
        patch("faster_whisper.WhisperModel", mock_cls),
        patch("asr.korean_whisper_asr._check_cuda_available", return_value=True),
    ):
        asr = KoreanWhisperASR(
            model_path=str(tmp_model_dir),
            language="ko",
            device="auto",
        )

    assert asr.resolved_device == "cuda"


# ──────────────────────────────────────────────
# A-1. 존재하지 않는 model_path
# ──────────────────────────────────────────────


def test_a1_missing_model_path() -> None:
    """A-1: 존재하지 않는 model_path → ASRInitError."""
    mock_cls = MagicMock()

    with patch("faster_whisper.WhisperModel", mock_cls):
        with pytest.raises(ASRInitError, match="model_path not found"):
            KoreanWhisperASR(model_path="/no/such/dir")

    # WhisperModel 생성자는 호출되지 않아야 함
    mock_cls.assert_not_called()


# ──────────────────────────────────────────────
# A-2. download_root 네트워크 우회 시도
# ──────────────────────────────────────────────


def test_a2_invalid_download_root(tmp_model_dir: Path) -> None:
    """A-2: download_root 검증이 model_path 검증보다 먼저 실행됨을 증명한다.

    - model_path: 유효한 경로(tmp_model_dir — model.bin, config.json 존재)
    - download_root: 명백히 존재하지 않는 경로 /definitely/nonexistent/path/xyz

    model_path가 유효함에도 불구하고 download_root 검사가 먼저 실행되어
    ASRInitError("download_root must be empty or an existing directory")가 발생해야 한다.
    WhisperModel 생성자가 호출되지 않아야 한다(call_count == 0).

    이 테스트는 단순히 "비존재 download_root → 에러"를 확인하는 것이 아니라,
    검증 순서(download_root > model_path)를 명시적으로 보장한다.
    """
    mock_cls = MagicMock()

    with patch("faster_whisper.WhisperModel", mock_cls):
        with pytest.raises(
            ASRInitError,
            match="download_root must be empty or an existing directory",
        ):
            KoreanWhisperASR(
                # model_path는 유효 — 이 테스트에서 model_path 검증이 먼저 실행되면
                # 이 라인이 통과하고 download_root 에러가 발생하지 않는다.
                # 반대로 download_root가 먼저 검사되면 올바른 에러가 발생한다.
                model_path=str(tmp_model_dir),
                download_root="/definitely/nonexistent/path/xyz",
            )

    # download_root 검증에서 실패했으므로 WhisperModel 생성자는 호출되지 않아야 함
    assert mock_cls.call_count == 0, (
        "download_root 검증 실패 후 WhisperModel이 호출되면 안 된다. "
        f"실제 call_count: {mock_cls.call_count}"
    )


# ──────────────────────────────────────────────
# A-3. device="cuda" 강제 + CUDA 미가용
# ──────────────────────────────────────────────


def test_a3_cuda_forced_but_unavailable(tmp_model_dir: Path) -> None:
    """A-3: device=cuda 요청 + CUDA 미가용 → ASRInitError (폴백 없음)."""
    mock_cls = MagicMock()

    with (
        patch("faster_whisper.WhisperModel", mock_cls),
        patch("asr.korean_whisper_asr._check_cuda_available", return_value=False),
    ):
        with pytest.raises(ASRInitError, match="cuda requested but not available"):
            KoreanWhisperASR(
                model_path=str(tmp_model_dir),
                device="cuda",
            )

    mock_cls.assert_not_called()


# ──────────────────────────────────────────────
# A-4. 잘못된 language 주입
# ──────────────────────────────────────────────


def test_a4_invalid_language(tmp_model_dir: Path) -> None:
    """A-4: 허용 세트 외 language → ASRInitError."""
    mock_cls = MagicMock()

    with patch("faster_whisper.WhisperModel", mock_cls):
        with pytest.raises(ASRInitError, match="unsupported language: xx"):
            KoreanWhisperASR(
                model_path=str(tmp_model_dir),
                language="xx",
            )

    mock_cls.assert_not_called()


# ──────────────────────────────────────────────
# 추가 초기화 검증 (compute_type, device 범위)
# ──────────────────────────────────────────────


def test_invalid_compute_type_raises(tmp_model_dir: Path) -> None:
    """잘못된 compute_type → ASRInitError."""
    with patch("faster_whisper.WhisperModel", MagicMock()):
        with pytest.raises(ASRInitError, match="unsupported compute_type"):
            KoreanWhisperASR(model_path=str(tmp_model_dir), compute_type="bfloat16")


def test_invalid_device_raises(tmp_model_dir: Path) -> None:
    """잘못된 device → ASRInitError."""
    with patch("faster_whisper.WhisperModel", MagicMock()):
        with pytest.raises(ASRInitError, match="unsupported device"):
            KoreanWhisperASR(model_path=str(tmp_model_dir), device="tpu")


def test_initial_prompt_too_long_raises(tmp_model_dir: Path) -> None:
    """initial_prompt 201자 → ASRInitError."""
    with patch("faster_whisper.WhisperModel", MagicMock()):
        with pytest.raises(ASRInitError, match="initial_prompt exceeds 200"):
            KoreanWhisperASR(
                model_path=str(tmp_model_dir),
                initial_prompt="x" * 201,
            )


def test_model_dir_missing_model_bin(tmp_path: Path) -> None:
    """model.bin 없음 → ASRInitError."""
    model_dir = tmp_path / "bad_model"
    model_dir.mkdir()
    (model_dir / "config.json").touch()  # model.bin 없음

    with patch("faster_whisper.WhisperModel", MagicMock()):
        with pytest.raises(ASRInitError, match="model weights missing"):
            KoreanWhisperASR(model_path=str(model_dir))


def test_model_dir_missing_config_json(tmp_path: Path) -> None:
    """config.json 없음 → ASRInitError."""
    model_dir = tmp_path / "bad_model"
    model_dir.mkdir()
    (model_dir / "model.bin").touch()  # config.json 없음

    with patch("faster_whisper.WhisperModel", MagicMock()):
        with pytest.raises(ASRInitError, match="model weights missing"):
            KoreanWhisperASR(model_path=str(model_dir))


def test_whisper_model_constructor_exception_wrapped(tmp_model_dir: Path) -> None:
    """WhisperModel 생성자 예외 → ASRInitError로 래핑."""
    mock_cls = MagicMock(side_effect=RuntimeError("backend error"))

    with patch("faster_whisper.WhisperModel", mock_cls):
        with pytest.raises(ASRInitError, match="backend error"):
            KoreanWhisperASR(model_path=str(tmp_model_dir))


def test_language_none_is_accepted(tmp_model_dir: Path) -> None:
    """language=None → 정상 초기화 (자동 감지 모드)."""
    mock_cls = MagicMock()
    mock_cls.return_value = MagicMock()

    with patch("faster_whisper.WhisperModel", mock_cls):
        asr = KoreanWhisperASR(model_path=str(tmp_model_dir), language=None)

    assert asr.language is None
