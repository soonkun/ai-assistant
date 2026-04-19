# tests/vad/test_wiring.py
"""AppServiceContext wiring tests — N-3, N-4, A-5."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


def _make_tool_router_mock() -> MagicMock:
    """tool_router 모듈 mock — load_app_services 격리용.

    VAD 테스트는 ToolRouter/Screenshot 배선과 무관하므로 완전 격리한다.
    tests/tool_router/__init__.py가 먼저 실행되어 sys.modules["tool_router"]가
    오염된 경우에도 올바른 모듈이 로드되도록 patch.dict로 덮어쓴다.
    """
    mock_tr = MagicMock()

    class _FakeSSInitError(Exception):
        pass

    mock_tr.ScreenshotService = MagicMock(side_effect=_FakeSSInitError("non-Windows"))
    mock_tr.ScreenshotInitError = _FakeSSInitError
    mock_tr.ToolRouter = MagicMock()
    mock_tr.ToolRouterAdapter = MagicMock()
    return mock_tr


class TestN3WiringAfterLoadFromConfig:
    """N-3: AppServiceContext.load_from_config sets vad_engine to SileroVADEngine."""

    # spec: §N-3

    @pytest.mark.asyncio
    async def test_vad_engine_wired_after_load(self, tmp_path: Path) -> None:
        """spec: §N-3 — vad_engine is not None and is VADEngine after load."""
        from open_llm_vtuber.config_manager import read_yaml, validate_config
        from open_llm_vtuber.vad.silero import VADEngine

        from app.config import AppConfig
        from app.service_context import AppServiceContext

        mock_vad_model = MagicMock()
        mock_vad_model.return_value.item.return_value = 0.5

        config_path = Path(__file__).parent.parent / "app" / "fixtures" / "conf.valid.yaml"
        raw = read_yaml(str(config_path))
        config = validate_config(raw)

        assert config.character_config.vad_config.vad_model == "silero_vad"

        ctx = AppServiceContext()

        # CR-03: load_app_services must be called before load_from_config.
        # patch.dict ensures tool_router resolves to a clean mock regardless of
        # cross-test sys.modules pollution from tests/tool_router/__init__.py.
        app_config = AppConfig()
        app_config.paths.calendar_db_path = str(tmp_path / "test.db")
        with patch.dict(sys.modules, {"tool_router": _make_tool_router_mock()}):
            await ctx.load_app_services(app_config)

        async def _noop_agent(*args: Any, **kwargs: Any) -> None:
            return None

        async def _noop_mcp(*args: Any, **kwargs: Any) -> None:
            return None

        with (
            patch("open_llm_vtuber.vad.silero.load_silero_vad", return_value=mock_vad_model),
            patch("open_llm_vtuber.service_context.ServiceContext.init_asr"),
            patch("open_llm_vtuber.service_context.ServiceContext.init_tts"),
            patch(
                "app.service_context.AppServiceContext.init_agent",
                new=_noop_agent,
            ),
            patch("open_llm_vtuber.service_context.ServiceContext.init_translate"),
            patch("open_llm_vtuber.service_context.ServiceContext.init_live2d"),
            patch(
                "open_llm_vtuber.service_context.ServiceContext._init_mcp_components",
                new=_noop_mcp,
            ),
        ):
            await ctx.load_from_config(config)

        assert ctx.vad_engine is not None
        assert type(ctx.vad_engine).__name__ == "VADEngine"
        assert isinstance(ctx.vad_engine, VADEngine)

    @pytest.mark.asyncio
    async def test_vad_engine_smoothing_window(self, tmp_path: Path) -> None:
        """spec: §N-3 — vad_engine.config.smoothing_window == 5 (V1 default)."""
        from open_llm_vtuber.config_manager import read_yaml, validate_config

        from app.config import AppConfig
        from app.service_context import AppServiceContext

        mock_vad_model = MagicMock()
        mock_vad_model.return_value.item.return_value = 0.5

        config_path = Path(__file__).parent.parent / "app" / "fixtures" / "conf.valid.yaml"
        raw = read_yaml(str(config_path))
        config = validate_config(raw)

        ctx = AppServiceContext()

        # CR-03: load_app_services must be called before load_from_config
        app_config = AppConfig()
        app_config.paths.calendar_db_path = str(tmp_path / "test.db")
        with patch.dict(sys.modules, {"tool_router": _make_tool_router_mock()}):
            await ctx.load_app_services(app_config)

        async def _noop_agent(*args: Any, **kwargs: Any) -> None:
            return None

        async def _noop_mcp(*args: Any, **kwargs: Any) -> None:
            return None

        with (
            patch("open_llm_vtuber.vad.silero.load_silero_vad", return_value=mock_vad_model),
            patch("open_llm_vtuber.service_context.ServiceContext.init_asr"),
            patch("open_llm_vtuber.service_context.ServiceContext.init_tts"),
            patch(
                "app.service_context.AppServiceContext.init_agent",
                new=_noop_agent,
            ),
            patch("open_llm_vtuber.service_context.ServiceContext.init_translate"),
            patch("open_llm_vtuber.service_context.ServiceContext.init_live2d"),
            patch(
                "open_llm_vtuber.service_context.ServiceContext._init_mcp_components",
                new=_noop_mcp,
            ),
        ):
            await ctx.load_from_config(config)

        assert ctx.vad_engine is not None
        assert ctx.vad_engine.config.smoothing_window == 5  # type: ignore[union-attr]


class TestN4VadDisabledPath:
    """N-4: vad_model=null → vad_engine is None after load_from_config. WARNING logged."""

    # spec: §N-4

    @pytest.mark.asyncio
    async def test_vad_disabled_engine_is_none(self, tmp_path: Path) -> None:
        """spec: §N-4 — vad_engine is None and at least 1 WARNING about VAD is emitted.

        loguru uses its own sink (not stdlib logging), so we intercept loguru records
        directly via logger.add() with a list sink. caplog does not capture loguru
        output unless an interception handler is explicitly wired.
        """
        from loguru import logger

        from open_llm_vtuber.config_manager import read_yaml, validate_config
        from open_llm_vtuber.config_manager.vad import VADConfig

        from app.config import AppConfig
        from app.service_context import AppServiceContext

        config_path = Path(__file__).parent.parent / "app" / "fixtures" / "conf.valid.yaml"
        raw = read_yaml(str(config_path))
        config = validate_config(raw)

        # Disable VAD
        config.character_config.vad_config = VADConfig(vad_model=None, silero_vad=None)

        ctx = AppServiceContext()

        # CR-03: load_app_services must be called before load_from_config
        app_config = AppConfig()
        app_config.paths.calendar_db_path = str(tmp_path / "test.db")
        with patch.dict(sys.modules, {"tool_router": _make_tool_router_mock()}):
            await ctx.load_app_services(app_config)

        async def _noop_agent(*args: Any, **kwargs: Any) -> None:
            return None

        async def _noop_mcp(*args: Any, **kwargs: Any) -> None:
            return None

        # Intercept loguru records via a list sink
        captured_records: list[dict[str, Any]] = []

        def _list_sink(message: Any) -> None:
            record = message.record
            captured_records.append({"level": record["level"].name, "text": record["message"]})

        handler_id = logger.add(_list_sink, level="WARNING")
        try:
            with (
                patch("open_llm_vtuber.service_context.ServiceContext.init_asr"),
                patch("open_llm_vtuber.service_context.ServiceContext.init_tts"),
                patch(
                    "app.service_context.AppServiceContext.init_agent",
                    new=_noop_agent,
                ),
                patch("open_llm_vtuber.service_context.ServiceContext.init_translate"),
                patch("open_llm_vtuber.service_context.ServiceContext.init_live2d"),
                patch(
                    "open_llm_vtuber.service_context.ServiceContext._init_mcp_components",
                    new=_noop_mcp,
                ),
            ):
                await ctx.load_from_config(config)
        finally:
            logger.remove(handler_id)

        assert ctx.vad_engine is None

        # spec: §N-4 — at least 1 WARNING containing "VAD" or "disabled"
        vad_warnings = [
            r
            for r in captured_records
            if r["level"] == "WARNING"
            and (
                "VAD" in r["text"] or "vad" in r["text"].lower() or "disabled" in r["text"].lower()
            )
        ]
        assert len(vad_warnings) >= 1, (
            f"Expected at least 1 WARNING log about VAD disabled, "
            f"got captured_records: {captured_records}"
        )


class TestA5DuplicateInitVadShortCircuit:
    """A-5: Duplicate init_vad call with same config skips reload (upstream short-circuit)."""

    # spec: §A-5

    @pytest.mark.asyncio
    async def test_a5_duplicate_init_vad_skips_reload(self, tmp_path: Path) -> None:
        """spec: §A-5 — second init_vad with same config does NOT call load_silero_vad again.

        upstream service_context.py init_vad (L347-362):
          if not self.vad_engine or (self.character_config.vad_config != vad_config):
              ... calls VADFactory.get_vad_engine (which calls load_silero_vad)
          else:
              logger.info("VAD already initialized with the same config.")

        After the first load_from_config sets self.vad_engine and
        self.character_config.vad_config, a second init_vad with equal config enters
        the 'else' branch → load_silero_vad is NOT called again.
        mock call_count must be 1.
        """
        from open_llm_vtuber.config_manager import read_yaml, validate_config
        from open_llm_vtuber.config_manager.vad import SileroVADConfig, VADConfig

        from app.config import AppConfig
        from app.service_context import AppServiceContext

        # Two DISTINCT objects with IDENTICAL field values — tests pydantic __eq__ semantics
        vad_config_1 = VADConfig(
            vad_model="silero_vad",
            silero_vad=SileroVADConfig(
                orig_sr=16000,
                target_sr=16000,
                prob_threshold=0.4,
                db_threshold=60,
                required_hits=3,
                required_misses=24,
                smoothing_window=5,
            ),
        )
        vad_config_2 = VADConfig(
            vad_model="silero_vad",
            silero_vad=SileroVADConfig(
                orig_sr=16000,
                target_sr=16000,
                prob_threshold=0.4,
                db_threshold=60,
                required_hits=3,
                required_misses=24,
                smoothing_window=5,
            ),
        )
        # Sanity: they must be equal by pydantic value semantics but different objects
        assert vad_config_1 == vad_config_2, "Both configs must have equal field values"
        assert vad_config_1 is not vad_config_2, "They must be distinct objects"

        # Load config to initialize character_config so init_vad can access it
        config_path = Path(__file__).parent.parent / "app" / "fixtures" / "conf.valid.yaml"
        raw = read_yaml(str(config_path))
        config = validate_config(raw)
        config.character_config.vad_config = vad_config_1

        ctx = AppServiceContext()

        # CR-03: load_app_services must be called before load_from_config
        app_config = AppConfig()
        app_config.paths.calendar_db_path = str(tmp_path / "test.db")
        with patch.dict(sys.modules, {"tool_router": _make_tool_router_mock()}):
            await ctx.load_app_services(app_config)

        async def _noop_agent(*args: Any, **kwargs: Any) -> None:
            return None

        async def _noop_mcp(*args: Any, **kwargs: Any) -> None:
            return None

        mock_model = MagicMock()
        mock_model.return_value.item.return_value = 0.5

        with patch(
            "open_llm_vtuber.vad.silero.load_silero_vad",
            return_value=mock_model,
        ) as mock_load:
            with (
                patch("open_llm_vtuber.service_context.ServiceContext.init_asr"),
                patch("open_llm_vtuber.service_context.ServiceContext.init_tts"),
                patch(
                    "app.service_context.AppServiceContext.init_agent",
                    new=_noop_agent,
                ),
                patch("open_llm_vtuber.service_context.ServiceContext.init_translate"),
                patch("open_llm_vtuber.service_context.ServiceContext.init_live2d"),
                patch(
                    "open_llm_vtuber.service_context.ServiceContext._init_mcp_components",
                    new=_noop_mcp,
                ),
            ):
                # First call via load_from_config — initializes character_config + vad_engine
                await ctx.load_from_config(config)
                assert mock_load.call_count == 1, (
                    f"Expected load_silero_vad to be called once after first load_from_config, "
                    f"got {mock_load.call_count}"
                )

                # Second call with distinct but equal vad_config — upstream short-circuit applies
                ctx.init_vad(vad_config_2)
                assert mock_load.call_count == 1, (
                    f"Expected load_silero_vad to still be called only once after duplicate "
                    f"init_vad with same config (short-circuit at upstream L353), "
                    f"got {mock_load.call_count}"
                )
