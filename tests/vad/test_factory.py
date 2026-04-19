# tests/vad/test_factory.py
"""VADFactory tests — N-2, N-5, E-1, E-2, E-3, E-4, A-3, A-4."""

from __future__ import annotations

import threading
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


class TestN2FactoryReturnsVADEngine:
    """N-2: VADFactory.get_vad_engine('silero_vad', **kwargs) returns VADEngine (mock load)."""

    # spec: §N-2

    def test_returns_vad_engine_instance(self) -> None:
        """spec: §N-2 — factory returns VADEngine instance with correct config."""
        from open_llm_vtuber.vad.silero import VADEngine
        from open_llm_vtuber.vad.vad_factory import VADFactory

        mock_model = MagicMock()
        mock_model.return_value.item.return_value = 0.5

        # silero.py does `from silero_vad import load_silero_vad` at module level,
        # so the name is bound inside open_llm_vtuber.vad.silero — patch it there.
        with patch(
            "open_llm_vtuber.vad.silero.load_silero_vad", return_value=mock_model
        ) as mock_load:
            instance = VADFactory.get_vad_engine(
                "silero_vad",
                orig_sr=16000,
                target_sr=16000,
                prob_threshold=0.4,
                db_threshold=60,
                required_hits=3,
                required_misses=24,
                smoothing_window=5,
            )

        assert isinstance(instance, VADEngine)
        assert instance.config.prob_threshold == 0.4
        assert instance.window_size_samples == 512
        mock_load.assert_called_once()

    def test_has_detect_speech_method(self) -> None:
        """N-5: returned instance has callable detect_speech."""
        from open_llm_vtuber.vad.vad_factory import VADFactory

        mock_model = MagicMock()
        mock_model.return_value.item.return_value = 0.5

        with patch("open_llm_vtuber.vad.silero.load_silero_vad", return_value=mock_model):
            instance = VADFactory.get_vad_engine(
                "silero_vad",
                orig_sr=16000,
                target_sr=16000,
                prob_threshold=0.4,
                db_threshold=60,
                required_hits=3,
                required_misses=24,
                smoothing_window=5,
            )

        assert callable(getattr(instance, "detect_speech", None))


class TestN5DetectSpeechGenerator:
    """N-5: detect_speech returns a generator (protocol check only)."""

    # spec: §N-5

    def test_detect_speech_is_generator(self) -> None:
        """spec: §N-5 — detect_speech returns an iterable/generator."""
        from open_llm_vtuber.vad.vad_factory import VADFactory

        mock_model = MagicMock()
        mock_model.return_value.item.return_value = 0.8

        with patch("open_llm_vtuber.vad.silero.load_silero_vad", return_value=mock_model):
            engine = VADFactory.get_vad_engine(
                "silero_vad",
                orig_sr=16000,
                target_sr=16000,
                prob_threshold=0.4,
                db_threshold=60,
                required_hits=3,
                required_misses=24,
                smoothing_window=5,
            )

        audio_data = [0.1] * (512 * 10)
        result = engine.detect_speech(audio_data)
        assert hasattr(result, "__iter__"), "detect_speech should return an iterable"
        # Exhaust the generator — we don't assert specific yield values (upstream logic)
        list(result)


