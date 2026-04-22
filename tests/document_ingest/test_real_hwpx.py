# tests/document_ingest/test_real_hwpx.py
"""실제 사내 HWPX 파일 smoke 테스트 (스펙 §12.2 DoD).

@pytest.mark.slow — --run-slow 없이는 skip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from document_ingest.parsers.hwpx import _parse_hwpx

REAL_HWPX_PATH = Path("data/Documents/업무편람/식량원 기술지원과 업무편람(2025).hwpx")


@pytest.mark.slow
def test_real_hwpx_extracts_1000_paragraphs() -> None:
    """실제 사내 HWPX에서 1000단락 이상 추출.

    M_06 DoD §12.2: data/Documents/업무편람/식량원 기술지원과 업무편람(2025).hwpx
    로컬 smoke 테스트에서 ≥ 1000 단락 추출.
    """
    if not REAL_HWPX_PATH.exists():
        pytest.skip(f"실파일 없음: {REAL_HWPX_PATH}")

    segs = _parse_hwpx(str(REAL_HWPX_PATH))
    assert len(segs) >= 1000, f"단락 수 {len(segs)} < 1000. 네임스페이스 확인 필요."
