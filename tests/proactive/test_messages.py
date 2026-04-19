# tests/proactive/test_messages.py
"""_compose_message 출력 문자열 검증."""

from __future__ import annotations

import pytest

from proactive.messages import _compose_message


class TestComposeMessageMorningBriefing:
    """morning_briefing 토픽 메시지 합성 테스트."""

    def test_no_events(self) -> None:
        result = _compose_message("morning_briefing", {"events": []})
        assert "좋은 아침이에요!" in result
        assert "등록된 일정이 없어요" in result

    def test_with_events(self) -> None:
        events = [
            {"start_hhmm": "09:00", "title": "스탠드업"},
            {"start_hhmm": "14:00", "title": "팀 회의"},
        ]
        result = _compose_message("morning_briefing", {"events": events})
        assert "2개" in result
        assert "스탠드업" in result
        assert "팀 회의" in result

    def test_truncate_to_5_events(self) -> None:
        events = [{"start_hhmm": f"0{i}:00", "title": f"일정{i}"} for i in range(7)]
        result = _compose_message("morning_briefing", {"events": events})
        assert "외 2개 더" in result

    def test_missing_events_key(self) -> None:
        result = _compose_message("morning_briefing", {})
        assert "좋은 아침이에요!" in result
        assert "등록된 일정이 없어요" in result


class TestComposeMessageEventReminder:
    def test_basic(self) -> None:
        result = _compose_message(
            "event_reminder",
            {"title": "팀 회의", "minutes_until": 10},
        )
        assert "10분" in result
        assert "팀 회의" in result

    def test_missing_title(self) -> None:
        result = _compose_message("event_reminder", {"minutes_until": 5})
        assert "5분" in result

    def test_missing_minutes(self) -> None:
        result = _compose_message("event_reminder", {"title": "회의"})
        assert "10분" in result  # 기본값


class TestComposeMessageIdleAndOverwork:
    def test_idle_rest(self) -> None:
        result = _compose_message("idle_rest", {})
        assert "스트레칭" in result or "쉬" in result

    def test_overwork(self) -> None:
        result = _compose_message("overwork", {})
        assert "2시간" in result or "쉬어" in result


class TestComposeMessageUnknownTopic:
    def test_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="unknown topic"):
            _compose_message("unknown_topic", {})  # type: ignore[arg-type]
