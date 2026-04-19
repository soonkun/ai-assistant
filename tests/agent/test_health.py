# tests/agent/test_health.py
"""probe_ollama 헬스체크 테스트."""

from __future__ import annotations

import pytest
import respx
import httpx

from src.agent.health import probe_ollama


LOOPBACK = "http://127.0.0.1:11434"
LOOPBACK_V1 = "http://127.0.0.1:11434/v1"
MODEL = "gemma4:e4b"


@pytest.mark.asyncio
@respx.mock
async def test_probe_success_without_v1_suffix() -> None:
    """정상 케이스: /v1 없는 URL로 probe 성공."""
    respx.get(f"{LOOPBACK}/api/version").mock(
        return_value=httpx.Response(200, json={"version": "0.5.1"})
    )
    respx.get(f"{LOOPBACK}/api/tags").mock(
        return_value=httpx.Response(
            200,
            json={"models": [{"name": MODEL}, {"name": "llama3:8b"}]},
        )
    )

    health = await probe_ollama(LOOPBACK, MODEL)

    assert health.reachable is True
    assert health.model_available is True
    assert health.version == "0.5.1"
    assert health.base_url_normalized == LOOPBACK_V1
    assert health.error is None


@pytest.mark.asyncio
@respx.mock
async def test_probe_success_with_v1_suffix() -> None:
    """정상 케이스: /v1 suffix 있는 URL로 probe 성공 (내부에서 정규화)."""
    respx.get(f"{LOOPBACK}/api/version").mock(
        return_value=httpx.Response(200, json={"version": "0.5.1"})
    )
    respx.get(f"{LOOPBACK}/api/tags").mock(
        return_value=httpx.Response(
            200,
            json={"models": [{"name": MODEL}]},
        )
    )

    health = await probe_ollama(LOOPBACK_V1, MODEL)

    assert health.reachable is True
    assert health.model_available is True
    assert health.base_url_normalized == LOOPBACK_V1


@pytest.mark.asyncio
@respx.mock
async def test_probe_model_not_found() -> None:
    """A-2: 모델 태그 부재 — model_available=False."""
    respx.get(f"{LOOPBACK}/api/version").mock(
        return_value=httpx.Response(200, json={"version": "0.5.0"})
    )
    respx.get(f"{LOOPBACK}/api/tags").mock(
        return_value=httpx.Response(
            200,
            json={"models": [{"name": "llama3:8b"}]},
        )
    )

    health = await probe_ollama(LOOPBACK, MODEL)

    assert health.reachable is True
    assert health.model_available is False
    assert health.error is not None


@pytest.mark.asyncio
@respx.mock
async def test_probe_connection_error() -> None:
    """A-1 일부: 연결 에러 → reachable=False."""
    respx.get(f"{LOOPBACK}/api/version").mock(side_effect=httpx.ConnectError("refused"))

    health = await probe_ollama(LOOPBACK, MODEL)

    assert health.reachable is False
    assert health.model_available is False
    assert health.error is not None


@pytest.mark.asyncio
@respx.mock
async def test_probe_http_error_status() -> None:
    """HTTP 500 응답 → reachable=False."""
    respx.get(f"{LOOPBACK}/api/version").mock(
        return_value=httpx.Response(500, text="Internal Server Error")
    )

    health = await probe_ollama(LOOPBACK, MODEL)

    assert health.reachable is False
    assert health.model_available is False


@pytest.mark.asyncio
@respx.mock
async def test_probe_timeout() -> None:
    """타임아웃 → reachable=False."""
    respx.get(f"{LOOPBACK}/api/version").mock(side_effect=httpx.TimeoutException("timeout"))

    health = await probe_ollama(LOOPBACK, MODEL, timeout_sec=0.1)

    assert health.reachable is False
    assert health.model_available is False


@pytest.mark.asyncio
@respx.mock
async def test_probe_tags_error() -> None:
    """/api/tags 에러 시 reachable=True (version 성공), model_available=False."""
    respx.get(f"{LOOPBACK}/api/version").mock(
        return_value=httpx.Response(200, json={"version": "0.5.0"})
    )
    respx.get(f"{LOOPBACK}/api/tags").mock(side_effect=httpx.ConnectError("refused"))

    health = await probe_ollama(LOOPBACK, MODEL)

    assert health.reachable is True
    assert health.model_available is False
