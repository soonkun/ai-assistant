# src/app/logging.py
"""loguru 로깅 초기화 및 PII 마스킹 필터."""

import os
import re
import sys

from loguru import logger

# PII 패턴 (정규식 3종)
_PHONE_RE = re.compile(r"01[0-9]-?\d{3,4}-?\d{4}")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
_SSN_RE = re.compile(r"\d{6}-?[1-4]\d{6}")


def pii_mask(text: str) -> str:
    """PII 마스킹 유틸.

    - 휴대폰: r"01[0-9]-?\\d{3,4}-?\\d{4}" → "01X-XXXX-XXXX"
    - 이메일: r"[\\w.+-]+@[\\w.-]+\\.[A-Za-z]{2,}" → "<email>"
    - 주민등록번호: r"\\d{6}-?[1-4]\\d{6}" → "<ssn>"
    """
    text = _PHONE_RE.sub("01X-XXXX-XXXX", text)
    text = _EMAIL_RE.sub("<email>", text)
    text = _SSN_RE.sub("<ssn>", text)
    return text


def _pii_filter(record: dict) -> bool:  # type: ignore[type-arg]
    """loguru sink 필터: record["message"]에서 PII를 마스킹."""
    record["message"] = pii_mask(record["message"])
    # formatted message도 마스킹 (loguru는 message를 직접 수정해야 함)
    return True


def init_logging(log_dir: str, level: str = "INFO") -> None:
    """loguru sinks 구성.

    - stderr sink (색상 포맷)
    - 파일 sink: {log_dir}/app-YYYY-MM-DD.log, rotation="00:00",
      retention="7 days", compression="zip"
    - PII 마스킹 필터 적용
    """
    os.makedirs(log_dir, exist_ok=True)

    # 기존 핸들러 제거 (중복 등록 방지)
    logger.remove()

    fmt = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> — "
        "<level>{message}</level>"
    )

    # stderr sink
    logger.add(
        sys.stderr,
        level=level,
        format=fmt,
        colorize=True,
        filter=_pii_filter,  # type: ignore[arg-type]
    )

    # 파일 sink (비동기, PII 마스킹)
    log_path = os.path.join(log_dir, "app-{time:YYYY-MM-DD}.log")
    logger.add(
        log_path,
        level=level,
        format=fmt,
        rotation="00:00",
        retention="7 days",
        compression="zip",
        enqueue=True,  # 비동기 쓰기 — 이벤트 루프 블로킹 < 1 ms
        filter=_pii_filter,  # type: ignore[arg-type]
    )

    logger.info(f"로깅 초기화 완료: log_dir={log_dir}, level={level}")
