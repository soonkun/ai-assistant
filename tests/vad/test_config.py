# tests/vad/test_config.py
"""VADConfig schema tests — N-1, E-5, E-6, A-1, A-4."""

from __future__ import annotations

import pytest
import yaml
from pydantic import ValidationError


class TestN1ValidFullConfig:
    """N-1: VADConfig accepts valid 7-key config and parses correctly."""

    # spec: §N-1

    def test_model_validate_from_yaml_snippet(self) -> None:
        """spec: §N-1 — canonical conf.yaml vad_config section parses correctly."""
        """Parse the canonical conf.yaml vad_config section."""
        from open_llm_vtuber.config_manager.vad import VADConfig

        yaml_snippet = """
vad_model: "silero_vad"
silero_vad:
  orig_sr: 16000
  target_sr: 16000
  prob_threshold: 0.4
  db_threshold: 60
  required_hits: 3
  required_misses: 24
  smoothing_window: 5
"""
        data = yaml.safe_load(yaml_snippet)
        parsed = VADConfig.model_validate(data)

        assert parsed.vad_model == "silero_vad"
        assert parsed.silero_vad is not None
        assert parsed.silero_vad.prob_threshold == 0.4
        assert parsed.silero_vad.required_misses == 24
        assert parsed.silero_vad.orig_sr == 16000
        assert parsed.silero_vad.target_sr == 16000
        assert parsed.silero_vad.db_threshold == 60
        assert parsed.silero_vad.required_hits == 3
        assert parsed.silero_vad.smoothing_window == 5

    def test_all_seven_keys_present(self) -> None:
        """All 7 SileroVADConfig fields are accessible after parsing."""
        from open_llm_vtuber.config_manager.vad import SileroVADConfig, VADConfig

        silero = SileroVADConfig(
            orig_sr=16000,
            target_sr=16000,
            prob_threshold=0.4,
            db_threshold=60,
            required_hits=3,
            required_misses=24,
            smoothing_window=5,
        )
        vad_config = VADConfig(vad_model="silero_vad", silero_vad=silero)
        assert vad_config.silero_vad is not None
        dumped = vad_config.silero_vad.model_dump()
        expected_keys = {
            "orig_sr",
            "target_sr",
            "prob_threshold",
            "db_threshold",
            "required_hits",
            "required_misses",
            "smoothing_window",
        }
        assert expected_keys.issubset(dumped.keys())


class TestN2UpstreamDefaults:
    """N-2: VADConfig uses correct upstream defaults when instantiated with no args.

    SileroVADConfig in silero.py has defaults; config_manager/vad.py uses Field(...)
    (required). This test verifies the silero.py SileroVADConfig (not config_manager's)
    has defaults matching the spec.
    """

    def test_silero_py_config_defaults(self) -> None:
        """silero.py SileroVADConfig has the spec-mandated default values."""
        from open_llm_vtuber.vad.silero import SileroVADConfig

        cfg = SileroVADConfig()
        assert cfg.prob_threshold == 0.4
        assert cfg.db_threshold == 60
        assert cfg.required_hits == 3
        assert cfg.required_misses == 24
        assert cfg.smoothing_window == 5
        assert cfg.orig_sr == 16000
        assert cfg.target_sr == 16000


class TestN3YamlRoundTrip:
    """N-3: VADConfig round-trips through YAML serialization."""

    def test_yaml_round_trip(self) -> None:
        """dump → YAML string → load → same values."""
        from open_llm_vtuber.config_manager.vad import SileroVADConfig, VADConfig

        silero = SileroVADConfig(
            orig_sr=16000,
            target_sr=16000,
            prob_threshold=0.4,
            db_threshold=60,
            required_hits=3,
            required_misses=24,
            smoothing_window=5,
        )
        original = VADConfig(vad_model="silero_vad", silero_vad=silero)
        dumped = original.model_dump()

        # Serialize to YAML and back
        yaml_str = yaml.dump(dumped)
        reloaded_dict = yaml.safe_load(yaml_str)
        restored = VADConfig.model_validate(reloaded_dict)

        assert restored.vad_model == original.vad_model
        assert restored.silero_vad is not None
        assert original.silero_vad is not None
        assert restored.silero_vad.prob_threshold == original.silero_vad.prob_threshold
        assert restored.silero_vad.required_misses == original.silero_vad.required_misses
        assert restored.silero_vad.smoothing_window == original.silero_vad.smoothing_window
        assert restored.silero_vad.orig_sr == original.silero_vad.orig_sr


