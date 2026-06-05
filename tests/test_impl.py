import asyncio
from pathlib import Path
from sys import platform
from unittest.mock import patch

import pytest

from aiousbwatcher import AIOUSBWatcher, InotifyNotAvailableError, impl

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
async def test_aiousbwatcher_recovers_from_oserror(tmp_path: Path) -> None:
    """A transient OSError in the watch loop must not kill the watcher."""
    called: bool = False

    def callback() -> None:
        nonlocal called
        called = True

    attempts: int = 0
    real_run_watcher = AIOUSBWatcher._run_watcher

    async def flaky_run_watcher(self: AIOUSBWatcher) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError("transient inotify failure")
        await real_run_watcher(self)

    with (
        patch("aiousbwatcher.impl._PATH", str(tmp_path)),
        patch.object(impl, "_AUTO_RECOVER_TIME", 0),
        patch.object(AIOUSBWatcher, "_run_watcher", flaky_run_watcher),
    ):
        watcher = AIOUSBWatcher()
        watcher.async_register_callback(callback)
        stop = watcher.async_start()
        # First run raises OSError, watcher sleeps (0s) then restarts.
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        assert attempts >= 2
        assert not called
        (tmp_path / "test").touch()
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        assert called
        stop()


@pytest.mark.asyncio
@pytest.mark.skipif(
    platform != "linux", reason="Inotify not available on this platform"
)
async def test_aiousbwatcher_skips_unwatchable_directory(tmp_path: Path) -> None:
    """A directory that vanishes before add_watch must not crash the watcher."""
    called: bool = False

    def callback() -> None:
        nonlocal called
        called = True

    from asyncinotify import Inotify

    real_add_watch = Inotify.add_watch

    def flaky_add_watch(self, directory, mask):  # type: ignore[no-untyped-def]
        # Simulate a hotplug race: a freshly created subdir has already vanished.
        if Path(directory).name == "ghost":
            raise FileNotFoundError("directory vanished")
        return real_add_watch(self, directory, mask)

    with (
        patch("aiousbwatcher.impl._PATH", str(tmp_path)),
        patch.object(Inotify, "add_watch", flaky_add_watch),
    ):
        watcher = AIOUSBWatcher()
        watcher.async_register_callback(callback)
        stop = watcher.async_start()
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        assert not called
        # Creating "ghost" triggers a CREATE on the watched root (callback
        # fires) and then a failing add_watch on the new subdir (swallowed).
        (tmp_path / "ghost").mkdir()
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        assert called
        called = False  # type: ignore[unreachable]
        # The watcher must still be alive and processing root-level events.
        (tmp_path / "after").touch()
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        assert called
        stop()


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
