# src/app/ws_route.py
"""init_app_ws_route — upstream init_client_ws_route의 AppWebSocketHandler 주입 버전."""

from uuid import uuid4

from fastapi import APIRouter, WebSocket
from loguru import logger
from starlette.websockets import WebSocketDisconnect

from .service_context import AppServiceContext
from .ws_handler import AppWebSocketHandler


def init_app_ws_route(default_context_cache: AppServiceContext) -> APIRouter:
    """AppWebSocketHandler를 사용하는 /client-ws 라우터 반환.

    upstream routes.py의 init_client_ws_route와 동일한 엔드포인트 로직을 재구현.
    upstream 파일 수정 없이 AppWebSocketHandler를 주입하기 위한 유일한 경로.
    """
    router = APIRouter()
    ws_handler = AppWebSocketHandler(default_context_cache)

    @router.websocket("/client-ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        """WebSocket endpoint for client connections."""
        await websocket.accept()
        client_uid = str(uuid4())

        try:
            await ws_handler.handle_new_connection(websocket, client_uid)
            await ws_handler.handle_websocket_communication(websocket, client_uid)
        except WebSocketDisconnect:
            await ws_handler.handle_disconnect(client_uid)
        except Exception as exc:
            logger.error(f"WebSocket 연결 에러: {exc}")
            await ws_handler.handle_disconnect(client_uid)
            raise

    return router
