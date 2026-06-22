import asyncio
from pathlib import Path
from sys import platform
from unittest.mock import patch

import pytest

from aiousbwatcher import AIOUSBWatcher, InotifyNotAvailableError

_INOTIFY_WAIT_TIME = 0.2


@pytest.mark.asyncio
@pytest.mark.skipif(platform == "linux", reason="Inotify is available on this platform")
async def test_aiousbwatcher_not_available() -> None:
    with pytest.raises(InotifyNotAvailableError):
        watcher = AIOUSBWatcher()
        watcher.async_start()


@pytest.mark.asyncio
@pytest.mark.skipif(
    platform != "linux", reason="Inotify not available on this platform"
)
async def test_aiousbwatcher_callbacks(tmp_path: Path) -> None:
    called: bool = False

    def callback() -> None:
        nonlocal called
        called = True

    with patch("aiousbwatcher.impl._PATH", str(tmp_path)):
        watcher = AIOUSBWatcher()
        unregister = watcher.async_register_callback(callback)
        stop = watcher.async_start()
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        assert not called
        (tmp_path / "test").touch()
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        assert called
        called = False  # type: ignore[unreachable]
        unregister()
        stop()
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        assert not called


@pytest.mark.asyncio
@pytest.mark.skipif(
    platform != "linux", reason="Inotify not available on this platform"
)
async def test_aiousbwatcher_broken_callbacks(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    called: bool = False

    def callback() -> None:
        nonlocal called
        called = True

    def broken_callback() -> None:
        raise Exception("Broken")

    with patch("aiousbwatcher.impl._PATH", str(tmp_path)):
        watcher = AIOUSBWatcher()
        unregister = watcher.async_register_callback(broken_callback)
        unregister2 = watcher.async_register_callback(callback)
        stop = watcher.async_start()
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        assert not called
        (tmp_path / "test").touch()
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        assert called
        called = False  # type: ignore[unreachable]
        assert "Broken" in caplog.text
        unregister()
        unregister2()
        stop()
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        assert not called


@pytest.mark.asyncio
@pytest.mark.skipif(
    platform != "linux", reason="Inotify not available on this platform"
)
async def test_aiousbwatcher_attempt_to_start_twice(tmp_path: Path) -> None:
    with patch("aiousbwatcher.impl._PATH", str(tmp_path)):
        watcher = AIOUSBWatcher()
        stop = watcher.async_start()
        with pytest.raises(RuntimeError):
            watcher.async_start()
        stop()


@pytest.mark.asyncio
@pytest.mark.skipif(
    platform != "linux", reason="Inotify not available on this platform"
)
async def test_aiousbwatcher_subdirs_added(tmp_path: Path) -> None:
    called: bool = False

    def callback() -> None:
        nonlocal called
        called = True

    with patch("aiousbwatcher.impl._PATH", str(tmp_path)):
        watcher = AIOUSBWatcher()
        unregister = watcher.async_register_callback(callback)
        stop = watcher.async_start()
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        assert not called
        (tmp_path / "test").mkdir()
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        assert called
        called = False  # type: ignore[unreachable]
        (tmp_path / "test" / "test2").touch()
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        assert called
        called = False
        (tmp_path / "test" / "test2").unlink()
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        assert called
        called = False
        (tmp_path / "test").rmdir()
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        assert called
        called = False
        (tmp_path / "test").mkdir()
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        assert called
        called = False
        (tmp_path / "test" / "test2").touch()
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        assert called
        called = False
        unregister()
        stop()
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        assert not called


_DEBOUNCE_TIME = 0.5


@pytest.mark.asyncio
@pytest.mark.skipif(
    platform != "linux", reason="Inotify not available on this platform"
)
async def test_aiousbwatcher_debounce_coalesces_bursts(tmp_path: Path) -> None:
    count: int = 0

    def callback() -> None:
        nonlocal count
        count += 1

    with patch("aiousbwatcher.impl._PATH", str(tmp_path)):
        watcher = AIOUSBWatcher(debounce=_DEBOUNCE_TIME)
        unregister = watcher.async_register_callback(callback)
        stop = watcher.async_start()
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        assert count == 0
        # A burst of events within the debounce window must not fire yet.
        for i in range(3):
            (tmp_path / f"test{i}").touch()
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        assert count == 0
        # Once the events go quiet for the debounce window, fire exactly once.
        await asyncio.sleep(_DEBOUNCE_TIME)
        assert count == 1
        unregister()
        stop()
        await asyncio.sleep(_DEBOUNCE_TIME + _INOTIFY_WAIT_TIME)
        assert count == 1


@pytest.mark.asyncio
@pytest.mark.skipif(
    platform != "linux", reason="Inotify not available on this platform"
)
async def test_aiousbwatcher_debounce_cancelled_on_stop(tmp_path: Path) -> None:
    count: int = 0

    def callback() -> None:
        nonlocal count
        count += 1

    with patch("aiousbwatcher.impl._PATH", str(tmp_path)):
        watcher = AIOUSBWatcher(debounce=_DEBOUNCE_TIME)
        unregister = watcher.async_register_callback(callback)
        stop = watcher.async_start()
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        (tmp_path / "test").touch()
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        # Stopping while a debounced callback is still pending must drop it.
        assert count == 0
        unregister()
        stop()
        await asyncio.sleep(_DEBOUNCE_TIME + _INOTIFY_WAIT_TIME)
        assert count == 0
