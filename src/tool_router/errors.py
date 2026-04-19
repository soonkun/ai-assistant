# src/tool_router/errors.py
"""M_05b ToolRouter 에러 타입 정의."""


class ToolRouterError(Exception):
    """M_05b 공통 기본 예외."""


class ScreenshotInitError(ToolRouterError):
    """OS/권한/의존 라이브러리 문제로 ScreenshotService 초기화 실패."""


class ScreenshotCaptureError(ToolRouterError):
    """런타임 캡처 실패(디스플레이 분리, DPI 변경 등).

    dispatch()는 이를 catch해서 ToolResult(ok=False)로 변환.
    """


class AgentProtocolError(Exception):
    """upstream `__API_NOT_SUPPORT_TOOLS__` 등 본 모듈이 허용하지 않는 경로로 진입.

    agent 레이어와 공용 계약. ToolRouterError를 상속하지 않는 독립 예외 계층.
    """
