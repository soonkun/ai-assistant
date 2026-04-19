# tests/tool_router/test_screenshot.py
"""ScreenshotService 단위 테스트 — non-Windows error, continuous lifecycle."""

import platform
import sys
from types import ModuleType
from typing import Any
from unittest.mock import patch

import pytest

from src.tool_router.errors import ScreenshotCaptureError, ScreenshotInitError


def _make_fake_mss_module() -> ModuleType:
    """fake mss 모듈 반환."""
    fake_mss = ModuleType("mss")

    class FakeSctImg:
        width = 1920
        height = 1080
        rgb = b"\x00" * (1920 * 1080 * 3)

    class FakeSct:
        monitors = [
            {"left": 0, "top": 0, "width": 3840, "height": 1080},  # index 0: all
            {"left": 0, "top": 0, "width": 1920, "height": 1080},  # index 1: primary
        ]

        def grab(self, monitor: Any) -> FakeSctImg:
            return FakeSctImg()

        def close(self) -> None:
            pass

        def __enter__(self) -> "FakeSct":
            return self

        def __exit__(self, *args: Any) -> None:
            self.close()

    def fake_mss_constructor() -> FakeSct:
        return FakeSct()

    fake_mss.mss = fake_mss_constructor  # type: ignore[attr-defined]
    return fake_mss


def _make_fake_pil_module() -> ModuleType:
    """fake PIL.Image 모듈 반환 (sys.modules 등록은 호출자가 담당)."""
    import io

    pil_mod = ModuleType("PIL")
    image_mod = ModuleType("PIL.Image")

    class FakeImage:
        def save(self, buf: io.BytesIO, format: str, compress_level: int = 6) -> None:
            buf.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)  # minimal fake PNG

    def frombytes(mode: str, size: tuple, data: bytes) -> FakeImage:
        return FakeImage()

    image_mod.frombytes = frombytes  # type: ignore[attr-defined]
    pil_mod.Image = image_mod  # type: ignore[attr-defined]
    return pil_mod


@pytest.fixture(autouse=True)
def install_fakes(monkeypatch: pytest.MonkeyPatch) -> None:
    """모든 테스트에 fake mss/PIL 설치. monkeypatch를 사용해 테스트 종료 후 자동 복원."""

    pil_mod = _make_fake_pil_module()
    monkeypatch.setitem(sys.modules, "mss", _make_fake_mss_module())
    monkeypatch.setitem(sys.modules, "PIL", pil_mod)
    monkeypatch.setitem(sys.modules, "PIL.Image", pil_mod.Image)  # type: ignore[attr-defined]


def test_screenshot_init_error_on_non_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    """non-Windows에서 ScreenshotInitError raise."""
    monkeypatch.setattr(platform, "system", lambda: "Linux")

    # 모듈 재임포트 없이 patch
    from src.tool_router import screenshot as ss_module

    with patch.object(ss_module.platform, "system", return_value="Linux"):
        with pytest.raises(ScreenshotInitError):
            from src.tool_router.screenshot import ScreenshotService

            ScreenshotService()


def test_screenshot_init_success_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    """Windows에서 ScreenshotService 초기화 성공."""
    from src.tool_router import screenshot as ss_module

    with patch.object(ss_module.platform, "system", return_value="Windows"):
        from src.tool_router.screenshot import ScreenshotService

        svc = ScreenshotService()
        assert svc is not None


async def test_capture_once_returns_data_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """capture_once가 data:image/png;base64, 형식 반환."""
    from src.tool_router import screenshot as ss_module

    with patch.object(ss_module.platform, "system", return_value="Windows"):
        from src.tool_router.screenshot import ScreenshotService

        svc = ScreenshotService()
        data_url = await svc.capture_once()
        assert data_url.startswith("data:image/png;base64,")


async def test_continuous_mode_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    """연속 모드 시작 → 실행 중 → 중지 lifecycle."""
    from src.tool_router import screenshot as ss_module

    with patch.object(ss_module.platform, "system", return_value="Windows"):
        from src.tool_router.screenshot import ScreenshotService

        send_text_calls: list[dict] = []

        async def mock_send(msg: dict) -> None:
            send_text_calls.append(msg)

        svc = ScreenshotService(send_text=mock_send, interval_min=0.1, interval_max=60.0)

        assert not svc.is_continuous_running
        await svc.start_continuous(0.5)
        assert svc.is_continuous_running
        assert len(send_text_calls) == 1
        assert send_text_calls[0]["type"] == "privacy_warning"

        await svc.stop_continuous()
        assert not svc.is_continuous_running


async def test_continuous_mode_already_running_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """이미 실행 중인 상태에서 start_continuous → ScreenshotCaptureError."""
    from src.tool_router import screenshot as ss_module

    with patch.object(ss_module.platform, "system", return_value="Windows"):
        from src.tool_router.screenshot import ScreenshotService

        svc = ScreenshotService(interval_min=0.1, interval_max=60.0)
        await svc.start_continuous(0.5)
        assert svc.is_continuous_running

        with pytest.raises(ScreenshotCaptureError, match="continuous_already_running"):
            await svc.start_continuous(0.5)

        await svc.stop_continuous()


async def test_continuous_mode_invalid_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    """interval 범위 밖 → ValueError."""
    from src.tool_router import screenshot as ss_module

    with patch.object(ss_module.platform, "system", return_value="Windows"):
        from src.tool_router.screenshot import ScreenshotService

        svc = ScreenshotService()
        with pytest.raises(ValueError):
            await svc.start_continuous(0.1)  # < interval_min(1.0)


async def test_stop_continuous_noop_when_not_running(monkeypatch: pytest.MonkeyPatch) -> None:
    """stop_continuous가 실행 중이 아닐 때 no-op."""
    from src.tool_router import screenshot as ss_module

    with patch.object(ss_module.platform, "system", return_value="Windows"):
        from src.tool_router.screenshot import ScreenshotService

        svc = ScreenshotService()
        # 예외 없이 완료
        await svc.stop_continuous()
        assert not svc.is_continuous_running
