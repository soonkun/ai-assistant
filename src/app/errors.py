# src/app/errors.py
"""공용 예외 클래스 정의."""


class PrivacyViolationError(Exception):
    """Ollama 또는 하위 서비스 URL이 사설 IP/loopback 규칙을 위반했을 때."""


class ConfigLoadError(Exception):
    """설정 파일 로딩 또는 파싱 실패."""


class ServiceInitError(Exception):
    """하위 서비스 초기화 실패."""
