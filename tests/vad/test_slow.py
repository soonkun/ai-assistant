# tests/vad/test_slow.py
"""Slow tests — S-1: real load_silero_vad call (CI default: skip)."""

from __future__ import annotations

import importlib.util
import sys

import pytest


def _check_silero_available() -> bool:
    """Return True only if silero_vad is a real installed package (not a MagicMock).

    importlib.util.find_spec raises ValueError when sys.modules["silero_vad"].__spec__
    is None — which is exactly how root conftest.py mocks it. We catch that and
    treat it as "not available".
    """
    mod = sys.modules.get("silero_vad")
    if mod is not None and getattr(mod, "__spec__", None) is None:
        # Mocked package — not a real install
        return False
    try:
        return importlib.util.find_spec("silero_vad") is not None
    except ValueError:
        return False


_silero_available = _check_silero_available()


@pytest.mark.slow
@pytest.mark.skipif(
    not _silero_available,
    reason="Requires real silero-vad package installed",
)
class TestS1RealSileroLoad:
    """S-1: Real load_silero_vad() call — verifies offline-safe model load."""

    def test_real_load_no_network(self) -> None:
        """Instantiate VADEngine with the real silero_vad package.

        Monkey-patches requests and urllib to reject external calls.
        Should succeed if silero-vad>=5.0 is installed (model bundled in wheel).
        """
        import sys
        from unittest.mock import patch

        network_call_count = 0

        def reject_network(*args: object, **kwargs: object) -> None:
            nonlocal network_call_count
            network_call_count += 1
            raise ConnectionError(
                "Network call detected during VAD initialization — offline violation!"
            )

        # Remove mock silero_vad if present so real package is used
        real_silero = sys.modules.pop("silero_vad", None)

        try:
            from open_llm_vtuber.vad.vad_factory import VADFactory

            # Monkey-patch network entry points
            with (
                patch("urllib.request.urlopen", side_effect=reject_network),
                patch("urllib.request.urlretrieve", side_effect=reject_network),
            ):
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

            assert engine is not None
            assert network_call_count == 0, (
                f"Detected {network_call_count} network call(s) during VAD init. "
                "Install silero-vad>=5.0 (model bundled in wheel)."
            )
        finally:
            if real_silero is not None:
                sys.modules["silero_vad"] = real_silero  # type: ignore[assignment]
