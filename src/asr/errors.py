# src/asr/errors.py
"""ASR 모듈 고유 예외 타입."""


class ASRInitError(Exception):
    """모델 로드·경로 검증·디바이스 초기화 실패."""


class ASRRuntimeError(Exception):
    """transcribe 도중의 복구 불가능한 에러 (백엔드 예외 전파)."""
