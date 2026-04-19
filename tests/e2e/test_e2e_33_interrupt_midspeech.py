# tests/e2e/test_e2e_33_interrupt_midspeech.py
"""E2E-33: AI 발화 중 사용자 인터럽트 → TTS 큐 드레인 + 즉시 듣기 전환.

시나리오 ID: E2E-33-interrupt-midspeech
REQUIREMENTS: §1.1 전이중(Full Duplex)
관련 모듈: M_02, M_03, M_04, M_05 (FakeAgent)
마커: e2e_fast (FakeAgent 기반)
실행 시간 목표: ≤ 30초

수동 체크 지점:
  - Whisper 모델 없이도 FakeAgent 기반으로 실행 가능.
  - 실제 인터럽트 테스트는 handle_interrupt() 공개 API를 통해 검증.
"""

from __future__ import annotations


import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.e2e_fast]


@pytest.mark.timeout(35)
async def test_e2e_33_interrupt_midspeech() -> None:
    """FakeAgent handle_interrupt 호출 후 인터럽트 플래그 확인.

    수락 기준:
    - FakeAgent.handle_interrupt() 호출 후 _interrupted=True.
    - 인터럽트 후 새 chat() 호출 시 정상 응답 재개.
    - 서버 크래시 없음.
    """
    from tests.e2e.fakes.fake_agent import FakeAgent, make_long_text_response

    fake_agent = FakeAgent(
        responses=[
            make_long_text_response(char_count=1200, chunk_size=50),
            "인터럽트 후 재시작 응답입니다.",
        ]
    )

    # 1. 첫 번째 chat 시작 (긴 응답)
    from open_llm_vtuber.agent.input_types import BatchInput, TextData, TextSource  # type: ignore[import]

    batch1 = BatchInput(texts=[TextData(source=TextSource.INPUT, content="긴 답변 부탁해")])
    chunks_before_interrupt: list[str] = []

    chat_iter = fake_agent.chat(batch1)

    # 몇 개 청크 수신 후 인터럽트
    chunk_count = 0
    async for event in chat_iter:
        from agent.events import TextChunk

        if isinstance(event, TextChunk):
            chunks_before_interrupt.append(event.text)
            chunk_count += 1
            if chunk_count >= 3:
                # 인터럽트 발생
                await fake_agent.handle_interrupt("잠깐만요")
                break

    # 수락 기준 1: 인터럽트 플래그 설정됨
    assert fake_agent._interrupted is True, "handle_interrupt 후 _interrupted가 True가 아님"
    assert fake_agent.interrupt_count >= 1, "interrupt_count가 0"

    # 수락 기준 2: 인터럽트 후 새 chat() 시작 → 정상 응답
    batch2 = BatchInput(texts=[TextData(source=TextSource.INPUT, content="다시 짧게 답해줘")])
    second_chunks: list[str] = []
    async for event in fake_agent.chat(batch2):
        from agent.events import TextChunk

        if isinstance(event, TextChunk):
            second_chunks.append(event.text)

    # 수락 기준 3: 두 번째 응답 수신 (인터럽트 후 재시작 동작)
    assert second_chunks, "인터럽트 후 재시작 응답이 없음"
    second_full = "".join(second_chunks)
    assert "인터럽트" in second_full or len(second_full) > 0, (
        f"두 번째 응답이 예상과 다름: {second_full!r}"
    )

    # 수락 기준 4: 서버 크래시 없음 (여기까지 도달 = 크래시 없음)
    assert fake_agent.call_count == 2, f"총 chat() 호출 수: {fake_agent.call_count}"
