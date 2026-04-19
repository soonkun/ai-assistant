# tests/tts/test_xtts_engine.py
"""XttsV2Engine 단위 테스트."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from open_llm_vtuber.tts.tts_interface import TTSInterface
from tts.errors import TTSInitError, TTSRuntimeError
from tts.xtts_v2_engine import XttsV2Engine, _set_xtts_env_vars


def _make_xtts_engine(
    tmp_xtts_dir: Path,
    tmp_valid_wav: Path,
    mock_coqui_tts: MagicMock,
    *,
    language: str = "ko",
    device: str = "cpu",
) -> XttsV2Engine:
    """XTTS v2 모듈을 mock 상태에서 XttsV2Engine을 생성한다."""
    mock_tts_module = MagicMock()
    mock_coqui_cls = MagicMock(return_value=mock_coqui_tts)
    mock_tts_module.TTS = mock_coqui_cls

    with (
        patch("tts._device._check_cuda_available", return_value=False),
        patch("tts.xtts_v2_engine._set_xtts_env_vars"),
        patch.dict(sys.modules, {"TTS": MagicMock(), "TTS.api": mock_tts_module}),
    ):
        engine = XttsV2Engine(
            model_dir=str(tmp_xtts_dir),
            speaker_wav=str(tmp_valid_wav),
            language=language,
            device=device,
        )
    return engine


# ---------------------------------------------------------------------------
# 정상 케이스
# ---------------------------------------------------------------------------


class TestXttsV2EngineInit:
    """N-4: 정상 초기화."""

    def test_normal_init(
        self,
        tmp_xtts_dir: Path,
        tmp_valid_wav: Path,
        mock_coqui_tts: MagicMock,
    ) -> None:
        """N-4: XttsV2Engine 정상 초기화."""
        engine = _make_xtts_engine(tmp_xtts_dir, tmp_valid_wav, mock_coqui_tts)
        assert engine.language == "ko"
        assert engine.speaker_wav.endswith(".wav")
        # speaker_wav는 절대 경로여야 한다
        assert Path(engine.speaker_wav).is_absolute()
        assert isinstance(engine, TTSInterface)

    def test_init_with_35s_wav(
        self,
        tmp_xtts_dir: Path,
        tmp_35s_wav: Path,
        mock_coqui_tts: MagicMock,
    ) -> None:
        """E-4: 3.5초 경계값 WAV로 초기화 성공."""
        engine = _make_xtts_engine(tmp_xtts_dir, tmp_35s_wav, mock_coqui_tts)
        assert engine.speaker_wav.endswith(".wav")


# ---------------------------------------------------------------------------
# 적대적 케이스
# ---------------------------------------------------------------------------


class TestXttsV2EngineAdversarial:
    """A-3, A-4."""

    def test_stereo_wav_raises(
        self,
        tmp_xtts_dir: Path,
        tmp_stereo_wav: Path,
        mock_coqui_tts: MagicMock,
    ) -> None:
        """A-3: 2채널 WAV → TTSInitError, __cause__ is ValueError, 메시지에 'channels'."""
        mock_tts_module = MagicMock()
        mock_tts_module.TTS = MagicMock(return_value=mock_coqui_tts)
        with (
            patch("tts._device._check_cuda_available", return_value=False),
            patch("tts.xtts_v2_engine._set_xtts_env_vars"),
            patch.dict(sys.modules, {"TTS": MagicMock(), "TTS.api": mock_tts_module}),
        ):
            with pytest.raises(TTSInitError) as exc_info:
                XttsV2Engine(
                    model_dir=str(tmp_xtts_dir),
                    speaker_wav=str(tmp_stereo_wav),
                )

        assert "channels" in str(exc_info.value).lower()
        assert isinstance(exc_info.value.__cause__, ValueError)
        # TTS.api.TTS 호출 없음
        mock_tts_module.TTS.assert_not_called()

    def test_short_wav_raises(
        self,
        tmp_xtts_dir: Path,
        tmp_short_wav: Path,
        mock_coqui_tts: MagicMock,
    ) -> None:
        """A-4: 1.5초 WAV → TTSInitError, 메시지에 'duration'."""
        mock_tts_module = MagicMock()
        mock_tts_module.TTS = MagicMock(return_value=mock_coqui_tts)
        with (
            patch("tts._device._check_cuda_available", return_value=False),
            patch("tts.xtts_v2_engine._set_xtts_env_vars"),
            patch.dict(sys.modules, {"TTS": MagicMock(), "TTS.api": mock_tts_module}),
        ):
            with pytest.raises(TTSInitError) as exc_info:
                XttsV2Engine(
                    model_dir=str(tmp_xtts_dir),
                    speaker_wav=str(tmp_short_wav),
                )

        assert "duration" in str(exc_info.value).lower()
        mock_tts_module.TTS.assert_not_called()

    def test_model_dir_not_found(self, tmp_valid_wav: Path) -> None:
        """XTTS model_dir 부재 → TTSInitError."""
        with pytest.raises(TTSInitError, match="model_dir not found"):
            XttsV2Engine(
                model_dir="/no/such/dir",
                speaker_wav=str(tmp_valid_wav),
            )


# ---------------------------------------------------------------------------
# 엣지 케이스 (M-6)
# ---------------------------------------------------------------------------


class TestXttsV2EngineEdge:
    """E-1(빈 텍스트), E-2(1000자 절단)."""

    def test_empty_text_raises(
        self,
        tmp_xtts_dir: Path,
        tmp_valid_wav: Path,
        mock_coqui_tts: MagicMock,
    ) -> None:
        """E-1: 빈 텍스트 → TTSRuntimeError('empty text')."""
        engine = _make_xtts_engine(tmp_xtts_dir, tmp_valid_wav, mock_coqui_tts)
        with pytest.raises(TTSRuntimeError, match="empty text"):
            engine.generate_audio("")
        mock_coqui_tts.tts_to_file.assert_not_called()

    def test_text_truncated_at_1000(
        self,
        tmp_xtts_dir: Path,
        tmp_valid_wav: Path,
        mock_coqui_tts: MagicMock,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """E-2: 1000자 초과 텍스트는 1000자로 절단되어 generate_audio 호출."""
        engine = _make_xtts_engine(tmp_xtts_dir, tmp_valid_wav, mock_coqui_tts, device="cpu")
        # cache_dir를 tmp_path로 설정
        engine.cache_dir = str(tmp_path / "cache")

        long_text = "가" * 1500

        def fake_tts_to_file(
            text: str,
            speaker_wav: str,
            language: str,
            file_path: str,
        ) -> None:
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            Path(file_path).write_bytes(b"\x00" * 512)

        mock_coqui_tts.tts_to_file.side_effect = fake_tts_to_file

        with caplog.at_level(logging.WARNING, logger="tts.xtts_v2_engine"):
            engine.generate_audio(long_text)

        call_text = mock_coqui_tts.tts_to_file.call_args[1]["text"]
        assert len(call_text) == 1000
        assert any("truncating" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# 추가 적대적 케이스 (M-5)
# ---------------------------------------------------------------------------


class TestXttsV2EngineBackendException:
    """A-8: 백엔드 예외 → TTSError로 변환."""

    def test_backend_raises_runtime_error(
        self,
        tmp_xtts_dir: Path,
        tmp_valid_wav: Path,
        mock_coqui_tts: MagicMock,
        tmp_path: Path,
    ) -> None:
        """A-8: tts.tts_to_file가 RuntimeError → TTSRuntimeError로 변환."""
        engine = _make_xtts_engine(tmp_xtts_dir, tmp_valid_wav, mock_coqui_tts)
        engine.cache_dir = str(tmp_path / "cache")

        original_exc = RuntimeError("CUDA OOM in XTTS")
        mock_coqui_tts.tts_to_file.side_effect = original_exc

        with pytest.raises(TTSRuntimeError, match="CUDA OOM in XTTS") as exc_info:
            engine.generate_audio("테스트 텍스트")

        assert exc_info.value.__cause__ is original_exc


# ---------------------------------------------------------------------------
# env var 실제 설정 테스트 (M-7)
# ---------------------------------------------------------------------------


class TestXttsEnvVars:
    """M-7: _set_xtts_env_vars 호출 후 os.environ 실제 값 검증."""

    def test_env_vars_set_correctly(self) -> None:
        """M-7: _set_xtts_env_vars 호출 후 4개 환경변수가 모두 설정됨."""
        nltk_dir = "/tmp/test_nltk_data"
        # 기존 환경변수를 임시 제거해 설정을 강제
        saved = {}
        for key in ("COQUI_TOS_AGREED", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "NLTK_DATA"):
            saved[key] = os.environ.pop(key, None)

        try:
            _set_xtts_env_vars(nltk_data_dir=nltk_dir)
            assert os.environ.get("COQUI_TOS_AGREED") == "1"
            assert os.environ.get("HF_HUB_OFFLINE") == "1"
            assert os.environ.get("TRANSFORMERS_OFFLINE") == "1"
            assert os.environ.get("NLTK_DATA") == nltk_dir
        finally:
            # 테스트 후 복원
            for key, val in saved.items():
                if val is not None:
                    os.environ[key] = val
                else:
                    os.environ.pop(key, None)

    def test_existing_env_vars_not_overwritten(self) -> None:
        """M-7: 이미 설정된 환경변수는 덮어쓰지 않는다."""
        os.environ["COQUI_TOS_AGREED"] = "already_set"
        os.environ["NLTK_DATA"] = "/existing/path"
        try:
            _set_xtts_env_vars(nltk_data_dir="/new/path")
            assert os.environ["COQUI_TOS_AGREED"] == "already_set"
            assert os.environ["NLTK_DATA"] == "/existing/path"
        finally:
            os.environ.pop("COQUI_TOS_AGREED", None)
            os.environ.pop("NLTK_DATA", None)
