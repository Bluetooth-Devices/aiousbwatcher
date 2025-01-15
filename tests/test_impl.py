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
        unregister()
        stop()
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        assert not called
