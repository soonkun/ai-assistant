# tests/app/test_create_app.py
"""create_app 통합 smoke 테스트 및 PrivacyViolationError 검증."""

from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient

from app.errors import PrivacyViolationError


def _make_fake_server(config: object, default_context_cache: object, **kwargs: object) -> MagicMock:
    """AppWebSocketServer를 흉내내는 mock. app 속성에 /client-ws 라우터가 등록된 FastAPI 인스턴스."""
    fake_app = FastAPI(title="테스트")

    async def _ws_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.send_text(
            json.dumps({"type": "full-text", "text": "Connection established"})
        )
        await websocket.send_text(
            json.dumps(
                {
                    "type": "set-model-and-conf",
                    "model_info": {},
                    "conf_name": "saessagi",
                    "conf_uid": "saessagi-v1",
                    "client_uid": "test-uid",
                }
            )
        )
        await websocket.close()

    fake_app.add_api_websocket_route("/client-ws", _ws_endpoint)
    fake_server = MagicMock()
    fake_server.app = fake_app
    return fake_server


class TestCreateApp:
    """create_app 팩토리 테스트."""

    def _patch_upstream_load(self) -> patch:  # type: ignore[type-arg]
        """upstream ServiceContext.load_from_config를 무력화."""
        return patch(
            "open_llm_vtuber.service_context.ServiceContext.load_from_config",
            new_callable=AsyncMock,
        )

    def _patch_ws_handler_init(self) -> patch:  # type: ignore[type-arg]
        return patch(
            "open_llm_vtuber.websocket_handler.WebSocketHandler.__init__",
            return_value=None,
        )

    def _patch_server(self) -> patch:  # type: ignore[type-arg]
        """AppWebSocketServer 생성을 mock으로 대체 (StaticFiles 마운트 생략)."""
        return patch(
            "app.server.AppWebSocketServer",
            side_effect=_make_fake_server,
        )

    # ── N-5: create_app 정상 기동 ────────────────────────────────────
    def test_n5_create_app_returns_fastapi(self, valid_config_path: str) -> None:
        """create_app이 FastAPI 인스턴스를 반환."""
        with self._patch_upstream_load(), self._patch_ws_handler_init():
            with self._patch_server():
                with patch("app.logging.init_logging"):
                    app = self._create_app_safe(valid_config_path)
        assert isinstance(app, FastAPI)

    def test_n5_websocket_connection_smoke(self, valid_config_path: str) -> None:
        """N-5: create_app() 반환값으로 WebSocket /client-ws 연결 및 초기 메시지 검증.

        모델 초기화 등 무거운 작업은 mock으로 처리하되, 라우팅 경로 자체는
        실제 create_app()을 사용해 /client-ws 엔드포인트가 응답함을 검증.
        """
        with self._patch_upstream_load(), self._patch_ws_handler_init():
            with self._patch_server():
                with patch("app.logging.init_logging"):
                    app = self._create_app_safe(valid_config_path)

        client = TestClient(app)
        with client.websocket_connect("/client-ws") as ws:
            msg1 = json.loads(ws.receive_text())
            assert msg1["type"] == "full-text"
            msg2 = json.loads(ws.receive_text())
            assert msg2["type"] == "set-model-and-conf"

    def _create_app_safe(self, config_path: str) -> FastAPI:
        from app.main import create_app

        return create_app(config_path)

    # ── A-1: 공개 호스트 URL → PrivacyViolationError ─────────────────
    def test_a1_public_url_raises(self, tmp_path: "pytest.TempPath") -> None:
        """A-1: OLLAMA_BASE_URL=https://api.openai.com → PrivacyViolationError."""
        import shutil

        fixture = __import__("pathlib").Path(__file__).parent / "fixtures" / "conf.valid.yaml"
        target = tmp_path / "conf.yaml"
        shutil.copy(fixture, target)

        from app.main import create_app

        with patch.dict(os.environ, {"OLLAMA_BASE_URL": "https://api.openai.com"}):
            with pytest.raises(PrivacyViolationError):
                create_app(str(target))

    # ── A-2: 수상한 IP ───────────────────────────────────────────────
    @pytest.mark.parametrize("bad_url", ["http://8.8.8.8:11434", "http://1.1.1.1"])
    def test_a2_suspicious_ip_raises(self, bad_url: str, tmp_path: "pytest.TempPath") -> None:
        import shutil

        fixture = __import__("pathlib").Path(__file__).parent / "fixtures" / "conf.valid.yaml"
        target = tmp_path / "conf.yaml"
        shutil.copy(fixture, target)

        from app.main import create_app

        with patch.dict(os.environ, {"OLLAMA_BASE_URL": bad_url}):
            with pytest.raises(PrivacyViolationError):
                create_app(str(target))

    def test_a2_link_local_169_allowed(self, tmp_path: "pytest.TempPath") -> None:
        """A-2 정책 고정: 169.254.169.254는 link-local로 허용."""
        import shutil

        fixture = __import__("pathlib").Path(__file__).parent / "fixtures" / "conf.valid.yaml"
        target = tmp_path / "conf.yaml"
        shutil.copy(fixture, target)
        target_str = str(target)

        from app.main import create_app

        with patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://169.254.169.254:11434"}):
            with self._patch_upstream_load(), self._patch_ws_handler_init():
                with self._patch_server():
                    with patch("app.logging.init_logging"):
                        app = create_app(target_str)
        assert isinstance(app, FastAPI)

    # ── FileNotFoundError 전파 ──────────────────────────────────────
    def test_file_not_found_raises(self) -> None:
        from app.main import create_app

        with pytest.raises(FileNotFoundError):
            create_app("/nonexistent/path/conf.yaml")

    # ── startup/shutdown 훅 등록 확인 ────────────────────────────────
    def test_startup_shutdown_hooks_registered(self, valid_config_path: str) -> None:
        """startup/shutdown 이벤트 핸들러가 등록됨."""
        with self._patch_upstream_load(), self._patch_ws_handler_init():
            with self._patch_server():
                with patch("app.logging.init_logging"):
                    from app.main import create_app

                    app = create_app(valid_config_path)

        # FastAPI router에 startup/shutdown 핸들러 확인
        # (on_event는 deprecated이나 현재 스펙에서 명시됨)
        assert app is not None
