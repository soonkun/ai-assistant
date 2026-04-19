# src/agent/errors.py
"""GemmaChatAgent 에러 타입 정의."""


class AgentInitError(Exception):
    """GemmaChatAgent 초기화 단계 에러 (설정 위반, Ollama 헬스체크 실패 등)."""


class AgentBackendError(Exception):
    """초기화 재시도(3회) 모두 실패 또는 런타임 치명적 백엔드 에러."""


class AgentProtocolError(Exception):
    """upstream `__API_NOT_SUPPORT_TOOLS__` 등 본 모듈이 허용하지 않는 경로로 진입."""
