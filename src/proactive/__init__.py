# src/proactive/__init__.py
"""ProactiveDispatcher 패키지 공개 심볼.

사용 예:
    from proactive import ProactiveDispatcher, ProactiveTopic, TOPICS
"""

from __future__ import annotations

from proactive.dispatcher import ProactiveDispatcher, SendTextCallback
from proactive.errors import ProactiveError, ProactiveInitError
from proactive.types import TOPICS, ProactiveTopic

__all__ = [
    "ProactiveDispatcher",
    "SendTextCallback",
    "ProactiveError",
    "ProactiveInitError",
    "ProactiveTopic",
    "TOPICS",
]