class TestE1PartialKeys:
    """E-1: Partial key dict — SileroVADConfig requires all fields (Field(...)).

    config_manager/vad.py SileroVADConfig uses Field(...) for all 7 keys,
    so partial keys raise ValidationError (all required).
    """

    def test_partial_keys_raises_validation_error(self) -> None:
        """Only prob_threshold provided — ValidationError expected for missing fields."""
        from open_llm_vtuber.config_manager.vad import VADConfig

        with pytest.raises(ValidationError):
            VADConfig.model_validate(
                {
                    "vad_model": "silero_vad",
                    "silero_vad": {"prob_threshold": 0.4},
                }
            )


class TestE2OldKeysNotAccepted:
    """E-2: Old keys threshold / min_silence_duration_ms are NOT in upstream schema."""

    def test_old_keys_are_not_accepted(self) -> None:
        """Old M_01 example YAML keys are not valid SileroVADConfig fields.

        pydantic v2 with model_config extra='ignore' silently drops unknown fields;
        with extra='forbid' it raises. We test that the old keys do NOT map to
        the expected new fields — i.e. prob_threshold remains 0.4 (default) if
        'threshold' is provided instead.
        """
        from open_llm_vtuber.config_manager.vad import VADConfig

        # When providing only old keys (plus the required numeric ones), the
        # config_manager SileroVADConfig will either raise (extra='forbid') or
        # silently ignore the unknown fields.  Either behavior is acceptable as
        # long as the old key names are not treated as valid aliases.
        #
        # We verify: if we provide all required new keys AND old keys, validation
        # succeeds (old keys silently ignored), and the known fields parse correctly.
        data = {
            "vad_model": "silero_vad",
            "silero_vad": {
                "orig_sr": 16000,
                "target_sr": 16000,
                "prob_threshold": 0.4,
                "db_threshold": 60,
                "required_hits": 3,
                "required_misses": 24,
                "smoothing_window": 5,
                # Old keys — should be ignored or raise, not silently accepted as valid
                "threshold": 0.5,
                "min_silence_duration_ms": 700,
            },
        }
        # pydantic v2 default is to ignore extra fields — this should NOT raise
        # The important thing: "threshold" does NOT become prob_threshold
        parsed = VADConfig.model_validate(data)
        assert parsed.silero_vad is not None
        # prob_threshold is set by the explicit key, not hijacked by old key
        assert parsed.silero_vad.prob_threshold == 0.4
        # Verify old keys don't appear as model fields
        dumped = parsed.silero_vad.model_dump()
        assert "threshold" not in dumped
        assert "min_silence_duration_ms" not in dumped


class TestE3BoundaryProbThreshold:
    """E-3: prob_threshold=0.0 and prob_threshold=1.0 boundary values are accepted."""

    def test_prob_threshold_zero(self) -> None:
        from open_llm_vtuber.config_manager.vad import SileroVADConfig

        cfg = SileroVADConfig(
            orig_sr=16000,
            target_sr=16000,
            prob_threshold=0.0,
            db_threshold=60,
            required_hits=3,
            required_misses=24,
            smoothing_window=5,
        )
        assert cfg.prob_threshold == 0.0

    def test_prob_threshold_one(self) -> None:
        from open_llm_vtuber.config_manager.vad import SileroVADConfig

        cfg = SileroVADConfig(
            orig_sr=16000,
            target_sr=16000,
            prob_threshold=1.0,
            db_threshold=60,
            required_hits=3,
            required_misses=24,
            smoothing_window=5,
        )
        assert cfg.prob_threshold == 1.0


class TestA1UnsupportedEngine:
    """A-1: vad_model='webrtc_vad' — unsupported engine → ValidationError."""

    # spec: §A-1

    def test_webrtc_vad_rejected(self) -> None:
        """spec: §A-1 — VADConfig.vad_model is Optional[Literal['silero_vad']] — only silero_vad allowed."""
        from open_llm_vtuber.config_manager.vad import VADConfig

        with pytest.raises(ValidationError):
            VADConfig.model_validate({"vad_model": "webrtc_vad"})


