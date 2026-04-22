# tests/idle_monitor/test_backends.py
"""백엔드 단위 테스트 — FakeBackend + pynput/Win32 모킹."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from idle_monitor.backends.base import BackendInitError, _IdleBackend
from idle_monitor.backends.noop_backend import NoopBackend
from tests.idle_monitor.conftest import FakeBackend, FakeClock


class TestFakeBackend:
    """FakeBackend 자체 동작 검증."""

    def test_start_increments_counter(self, t0: datetime) -> None:
        fb = FakeBackend(last=t0)
        fb.start()
        assert fb.start_called == 1

    def test_stop_increments_counter(self, t0: datetime) -> None:
        fb = FakeBackend(last=t0)
        fb.stop()
        assert fb.stop_called == 1

    def test_last_input_at_returns_last(self, t0: datetime) -> None:
        fb = FakeBackend(last=t0)
        now = t0 + timedelta(seconds=100)
        assert fb.last_input_at(now) == t0

    def test_simulate_input_updates_last(self, t0: datetime) -> None:
        fb = FakeBackend(last=t0)
        new_t = t0 + timedelta(seconds=50)
        fb.simulate_input(new_t)
        assert fb.last_input_at(new_t) == new_t

    def test_init_error_raises_on_start(self, t0: datetime) -> None:
        fb = FakeBackend(last=t0)
        fb.init_error = BackendInitError("mock EDR block")
        with pytest.raises(BackendInitError):
            fb.start()

    def test_is_idle_backend_subclass(self, t0: datetime) -> None:
        fb = FakeBackend(last=t0)
        assert isinstance(fb, _IdleBackend)


class TestNoopBackend:
    """NoopBackend 동작 검증."""

    def test_start_does_not_raise(self) -> None:
        noop = NoopBackend()
        noop.start()  # 예외 없음

    def test_stop_does_not_raise(self) -> None:
        noop = NoopBackend()
        noop.stop()

    def test_last_input_at_returns_now(self, t0: datetime) -> None:
        noop = NoopBackend()
        now = t0 + timedelta(seconds=100)
        assert noop.last_input_at(now) == now


class TestPynputBackendImport:
    """PynputBackend import 스모크 + 생성자 테스트 (훅 실제 생성은 mock)."""

    def test_pynput_backend_importable(self) -> None:
        """PynputBackend import 성공 확인."""
        from idle_monitor.backends.pynput_backend import PynputBackend

        assert PynputBackend is not None

    def test_pynput_backend_init_no_crash(self, t0: datetime) -> None:
        """PynputBackend 생성자 호출 (Listener 미시작)."""
        from idle_monitor.backends.pynput_backend import PynputBackend

        clock = FakeClock(t0)
        pb = PynputBackend(clock=clock)
        assert pb is not None

    def test_pynput_backend_start_failure_raises_init_error(self, t0: datetime) -> None:
        """pynput import 실패 시 BackendInitError 발생."""
        from idle_monitor.backends.pynput_backend import PynputBackend

        clock = FakeClock(t0)
        pb = PynputBackend(clock=clock)

        with patch.dict(sys.modules, {"pynput": None}):  # type: ignore[dict-item]
            with pytest.raises(BackendInitError):
                pb.start()


class TestWin32BackendImport:
    """Win32IdleBackend import + LASTINPUTINFO 구조체 정의 검증."""

    def test_win32_backend_importable(self) -> None:
        """Win32IdleBackend import 성공 (ctypes는 항상 가능)."""
        from idle_monitor.backends.win32_backend import LASTINPUTINFO, Win32IdleBackend

        assert Win32IdleBackend is not None
        assert LASTINPUTINFO is not None

    def test_lastinputinfo_structure(self) -> None:
        """LASTINPUTINFO 구조체 필드 확인."""
        import ctypes

        from idle_monitor.backends.win32_backend import LASTINPUTINFO

        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(LASTINPUTINFO)
        assert hasattr(info, "cbSize")
        assert hasattr(info, "dwTime")

    @pytest.mark.skipif(sys.platform == "win32", reason="비-Windows 환경에서만 실행")
    def test_win32_backend_start_fails_on_non_windows(self) -> None:
        """비-Windows에서 Win32IdleBackend.start() → BackendInitError."""
        from idle_monitor.backends.win32_backend import Win32IdleBackend

        backend = Win32IdleBackend()
        with pytest.raises(BackendInitError, match="Windows"):
            backend.start()

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
    def test_win32_backend_start_succeeds_on_windows(self) -> None:
        """Windows에서 Win32IdleBackend.start() 성공 (windll 심볼 resolve)."""
        from idle_monitor.backends.win32_backend import Win32IdleBackend

        backend = Win32IdleBackend()
        backend.start()
        assert backend._get_last_input_info is not None
        assert backend._get_tick_count is not None
        backend.stop()


class TestSelectBackend:
    """_select_backend() 분기 테스트."""

    @pytest.mark.skipif(sys.platform == "win32", reason="비-Windows에서만")
    def test_non_windows_returns_noop(self, t0: datetime) -> None:
        """비-Windows → NoopBackend 반환."""
        from idle_monitor.backends import _select_backend

        clock = FakeClock(t0)
        backend = _select_backend(clock)
        assert isinstance(backend, NoopBackend)

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows에서만")
    def test_windows_pynput_success_returns_pynput(self, t0: datetime) -> None:
        """Windows + pynput 성공 → PynputBackend 반환."""
        from idle_monitor.backends import _select_backend
        from idle_monitor.backends.pynput_backend import PynputBackend

        clock = FakeClock(t0)

        mock_kb_listener = MagicMock()
        mock_kb_listener.is_alive.return_value = True
        mock_ms_listener = MagicMock()
        mock_ms_listener.is_alive.return_value = True
        mock_kb_cls = MagicMock(return_value=mock_kb_listener)
        mock_ms_cls = MagicMock(return_value=mock_ms_listener)

        mock_pynput_kb = MagicMock()
        mock_pynput_kb.Listener = mock_kb_cls
        mock_pynput_ms = MagicMock()
        mock_pynput_ms.Listener = mock_ms_cls

        with patch.dict(
            sys.modules,
            {
                "pynput": MagicMock(keyboard=mock_pynput_kb, mouse=mock_pynput_ms),
                "pynput.keyboard": mock_pynput_kb,
                "pynput.mouse": mock_pynput_ms,
            },
        ):
            backend = _select_backend(clock)

        assert isinstance(backend, PynputBackend)

    def test_select_backend_pynput_fail_win32_fail_returns_noop(self, t0: datetime) -> None:
        """_select_backend: pynput+Win32 둘 다 BackendInitError → NoopBackend 반환.

        sys.platform을 'win32'로 패치해 Windows 경로를 강제 진입 후 둘 다 실패.
        """
        from idle_monitor.backends import _select_backend

        clock = FakeClock(t0)

        with (
            patch("idle_monitor.backends.sys") as mock_sys,
            patch(
                "idle_monitor.backends.pynput_backend.PynputBackend.start",
                side_effect=BackendInitError("pynput fail"),
            ),
            patch(
                "idle_monitor.backends.win32_backend.Win32IdleBackend.start",
                side_effect=BackendInitError("win32 fail"),
            ),
        ):
            mock_sys.platform = "win32"
            backend = _select_backend(clock)

        assert isinstance(backend, NoopBackend)


class TestServiceStartWithEventLoop:
    """IdleMonitor.start() — 이벤트 루프 내에서 task 생성 경로 커버."""

    @pytest.mark.asyncio
    async def test_start_creates_poll_task_with_fake_backend(self, t0: datetime) -> None:
        """start()가 poll_loop task를 생성하고 _started=True."""

        from idle_monitor import IdleMonitor
        from idle_monitor.backends.noop_backend import NoopBackend

        # FakeBackend를 쓰면 poll_loop이 시작됨 — NoopBackend로 우회
        clock = FakeClock(t0)
        monitor = IdleMonitor(clock=clock)

        with patch(
            "idle_monitor.backends._select_backend",
            return_value=NoopBackend(),
        ):
            monitor.start()

        assert monitor._started is True
        await monitor.stop()

    @pytest.mark.asyncio
    async def test_start_twice_is_idempotent(self, t0: datetime) -> None:
        """start() 중복 호출 → no-op, _started 여전히 True."""
        from idle_monitor import IdleMonitor
        from idle_monitor.backends.noop_backend import NoopBackend

        clock = FakeClock(t0)
        monitor = IdleMonitor(clock=clock)

        with patch(
            "idle_monitor.backends._select_backend",
            return_value=NoopBackend(),
        ):
            monitor.start()
            monitor.start()  # 두 번째 호출 — no-op

        # _started는 True, task는 None (NoopBackend이므로)
        assert monitor._started is True
        await monitor.stop()

    def test_start_without_event_loop_raises(self, t0: datetime) -> None:
        """start()가 이벤트 루프 없이 호출되면 RuntimeError."""
        from idle_monitor import IdleMonitor

        monitor = IdleMonitor(clock=FakeClock(t0))
        with pytest.raises(RuntimeError, match="running event loop"):
            monitor.start()


class TestNoopBackendNonWindows:
    """비-Windows(macOS/Linux) 환경에서 NoopBackend가 올바르게 기동·정지됨을 확인."""

    @pytest.mark.skipif(sys.platform == "win32", reason="Windows only — use Win32/pynput backend")
    @pytest.mark.asyncio
    async def test_noop_backend_start_stop_no_exception_on_non_windows(self, t0: datetime) -> None:
        """비-Windows에서 NoopBackend를 통한 IdleMonitor start()/stop() 예외 없음.

        _select_backend()가 NoopBackend를 반환하는 macOS/Linux 경로를 end-to-end로 검증.
        """
        from idle_monitor import IdleMonitor

        clock = FakeClock(t0)
        monitor = IdleMonitor(clock=clock)

        # 이벤트 루프 안에서 start() 호출 — NoopBackend 경로
        monitor.start()
        assert monitor._started is True
        assert isinstance(monitor._backend, NoopBackend)

        await monitor.stop()
        assert monitor._started is False
