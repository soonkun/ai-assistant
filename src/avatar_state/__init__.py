# src/avatar_state/__init__.py
"""AvatarState 패키지 공개 심볼.

사용 예:
    from avatar_state import AvatarState, AvatarEvent, Emotion
"""

from __future__ import annotations

from .service import AvatarState, SendTextCallback
from .types import (
    CROSSFADE_DEFAULT_MS,
    CROSSFADE_MAX_MS,
    CROSSFADE_MIN_MS,
    AvatarEvent,
    Emotion,
)

__all__ = [
    "AvatarState",
    "AvatarEvent",
    "Emotion",
    "SendTextCallback",
    "CROSSFADE_DEFAULT_MS",
    "CROSSFADE_MIN_MS",
    "CROSSFADE_MAX_MS",
]
