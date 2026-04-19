# tests/asr/conftest.py
"""공통 픽스처 및 헬퍼."""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple
from unittest.mock import MagicMock, patch

import pytest


# ──────────────────────────────────────────────
# 헬퍼 타입 (test 파일에서 conftest를 통해 접근)
# ──────────────────────────────────────────────


class MockSegment(NamedTuple):
    """faster_whisper Segment의 최소 구현."""

    text: str


class MockInfo:
    """faster_whisper TranscriptionInfo의 최소 구현."""

    def __init__(self, language: str = "ko") -> None:
        self.language = language


# ──────────────────────────────────────────────
# 픽스처
# ──────────────────────────────────────────────


@pytest.fixture()
def tmp_model_dir(tmp_path: Path) -> Path:
    """model.bin과 config.json이 존재하는 임시 모델 디렉토리."""
    model_dir = tmp_path / "whisper-test"
    model_dir.mkdir(parents=True)
    (model_dir / "model.bin").touch()
    (model_dir / "config.json").touch()
    return model_dir


@pytest.fixture()
def patched_whisper(tmp_model_dir: Path) -> MagicMock:
    """WhisperModel을 패치하고 tmp_model_dir을 사용하는 통합 픽스처."""
    mock_cls = MagicMock()
    mock_instance = MagicMock()
    mock_instance.transcribe.return_value = ([], MockInfo("ko"))
    mock_cls.return_value = mock_instance

    with patch("faster_whisper.WhisperModel", mock_cls):
        yield mock_cls
