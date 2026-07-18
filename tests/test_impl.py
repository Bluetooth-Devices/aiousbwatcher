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


@pytest.mark.asyncio
@pytest.mark.skipif(
    platform != "linux", reason="Inotify not available on this platform"
)
async def test_aiousbwatcher_path_created_after_start(tmp_path: Path) -> None:
    called: bool = False

    def callback() -> None:
        nonlocal called
        called = True

    usb_path = tmp_path / "usb"
    with patch("aiousbwatcher.impl._PATH", str(usb_path)):
        watcher = AIOUSBWatcher()
        watcher.async_register_callback(callback)
        stop = watcher.async_start()
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        assert not called
        usb_path.mkdir()
        (usb_path / "001").mkdir()
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        (usb_path / "001" / "002").touch()
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        assert called
        stop()  # type: ignore[unreachable]


@pytest.mark.asyncio
@pytest.mark.skipif(
    platform != "linux", reason="Inotify not available on this platform"
)
async def test_aiousbwatcher_path_replaced_after_start(tmp_path: Path) -> None:
    called: bool = False

    def callback() -> None:
        nonlocal called
        called = True

    usb_path = tmp_path / "usb"
    usb_path.mkdir()
    with patch("aiousbwatcher.impl._PATH", str(usb_path)):
        watcher = AIOUSBWatcher()
        watcher.async_register_callback(callback)
        stop = watcher.async_start()
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        usb_path.rmdir()
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        usb_path.mkdir()
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        called = False
        (usb_path / "001").touch()
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        assert called
        stop()


@pytest.mark.asyncio
@pytest.mark.skipif(
    platform != "linux", reason="Inotify not available on this platform"
)
async def test_aiousbwatcher_ignores_sibling_paths(tmp_path: Path) -> None:
    called: bool = False

    def callback() -> None:
        nonlocal called
        called = True

    usb_path = tmp_path / "usb"
    usb_path.mkdir()
    with patch("aiousbwatcher.impl._PATH", str(usb_path)):
        watcher = AIOUSBWatcher()
        watcher.async_register_callback(callback)
        stop = watcher.async_start()
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        (tmp_path / "not-usb").mkdir()
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        assert not called
        stop()


def test_get_watch_paths_walks_up_to_nearest_existing_ancestor(tmp_path: Path) -> None:
    from aiousbwatcher.impl import _get_watch_paths

    # path and its intermediate parents do not exist yet; the nearest existing
    # ancestor (tmp_path) must be returned so a later mkdir is noticed.
    missing = tmp_path / "a" / "b" / "usb"
    assert _get_watch_paths(missing) == [tmp_path]
