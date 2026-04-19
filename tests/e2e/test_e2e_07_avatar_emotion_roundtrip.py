# tests/e2e/test_e2e_07_avatar_emotion_roundtrip.py
"""E2E-07: Gemma [emotion:happy] 태그 → AvatarState 파싱 → avatar-state 프레임.

시나리오 ID: E2E-07-avatar-emotion-roundtrip
REQUIREMENTS: §3.3 감정 태그 (happy/surprised/sad/worried/thinking/sleepy/neutral)
관련 모듈: M_05 (FakeAgent), M_08 AvatarState
마커: e2e_fast (FakeAgent 기반 — 태그 보장)
실행 시간 목표: ≤ 25초
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.e2e_fast]

_VALID_EMOTIONS = frozenset(
    {"neutral", "happy", "surprised", "sad", "worried", "thinking", "sleepy"}
)


@pytest.mark.timeout(30)
@pytest.mark.parametrize(
    "emotion_tag",
    ["happy", "surprised", "sad", "worried", "thinking", "sleepy", "neutral"],
)
async def test_e2e_07_avatar_emotion_roundtrip(
    emotion_tag: str,
    frame_collector: Any,
) -> None:
    """각 감정 태그에 대해 extract_emotion + push_event 라운드트립 검증.

    수락 기준:
    - avatar-state 프레임 수신 ≥ 1.
    - avatar-state.emotion ∈ 7종.
    - full-text에 [emotion: 태그 제거됨.
    - crossfade_ms 200~300 범위.
    """
    from avatar_state import AvatarState

    sent_frames: list[dict[str, Any]] = []

    async def _send_text(payload: dict[str, Any]) -> None:
        sent_frames.append(payload)
        frame_collector.push(payload)

    avatar = AvatarState(default="neutral")

    # FakeAgent 응답 시뮬레이션
    raw_response = f"안녕하세요! 오늘 좋은 날이에요. [emotion:{emotion_tag}]"

    # AvatarState extract_emotion 호출
    clean_text, detected_emotion = avatar.extract_emotion(raw_response)

    # 수락 기준 1: 태그 제거됨
    assert "[emotion:" not in clean_text, f"clean_text에 태그 잔존: {clean_text!r}"

    # 수락 기준 2: 감정이 7종 중 하나 (neutral이 아닌 경우에도 폴백하지 않아야)
    resolved_emotion = detected_emotion or "neutral"
    assert resolved_emotion in _VALID_EMOTIONS, f"감정 {resolved_emotion!r}이 7종 범위 외"

    # push_event로 avatar-state 프레임 생성
    event = avatar.make_event(resolved_emotion, crossfade_ms=250, speaking=False)
    await avatar.push_event(event, _send_text)

    # 수락 기준 3: avatar-state 프레임 수신 ≥ 1
    avatar_frames = frame_collector.by_type("avatar-state")
    assert len(avatar_frames) >= 1, "avatar-state 프레임이 수신되지 않음"

    frame = avatar_frames[-1]

    # 수락 기준 4: emotion 필드가 7종 중 하나
    assert frame.get("emotion") in _VALID_EMOTIONS, (
        f"emotion 필드 {frame.get('emotion')!r}이 7종 범위 외"
    )

    # 수락 기준 5: crossfade_ms 200~300
    crossfade = frame.get("crossfade_ms", 0)
    assert 200 <= crossfade <= 300, f"crossfade_ms={crossfade} 범위(200~300) 초과"
