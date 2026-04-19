# tests/e2e/conftest.py
"""E2E 공통 pytest 픽스처.

E2E_SCENARIOS §4 11종 픽스처 정책 구현.
모든 E2E 테스트는 이 conftest를 통해 격리된 환경에서 실행된다.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import pytest
from loguru import logger

# upstream src 경로 보장
_UPSTREAM_SRC = Path(__file__).parent.parent.parent / "upstream" / "Open-LLM-VTuber" / "src"
if str(_UPSTREAM_SRC) not in sys.path:
    sys.path.insert(0, str(_UPSTREAM_SRC))

from tests.e2e.helpers.ws_client import FrameCollector  # noqa: E402

# ── 환경 설정 ─────────────────────────────────────────────────────────────
os.environ.setdefault("TZ", "Asia/Seoul")
_KST = ZoneInfo("Asia/Seoul")
_E2E_FIXTURES = Path(__file__).parent / "fixtures"


# ============================================================================
# 오프라인 가드 (autouse=True, session scope)
# ============================================================================


@pytest.fixture(scope="session", autouse=True)
def offline_guard() -> "pytest.Generator[None, None, None]":
    """외부 네트워크 차단 (getaddrinfo 패치).

    허용 호스트: 127.0.0.1, localhost, OLLAMA_BASE_URL 파싱 host.
    E2E_SCENARIOS §1.3 오프라인 보장.
    """
    from tests.e2e.helpers.offline_guard import (
        install_getaddrinfo_patch,
        remove_getaddrinfo_patch,
    )

    install_getaddrinfo_patch()
    yield
    remove_getaddrinfo_patch()


# ============================================================================
# Ollama 가용성 체크 (session scope)
# ============================================================================


def _check_ollama_available() -> bool:
    """Ollama health check. GET /api/tags 응답 여부만 확인."""
    import urllib.parse
    import urllib.request

    base_url = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    health_url = base_url.rstrip("/") + "/api/tags"
    try:
        with urllib.request.urlopen(health_url, timeout=3) as resp:  # noqa: S310
            return resp.status == 200
    except Exception:
        return False


@pytest.fixture(scope="session")
def ollama_available() -> bool:
    """Ollama 가용 여부를 session scope으로 캐싱."""
    return _check_ollama_available()


# ============================================================================
# tmp_data_dir (function scope)
# ============================================================================


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    """각 테스트마다 격리된 임시 데이터 루트.

    하위 디렉토리: vector_store/, logs/, cache/
    """
    for sub in ("vector_store", "logs", "cache", "speaker_refs"):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
    return tmp_path


# ============================================================================
# app_config (function scope)
# ============================================================================


@pytest.fixture
def app_config(tmp_data_dir: Path) -> Any:
    """테스트용 AppConfig 인스턴스.

    tmp_data_dir 경로로 DB/로그/캐시 경로를 오버라이드.
    """
    from app.config import AppConfig, OllamaConfig, PathsConfig

    ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    # E2E 테스트는 메모리 여유를 위해 e2b를 기본으로 사용 (WSL+Ollama 동시 구동 안정성).
    # REQUIREMENTS §8은 e4b 확정이며 프로덕션 기본값은 src/app/config.py에 그대로 유지된다.
    # OLLAMA_MODEL=gemma4:e4b 로 override 가능.
    ollama_model = os.environ.get("OLLAMA_MODEL", "gemma4:e2b")
    return AppConfig(
        paths=PathsConfig(
            data_dir=str(tmp_data_dir),
            vector_store_dir=str(tmp_data_dir / "vector_store"),
            calendar_db_path=str(tmp_data_dir / "calendar.db"),
            chat_history_dir=str(tmp_data_dir / "chat_history"),
            log_dir=str(tmp_data_dir / "logs"),
            assets_dir="assets",
        ),
        ollama=OllamaConfig(base_url=ollama_url, model=ollama_model),
        morning_briefing_time="09:00",
        dnd_enabled=False,
    )


# ============================================================================
# fake_service_context (function scope)
# 실제 모델 없이 동작하는 경량 서비스 컨텍스트
# ============================================================================


@pytest.fixture
def fake_service_context(tmp_data_dir: Path, app_config: Any) -> Any:
    """모델 없이 동작하는 AppServiceContext (mock 기반).

    실제 ASR/TTS/LLM은 mock으로 대체.
    calendar_service, avatar_state, idle_monitor, proactive_dispatcher는 실제 인스턴스.
    """

    ctx = MagicMock()
    ctx.app_config = app_config
    ctx._active_ws = None
    ctx.rag_service = None
    ctx.screenshot_service = None
    ctx.tool_router = None
    ctx.tool_router_adapter = None

    # CalendarService 실제 인스턴스
    from calendar_service.service import CalendarService

    calendar_db = str(tmp_data_dir / "calendar.db")
    ctx.calendar_service = CalendarService(calendar_db)

    # AvatarState 실제 인스턴스
    from avatar_state import AvatarState

    ctx.avatar_state = AvatarState(default="neutral")

    # IdleMonitor (NoopBackend)
    from idle_monitor import IdleMonitor
    from idle_monitor.backends.noop_backend import NoopBackend

    ctx.idle_monitor = IdleMonitor(backend=NoopBackend())

    # upstream mock (agent_engine, tts_engine, vad_engine, asr_engine 등)
    ctx.agent_engine = MagicMock()
    ctx.tts_engine = None
    ctx.vad_engine = None
    ctx.asr_engine = None
    ctx.system_prompt = ""
    ctx.character_config = MagicMock()
    ctx.client_contexts = {}
    ctx.tool_manager = None
    ctx.tool_executor = None

    # close mock
    ctx.close = AsyncMock()
    ctx.load_from_config = AsyncMock()

    return ctx


# ============================================================================
# frame_collector (function scope)
# ============================================================================


@pytest.fixture
def frame_collector() -> FrameCollector:
    """WebSocket 프레임 수집기."""
    return FrameCollector()


# ============================================================================
# frozen_clock (function scope)
# ============================================================================


@pytest.fixture
def frozen_clock() -> Any:
    """테스트용 고정 시계 (FakeClock). 시각 주입 용도."""
    from tests.proactive.fakes import FakeClock

    return FakeClock(initial=datetime(2026, 4, 20, 9, 0, 0, tzinfo=ZoneInfo("Asia/Seoul")))


# ============================================================================
# calendar_service (function scope) — 편의 픽스처
# ============================================================================


@pytest.fixture
def calendar_service(tmp_data_dir: Path) -> Any:
    """격리된 CalendarService 인스턴스."""
    from calendar_service.service import CalendarService

    return CalendarService(str(tmp_data_dir / "calendar.db"))


# ============================================================================
# fake_proactive_dispatcher (function scope)
# ============================================================================


@pytest.fixture
def fake_idle_monitor() -> Any:
    """FakeIdleMonitor 인스턴스."""
    from tests.proactive.fakes import FakeIdleMonitor

    return FakeIdleMonitor()


@pytest.fixture
def fake_send_text_collector() -> tuple[list[dict[str, Any]], Any]:
    """(frames, send_text_callback) 튜플. frames 리스트에 송신된 페이로드 수집."""
    frames: list[dict[str, Any]] = []

    async def _collect(payload: dict[str, Any]) -> None:
        frames.append(payload)

    return frames, _collect


# ============================================================================
# proactive_dispatcher (function scope) — FakeScheduler 기반
# ============================================================================


@pytest.fixture
def fake_proactive_dispatcher(
    calendar_service: Any,
    fake_idle_monitor: Any,
    fake_send_text_collector: tuple[list[dict[str, Any]], Any],
) -> Any:
    """FakeScheduler 기반 ProactiveDispatcher."""
    from proactive import ProactiveDispatcher
    from tests.proactive.fakes import FakeScheduler

    frames, send_text = fake_send_text_collector
    scheduler = FakeScheduler()
    return ProactiveDispatcher(
        calendar=calendar_service,
        idle_monitor=fake_idle_monitor,
        send_text=send_text,
        morning_time="09:00",
        cooldown_min=30,
        dnd_enabled=False,
        scheduler=scheduler,
    )


# ============================================================================
# artifacts hook (conftest-level)
# ============================================================================


def _get_artifacts_dir(item: Any) -> Path:
    scenario_id = item.nodeid.replace("/", "_").replace("::", "_")
    artifacts = Path(__file__).parent / "artifacts" / scenario_id
    artifacts.mkdir(parents=True, exist_ok=True)
    return artifacts


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item: Any, call: Any) -> Any:
    """실패한 E2E 테스트의 아티팩트(프레임 덤프)를 artifacts/ 에 저장."""
    outcome = yield
    report = outcome.get_result()

    if report.when == "call" and report.failed:
        artifacts_dir = _get_artifacts_dir(item)
        # frame_collector 픽스처가 있으면 덤프
        collector: FrameCollector | None = item.funcargs.get("frame_collector")
        if collector is not None:
            dump_path = artifacts_dir / "ws_frames.json"
            try:
                dump_path.write_text(
                    json.dumps(collector.all_frames(), indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            except Exception as exc:
                logger.warning(f"artifacts dump 실패: {exc}")
