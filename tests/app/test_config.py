# tests/app/test_config.py
"""load_full_config / AppConfig validation 테스트."""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.config import AppConfig, HardwareProfile, load_full_config


class TestLoadFullConfig:
    """N-1, N-2, E-1, E-2, A-1, A-2 케이스."""

    # ── N-1: 기본 YAML 로딩 ───────────────────────────────────────────
    def test_n1_load_valid_config(self, valid_config_path: str) -> None:
        config = load_full_config(valid_config_path)
        assert config.app.profile == HardwareProfile.MIN
        assert config.app.ollama.base_url == "http://127.0.0.1:11434"
        assert config.upstream is not None

    # ── N-2: 환경변수 오버라이드 ─────────────────────────────────────
    def test_n2_env_override_ollama_url(self, valid_config_path: str) -> None:
        override_url = "http://192.168.1.10:11434"
        with patch.dict(os.environ, {"OLLAMA_BASE_URL": override_url}):
            config = load_full_config(valid_config_path)
        assert config.app.ollama.base_url == override_url
        # upstream llm_configs도 오버라이드되어야 함
        try:
            upstream_url = (
                config.upstream.character_config.agent_config.llm_configs.ollama_llm.base_url
            )
            assert upstream_url == override_url
        except AttributeError:
            pass  # upstream 구조가 없을 경우 패스

    # ── E-1: app 일부 필드 누락 → 기본값으로 채워짐 ─────────────────
    def test_e1_missing_app_fields_use_defaults(self, missing_app_config_path: str) -> None:
        config = load_full_config(missing_app_config_path)
        # idle_threshold_min은 10 (YAML 명시값)
        assert config.app.idle_threshold_min == 10
        # 나머지는 기본값
        assert config.app.ollama.base_url == "http://127.0.0.1:11434"
        assert config.app.paths.data_dir == "data"

    # ── E-2: morning_briefing_time 포맷 ─────────────────────────────
    def test_e2_briefing_time_zero_padding_normalized(self) -> None:
        cfg = AppConfig(morning_briefing_time="9:5")  # type: ignore[call-arg]
        assert cfg.morning_briefing_time == "09:05"

    def test_e2_briefing_time_invalid_raises(self) -> None:
        with pytest.raises(ValidationError):
            AppConfig(morning_briefing_time="25:00")  # type: ignore[call-arg]

    def test_e2_briefing_time_invalid_minutes(self) -> None:
        with pytest.raises(ValidationError):
            AppConfig(morning_briefing_time="12:60")  # type: ignore[call-arg]

    # ── FileNotFoundError 전파 ──────────────────────────────────────
    def test_file_not_found_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_full_config("/nonexistent/path/conf.yaml")


class TestAppConfig:
    """AppConfig 기본값 및 검증 테스트."""

    def test_defaults(self) -> None:
        cfg = AppConfig()  # type: ignore[call-arg]
        assert cfg.profile == HardwareProfile.MIN
        assert cfg.ollama.base_url == "http://127.0.0.1:11434"
        assert cfg.paths.data_dir == "data"
        assert cfg.idle_threshold_min == 45
        assert cfg.rag_min_score == 0.35

    def test_idle_threshold_boundary(self) -> None:
        cfg = AppConfig(idle_threshold_min=1)  # type: ignore[call-arg]
        assert cfg.idle_threshold_min == 1
        with pytest.raises(ValidationError):
            AppConfig(idle_threshold_min=0)  # type: ignore[call-arg]

    def test_rag_min_score_boundary(self) -> None:
        cfg = AppConfig(rag_min_score=0.0)  # type: ignore[call-arg]
        assert cfg.rag_min_score == 0.0
        with pytest.raises(ValidationError):
            AppConfig(rag_min_score=1.1)  # type: ignore[call-arg]

    def test_screenshot_interval_boundary(self) -> None:
        with pytest.raises(ValidationError):
            AppConfig(screenshot_continuous_interval_sec=61)  # type: ignore[call-arg]

    def test_briefing_time_default(self) -> None:
        cfg = AppConfig()  # type: ignore[call-arg]
        assert cfg.morning_briefing_time == "09:00"
