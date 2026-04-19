# src/proactive/messages.py
"""토픽별 한국어 고정 템플릿 메시지 합성 (D-1 결정)."""

from __future__ import annotations

from typing import Any

from .types import ProactiveTopic


def _compose_message(topic: ProactiveTopic, context: dict[str, Any]) -> str:
    """토픽과 컨텍스트를 기반으로 한국어 메시지를 합성한다.

    V1: 고정 한국어 템플릿 사용. LLM 자연어 생성 위임 금지(D-1).
    upstream `proactive_speak_prompt` 경로가 최종 자연어 프롬프트를 생성한다.
    본 함수의 출력은 payload의 `text` 필드 — 로깅·V2 확장용.

    Args:
        topic: ProactiveTopic 4종 중 하나.
        context: 토픽별 부가 정보 dict.

    Returns:
        한국어 메시지 문자열. 빈 문자열 금지 (len >= 1).

    Raises:
        ValueError: topic이 알 수 없는 값인 경우.
    """
    if topic == "morning_briefing":
        events = context.get("events") or []
        if not events:
            return "좋은 아침이에요! 오늘은 등록된 일정이 없어요."
        lines = [f"좋은 아침이에요! 오늘 일정은 {len(events)}개예요."]
        for ev in events[:5]:  # 최대 5개만 읽어주기
            start = ev.get("start_hhmm", "?")
            title = ev.get("title", "제목 없음")
            lines.append(f"- {start} {title}")
        if len(events) > 5:
            lines.append(f"(외 {len(events) - 5}개 더)")
        return "\n".join(lines)

    if topic == "event_reminder":
        title = context.get("title", "일정")
        minutes = context.get("minutes_until", 10)
        return f"{minutes}분 뒤 '{title}' 일정이 있어요."

    if topic == "idle_rest":
        return "오래 쉬지 않고 계셨네요. 잠깐 스트레칭은 어떠세요?"

    if topic == "overwork":
        return "2시간 넘게 집중하셨어요. 잠깐 눈을 감고 쉬어보세요."

    raise ValueError(f"unknown topic: {topic!r}")
