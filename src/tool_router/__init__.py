# src/tool_router/__init__.py
"""M_05b ToolRouter — 로컬 파이썬 핸들러 디스패처."""

from .errors import (
    AgentProtocolError,
    ScreenshotCaptureError,
    ScreenshotInitError,
    ToolRouterError,
)
from .router import ToolRouter
from .screenshot import ScreenshotService, SendTextCallback
from .types import ToolErrorCode, ToolResult, ToolSpec
from .upstream_adapter import CompositeToolExecutor, ToolRouterAdapter

__all__ = [
    "ToolRouterError",
    "ScreenshotInitError",
    "ScreenshotCaptureError",
    "AgentProtocolError",
    "ToolSpec",
    "ToolResult",
    "ToolErrorCode",
    "ToolRouter",
    "ScreenshotService",
    "SendTextCallback",
    "ToolRouterAdapter",
    "CompositeToolExecutor",
]
