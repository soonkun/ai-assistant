# src/avatar_state/tag_parser.py
"""태그 파싱 로직.

공개 함수:
  extract_emotion(text) -> (clean_text, Emotion | None)

모듈 로드 시 정규식 1회 컴파일.
"""

from __future__ import annotations

import re

from loguru import logger

from .types import Emotion, _SPOKEN_EMOTIONS

# ---------------------------------------------------------------------------
# 모듈 전역 정규식 (로드 시 1회 컴파일)
# ---------------------------------------------------------------------------

# ASCII 알파벳 + 밑줄만 허용. 숫자·한글·특수문자(<, > 등)는 매치 실패(D-8).
# re.IGNORECASE: 대소문자 무관 매칭 후 .lower()로 정규화.
_TAG_RE: re.Pattern[str] = re.compile(r"\[emotion:([a-zA-Z_]+)\]", re.IGNORECASE)


def extract_emotion(text: str) -> tuple[str, Emotion | None]:
    """완결된 응답 문자열에서 `[emotion:<key>]` 태그를 추출·제거한다.

    Args:
        text: 파싱할 텍스트. 완결된 스트림 청크여야 한다(부분 매칭 미지원, §5.2).
              빈 문자열 허용.

    Returns:
        (clean_text, emotion):
          - clean_text: 모든 매치된 태그가 제거된 텍스트. 공백 보존(§6.4).
          - emotion: 첫 번째 _SPOKEN_EMOTIONS 소속 키.
              미지/비발화 키(study 포함) → "neutral" 폴백.
              태그 없음 → None.

    Raises:
        TypeError: text가 str이 아닐 때.
    """
    if not isinstance(text, str):
        raise TypeError("text must be str")

    if text == "":
        return ("", None)

    # 1. 전체 매치 수집
    matches = list(_TAG_RE.finditer(text))

    # 2. 첫 번째 유효 발화 키 선택
    #    - _SPOKEN_EMOTIONS 소속 → 채택 후 break
    #    - 미지/비발화(study 포함) → neutral 폴백 + break(§10 A-1: 첫 등장 기준 D-3 확정)
    first_emotion: Emotion | None = None
    for m in matches:
        key = m.group(1).lower()
        if key in _SPOKEN_EMOTIONS:
            first_emotion = key  # type: ignore[assignment]
            break
        else:
            logger.warning("unknown emotion tag: {!r}", m.group(0))
            first_emotion = "neutral"
            # 첫 등장 미지 키가 neutral로 확정되면 루프 종료(A-1: 이후 유효 키도 무시)
            break

    # 3. 모든 태그 제거 (공백 보존, §6.4)
    clean = _TAG_RE.sub("", text)

    return (clean, first_emotion)
