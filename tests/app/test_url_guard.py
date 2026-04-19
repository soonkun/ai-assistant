# tests/app/test_url_guard.py
"""is_private_or_loopback / enforce_private_url 단위 테스트."""

import pytest

from app.url_guard import PrivacyViolationError, enforce_private_url, is_private_or_loopback


class TestIsPrivateOrLoopback:
    """N-3: 허용 케이스 전수 + 거부 케이스."""

    # ── 정상 케이스 ──────────────────────────────────────────────────────
    @pytest.mark.parametrize(
        "url",
        [
            "http://127.0.0.1:11434",  # loopback
            "http://localhost",  # localhost 정확히 일치
            "http://localhost:11434",  # localhost + port
            "http://10.0.0.5",  # RFC1918 class A
            "http://172.20.1.1",  # RFC1918 class B
            "http://192.168.0.5",  # RFC1918 class C
            "http://[::1]",  # IPv6 loopback
            "http://[fc00::1]",  # IPv6 ULA
            "http://192.168.219.109:11434",  # 개발 주소
            "ws://127.0.0.1:8080",  # ws 스킴
            "wss://192.168.1.1:443",  # wss 스킴
        ],
    )
    def test_allowed_urls(self, url: str) -> None:
        assert is_private_or_loopback(url) is True

    # ── 엣지 케이스 ──────────────────────────────────────────────────────
    def test_link_local_v4_allowed(self) -> None:
        """169.254.0.0/16 (link-local)은 허용."""
        assert is_private_or_loopback("http://169.254.169.254") is True  # A-2 정책 고정

    def test_link_local_v6_allowed(self) -> None:
        assert is_private_or_loopback("http://[fe80::1]") is True

    # ── 적대적 케이스 ────────────────────────────────────────────────────
    @pytest.mark.parametrize(
        "url",
        [
            "https://api.openai.com",  # A-1
            "http://8.8.8.8:11434",  # A-2
            "http://1.1.1.1",  # A-2
            "http://google.com",  # FQDN → 거부
            "http://0.0.0.0",  # 이 주소도 허용 안 됨
        ],
    )
    def test_blocked_urls(self, url: str) -> None:
        assert is_private_or_loopback(url) is False

    def test_invalid_scheme_blocked(self) -> None:
        assert is_private_or_loopback("ftp://127.0.0.1") is False

    def test_empty_url(self) -> None:
        assert is_private_or_loopback("") is False


class TestEnforcePrivateUrl:
    """enforce_private_url 검증."""

    def test_valid_url_no_exception(self) -> None:
        enforce_private_url("http://127.0.0.1:11434")  # 예외 없음

    def test_public_url_raises(self) -> None:
        with pytest.raises(PrivacyViolationError, match="must be loopback or RFC1918"):
            enforce_private_url("https://api.openai.com")

    def test_invalid_port_raises(self) -> None:
        with pytest.raises(PrivacyViolationError, match="포트 범위"):
            enforce_private_url("http://127.0.0.1:99999")

    def test_custom_field_name_in_message(self) -> None:
        with pytest.raises(PrivacyViolationError) as exc_info:
            enforce_private_url("http://8.8.8.8", field_name="CUSTOM_URL")
        assert "CUSTOM_URL" in str(exc_info.value)

    # ── 엣지 케이스 ──────────────────────────────────────────────────────
    def test_port_boundary_valid_low(self) -> None:
        enforce_private_url("http://127.0.0.1:1")  # 포트 1

    def test_port_boundary_valid_high(self) -> None:
        enforce_private_url("http://192.168.1.1:65535")  # 포트 65535

    def test_no_port_allowed(self) -> None:
        enforce_private_url("http://127.0.0.1")  # 포트 없음 허용

    def test_localhost_allowed(self) -> None:
        enforce_private_url("http://localhost:8080")
