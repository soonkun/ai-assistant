# tests/e2e/helpers/ws_client.py
"""WebSocket 테스트 클라이언트 헬퍼.

httpx + starlette TestClient 기반 WebSocket 테스트 래퍼.
프레임 수집·필터 유틸을 제공한다.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any


class FrameCollector:
    """WebSocket 프레임을 list[dict]로 수집.

    asyncio.Queue를 내부에 두어 수신 태스크에서 큐에 쌓고,
    collect_until() 또는 collect_type() 로 소비한다.
    """

    def __init__(self) -> None:
        self._frames: list[dict[str, Any]] = []
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    def push(self, frame: dict[str, Any]) -> None:
        """수신 태스크가 호출: 프레임을 저장."""
        self._frames.append(frame)
        self._queue.put_nowait(frame)

    def all_frames(self) -> list[dict[str, Any]]:
        """수집된 모든 프레임 복사본 반환."""
        return list(self._frames)

    def by_type(self, frame_type: str) -> list[dict[str, Any]]:
        """특정 type의 프레임만 필터링해 반환."""
        return [f for f in self._frames if f.get("type") == frame_type]

    def clear(self) -> None:
        """수집된 프레임 초기화."""
        self._frames.clear()
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    async def wait_for_type(
        self,
        frame_type: str,
        timeout: float = 10.0,
    ) -> dict[str, Any]:
        """특정 type의 프레임이 올 때까지 대기. timeout 초과 시 TimeoutError."""
        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            # 이미 수집된 것 중에 있으면 즉시 반환
            for f in self._frames:
                if f.get("type") == frame_type:
                    return f
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                raise TimeoutError(
                    f"frame type={frame_type!r} not received within {timeout}s. "
                    f"Got: {[f.get('type') for f in self._frames]}"
                )
            try:
                frame = await asyncio.wait_for(self._queue.get(), timeout=min(remaining, 1.0))
                if frame.get("type") == frame_type:
                    return frame
            except (asyncio.TimeoutError, TimeoutError):
                continue

    async def wait_for_matching(
        self,
        predicate: Any,
        timeout: float = 10.0,
        description: str = "matching frame",
    ) -> dict[str, Any]:
        """predicate(frame) == True인 첫 프레임을 기다린다."""
        deadline = asyncio.get_event_loop().time() + timeout
        # 이미 수집된 것 중에 있으면 즉시 반환
        for f in self._frames:
            if predicate(f):
                return f
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                raise TimeoutError(
                    f"{description} not received within {timeout}s. "
                    f"Got: {[f.get('type') for f in self._frames]}"
                )
            try:
                frame = await asyncio.wait_for(self._queue.get(), timeout=min(remaining, 1.0))
                if predicate(frame):
                    return frame
            except (asyncio.TimeoutError, TimeoutError):
                continue


async def ws_send_json(ws: Any, payload: dict[str, Any]) -> None:
    """WebSocket에 JSON 페이로드를 송신하는 헬퍼."""
    await ws.send_text(json.dumps(payload))
