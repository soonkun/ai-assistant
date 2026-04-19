# src/idle_monitor/__init__.py
"""IdleMonitor 패키지 공개 심볼.

사용 예:
    from idle_monitor import IdleMonitor, IdleEvent, IdleEventCallback
"""

from __future__ import annotations

from idle_monitor.errors import BackendInitError, IdleMonitorError
from idle_monitor.service import IdleMonitor
from idle_monitor.types import IdleEvent, IdleEventCallback

__all__ = [
    "IdleMonitor",
    "IdleEvent",
    "IdleEventCallback",
    "IdleMonitorError",
    "BackendInitError",
]
