# src/agent/health.py
"""Ollama 헬스체크 — probe_ollama, OllamaHealth."""

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OllamaHealth:
    """Ollama 헬스체크 결과."""

    reachable: bool
    version: str | None  # /api/version 결과 or None
    model_available: bool  # /api/tags에 model이 포함되어 있는가
    base_url_normalized: str  # "/v1" suffix 포함
    error: str | None  # 실패 시 사람 읽을 수 있는 이유


def _normalize_base_url(base_url: str) -> tuple[str, str]:
    """base_url을 정규화해서 (api_root, openai_root) 반환.

    - api_root: Ollama 네이티브 API 루트 (/api/version, /api/tags 등)
    - openai_root: OpenAI 호환 경로 루트 (항상 /v1 suffix 포함)
    """
    url = base_url.rstrip("/")
    if url.endswith("/v1"):
        api_root = url[: -len("/v1")]
    else:
        api_root = url
    openai_root = api_root + "/v1"
    return api_root, openai_root


async def probe_ollama(
    base_url: str,
    model: str,
    timeout_sec: float = 3.0,
) -> OllamaHealth:
    """httpx.AsyncClient로 GET {base_url}/api/version, {base_url}/api/tags 호출.

    base_url은 "http://host:port" 또는 "http://host:port/v1" 둘 다 수용. "/v1"은
    OpenAI 경로에 필요하나 /api/*는 Ollama 네이티브 경로이므로 원본 루트로 접근한다.

    실패 조건:
      - 타임아웃, ConnectionError → reachable=False
      - HTTP 상태 != 200 → reachable=False
      - /api/tags 응답에 model 태그 부재 → model_available=False

    Raises: 자체 예외 없음. 모든 실패는 OllamaHealth로 반환.
    """
    api_root, openai_root = _normalize_base_url(base_url)

    version: str | None = None
    model_available = False
    error: str | None = None

    try:
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            # /api/version 호출
            try:
                resp = await client.get(f"{api_root}/api/version")
                if resp.status_code == 200:
                    data = resp.json()
                    version = data.get("version")
                    logger.debug(f"Ollama version: {version}")
                else:
                    error = f"HTTP {resp.status_code} from /api/version"
                    logger.warning(error)
                    return OllamaHealth(
                        reachable=False,
                        version=None,
                        model_available=False,
                        base_url_normalized=openai_root,
                        error=error,
                    )
            except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as e:
                error = f"Connection error on /api/version: {e}"
                logger.warning(error)
                return OllamaHealth(
                    reachable=False,
                    version=None,
                    model_available=False,
                    base_url_normalized=openai_root,
                    error=error,
                )

            # /api/tags 호출
            try:
                resp = await client.get(f"{api_root}/api/tags")
                if resp.status_code == 200:
                    data = resp.json()
                    models_list = data.get("models", [])
                    available_names = [m.get("name", "") for m in models_list]
                    # 정확한 태그 매칭
                    model_available = model in available_names
                    logger.debug(
                        f"Available models: {available_names}, looking for: {model}, found: {model_available}"
                    )
                else:
                    error = f"HTTP {resp.status_code} from /api/tags"
                    logger.warning(error)
                    return OllamaHealth(
                        reachable=True,
                        version=version,
                        model_available=False,
                        base_url_normalized=openai_root,
                        error=error,
                    )
            except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as e:
                error = f"Connection error on /api/tags: {e}"
                logger.warning(error)
                return OllamaHealth(
                    reachable=True,
                    version=version,
                    model_available=False,
                    base_url_normalized=openai_root,
                    error=error,
                )

    except Exception as e:
        error = f"Unexpected error during probe: {e}"
        logger.error(error)
        return OllamaHealth(
            reachable=False,
            version=None,
            model_available=False,
            base_url_normalized=openai_root,
            error=error,
        )

    return OllamaHealth(
        reachable=True,
        version=version,
        model_available=model_available,
        base_url_normalized=openai_root,
        error=None if model_available else f"Model '{model}' not found in Ollama",
    )