class TestA2EmptyVadConfig:
    """A-2: Completely empty vad config dict → uses all defaults (no crash)."""

    # spec: §A-2 (config schema variant — silero_vad package absence is in test_import.py)

    def test_empty_dict_uses_defaults(self) -> None:
        """VADConfig with empty dict: vad_model=None, silero_vad=None."""
        from open_llm_vtuber.config_manager.vad import VADConfig

        parsed = VADConfig.model_validate({})
        assert parsed.vad_model is None
        assert parsed.silero_vad is None


class TestA4WrongTypeCoercion:
    """A-4: Wrong type injection — orig_sr='16000' (str instead of int).

    spec: §A-4 — pydantic v2 default coercion converts str '16000' to int 16000.
    The process must not die. Document actual behavior here.
    """

    # spec: §A-4

    def test_orig_sr_str_coerced_or_rejected(self) -> None:
        """spec: §A-4 — SileroVADConfig(orig_sr='16000') either coerces to int or raises ValidationError.

        pydantic v2 default (lax mode): coerces str '16000' → int 16000.
        Either behavior is acceptable — this test documents what actually happens
        and asserts the process does NOT crash unexpectedly.
        """
        from open_llm_vtuber.config_manager.vad import SileroVADConfig

        try:
            cfg = SileroVADConfig(
                orig_sr="16000",  # type: ignore[arg-type]  # intentional wrong type
                target_sr=16000,
                prob_threshold=0.4,
                db_threshold=60,
                required_hits=3,
                required_misses=24,
                smoothing_window=5,
            )
            # pydantic v2 coerced str → int: document the coercion
            assert cfg.orig_sr == 16000, (
                f"Expected pydantic to coerce '16000' → 16000, got {cfg.orig_sr!r}"
            )
            assert isinstance(cfg.orig_sr, int), (
                f"Expected orig_sr to be int after coercion, got {type(cfg.orig_sr)}"
            )
        except Exception as exc:
            # pydantic strict mode or ValidationError: also acceptable
            from pydantic import ValidationError as PydanticValidationError

            assert isinstance(exc, PydanticValidationError), (
                f"Expected ValidationError if coercion fails, got {type(exc)}: {exc}"
            )


class TestE5ProbThresholdOutOfRange:
    """E-5: prob_threshold=1.5 — upstream has no range validation → accepted.  # spec: §E-5

    RISK NOTE: upstream config_manager/vad.py does not validate [0.0, 1.0] range.
    This test documents the current (permissive) behavior. When M_01 adds ge/le
    constraints, update this test to expect ValidationError.
    """

    def test_out_of_range_threshold_is_accepted(self) -> None:
        from open_llm_vtuber.config_manager.vad import SileroVADConfig, VADConfig

        silero = SileroVADConfig(
            orig_sr=16000,
            target_sr=16000,
            prob_threshold=1.5,
            db_threshold=60,
            required_hits=3,
            required_misses=24,
            smoothing_window=5,
        )
        cfg = VADConfig(vad_model="silero_vad", silero_vad=silero)
        assert cfg.silero_vad is not None
        assert cfg.silero_vad.prob_threshold == 1.5


class TestE6MissingRequiredKeys:
    """E-6: Missing required fields → ValidationError listing missing fields."""

    # spec: §E-6

    def test_missing_required_fields_raises(self) -> None:
        """spec: §E-6 — ValidationError lists all 6 missing required fields."""
        from open_llm_vtuber.config_manager.vad import VADConfig

        with pytest.raises(ValidationError) as exc_info:
            VADConfig.model_validate(
                {
                    "vad_model": "silero_vad",
                    "silero_vad": {"prob_threshold": 0.4},
                }
            )

        error_str = str(exc_info.value)
        # All 6 missing required fields should be mentioned
        for field in (
            "orig_sr",
            "target_sr",
            "db_threshold",
            "required_hits",
            "required_misses",
            "smoothing_window",
        ):
            assert field in error_str, f"Expected '{field}' in error: {error_str}"
