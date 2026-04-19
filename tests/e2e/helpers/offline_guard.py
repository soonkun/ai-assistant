# tests/e2e/helpers/offline_guard.py
"""오프라인 가드: 외부 네트워크 차단 유틸.

pytest-socket 기반 + custom getaddrinfo 패치.
허용 호스트: 127.0.0.1, localhost, OLLAMA_BASE_URL 파싱 host.
"""

from __future__ import annotations

import os
import socket
import urllib.parse
from typing import Any


def _get_ollama_host() -> str | None:
    """OLLAMA_BASE_URL 환경변수에서 host만 파싱."""
    url = os.environ.get("OLLAMA_BASE_URL", "")
    if not url:
        return None
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname
    return host


ALLOWED_HOSTS: frozenset[str] = frozenset(
    filter(
        None,
        ["127.0.0.1", "localhost", _get_ollama_host()],
    )
)

_ORIGINAL_GETADDRINFO = socket.getaddrinfo


def _patched_getaddrinfo(
    host: str | bytes | bytearray | None,
    port: Any,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """외부 호스트 resolve 시 RuntimeError 발생."""
    if isinstance(host, (bytes, bytearray)):
        host_str = host.decode("ascii", errors="replace")
    elif host is None:
        host_str = ""
    else:
        host_str = str(host)

    if host_str and host_str not in ALLOWED_HOSTS:
        raise RuntimeError(
            f"offline policy violation: {host_str}:{port} — "
            f"only {sorted(ALLOWED_HOSTS)} are allowed"
        )
    return _ORIGINAL_GETADDRINFO(host, port, *args, **kwargs)


def install_getaddrinfo_patch() -> None:
    """getaddrinfo를 패치해 외부 호스트 resolve 차단."""
    socket.getaddrinfo = _patched_getaddrinfo  # type: ignore[assignment]


def remove_getaddrinfo_patch() -> None:
    """패치 제거."""
    socket.getaddrinfo = _ORIGINAL_GETADDRINFO  # type: ignore[assignment]
