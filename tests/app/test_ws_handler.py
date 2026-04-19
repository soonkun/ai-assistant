# tests/app/test_ws_handler.py
"""AppWebSocketHandler 신규 3종 메시지 핸들러 테스트."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.ws_route import init_app_ws_route

from app.config import AppConfig
from app.ws_handler import AppWebSocketHandler, ContinuousCaptureTask
from open_llm_vtuber.websocket_handler import WebSocketHandler


# ── A-4 테스트: 실제 AppWebSocketHandler 경로를 통해 바이너리 프레임 동작 검증 ──
# 실제 handle_websocket_communication 루프를 거쳐 upstream 동작을 검증한다.
# upstream websocket_handler.py 분석 결과:
#   receive_json()에 binary 프레임 도착 시 → ValueError("Data is not text") 발생
#   → except json.JSONDecodeError 가 아닌 except Exception 경로로 진입
#   → await websocket.send_text(json.dumps({"type": "error", "message": str(e)})) 호출 후 continue
#   (스펙 A-4의 "error 메시지 송신 없이 continue" 설명은 upstream 실제 동작과 다름)
# 이 테스트는 spec 설명이 아닌 upstream 실제 코드 동작을 회귀 방지 목적으로 고정한다.


def _make_handler() -> tuple[AppWebSocketHandler, MagicMock]:
    """AppWebSocketHandler와 dummy context cache를 반환."""
    ctx = MagicMock()
    ctx.screenshot_service = None
    ctx.app_config = AppConfig()  # type: ignore[call-arg]
    ctx.config = MagicMock()
    ctx.system_config = MagicMock()
    ctx.character_config = MagicMock()
    ctx.live2d_model = MagicMock()
    ctx.live2d_model.model_info = {}

    with patch(
        "open_llm_vtuber.websocket_handler.WebSocketHandler.__init__",
        return_value=None,
    ):
        handler = AppWebSocketHandler.__new__(AppWebSocketHandler)

    handler.default_context_cache = ctx
    handler.client_connections = {}
    handler.client_contexts = {}
    handler.chat_group_manager = MagicMock()
    handler.current_conversation_tasks = {}
    handler.received_data_buffers = {}
    handler._continuous_tasks = {}
    handler._tasks_lock = asyncio.Lock()
    handler._message_handlers = handler._init_message_handlers()
    return handler, ctx


def _make_websocket() -> MagicMock:
    ws = MagicMock()
    ws.send_json = AsyncMock()
    ws.send_text = AsyncMock()
    return ws


class TestInitMessageHandlers:
    """N-4: 신규 메시지 타입 등록 확인."""

    def test_n4_new_handlers_registered(self) -> None:
        handler, _ = _make_handler()
        handlers = handler._init_message_handlers()
        assert "screenshot-trigger" in handlers
        assert "start-continuous-capture" in handlers
        assert "stop-continuous-capture" in handlers

    def test_n4_upstream_handlers_preserved(self) -> None:
        handler, _ = _make_handler()
        handlers = handler._init_message_handlers()
        assert "text-input" in handlers
        assert "heartbeat" in handlers
        assert "interrupt-signal" in handlers


class TestScreenshotTrigger:
    """screenshot-trigger 핸들러 테스트."""

    @pytest.mark.asyncio
    async def test_n4_monitor_index_region_ignored_with_warn(self) -> None:
        """N-4 (CR-05): monitor_index=5, region 비기본값 → capture_once()만 호출, WARN 1회 로그.

        ws_handler는 loguru를 사용하므로 stdlib caplog 대신 loguru sink를 직접 intercept한다.
        """
        from loguru import logger as loguru_logger

        handler, ctx = _make_handler()
        ws = _make_websocket()

        svc = MagicMock()
        svc.capture_once = AsyncMock(return_value="data:image/png;base64,iVBORw0KGgo=")
        ctx.screenshot_service = svc
        handler.client_contexts["uid1"] = ctx

        captured_warnings: list[str] = []

        def _sink(message: object) -> None:
            record = message.record
            if record["level"].name == "WARNING":
                captured_warnings.append(record["message"])

        sink_id = loguru_logger.add(_sink, level="WARNING")
        try:
            with patch.object(handler, "_handle_conversation_trigger", new_callable=AsyncMock):
                await handler._handle_screenshot_trigger(
                    ws,
                    "uid1",
                    {
                        "type": "screenshot-trigger",
                        "monitor_index": 5,
                        "region": {"x": 0, "y": 0, "w": 100, "h": 100},
                    },
                )
        finally:
            loguru_logger.remove(sink_id)

        # capture_once()만 호출됨 (capture() 아님)
        svc.capture_once.assert_called_once()

        # WARN 로그 1회 — "V1에서 무시됨" 포함
        v1_warns = [m for m in captured_warnings if "V1에서 무시됨" in m]
        assert len(v1_warns) >= 1, f"WARN 로그 미발생. 캡처된 WARNING 메시지: {captured_warnings}"

    @pytest.mark.asyncio
    async def test_service_unavailable_sends_error(self) -> None:
        handler, ctx = _make_handler()
        ws = _make_websocket()
        ctx.screenshot_service = None
        handler.client_contexts["uid1"] = ctx

        await handler._handle_screenshot_trigger(ws, "uid1", {"type": "screenshot-trigger"})

        ws.send_json.assert_called_once()
        msg = ws.send_json.call_args[0][0]
        assert msg["type"] == "error"
        assert "screenshot_failed" in msg["message"]

    @pytest.mark.asyncio
    async def test_e5_region_capture_failure_sends_error(self) -> None:
        """E-5: 캡처 실패 시 error 메시지 송신, 예외 전파 없음."""
        handler, ctx = _make_handler()
        ws = _make_websocket()

        svc = MagicMock()
        # CR-05: capture_once() 사용으로 교체
        svc.capture_once = AsyncMock(side_effect=ValueError("capture failed"))
        ctx.screenshot_service = svc
        handler.client_contexts["uid1"] = ctx

        await handler._handle_screenshot_trigger(
            ws,
            "uid1",
            {"type": "screenshot-trigger", "region": {"x": 99999, "y": 0, "w": 100, "h": 100}},
        )

        ws.send_json.assert_called_once()
        msg = ws.send_json.call_args[0][0]
        assert msg["type"] == "error"
        assert "screenshot_failed" in msg["message"]

    @pytest.mark.asyncio
    async def test_a5_oversized_prompt_rejected(self) -> None:
        """A-5: 1MiB prompt → 256KiB 상한 위반 → error, 캡처 안 함."""
        handler, ctx = _make_handler()
        ws = _make_websocket()

        svc = MagicMock()
        # CR-05: capture_once() 사용으로 교체
        svc.capture_once = AsyncMock(return_value="data:image/png;base64,iVBORw0KGgo=")
        ctx.screenshot_service = svc
        handler.client_contexts["uid1"] = ctx

        big_prompt = "A" * (1024 * 1024 + 1)  # > 1MiB
        await handler._handle_screenshot_trigger(
            ws, "uid1", {"type": "screenshot-trigger", "prompt": big_prompt}
        )

        ws.send_json.assert_called_once()
        msg = ws.send_json.call_args[0][0]
        assert msg["type"] == "error"
        svc.capture_once.assert_not_called()


class TestContinuousCapture:
    """start/stop-continuous-capture 핸들러 테스트."""

    @pytest.mark.asyncio
    async def test_start_registers_task(self) -> None:
        handler, ctx = _make_handler()
        ws = _make_websocket()

        svc = MagicMock()
        # CR-05: capture_once() 사용으로 교체
        svc.capture_once = AsyncMock(return_value="data:image/png;base64,iVBORw0KGgo=")
        ctx.screenshot_service = svc
        handler.client_contexts["uid1"] = ctx

        await handler._handle_start_continuous_capture(
            ws, "uid1", {"type": "start-continuous-capture", "interval_sec": 10}
        )

        assert "uid1" in handler._continuous_tasks
        ws.send_json.assert_called_once()
        msg = ws.send_json.call_args[0][0]
        assert msg["type"] == "continuous-capture-state"
        assert msg["running"] is True
        assert msg["interval_sec"] == 10

        # 정리
        await handler._cancel_continuous_task("uid1")

    @pytest.mark.asyncio
    async def test_start_monitor_index_region_ignored_with_warn(self) -> None:
        """CR-05 MAJOR-3 수정: start-continuous-capture도 비기본값 WARN 1회."""
        from loguru import logger as loguru_logger

        handler, ctx = _make_handler()
        ws = _make_websocket()

        svc = MagicMock()
        svc.capture_once = AsyncMock(return_value="data:image/png;base64,iVBORw0KGgo=")
        ctx.screenshot_service = svc
        handler.client_contexts["uid1"] = ctx

        captured_warnings: list[str] = []

        def _sink(message: object) -> None:
            record = message.record
            if record["level"].name == "WARNING":
                captured_warnings.append(record["message"])

        sink_id = loguru_logger.add(_sink, level="WARNING")
        try:
            await handler._handle_start_continuous_capture(
                ws,
                "uid1",
                {
                    "type": "start-continuous-capture",
                    "interval_sec": 10,
                    "monitor_index": 5,
                    "region": {"x": 0, "y": 0, "w": 100, "h": 100},
                },
            )
        finally:
            loguru_logger.remove(sink_id)
            await handler._cancel_continuous_task("uid1")

        v1_warns = [m for m in captured_warnings if "V1에서 무시됨" in m]
        assert len(v1_warns) >= 1, f"WARN 로그 미발생. 캡처된: {captured_warnings}"

    @pytest.mark.asyncio
    async def test_n6_stop_cancels_task(self) -> None:
        """N-6: stop-continuous-capture → 태스크 취소, running=False 응답."""
        handler, ctx = _make_handler()
        ws = _make_websocket()
        handler.client_contexts["uid1"] = ctx

        # 실행 중인 태스크 직접 등록
        loop_task = asyncio.create_task(asyncio.sleep(999))
        handler._continuous_tasks["uid1"] = ContinuousCaptureTask(
            client_uid="uid1",
            interval_sec=5,
            monitor_index=0,
            prompt_template="",
            task=loop_task,
        )

        await handler._handle_stop_continuous_capture(ws, "uid1", {})

        assert "uid1" not in handler._continuous_tasks
        assert loop_task.cancelled() or loop_task.done()
        ws.send_json.assert_called_once()
        msg = ws.send_json.call_args[0][0]
        assert msg["type"] == "continuous-capture-state"
        assert msg["running"] is False

    @pytest.mark.asyncio
    async def test_stop_no_task_no_error(self) -> None:
        """태스크 없을 때 stop → no-op, {running:false} 응답."""
        handler, ctx = _make_handler()
        ws = _make_websocket()

        await handler._handle_stop_continuous_capture(ws, "uid_none", {})

        ws.send_json.assert_called_once()
        msg = ws.send_json.call_args[0][0]
        assert msg["running"] is False

    @pytest.mark.asyncio
    async def test_invalid_interval_sends_error(self) -> None:
        """interval_sec 범위 위반 → error 메시지."""
        handler, ctx = _make_handler()
        ws = _make_websocket()
        handler.client_contexts["uid1"] = ctx

        await handler._handle_start_continuous_capture(
            ws, "uid1", {"type": "start-continuous-capture", "interval_sec": 0}
        )

        ws.send_json.assert_called_once()
        msg = ws.send_json.call_args[0][0]
        assert msg["type"] == "error"
        assert "interval_sec" in msg["message"]

    @pytest.mark.asyncio
    async def test_e3_duplicate_start_replaces_task(self) -> None:
        """E-3: 연속 캡처 중복 시작 → 기존 태스크 취소, 새 태스크 등록."""
        handler, ctx = _make_handler()
        ws = _make_websocket()
        handler.client_contexts["uid1"] = ctx

        first_task = asyncio.create_task(asyncio.sleep(999))
        handler._continuous_tasks["uid1"] = ContinuousCaptureTask(
            client_uid="uid1",
            interval_sec=5,
            monitor_index=0,
            prompt_template="",
            task=first_task,
        )

        await handler._handle_start_continuous_capture(
            ws, "uid1", {"type": "start-continuous-capture", "interval_sec": 3}
        )

        assert first_task.cancelled() or first_task.done()
        assert "uid1" in handler._continuous_tasks
        assert handler._continuous_tasks["uid1"].interval_sec == 3
        assert len(handler._continuous_tasks) == 1

        # 정리
        await handler._cancel_continuous_task("uid1")

    @pytest.mark.asyncio
    async def test_e4_disconnect_cancels_task(self) -> None:
        """E-4: handle_disconnect 경로에서 태스크 취소 및 _continuous_tasks에서 제거."""
        handler, ctx = _make_handler()

        loop_task = asyncio.create_task(asyncio.sleep(999))
        handler._continuous_tasks["uid1"] = ContinuousCaptureTask(
            client_uid="uid1",
            interval_sec=5,
            monitor_index=0,
            prompt_template="",
            task=loop_task,
        )

        # handle_disconnect를 직접 호출하되 upstream super().handle_disconnect는 Mock으로 패치
        with patch.object(WebSocketHandler, "handle_disconnect", new_callable=AsyncMock):
            await handler.handle_disconnect("uid1")

        assert "uid1" not in handler._continuous_tasks
        assert loop_task.cancelled() or loop_task.done()


class TestDoSResilience:
    """A-3: start-continuous-capture 스팸 DoS."""

    @pytest.mark.asyncio
    async def test_a3_spam_keeps_one_task(self) -> None:
        """A-3: 100회 연속 start 후에도 _continuous_tasks는 1건 이하.

        MAJOR-10: RSS 기반 비결정적 어서션 제거 → 상태 기반 어서션으로 교체.
        """
        handler, ctx = _make_handler()
        ws = _make_websocket()
        handler.client_contexts["uid1"] = ctx

        previous_task = None
        for i in range(100):  # 스펙 명세: 100회
            # 50번째 직전에 현재 태스크 참조 저장
            if i == 50 and handler._continuous_tasks:
                previous_task = list(handler._continuous_tasks.values())[0].task

            await handler._handle_start_continuous_capture(
                ws, "uid1", {"type": "start-continuous-capture", "interval_sec": 5}
            )
            await asyncio.sleep(0)

        # 핵심 상태 검증: 항상 1건 이하
        assert len(handler._continuous_tasks) <= 1, (
            f"_continuous_tasks에 {len(handler._continuous_tasks)}건이 존재 (1건 이하여야 함)"
        )

        # 50번째에 포착한 태스크는 이후 교체돼 done/cancelled 상태여야 함
        if previous_task is not None:
            assert previous_task.done(), "이전 태스크가 취소 또는 완료 상태가 아님"

        # 정리
        await handler._cancel_continuous_task("uid1")


class TestBinaryFrame:
    """A-4: 바이너리 프레임 주입 테스트 — 실제 AppWebSocketHandler 경로 사용."""

    def test_a4_binary_frame_error_sent(self) -> None:
        """A-4: TestClient로 실제 AppWebSocketHandler를 통해 binary frame 동작 검증.

        upstream websocket_handler.py handle_websocket_communication 실제 동작:
          1. receive_json()에 binary 프레임 도착
             → Starlette가 ValueError("Data is not text") 발생
          2. except json.JSONDecodeError: 는 매칭 안 됨 (ValueError ≠ JSONDecodeError)
          3. except Exception as e: 경로로 진입
             → send_text(json.dumps({"type": "error", "message": str(e)})) 호출 후 continue

        즉 binary 프레임 수신 시 서버는 {"type": "error"} 메시지를 송신한 뒤 루프를 계속한다.

        NOTE: spec §A-4의 설명("error 메시지 송신 없이 continue")은 upstream 실제 코드와 다르다.
        이 테스트는 spec 설명이 아닌 upstream 코드의 실제 동작을 회귀 방지 목적으로 고정한다.

        구현 참조: upstream/Open-LLM-VTuber/src/open_llm_vtuber/websocket_handler.py L214-234
        """
        ctx = MagicMock()
        ctx.screenshot_service = None
        ctx.app_config = None
        ctx.config = MagicMock()
        ctx.system_config = MagicMock()
        ctx.character_config = MagicMock()
        ctx.character_config.conf_name = "saessagi"
        ctx.character_config.conf_uid = "saessagi-v1"
        ctx.live2d_model = MagicMock()
        ctx.live2d_model.model_info = {}

        # handle_new_connection / handle_disconnect 을 no-op AsyncMock으로 패치해
        # upstream 서비스 초기화와 정리 로직을 건너뜀.
        # handle_websocket_communication 경로만 실제 upstream 코드로 실행한다.
        # 패치는 TestClient 요청 처리 중에도 활성 상태여야 하므로 단일 with 블록 안에서 수행.
        with (
            patch(
                "open_llm_vtuber.websocket_handler.WebSocketHandler.__init__",
                return_value=None,
            ),
            patch.object(
                AppWebSocketHandler,
                "handle_new_connection",
                new_callable=AsyncMock,
            ),
            patch.object(
                AppWebSocketHandler,
                "handle_disconnect",
                new_callable=AsyncMock,
            ),
        ):
            router = init_app_ws_route(ctx)

            test_app = FastAPI()
            test_app.include_router(router)

            client = TestClient(test_app)
            with client.websocket_connect("/client-ws") as ws:
                # binary 프레임 전송 — 서버에서 ValueError → except Exception → error 메시지 송신
                ws.send_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")

                # 핵심 검증: upstream except Exception 경로로 error 메시지가 송신됨
                response = ws.receive_json()
                assert response.get("type") == "error", (
                    f"바이너리 프레임 후 error 메시지 미수신 (실제 응답: {response}). "
                    "upstream except Exception 경로가 error 메시지를 송신해야 함."
                )
                # 메시지에 ValueError 내용("Data is not text") 포함 여부 확인
                assert "message" in response, "error 응답에 'message' 필드가 없음"


class TestContinuousLoopFailure:
    """연속 캡처 루프 3회 실패 테스트."""

    @pytest.mark.asyncio
    async def test_three_consecutive_failures_stops_loop(self) -> None:
        """연속 캡처 루프에서 3회 연속 예외 발생 시 루프 종료 + error 메시지 전송."""
        handler, ctx = _make_handler()
        ws = _make_websocket()

        # 캡처가 항상 실패하는 mock (CR-05: capture_once() 사용으로 교체)
        svc = MagicMock()
        svc.capture_once = AsyncMock(side_effect=RuntimeError("capture device unavailable"))
        ctx.screenshot_service = svc

        # default_context_cache에 screenshot_service 설정 (CRITICAL #1 수정 반영)
        handler.default_context_cache.screenshot_service = svc

        # interval을 0으로 설정해 sleep 없이 빠르게 실행
        # asyncio.sleep을 패치해 즉시 리턴
        with patch("asyncio.sleep", new_callable=AsyncMock):
            loop_coro = handler._continuous_capture_loop(ws, "uid1", 1, 0, "test prompt")
            await loop_coro

        # 3회 실패 후 루프가 종료되어야 함
        # error 메시지가 전송됐는지 확인
        ws.send_json.assert_called_once()
        msg = ws.send_json.call_args[0][0]
        assert msg["type"] == "error"
        assert "continuous capture failed 3 times" in msg["message"]
        # 3회 캡처 시도 확인
        assert svc.capture_once.call_count == 3
