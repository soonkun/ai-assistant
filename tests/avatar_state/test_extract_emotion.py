# tests/avatar_state/test_extract_emotion.py
"""extract_emotion 정상·엣지·적대적 케이스 테스트."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import pytest

from avatar_state.service import AvatarState


# ---------------------------------------------------------------------------
# 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def state() -> AvatarState:
    return AvatarState()


# ---------------------------------------------------------------------------
# loguru WARNING 캡처 헬퍼
# ---------------------------------------------------------------------------


def _capture_warnings(func: Callable[[], Any]) -> tuple[Any, list[str]]:
    """func() 실행 중 loguru WARNING 이상 메시지를 리스트로 수집해 반환."""
    from loguru import logger

    records: list[str] = []

    def _sink(message: object) -> None:
        records.append(str(message))

    handler_id = logger.add(_sink, level="WARNING")
    try:
        result = func()
    finally:
        logger.remove(handler_id)
    return result, records


# ---------------------------------------------------------------------------
# 정상 케이스 (N)
# ---------------------------------------------------------------------------


class TestNormal:
    """N-1 ~ N-4(extract 관련): 정상 흐름."""

    def test_n1_single_tag_extracted(self, state: AvatarState) -> None:
        """N-1: [emotion:happy] 파싱 + 태그 제거."""
        clean, emotion = state.extract_emotion("[emotion:happy] 안녕하세요")
        assert clean == " 안녕하세요"
        assert emotion == "happy"

    def test_n2_no_tag(self, state: AvatarState) -> None:
        """N-2: 태그 없음 → (text, None)."""
        clean, emotion = state.extract_emotion("오늘 날씨 좋아요")
        assert clean == "오늘 날씨 좋아요"
        assert emotion is None

    def test_n3_multi_tag_first_wins(self, state: AvatarState) -> None:
        """N-3: 다중 태그 — 첫 번째만 채택 (D-2)."""
        clean, emotion = state.extract_emotion("[emotion:happy] 좋다 [emotion:sad] 슬프다")
        assert clean == " 좋다  슬프다"
        assert emotion == "happy"

    def test_n4_case_insensitive(self, state: AvatarState) -> None:
        """N-4: 대소문자 혼용 → lower 정규화."""
        clean, emotion = state.extract_emotion("[EMOTION:Happy] 안녕 [Emotion:SLEEPY]")
        assert clean == " 안녕 "
        assert emotion == "happy"

    def test_n4_korean_between_tags(self, state: AvatarState) -> None:
        """N-6(스펙) 한글 사이 삽입 — 공백 없음."""
        clean, emotion = state.extract_emotion("안녕[emotion:happy]하세요")
        assert clean == "안녕하세요"
        assert emotion == "happy"

    def test_tag_only_string(self, state: AvatarState) -> None:
        """E-2: 태그만 있는 문자열 → clean == ""."""
        clean, emotion = state.extract_emotion("[emotion:happy]")
        assert clean == ""
        assert emotion == "happy"

    def test_all_spoken_emotions_parse(self, state: AvatarState) -> None:
        """7종 발화 감정 모두 정상 파싱."""
        from avatar_state.types import _SPOKEN_EMOTIONS

        for emo in _SPOKEN_EMOTIONS:
            _, emotion = state.extract_emotion(f"[emotion:{emo}]")
            assert emotion == emo, f"Expected {emo}, got {emotion}"


# ---------------------------------------------------------------------------
# 엣지 케이스 (E)
# ---------------------------------------------------------------------------


class TestEdge:
    """E-1 ~ E-8: 경계 조건."""

    def test_e1_empty_string(self, state: AvatarState) -> None:
        """E-1: 빈 문자열 → ("", None)."""
        clean, emotion = state.extract_emotion("")
        assert clean == ""
        assert emotion is None

    def test_e3_nested_brackets(self, state: AvatarState) -> None:
        """E-3: 중첩 브래킷 [[emotion:happy]] → 내부 태그 제거, 외부 [] 보존."""
        clean, emotion = state.extract_emotion("[[emotion:happy]]")
        assert clean == "[]"
        assert emotion == "happy"

    def test_e4_incomplete_tag(self, state: AvatarState) -> None:
        """E-4: 미완결 태그 → 매치 실패, 원문 그대로."""
        text = "안녕 [emotion:ha 기분"
        clean, emotion = state.extract_emotion(text)
        assert clean == text
        assert emotion is None

    def test_e5_unknown_key_neutral_fallback(self, state: AvatarState) -> None:
        """E-5: 미지 키 → neutral 폴백 + WARNING."""
        result, warnings = _capture_warnings(
            lambda: state.extract_emotion("[emotion:joy] 기분 좋아")
        )
        clean, emotion = result  # type: ignore[misc]
        assert emotion == "neutral"
        assert clean == " 기분 좋아"
        assert any("joy" in w for w in warnings), f"No warning with 'joy': {warnings}"

    def test_e6_crossfade_boundaries(self) -> None:
        """E-6: crossfade_ms 경계값 성공/실패."""
        from avatar_state.types import AvatarEvent

        # 성공
        AvatarEvent(emotion="happy", crossfade_ms=200)
        AvatarEvent(emotion="happy", crossfade_ms=300)
        # 실패
        with pytest.raises(ValueError):
            AvatarEvent(emotion="happy", crossfade_ms=199)
        with pytest.raises(ValueError):
            AvatarEvent(emotion="happy", crossfade_ms=301)

    def test_e7_speaking_bool_type(self) -> None:
        """E-7: speaking 플래그 — 런타임 검증 없음, mypy로만 차단."""
        from avatar_state.types import AvatarEvent

        # truthy 값도 생성은 가능 (spec §8 참조)
        ev = AvatarEvent(emotion="happy", speaking=True)
        assert ev.speaking is True

    def test_e8_study_tag_neutral_fallback(self, state: AvatarState) -> None:
        """E-8: [emotion:study] → neutral 폴백 + WARNING + 태그 제거."""
        result, warnings = _capture_warnings(lambda: state.extract_emotion("[emotion:study] 하이"))
        clean, emotion = result  # type: ignore[misc]
        assert emotion == "neutral", f"Expected 'neutral', got {emotion!r}"
        assert clean == " 하이"
        assert any("[emotion:study]" in w for w in warnings), (
            f"Warning with '[emotion:study]' not found: {warnings}"
        )
        # 회귀 보호: warning 정확히 1회
        assert len(warnings) == 1, f"Expected exactly 1 warning, got {len(warnings)}: {warnings}"

    def test_e8_study_tag_only(self, state: AvatarState) -> None:
        """E-8 서브케이스: [emotion:study] 단독 → ("", "neutral")."""
        result, warnings = _capture_warnings(lambda: state.extract_emotion("[emotion:study]"))
        clean, emotion = result  # type: ignore[misc]
        assert clean == ""
        assert emotion == "neutral"
        assert len(warnings) == 1, f"Expected exactly 1 warning, got {len(warnings)}: {warnings}"


# ---------------------------------------------------------------------------
# 적대적 케이스 (A)
# ---------------------------------------------------------------------------


class TestAdversarial:
    """A-1 ~ A-4: 적대적 입력."""

    def test_a1_unknown_then_valid_neutral_wins(self, state: AvatarState) -> None:
        """A-1: 미지 키가 앞, 유효 키가 뒤 → neutral 폴백 (덮어쓰기 안 함)."""
        result, warnings = _capture_warnings(
            lambda: state.extract_emotion("[emotion:joy] [emotion:happy]")
        )
        clean, emotion = result  # type: ignore[misc]
        # 첫 번째 태그가 미지 키 → neutral 폴백, 이후 유효 키도 "첫 번째" 이후이므로 neutral 유지
        assert emotion == "neutral", f"Expected 'neutral', got {emotion!r}"
        assert any("joy" in w for w in warnings)
        # 회귀 보호: warning 정확히 1회
        assert len(warnings) == 1, f"Expected exactly 1 warning, got {len(warnings)}: {warnings}"

    def test_a2_xss_attempt(self, state: AvatarState) -> None:
        """A-2: XSS 시도 → 정규식 매치 실패, 원문 그대로."""
        text = "[emotion:<script>alert(1)</script>] 안녕"
        clean, emotion = state.extract_emotion(text)
        assert emotion is None
        # 태그가 제거되지 않고 원문 그대로 반환
        assert clean == text

    def test_a3_very_long_input(self, state: AvatarState) -> None:
        """A-3: 10KB+ 긴 입력 → 20ms 이내 완료."""
        long_text = "[emotion:happy] 문장 " * 500  # ~10KB, 태그 500개
        start = time.perf_counter()
        clean, emotion = state.extract_emotion(long_text)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert emotion == "happy"
        assert elapsed_ms < 20, f"Took {elapsed_ms:.1f}ms, expected < 20ms"
        assert "[emotion:happy]" not in clean

    def test_a4_non_string_inputs(self, state: AvatarState) -> None:
        """A-4: 비-문자열 입력 → TypeError."""
        with pytest.raises(TypeError, match="text must be str"):
            state.extract_emotion(None)  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="text must be str"):
            state.extract_emotion(b"[emotion:happy]")  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="text must be str"):
            state.extract_emotion(123)  # type: ignore[arg-type]

    def test_upstream_single_key_not_matched(self, state: AvatarState) -> None:
        """DoD: upstream [happy] 단일 키 문법은 매치 안 됨."""
        clean, emotion = state.extract_emotion("[happy]")
        assert emotion is None
        assert clean == "[happy]"
