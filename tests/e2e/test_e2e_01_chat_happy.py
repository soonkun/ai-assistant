# tests/e2e/test_e2e_01_chat_happy.py
"""E2E-01: 텍스트 채팅 1턴 해피패스 (FakeAgent 기반).

시나리오 ID: E2E-01-chat-happy
REQUIREMENTS: §1.2 텍스트 대화 · §1.1 TTS · §3.3 감정 태그
관련 모듈: M_01, M_04, M_05, M_08
마커: e2e_fast (FakeAgent 기반) / e2e_model (실제 Gemma)
실행 시간 목표: ≤ 25초

FakeAgent 버전:
  - AvatarState.extract_emotion + push_event 라운드트립 검증.
  - [emotion:happy] 태그 제거 + avatar-state 프레임 검증.
  - 외부 네트워크 호출 0건 (offline_guard autouse).

실제 Gemma 버전 (e2e_model):
  - 실제 Ollama 연결 + 스트리밍 응답 검증.
  - 수동 체크 지점: Ollama와 MeloTTS 모델이 로컬에 배치됐는지 확인.
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.e2e_fast]


@pytest.mark.timeout(30)
async def test_e2e_01_chat_happy_fake_agent(
    frame_collector: Any,
) -> None:
    """FakeAgent 기반 텍스트 채팅 1턴 해피패스.

    수락 기준:
    - AvatarState.extract_emotion이 [emotion:happy] 태그를 추출.
    - clean_text에 [emotion: 태그 없음.
    - avatar-state 프레임 수신 ≥ 1.
    - avatar-state.emotion ∈ 8종.
    - crossfade_ms 200~300.
    - 외부 네트워크 호출 0건 (offline_guard autouse fixture).
    """
    from avatar_state import AvatarState
    from tests.e2e.fakes.fake_agent import FakeAgent, make_emotion_response

    sent_frames: list[dict[str, Any]] = []

    async def _send_text(payload: dict[str, Any]) -> None:
        sent_frames.append(payload)
        frame_collector.push(payload)

    avatar = AvatarState(default="neutral")

    # FakeAgent 응답 (happy 태그 포함)
    fake_agent = FakeAgent(
        responses=[make_emotion_response(text="안녕하세요! 만나서 반가워요!", emotion_tag="happy")]
    )

    # 채팅 시뮬레이션: FakeAgent.chat() → 이벤트 스트림 처리
    from agent.events import TextChunk

    user_input = "안녕 새싹이야, 오늘 기분 어때?"
    from open_llm_vtuber.agent.input_types import BatchInput, TextData, TextSource  # type: ignore[import]

    batch = BatchInput(texts=[TextData(source=TextSource.INPUT, content=user_input)])

    full_text_parts: list[str] = []
    async for event in fake_agent.chat(batch):
        if isinstance(event, TextChunk):
            full_text_parts.append(event.text)

    full_response = "".join(full_text_parts)

    # AvatarState 처리
    clean_text, emotion = avatar.extract_emotion(full_response)

    # 수락 기준 1: 태그 제거됨
    assert "[emotion:" not in clean_text, f"clean_text에 태그 잔존: {clean_text!r}"

    # 수락 기준 2: 감정 감지됨
    assert emotion is not None, "감정 태그가 감지되지 않음"

    # push_event
    resolved_emotion = emotion if emotion is not None else "neutral"
    event_obj = avatar.make_event(resolved_emotion, crossfade_ms=250)
    await avatar.push_event(event_obj, _send_text)

    # 수락 기준 3: avatar-state 프레임 수신
    avatar_frames = frame_collector.by_type("avatar-state")
    assert len(avatar_frames) >= 1, "avatar-state 프레임 없음"

    frame = avatar_frames[0]

    # 수락 기준 4: emotion 유효
    valid_emotions = frozenset(
        {"neutral", "happy", "surprised", "sad", "worried", "thinking", "sleepy", "study"}
    )
    assert frame.get("emotion") in valid_emotions, f"emotion {frame.get('emotion')!r}이 8종 범위 외"

    # 수락 기준 5: crossfade_ms 200~300
    crossfade = frame.get("crossfade_ms", 0)
    assert 200 <= crossfade <= 300, f"crossfade_ms={crossfade} 범위 초과"

    # 수락 기준 6: FakeAgent가 정확히 1회 호출됨
    assert fake_agent.call_count == 1, f"FakeAgent 호출 횟수: {fake_agent.call_count}"
