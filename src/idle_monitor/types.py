# src/idle_monitor/types.py
"""IdleMonitor 공개 타입 alias."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Literal

IdleEvent = Literal["idle_rest", "overwork"]
"""유휴 감지 이벤트 Literal."""

IdleEventCallback = Callable[[IdleEvent], Awaitable[None]]
"""이벤트 콜백 시그니처. IdleEvent Literal 외의 페이로드는 전달하지 않는다."""
