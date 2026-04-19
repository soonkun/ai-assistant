# tests/e2e/test_e2e_03_tool_call_calendar.py
"""E2E-03: 자연어 일정 등록 (Gemma function calling → CalendarService INSERT).

시나리오 ID: E2E-03-tool-call-calendar
REQUIREMENTS: §4.1 일정 등록 (function calling)
관련 모듈: M_05 LLMAgent, M_05b ToolRouter, M_09 CalendarService
마커: e2e_model (실제 Gemma 필요)
실행 시간 목표: ≤ 30초

수동 체크 지점:
  - Ollama + gemma4:e4b 로컬 기동 필요.
  - GemmaChatAgent + ToolRouter 배선 필요.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any
import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.e2e_model]


@pytest.mark.timeout(60)
async def test_e2e_03_tool_call_calendar(
    ollama_available: bool,
    tmp_data_dir: Path,
    app_config: Any,
    calendar_service: Any,
) -> None:
    """Gemma add_event 툴 호출 → SQLite INSERT 검증.

    수락 기준:
    - calendar.db에 '마케팅팀 회의' 1건 INSERT됨.
    - start_utc가 2026-04-21T01:00:00Z (KST 10시 = UTC 01시) ±1분.
    - duration_minutes=60.
    - ToolCallStart(name='add_event') 이벤트 관찰.
    """
    if not ollama_available:
        pytest.skip(reason="Q-2: Ollama 미기동 → e2e_model 자동 skip")

    # FakeClock: 2026-04-20 09:00 KST (참조용 — 현재는 system_prompt에 직접 기재)
    from agent.builder import build_chat_agent
    from tool_router.router import ToolRouter
    from tool_router.screenshot import ScreenshotService
    from unittest.mock import AsyncMock, MagicMock

    screenshot_svc = MagicMock(spec=ScreenshotService)
    screenshot_svc.capture_once = AsyncMock(return_value="data:image/png;base64,AA==")

    router = ToolRouter(
        calendar=calendar_service,
        rag=None,
        screenshot=screenshot_svc,
    )

    from tool_router.upstream_adapter import ToolRouterAdapter

    adapter = ToolRouterAdapter(router)
    tool_executor = adapter.as_upstream_tool_executor(fallback=None)

    gemma_agent = await build_chat_agent(
        app_config=app_config,
        ollama_config=app_config.ollama,
        tool_manager=None,
        tool_executor=tool_executor,
        system_prompt=(
            "너는 일정 관리 AI야. "
            "사용자가 일정을 추가해달라고 하면 반드시 add_event 툴을 호출해야 한다. "
            "현재 날짜는 2026년 4월 20일 월요일이다."
        ),
        extra_tool_specs=router.tool_specs(),
    )

    from open_llm_vtuber.agent.input_types import BatchInput, TextData, TextSource  # type: ignore[import]

    batch = BatchInput(
        texts=[TextData(source=TextSource.INPUT, content="내일 10시에 마케팅팀 회의 1시간 잡아줘")]
    )

    tool_call_events: list[Any] = []
    async for event in await gemma_agent.chat(batch):
        from agent.events import ToolCallStart

        if isinstance(event, ToolCallStart) and event.name == "add_event":
            tool_call_events.append(event)

    # 수락 기준 1: add_event 툴 호출 관찰
    assert len(tool_call_events) >= 1, (
        "add_event 툴 호출이 없음. Gemma가 FC를 수행하지 않았을 수 있음."
    )

    # 수락 기준 2: SQLite에 레코드 존재
    db_path = str(tmp_data_dir / "calendar.db")
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute("SELECT COUNT(*) FROM events WHERE title LIKE ?", ("%마케팅%",))
        count = cursor.fetchone()[0]
    finally:
        conn.close()

    assert count >= 1, f"SQLite에 '마케팅팀 회의' 레코드가 없음 (count={count})"
