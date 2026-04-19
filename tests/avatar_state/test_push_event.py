# tests/avatar_state/test_push_event.py
"""push_event 정상·엣지·적대적 케이스 테스트."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock

import pytest

from avatar_state.service import AvatarState
from avatar_state.types import AvatarEvent


# ---------------------------------------------------------------------------
# loguru ERROR 캡처 헬퍼
# ---------------------------------------------------------------------------


async def _capture_errors_async(
    coro_func: Callable[[], Awaitable[Any]],
) -> tuple[Any, list[str]]:
    """coro_func() 실행 중 loguru ERROR 이상 메시지를 리스트로 수집해 반환."""
    from loguru import logger

    records: list[str] = []

    def _sink(message: object) -> None:
        records.append(str(message))

    handler_id = logger.add(_sink, level="ERROR")
    result: Any = None
    exc_to_raise: BaseException | None = None
    try:
        result = await coro_func()
    except Exception as exc:
        exc_to_raise = exc
    finally:
        logger.remove(handler_id)
    if exc_to_raise is not None:
        raise exc_to_raise
    return result, records


# ---------------------------------------------------------------------------
# 정상 케이스 (N)
# ---------------------------------------------------------------------------


class TestNormal:
    async def test_n5_push_event_payload_and_state(self) -> None:
        """N-5: push_event 호출 시 정확한 페이로드 + 상태 갱신."""
        state = AvatarState()
        send_text = AsyncMock()

        await state.push_event(
            AvatarEvent(emotion="happy", crossfade_ms=250, speaking=True),
            send_text,
        )

        send_text.assert_called_once_with(
            {
                "type": "avatar-state",
                "emotion": "happy",
                "crossfade_ms": 250,
                "speaking": True,
            }
        )
        assert state.current_emotion == "happy"
        assert state.is_speaking is True

    def test_n6_make_event_defaults(self) -> None:
        """N-6: make_event 편의 메서드 기본값."""
        state = AvatarState()
        ev = state.make_event("sleepy")
        assert ev == AvatarEvent(emotion="sleepy", crossfade_ms=250, speaking=False)

    async def test_n7_concurrent_push_event_order(self) -> None:
        """N-7: 동시 push_event 호출 시 순서 보장."""
        state = AvatarState()
        call_order: list[str] = []

        async def send_text(payload: dict) -> None:
            call_order.append(payload["emotion"])

        await asyncio.gather(
            state.push_event(AvatarEvent(emotion="happy"), send_text),
            state.push_event(AvatarEvent(emotion="sad"), send_text),
            state.push_event(AvatarEvent(emotion="neutral"), send_text),
        )

        assert call_order == ["happy", "sad", "neutral"]

    async def test_n8_study_emit_via_push_event(self) -> None:
        """N-8: study 시스템 상태 직접 emit."""
        state = AvatarState()
        send_text = AsyncMock()

        await state.push_event(
            AvatarEvent(emotion="study", crossfade_ms=250, speaking=False),
            send_text,
        )

        send_text.assert_called_once()
        payload = send_text.call_args[0][0]
        assert payload["emotion"] == "study"
        assert payload["type"] == "avatar-state"
        assert state.current_emotion == "study"
        assert state.is_speaking is False

        # _VALID_EMOTIONS에 study 포함 단언
        from avatar_state.types import _VALID_EMOTIONS

        assert "study" in _VALID_EMOTIONS

    async def test_payload_has_exactly_4_keys(self) -> None:
        """DoD: 송신 페이로드가 정확히 4키({type, emotion, crossfade_ms, speaking})."""
        state = AvatarState()
        send_text = AsyncMock()

        await state.push_event(AvatarEvent(emotion="neutral"), send_text)

        payload = send_text.call_args[0][0]
        assert set(payload.keys()) == {"type", "emotion", "crossfade_ms", "speaking"}


# ---------------------------------------------------------------------------
# 엣지 케이스 (E)
# ---------------------------------------------------------------------------


class TestEdge:
    async def test_e7_push_event_failure_state_unchanged(self) -> None:
        """E-7: send_text 예외 → ConnectionError 전파, 상태 불변."""
        state = AvatarState()
        initial_emotion = state.current_emotion

        async def failing_send(payload: dict) -> None:
            raise ConnectionError("WebSocket closed")

        with pytest.raises(ConnectionError):
            await state.push_event(AvatarEvent(emotion="happy"), failing_send)

        assert state.current_emotion == initial_emotion

    def test_current_emotion_default(self) -> None:
        """초기 current_emotion == default("neutral")."""
        state = AvatarState()
        assert state.current_emotion == "neutral"

    def test_custom_default(self) -> None:
        """default 인자로 초기 감정 설정."""
        state = AvatarState(default="happy")
        assert state.current_emotion == "happy"

    def test_invalid_default_raises(self) -> None:
        """잘못된 default → ValueError."""
        with pytest.raises(ValueError):
            AvatarState(default="joy")  # type: ignore[arg-type]

    async def test_is_speaking_updated(self) -> None:
        """is_speaking이 push_event 성공 후 갱신됨."""
        state = AvatarState()
        assert state.is_speaking is False

        send_text = AsyncMock()
        await state.push_event(AvatarEvent(emotion="happy", speaking=True), send_text)
        assert state.is_speaking is True


# ---------------------------------------------------------------------------
# 적대적 케이스 (A)
# ---------------------------------------------------------------------------


class TestAdversarial:
    async def test_a4_send_text_exception_propagates(self) -> None:
        """A-4: send_text가 예외를 던지면 push_event가 전파한다."""

        class CustomError(Exception):
            pass

        state = AvatarState()
        send_text = AsyncMock(side_effect=CustomError("boom"))

        with pytest.raises(CustomError, match="boom"):
            await state.push_event(AvatarEvent(emotion="sad"), send_text)

    async def test_push_event_type_error_non_avatar_event(self) -> None:
        """push_event에 AvatarEvent 아닌 값 → TypeError."""
        state = AvatarState()
        send_text = AsyncMock()

        with pytest.raises(TypeError, match="event must be AvatarEvent"):
            await state.push_event(None, send_text)  # type: ignore[arg-type]

    async def test_cancelled_error_propagates(self) -> None:
        """asyncio.CancelledError는 전파된다."""
        state = AvatarState()

        async def cancel_send(payload: dict) -> None:
            raise asyncio.CancelledError()

        with pytest.raises(asyncio.CancelledError):
            await state.push_event(AvatarEvent(emotion="neutral"), cancel_send)

    async def test_study_default_state_allowed(self) -> None:
        """AvatarState(default="study") 생성 가능 — study는 _VALID_EMOTIONS 소속."""
        state = AvatarState(default="study")
        assert state.current_emotion == "study"

    async def test_send_text_exception_logger_error_contains_emotion(self) -> None:
        """send_text 예외 발생 시 logger.error가 emotion 값을 포함해 호출됨 (B2 회귀)."""
        state = AvatarState()

        async def failing_send(payload: dict[str, Any]) -> None:
            raise RuntimeError("connection lost")

        records: list[str] = []

        from loguru import logger

        handler_id = logger.add(lambda msg: records.append(str(msg)), level="ERROR")
        try:
            with pytest.raises(RuntimeError):
                await state.push_event(AvatarEvent(emotion="sad"), failing_send)
        finally:
            logger.remove(handler_id)

        assert len(records) == 1, f"Expected 1 error log, got {len(records)}: {records}"
        assert "sad" in records[0], f"emotion 'sad' not found in error log: {records[0]!r}"
