# tests/e2e/test_e2e_27_tts_init_fail_text_only.py
"""E2E-27: TTS 초기화 실패 → 텍스트 채팅은 계속 동작.

시나리오 ID: E2E-27-tts-init-fail-text-only
REQUIREMENTS: §9 비기능 (우아한 저하) + M_04 배선 정책
관련 모듈: M_04 TTSEngine, M_01 AppServiceContext
마커: e2e_fast
실행 시간 목표: ≤ 15초
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.e2e_fast]


@pytest.mark.timeout(20)
async def test_e2e_27_tts_init_fail_text_only(
    app_config: Any,
) -> None:
    """TTS 초기화 실패 시 tts_engine=None 설정 + WARNING 로그.

    수락 기준:
    - AppServiceContext.init_tts()에서 TTSInitError 포착.
    - tts_engine=None으로 설정 (앱 기동 성공).
    - 로그에 "TTSInitError" 포함 WARNING 1건 이상.
    - AppServiceContext 자체는 크래시 없음.
    """

    from loguru import logger

    from app.service_context import AppServiceContext
    from tts.errors import TTSInitError

    # 로그 캡처
    log_messages: list[str] = []

    def _capture_log(msg: Any) -> None:
        log_messages.append(str(msg))

    log_id = logger.add(_capture_log, level="WARNING")

    try:
        ctx = AppServiceContext()

        # app_config에 존재하지 않는 TTS 모델 경로 주입
        from app.config import TtsConfig, MeloTtsSubConfig

        bad_config = app_config.model_copy(
            update={"tts": TtsConfig(melo=MeloTtsSubConfig(model_dir="/nonexistent/tts/path"))}
        )
        ctx.app_config = bad_config

        # build_tts_engine이 TTSInitError를 발생시키도록 패치
        with patch("tts.builder.build_tts_engine", side_effect=TTSInitError("모델 없음")):
            # init_tts 호출 (should_init=True 강제)
            ctx.tts_engine = None  # type: ignore[assignment]
            ctx.character_config = MagicMock()
            ctx.character_config.tts_config = None  # 다른 config → should_init=True

            tts_config_mock = MagicMock()
            tts_config_mock.__eq__ = lambda self, other: False  # 항상 재초기화
            ctx.init_tts(tts_config_mock)

        # 수락 기준 1: tts_engine = None (TTSInitError 포착 후)
        assert ctx.tts_engine is None, f"tts_engine이 None이 아님: {ctx.tts_engine}"

        # 수락 기준 2: WARNING 로그에 "TTSInitError" 포함
        tts_warning = any("TTSInitError" in m for m in log_messages)
        assert tts_warning, f"TTSInitError WARNING 로그가 없음. 캡처된 로그: {log_messages}"

    finally:
        logger.remove(log_id)
