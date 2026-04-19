# src/tts/errors.py
"""TTS 모듈 예외 정의."""


class TTSInitError(Exception):
    """모델 파일 누락, 라이브러리 로드 실패, 화자 참조 WAV 검증 실패 등 초기화 단계 에러."""


class TTSRuntimeError(Exception):
    """generate_audio 도중의 복구 불가능한 합성 실패."""
