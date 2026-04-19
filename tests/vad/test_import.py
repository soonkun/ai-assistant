# tests/vad/test_import.py
"""Import error tests — A-2: silero_vad package missing → ImportError."""

from __future__ import annotations

import importlib
import sys


class TestA2SileroVadImportError:
    """A-2: When silero_vad package is absent, importing VADEngine raises ImportError.

    Uses the Python sentinel mechanism: setting sys.modules["silero_vad"] = None
    tells the import machinery that the module does not exist, causing any
    `import silero_vad` or `from silero_vad import ...` to raise ImportError.
    This is deterministic regardless of whether silero-vad is installed or not.
    """

    # spec: §A-2

    def test_import_error_when_silero_vad_missing(self) -> None:
        """spec: §A-2 — ImportError is raised when silero_vad package is absent.

        Mechanism: sys.modules["silero_vad"] = None is the standard Python
        sentinel that makes `from silero_vad import ...` raise ImportError.
        upstream silero.py line 9: `from silero_vad import load_silero_vad`
        is a module-level import, so reloading the module will trigger it.
        """
        silero_vad_key = "silero_vad"
        silero_module_key = "open_llm_vtuber.vad.silero"

        # Save original state
        saved_silero_vad = sys.modules.get(silero_vad_key, _SENTINEL)
        saved_silero_module = sys.modules.get(silero_module_key, _SENTINEL)

        try:
            # Set silero_vad sentinel: Python's "this module does not exist" marker
            sys.modules[silero_vad_key] = None  # type: ignore[assignment]

            # Remove cached silero module so it will be re-imported
            sys.modules.pop(silero_module_key, None)

            # Attempting to import open_llm_vtuber.vad.silero must raise ImportError
            # because silero.py does `from silero_vad import load_silero_vad` at top level
            import_error_raised = False
            try:
                import open_llm_vtuber.vad.silero  # noqa: F401

                # If the module was already cached before our pop, force a reload
                importlib.reload(open_llm_vtuber.vad.silero)
            except ImportError:
                import_error_raised = True

            assert import_error_raised, (
                "Expected ImportError when silero_vad sentinel (None) is in sys.modules, "
                "but no ImportError was raised. "
                "Check that upstream silero.py still imports from silero_vad at module level."
            )
        finally:
            # Restore original sys.modules state
            if saved_silero_vad is _SENTINEL:
                sys.modules.pop(silero_vad_key, None)
            else:
                sys.modules[silero_vad_key] = saved_silero_vad  # type: ignore[assignment]

            if saved_silero_module is _SENTINEL:
                sys.modules.pop(silero_module_key, None)
            else:
                sys.modules[silero_module_key] = saved_silero_module  # type: ignore[assignment]


# Sentinel object to distinguish "key not in sys.modules" from "key maps to None"
_SENTINEL = object()
