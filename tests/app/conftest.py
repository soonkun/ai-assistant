# tests/app/conftest.py
"""pytest 픽스처: tmp conf.yaml, mock services, TestClient."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# upstream/Open-LLM-VTuber/src를 PYTHONPATH에 추가
_UPSTREAM_SRC = Path(__file__).parent.parent.parent / "upstream" / "Open-LLM-VTuber" / "src"
if str(_UPSTREAM_SRC) not in sys.path:
    sys.path.insert(0, str(_UPSTREAM_SRC))

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def valid_config_path() -> str:
    return str(FIXTURES_DIR / "conf.valid.yaml")


@pytest.fixture
def missing_app_config_path() -> str:
    return str(FIXTURES_DIR / "conf.missing_app.yaml")


@pytest.fixture
def invalid_url_config_path() -> str:
    return str(FIXTURES_DIR / "conf.invalid_url.yaml")


@pytest.fixture
def mock_screenshot_service() -> MagicMock:
    svc = MagicMock()
    svc.capture = AsyncMock(return_value=b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    return svc


@pytest.fixture
def mock_app_service_context(valid_config_path: str) -> MagicMock:
    """upstream import 없이 AppServiceContext를 흉내내는 Mock."""
    ctx = MagicMock()
    ctx.idle_monitor = None
    ctx.proactive_dispatcher = None
    ctx.rag_service = None
    ctx.calendar_service = None
    ctx.screenshot_service = None
    ctx.avatar_state = None
    ctx.app_config = None
    ctx.load_from_config = AsyncMock()
    ctx.load_app_services = AsyncMock()
    ctx.close = AsyncMock()
    return ctx
