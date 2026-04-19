# src/tts/_device.py
"""디바이스 해석 공통 유틸리티."""

from __future__ import annotations

import logging

from .errors import TTSInitError

logger = logging.getLogger(__name__)


def _check_cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except ImportError:
        return False


def resolve_device(device: str) -> str:
    """device 문자열을 실제 사용 디바이스로 해석한다.

    Raises:
        TTSInitError: device="cuda"이지만 CUDA 미가용인 경우.
    """
    if device == "auto":
        resolved = "cuda" if _check_cuda_available() else "cpu"
        logger.info("device=auto resolved to: %s", resolved)
        return resolved
    if device == "cuda":
        if not _check_cuda_available():
            logger.error("cuda requested but not available")
            raise TTSInitError("cuda requested but not available")
        return "cuda"
    return device
