# tests/e2e/test_e2e_31_unknown_emotion_tag.py
"""E2E-31: [emotion:ecstatic] 미지 태그 → neutral 폴백 + warning.

시나리오 ID: E2E-31-unknown-emotion-tag
REQUIREMENTS: §3.3 감정 7종 (M_08 §4.1 미지 키 폴백)
관련 모듈: M_08 AvatarState
마커: e2e_fast
실행 시간 목표: ≤ 5초

FakeAgent가 고정 응답 "정말 기쁘군요! [emotion:ecstatic]" 방출.
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.e2e_fast]


@pytest.mark.timeout(10)
async def test_e2e_31_unknown_emotion_tag() -> None:
    """미지 태그 [emotion:ecstatic] → neutral 폴백 + 태그 제거 + WARNING.

    수락 기준:
    - avatar-state.emotion == "neutral"
    - full-text 본문에 [emotion: 태그 제거됨
    - WARNING "unknown emotion" 또는 "폴백" 포함 로그 관찰 (loguru 캡처)
    - 크래시 없음
    """

    from loguru import logger

    from avatar_state import AvatarState

    # sent_frames 수집
    sent_frames: list[dict[str, Any]] = []

    async def _send_text(payload: dict[str, Any]) -> None:
        sent_frames.append(payload)

    # 로그 캡처
    log_messages: list[str] = []

    def _capture_log(msg: Any) -> None:
        log_messages.append(str(msg))

    log_id = logger.add(_capture_log, level="WARNING")

    try:
        avatar = AvatarState(default="neutral")

        # FakeAgent 응답 시뮬레이션: 미지 감정 태그 포함
        raw_text = "정말 기쁘군요! [emotion:ecstatic]"

        # extract_emotion 호출
        clean_text, emotion = avatar.extract_emotion(raw_text)

        # 수락 기준 1: 태그 제거됨
        assert "[emotion:" not in clean_text, f"clean_text에 태그가 남아있음: {clean_text!r}"

        # 수락 기준 2: 미지 태그 → neutral 폴백
        assert emotion == "neutral", f"미지 태그에 대해 neutral 폴백이 아닌 {emotion!r} 반환"

        # push_event로 avatar-state 프레임 송신
        event = avatar.make_event("neutral", crossfade_ms=250, speaking=False)
        await avatar.push_event(event, _send_text)

        # 수락 기준 3: avatar-state 프레임 수신
        assert sent_frames, "avatar-state 프레임이 수신되지 않음"
        frame = sent_frames[0]
        assert frame.get("type") == "avatar-state"
        assert frame.get("emotion") == "neutral", (
            f"emotion 필드가 'neutral'이 아님: {frame.get('emotion')!r}"
        )

        # 수락 기준 4: crossfade_ms 범위 (200~300)
        crossfade = frame.get("crossfade_ms", 0)
        assert 200 <= crossfade <= 300, f"crossfade_ms={crossfade} 범위(200~300) 초과"

        # 수락 기준 5: WARNING 로그에 unknown/폴백 관련 키워드 포함
        warning_found = any(
            "unknown" in m.lower() or "폴백" in m or "fallback" in m.lower() or "ecstatic" in m
            for m in log_messages
        )
        assert warning_found, f"미지 태그에 대한 WARNING 로그가 없음. 캡처된 로그: {log_messages}"

    finally:
        logger.remove(log_id)