class TestE1NonStandardSampleRate:
    """E-1: target_sr=8000 → window_size_samples=256, no exception, WARNING logged.

    spec: §E-1 — 로그 경고 1건 (target_sr != 16000).
    The WARNING is emitted by AppServiceContext.init_vad (M_01 loader responsibility
    per spec). Test verifies both the engine property and the log warning.
    """

    # spec: §E-1

    def test_8khz_config_creates_engine(self) -> None:
        """spec: §E-1 — window_size_samples=256 for 8 kHz config."""
        from open_llm_vtuber.vad.vad_factory import VADFactory

        mock_model = MagicMock()
        mock_model.return_value.item.return_value = 0.5

        with patch("open_llm_vtuber.vad.silero.load_silero_vad", return_value=mock_model):
            instance = VADFactory.get_vad_engine(
                "silero_vad",
                orig_sr=8000,
                target_sr=8000,
                prob_threshold=0.4,
                db_threshold=60,
                required_hits=3,
                required_misses=24,
                smoothing_window=5,
            )

        # upstream silero.py: 512 if target_sr == 16000 else 256
        assert instance.window_size_samples == 256

    @pytest.mark.asyncio
    async def test_8khz_config_emits_warning_via_app_context(self, tmp_path: Any) -> None:
        """spec: §E-1 — AppServiceContext.init_vad emits WARNING when target_sr != 16000.

        Uses load_from_config to initialize character_config, then calls init_vad
        directly with 8kHz config. loguru WARNING is captured via list sink.
        """
        import sys
        from pathlib import Path

        from loguru import logger

        from open_llm_vtuber.config_manager import read_yaml, validate_config
        from open_llm_vtuber.config_manager.vad import SileroVADConfig, VADConfig

        from app.config import AppConfig
        from app.service_context import AppServiceContext

        silero_cfg_8k = SileroVADConfig(
            orig_sr=8000,
            target_sr=8000,
            prob_threshold=0.4,
            db_threshold=60,
            required_hits=3,
            required_misses=24,
            smoothing_window=5,
        )
        vad_config_8k = VADConfig(vad_model="silero_vad", silero_vad=silero_cfg_8k)

        # Load standard config to initialize character_config
        config_path = Path(__file__).parent.parent / "app" / "fixtures" / "conf.valid.yaml"
        raw = read_yaml(str(config_path))
        config = validate_config(raw)

        ctx = AppServiceContext()

        # CR-03: load_app_services must be called before load_from_config.
        # patch.dict ensures tool_router resolves to a clean mock regardless of
        # cross-test sys.modules pollution from tests/tool_router/__init__.py.
        app_config = AppConfig()
        app_config.paths.calendar_db_path = str(tmp_path / "test.db")
        _mock_tr = MagicMock()

        class _FakeSSInitError(Exception):
            pass

        _mock_tr.ScreenshotService = MagicMock(side_effect=_FakeSSInitError("non-Windows"))
        _mock_tr.ScreenshotInitError = _FakeSSInitError
        _mock_tr.ToolRouter = MagicMock()
        _mock_tr.ToolRouterAdapter = MagicMock()
        with patch.dict(sys.modules, {"tool_router": _mock_tr}):
            await ctx.load_app_services(app_config)

        async def _noop_agent(*args: Any, **kwargs: Any) -> None:
            return None

        async def _noop_mcp(*args: Any, **kwargs: Any) -> None:
            return None

        mock_model = MagicMock()
        mock_model.return_value.item.return_value = 0.5

        # Initialize the context with standard 16k config first
        with (
            patch("open_llm_vtuber.vad.silero.load_silero_vad", return_value=mock_model),
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

        # Now call init_vad directly with 8k config — should emit WARNING via loguru
        captured_records: list[dict[str, Any]] = []

        def _list_sink(message: Any) -> None:
            record = message.record
            captured_records.append({"level": record["level"].name, "text": record["message"]})

        handler_id = logger.add(_list_sink, level="WARNING")
        try:
            with patch("open_llm_vtuber.vad.silero.load_silero_vad", return_value=mock_model):
                ctx.init_vad(vad_config_8k)
        finally:
            logger.remove(handler_id)

        # spec: §E-1 — at least 1 WARNING about non-standard target_sr
        warning_records = [
            r
            for r in captured_records
            if r["level"] == "WARNING"
            and ("target_sr" in r["text"] or "8000" in r["text"] or "16000" in r["text"])
        ]
        assert len(warning_records) >= 1, (
            f"Expected at least 1 WARNING about non-standard target_sr, "
            f"got captured_records: {captured_records}"
        )


class TestE2ShortAudioInput:
    """E-2: Audio input shorter than 512 samples → generator yields nothing."""

    # spec: §E-2

    def test_short_audio_yields_nothing(self) -> None:
        """spec: §E-2 — short audio yields nothing, no exception."""
        from open_llm_vtuber.vad.vad_factory import VADFactory

        mock_model = MagicMock()
        mock_model.return_value.item.return_value = 0.8

        with patch("open_llm_vtuber.vad.silero.load_silero_vad", return_value=mock_model):
            engine = VADFactory.get_vad_engine(
                "silero_vad",
                orig_sr=16000,
                target_sr=16000,
                prob_threshold=0.4,
                db_threshold=60,
                required_hits=3,
                required_misses=24,
                smoothing_window=5,
            )

        # 100 samples < 512 window_size_samples
        results = list(engine.detect_speech([0.0] * 100))
        assert results == []


class TestE3EmptyAudioInput:
    """E-3: Empty list input → generator terminates immediately."""

    # spec: §E-3

    def test_empty_list_yields_nothing(self) -> None:
        """spec: §E-3 — empty list yields nothing, no exception."""
        from open_llm_vtuber.vad.vad_factory import VADFactory

        mock_model = MagicMock()
        mock_model.return_value.item.return_value = 0.8

        with patch("open_llm_vtuber.vad.silero.load_silero_vad", return_value=mock_model):
            engine = VADFactory.get_vad_engine(
                "silero_vad",
                orig_sr=16000,
                target_sr=16000,
                prob_threshold=0.4,
                db_threshold=60,
                required_hits=3,
                required_misses=24,
                smoothing_window=5,
            )

        results = list(engine.detect_speech([]))
        assert results == []


class TestE4ProbThresholdZero:
    """E-4: prob_threshold=0.0 → engine creation succeeds."""

    # spec: §E-4

    def test_zero_threshold_engine_created(self) -> None:
        """spec: §E-4 — prob_threshold=0.0 engine created successfully."""
        from open_llm_vtuber.vad.vad_factory import VADFactory

        mock_model = MagicMock()
        mock_model.return_value.item.return_value = 0.001

        with patch("open_llm_vtuber.vad.silero.load_silero_vad", return_value=mock_model):
            engine = VADFactory.get_vad_engine(
                "silero_vad",
                orig_sr=16000,
                target_sr=16000,
                prob_threshold=0.0,
                db_threshold=60,
                required_hits=3,
                required_misses=24,
                smoothing_window=5,
            )

        assert engine is not None
        assert engine.config.prob_threshold == 0.0


class TestA3ConcurrentInstantiation:
    """A-3: Two concurrent VADFactory calls — both initialize without conflict."""

    # spec: §A-3 (adversarial: concurrent factory calls)

    def test_concurrent_instantiation(self) -> None:
        """spec: §A-3 — concurrent factory instantiation succeeds without conflict."""
        from open_llm_vtuber.vad.silero import VADEngine
        from open_llm_vtuber.vad.vad_factory import VADFactory

        results: list[Any] = []
        errors: list[Exception] = []

        def create_engine() -> None:
            mock_model = MagicMock()
            mock_model.return_value.item.return_value = 0.5
            with patch("open_llm_vtuber.vad.silero.load_silero_vad", return_value=mock_model):
                try:
                    engine = VADFactory.get_vad_engine(
                        "silero_vad",
                        orig_sr=16000,
                        target_sr=16000,
                        prob_threshold=0.4,
                        db_threshold=60,
                        required_hits=3,
                        required_misses=24,
                        smoothing_window=5,
                    )
                    results.append(engine)
                except Exception as exc:
                    errors.append(exc)

        t1 = threading.Thread(target=create_engine)
        t2 = threading.Thread(target=create_engine)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(errors) == 0, f"Errors during concurrent init: {errors}"
        assert len(results) == 2
        assert all(isinstance(e, VADEngine) for e in results)


class TestA4ModelLoadError:
    """A-4: Patched model raises on load → error propagates cleanly."""

    # spec: §A-4 (factory model load error — wrong type coercion is in test_config.py)

    def test_load_error_propagates(self) -> None:
        """spec: §A-4 — model load failure propagates the exception cleanly."""
        from open_llm_vtuber.vad.vad_factory import VADFactory

        def raise_on_load() -> None:
            raise RuntimeError("Model file not found")

        with patch("open_llm_vtuber.vad.silero.load_silero_vad", side_effect=raise_on_load):
            with pytest.raises(RuntimeError, match="Model file not found"):
                VADFactory.get_vad_engine(
                    "silero_vad",
                    orig_sr=16000,
                    target_sr=16000,
                    prob_threshold=0.4,
                    db_threshold=60,
                    required_hits=3,
                    required_misses=24,
                    smoothing_window=5,
                )
