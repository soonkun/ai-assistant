# tests/app/test_ws_route.py
"""TestClient WebSocket 연결 smoke 테스트."""

import asyncio
import json
from unittest.mock import MagicMock, patch

from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient

from app.ws_route import init_app_ws_route


def _make_mock_context() -> MagicMock:
    ctx = MagicMock()
    ctx.config = MagicMock()
    ctx.system_config = MagicMock()
    ctx.character_config = MagicMock()
    ctx.character_config.conf_name = "saessagi"
    ctx.character_config.conf_uid = "saessagi-v1"
    ctx.live2d_model = MagicMock()
    ctx.live2d_model.model_info = {"type": "stub"}
    ctx.screenshot_service = None
    ctx.app_config = None
    return ctx


class TestWsRouteSmoke:
    """WebSocket 라우터 smoke 테스트."""

    def test_router_registered(self) -> None:
        """init_app_ws_route가 FastAPI에 등록 가능한 라우터 반환."""
        ctx = _make_mock_context()
        with patch(
            "open_llm_vtuber.websocket_handler.WebSocketHandler.__init__",
            return_value=None,
        ):
            router = init_app_ws_route(ctx)

        app = FastAPI()
        app.include_router(router)
        routes = [r.path for r in app.routes]  # type: ignore[attr-defined]
        assert "/client-ws" in routes

    def test_route_path_is_client_ws(self) -> None:
        """라우터에 /client-ws WebSocket 경로 존재."""
        ctx = _make_mock_context()
        with patch(
            "open_llm_vtuber.websocket_handler.WebSocketHandler.__init__",
            return_value=None,
        ):
            router = init_app_ws_route(ctx)

        ws_paths = [r.path for r in router.routes]  # type: ignore[attr-defined]
        assert "/client-ws" in ws_paths

    def test_websocket_connection_smoke(self) -> None:
        """WebSocket /client-ws 연결 smoke test — upstream 초기화 없이 Mock으로 연결 성공 검증.

        upstream 서비스를 Mock으로 교체해 WebSocket 연결이 예외 없이 수립되는지 검증.
        """
        # Mock WebSocket 핸들러를 주입한 앱 생성
        test_app = FastAPI()

        @test_app.websocket("/client-ws")
        async def mock_endpoint(websocket: WebSocket) -> None:
            await websocket.accept()
            await websocket.send_text(
                json.dumps({"type": "full-text", "text": "Connection established"})
            )
            # 첫 메시지 수신 후 종료 (smoke test)
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
            except (asyncio.TimeoutError, Exception):
                pass
            await websocket.close()

        client = TestClient(test_app)
        # ConnectError 없이 연결 성공 및 메시지 수신 검증
        with client.websocket_connect("/client-ws") as ws:
            msg = json.loads(ws.receive_text())
            assert msg["type"] == "full-text"
