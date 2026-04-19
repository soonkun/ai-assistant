# src/proactive/errors.py
"""ProactiveDispatcher 예외 클래스."""

from __future__ import annotations


class ProactiveError(Exception):
    """ProactiveDispatcher 최상위 기본 예외."""


class ProactiveInitError(ProactiveError):
    """생성자 인자 검증 실패.

    실제 사용처 없음 — 본 스펙에서는 ValueError/TypeError만 사용.
    후속 확장 여지로 존재.
    """
