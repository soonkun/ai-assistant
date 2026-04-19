# src/app/__init__.py
"""M_01 AppCore 공개 API."""

# upstream 의존성이 없는 모듈은 즉시 import
from .config import (
    AppConfig,
    FullConfig,
    HardwareProfile,
    OllamaConfig,
    PathsConfig,
    load_full_config,
)
from .errors import ConfigLoadError, PrivacyViolationError, ServiceInitError
from .logging import init_logging, pii_mask
from .url_guard import enforce_private_url, is_private_or_loopback


# upstream 의존성이 있는 모듈은 lazy import (테스트 환경에서 upstream 없이도 로드 가능)
def __getattr__(name: str) -> object:
    if name == "AppServiceContext":
        from .service_context import AppServiceContext

        return AppServiceContext
    if name == "AppWebSocketHandler":
        from .ws_handler import AppWebSocketHandler

        return AppWebSocketHandler
    if name == "init_app_ws_route":
        from .ws_route import init_app_ws_route

        return init_app_ws_route
    if name == "AppWebSocketServer":
        from .server import AppWebSocketServer

        return AppWebSocketServer
    if name == "create_app":
        from .main import create_app

        return create_app
    if name == "run":
        from .main import run

        return run
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # config
    "AppConfig",
    "FullConfig",
    "HardwareProfile",
    "OllamaConfig",
    "PathsConfig",
    "load_full_config",
    # errors
    "ConfigLoadError",
    "PrivacyViolationError",
    "ServiceInitError",
    # logging
    "init_logging",
    "pii_mask",
    # url_guard
    "enforce_private_url",
    "is_private_or_loopback",
    # lazy-loaded (upstream 의존)
    "AppServiceContext",
    "AppWebSocketHandler",
    "init_app_ws_route",
    "AppWebSocketServer",
    "create_app",
    "run",
]
