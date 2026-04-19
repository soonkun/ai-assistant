# tests/e2e/test_e2e_23_calendar_duplicate.py
"""E2E-23: 동일 (title, start) 중복 INSERT 허용 + 경고 로그.

시나리오 ID: E2E-23-calendar-duplicate
REQUIREMENTS: §4.1 일정 등록 (M_09 §7.1 중복 허용 결정)
관련 모듈: M_05b ToolRouter, M_09 CalendarService
마커: e2e_model (실제 Gemma 필요)
실행 시간 목표: ≤ 40초 (2턴)

수동 체크 지점: Ollama gemma4:e4b 기동 필요.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.e2e_model]

_KST = ZoneInfo("Asia/Seoul")


@pytest.mark.timeout(80)
async def test_e2e_23_calendar_duplicate_direct(
    calendar_service: Any,
    tmp_data_dir: Path,
    caplog: Any,
) -> None:
    """CalendarService.add_event 직접 2회 호출 → 중복 허용 + WARNING 로그.

    e2e_fast 대체: 실제 Gemma 없이 CalendarService 직접 테스트.
    수락 기준:
    - COUNT(*) = 2, 두 id 다름.
    - WARNING 레벨 중복 경고 로그 (Python logging 또는 loguru 둘 다 허용).
    - 크래시 없음.
    """
    import logging

    now_kst = datetime(2026, 4, 21, 10, 0, 0, tzinfo=_KST)

    with caplog.at_level(logging.WARNING):
        # 첫 번째 추가
        ev1 = calendar_service.add_event(
            title="회의",
            start=now_kst,
            duration_minutes=60,
        )

        # 두 번째 중복 추가
        ev2 = calendar_service.add_event(
            title="회의",
            start=now_kst,
            duration_minutes=60,
        )

    # 수락 기준 1: COUNT = 2
    db_path = str(tmp_data_dir / "calendar.db")
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute("SELECT COUNT(*) FROM events WHERE title = ?", ("회의",))
        count = cursor.fetchone()[0]
    finally:
        conn.close()

    assert count == 2, f"중복 허용 후 COUNT = {count} (2여야 함)"

    # 수락 기준 2: 두 id 다름
    assert ev1.id != ev2.id, f"두 이벤트 id가 같음: {ev1.id} == {ev2.id}"

    # 수락 기준 3: WARNING 중복 경고 로그 (Python logging caplog 기반)
    dup_warning = any(
        "중복" in r.message or "duplicate" in r.message.lower()
        for r in caplog.records
        if r.levelno >= logging.WARNING
    )
    assert dup_warning, (
        f"중복 경고 WARNING 로그 없음. caplog records: "
        f"{[(r.levelname, r.message) for r in caplog.records]}"
    )
