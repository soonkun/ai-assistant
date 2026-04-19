# src/tool_router/screenshot.py
"""ScreenshotService — Windows 전체 화면 캡처 + 연속 모드."""

import asyncio
import base64
import contextlib
import io
import logging
import platform
from collections.abc import Awaitable, Callable
from typing import Any

from .errors import ScreenshotCaptureError, ScreenshotInitError

logger = logging.getLogger(__name__)

SendTextCallback = Callable[[dict[str, Any]], Awaitable[None]]

_PRIVACY_WARNING_TEXT = "연속 화면 공유를 시작합니다. 개인정보가 포함될 수 있으니 필요 시 '화면 공유 중지'라고 말씀해 주세요."


class ScreenshotService:
    """Windows 전체 화면 캡처 + 연속 모드.

    외부 모듈 의존 없음(M_05b 내부 전용). 연속 모드는 단일 인스턴스에서 **동시 1개**만
    허용한다. 다중 모니터 환경에서는 monitor=1(primary) 고정(V1).
    """

    def __init__(
        self,
        send_text: SendTextCallback | None = None,
        interval_min: float = 1.0,
        interval_max: float = 60.0,
    ) -> None:
        """
        Args:
            send_text: 연속 모드 진입 시 {"type":"privacy_warning","text":...} 이벤트를
                       전송할 비동기 콜백(WebSocket send_text). None이면 경고는 로그로만.
            interval_min: 연속 모드 허용 최소 주기(초). 기본 1.0.
            interval_max: 연속 모드 허용 최대 주기(초). 기본 60.0.

        Raises:
            ScreenshotInitError: platform.system() != "Windows", mss import 실패, 권한 부족.
        """
        if platform.system() != "Windows":
            raise ScreenshotInitError(
                f"ScreenshotService는 Windows에서만 동작합니다. 현재 OS: {platform.system()}"
            )

        try:
            import mss

            self._sct = mss.mss()
        except ImportError as exc:
            raise ScreenshotInitError(f"mss 패키지를 불러올 수 없습니다: {exc}") from exc
        except Exception as exc:
            raise ScreenshotInitError(f"mss 초기화 실패: {exc}") from exc

        self._send_text = send_text
        self._interval_min = interval_min
        self._interval_max = interval_max
        self._task: asyncio.Task[None] | None = None
        self._stop_event: asyncio.Event | None = None

        logger.info("ScreenshotService 초기화 완료.")

    def _capture_sync(self) -> str:
        """동기 캡처 — run_in_executor에서 실행됨.

        mss 인스턴스는 스레드 안전하지 않으므로 매번 새로 생성한다.

        Returns:
            "data:image/png;base64,..." 형식의 data URL.

        Raises:
            ScreenshotCaptureError: 캡처 또는 인코딩 실패.
        """
        try:
            import mss as mss_module
            from PIL import Image

            with mss_module.mss() as sct:
                monitor = sct.monitors[1]
                sct_img = sct.grab(monitor)
                w, h = sct_img.width, sct_img.height
                img = Image.frombytes("RGB", (w, h), sct_img.rgb)

            buf = io.BytesIO()
            img.save(buf, format="PNG", compress_level=6)
            raw = buf.getvalue()
            encoded = base64.b64encode(raw).decode("ascii")
            data_url = f"data:image/png;base64,{encoded}"

            size_mb = len(raw) / (1024 * 1024)
            if size_mb > 8:
                logger.warning("캡처 PNG 크기가 8MB 초과: %.1f MB", size_mb)

            logger.debug("캡처 완료: %dx%d, PNG %.1f KB", w, h, len(raw) / 1024)
            return data_url

        except ScreenshotInitError:
            raise
        except Exception as exc:
            raise ScreenshotCaptureError(f"화면 캡처 실패: {exc}") from exc

    async def capture_once(self) -> str:
        """단건 캡처. primary monitor 전체 화면을 PNG로 압축해 base64 data URL 반환.

        반환 형식: "data:image/png;base64,iVBORw0KGgo..."

        blocking I/O(mss.grab, PIL encode)를 run_in_executor로 분리해 이벤트 루프를 차단하지 않는다.

        Raises:
            ScreenshotCaptureError: 디스플레이 핸들 획득 실패, 인코딩 실패.
        """
        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(None, self._capture_sync)
        except ScreenshotCaptureError:
            raise
        except Exception as exc:
            raise ScreenshotCaptureError(f"화면 캡처 실패: {exc}") from exc

    async def start_continuous(
        self,
        interval_seconds: float,
        on_frame: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        """연속 모드 시작.

        1) interval_seconds가 [interval_min, interval_max] 밖이면 ValueError.
        2) 이미 실행 중이면 ScreenshotCaptureError("continuous_already_running").
        3) 첫 작업: send_text로 privacy_warning 이벤트 emit.
        4) asyncio.create_task로 _loop(interval_seconds, on_frame) 스케줄.
        """
        if not (self._interval_min <= interval_seconds <= self._interval_max):
            raise ValueError(
                f"interval_seconds={interval_seconds}는 허용 범위"
                f" [{self._interval_min}, {self._interval_max}] 밖입니다."
            )

        if self._task is not None and not self._task.done():
            raise ScreenshotCaptureError("continuous_already_running")

        warning_payload: dict[str, Any] = {
            "type": "privacy_warning",
            "text": _PRIVACY_WARNING_TEXT,
            "interval_seconds": interval_seconds,
        }
        if self._send_text is not None:
            await self._send_text(warning_payload)
        else:
            logger.warning("privacy_warning: %s", _PRIVACY_WARNING_TEXT)

        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._loop(interval_seconds, on_frame))
        logger.info("연속 캡처 모드 시작: interval=%.1f초", interval_seconds)

    async def _loop(
        self,
        interval_seconds: float,
        on_frame: Callable[[str], Awaitable[None]] | None,
    ) -> None:
        """연속 캡처 루프."""
        assert self._stop_event is not None
        try:
            while not self._stop_event.is_set():
                try:
                    data_url = await self.capture_once()
                    if on_frame is not None:
                        await on_frame(data_url)
                except ScreenshotInitError:
                    logger.error("연속 캡처 중단: 디스플레이 연결 해제")
                    break
                except ScreenshotCaptureError as exc:
                    logger.warning("캡처 틱 실패: %s", exc)

                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=interval_seconds)
                except asyncio.TimeoutError:
                    continue
        finally:
            logger.info("연속 캡처 루프 종료")

    async def stop_continuous(self) -> None:
        """연속 모드 종료. 실행 중이 아니면 no-op(에러 아님)."""
        if self._task is None:
            return

        if self._stop_event is not None:
            self._stop_event.set()

        try:
            await asyncio.wait_for(self._task, timeout=5.0)
        except asyncio.TimeoutError:
            self._task.cancel()
            with contextlib.suppress(BaseException):
                await self._task
        except asyncio.CancelledError:
            pass

        self._task = None
        self._stop_event = None
        logger.info("연속 캡처 모드 중지 완료.")

    @property
    def is_continuous_running(self) -> bool:
        """연속 모드가 현재 실행 중인지 반환."""
        return self._task is not None and not self._task.done()

    async def aclose(self) -> None:
        """종료 정리. stop_continuous() + mss 리소스 해제."""
        await self.stop_continuous()
        try:
            self._sct.close()
        except Exception as exc:
            logger.warning("mss 리소스 해제 실패: %s", exc)
        logger.info("ScreenshotService 종료 완료.")
