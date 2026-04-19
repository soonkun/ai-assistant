# src/proactive/types.py
"""ProactiveDispatcher 공개 타입 alias."""

from __future__ import annotations

from typing import Literal

ProactiveTopic = Literal["morning_briefing", "event_reminder", "idle_rest", "overwork"]
"""프로액티브 발화 토픽 Literal.

- morning_briefing: 매일 아침 일정 브리핑.
- event_reminder: 일정 10분 전 알림.
- idle_rest: 유휴 감지 후 휴식 권고.
- overwork: 2시간 연속 활동 후 휴식 권고.
"""

TOPICS: frozenset[ProactiveTopic] = frozenset(
    ["morning_briefing", "event_reminder", "idle_rest", "overwork"]
)
"""토픽 상수 집합 (typo 검증용)."""
