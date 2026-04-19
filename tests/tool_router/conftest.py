# tests/tool_router/conftest.py
"""공용 fixture — mock CalendarService/RagService, FakeScreenshotService, router, adapter."""

from datetime import datetime
from typing import Any
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from src.tool_router.router import ToolRouter
from src.tool_router.upstream_adapter import ToolRouterAdapter

from .fakes import (
    FakeCalendarService,
    FakeEvent,
    FakeRetrievalResult,
    FakeSearchHit,
)

KST = ZoneInfo("Asia/Seoul")


# ------------------------------------------------------------------ #
# FakeScreenshotService
# ------------------------------------------------------------------ #


class FakeScreenshotService:
    """테스트용 ScreenshotService 대역. 실제 mss/Windows API를 호출하지 않는다."""

    def __init__(
        self,
        capture_result: str = "data:image/png;base64,ABC123",
        raise_on_capture: Exception | None = None,
        continuous_running: bool = False,
    ) -> None:
        self._capture_result = capture_result
        self._raise_on_capture = raise_on_capture
        self._continuous_running = continuous_running
        self.capture_once_calls: int = 0
        self.start_continuous_calls: list[dict[str, Any]] = []
        self.stop_continuous_calls: int = 0
        self.send_text_calls: list[dict[str, Any]] = []
        self._send_text: Any = None

    async def capture_once(self) -> str:
        self.capture_once_calls += 1
        if self._raise_on_capture is not None:
            raise self._raise_on_capture
        return self._capture_result

    async def start_continuous(
        self,
        interval_seconds: float,
        on_frame: Any = None,
    ) -> None:
        self.start_continuous_calls.append(
            {"interval_seconds": interval_seconds, "on_frame": on_frame}
        )
        # privacy_warning 발행
        warning: dict[str, Any] = {
            "type": "privacy_warning",
            "text": "연속 화면 공유를 시작합니다. 개인정보가 포함될 수 있으니 필요 시 '화면 공유 중지'라고 말씀해 주세요.",
            "interval_seconds": interval_seconds,
        }
        if self._send_text is not None:
            await self._send_text(warning)
            self.send_text_calls.append(warning)
        self._continuous_running = True

    async def stop_continuous(self) -> None:
        self.stop_continuous_calls += 1
        self._continuous_running = False

    @property
    def is_continuous_running(self) -> bool:
        return self._continuous_running

    async def aclose(self) -> None:
        await self.stop_continuous()


# ------------------------------------------------------------------ #
# Fixtures
# ------------------------------------------------------------------ #


@pytest.fixture
def fake_calendar() -> FakeCalendarService:
    event = FakeEvent(
        id=42,
        title="회의",
        start=datetime(2026, 4, 20, 15, 0, tzinfo=KST),
        duration_minutes=60,
        description=None,
    )
    svc = FakeCalendarService(events=[event])
    return svc


@pytest.fixture
def mock_calendar() -> MagicMock:
    """MagicMock CalendarService."""
    m = MagicMock()
    event = FakeEvent(
        id=42,
        title="회의",
        start=datetime(2026, 4, 20, 15, 0, tzinfo=KST),
        duration_minutes=60,
        description=None,
    )
    m.add_event.return_value = event
    m.get_events.return_value = []
    return m


@pytest.fixture
def mock_rag() -> MagicMock:
    """MagicMock RagService."""
    m = MagicMock()
    hit = FakeSearchHit(
        doc_name="예산지침.pdf",
        page=12,
        section="예산 승인 절차",
        chunk_id="chunk-001",
        text="예산 승인은 팀장 결재 후 진행됩니다.",
        score=0.72,
    )
    result = FakeRetrievalResult(hits=[hit], found=True)
    m.retrieve.return_value = result
    m.format_citation.return_value = "`예산지침.pdf` 12페이지, '예산 승인 절차' 섹션"
    return m


@pytest.fixture
def fake_screenshot() -> FakeScreenshotService:
    return FakeScreenshotService()


@pytest.fixture
def router(
    mock_calendar: MagicMock, mock_rag: MagicMock, fake_screenshot: FakeScreenshotService
) -> ToolRouter:
    return ToolRouter(
        calendar=mock_calendar,
        rag=mock_rag,
        screenshot=fake_screenshot,
    )


@pytest.fixture
def adapter(router: ToolRouter) -> ToolRouterAdapter:
    return ToolRouterAdapter(router)


@pytest.fixture
def router_no_calendar(mock_rag: MagicMock, fake_screenshot: FakeScreenshotService) -> ToolRouter:
    return ToolRouter(calendar=None, rag=mock_rag, screenshot=fake_screenshot)


@pytest.fixture
def router_no_rag(mock_calendar: MagicMock, fake_screenshot: FakeScreenshotService) -> ToolRouter:
    return ToolRouter(calendar=mock_calendar, rag=None, screenshot=fake_screenshot)
