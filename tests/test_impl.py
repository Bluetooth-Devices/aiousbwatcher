import asyncio
from pathlib import Path
from sys import platform
from typing import Any
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
async def test_aiousbwatcher_double_unregister(tmp_path: Path) -> None:
    def callback() -> None:
        pass

    with patch("aiousbwatcher.impl._PATH", str(tmp_path)):
        watcher = AIOUSBWatcher()
        unregister = watcher.async_register_callback(callback)
        unregister()
        # Unregistering a second time must not raise.
        unregister()


@pytest.mark.asyncio
@pytest.mark.skipif(
    platform != "linux", reason="Inotify not available on this platform"
)
async def test_aiousbwatcher_event_during_startup(tmp_path: Path) -> None:
    """A change occurring immediately after async_start() must not be missed."""
    called: bool = False

    def callback() -> None:
        nonlocal called
        called = True

    with patch("aiousbwatcher.impl._PATH", str(tmp_path)):
        watcher = AIOUSBWatcher()
        unregister = watcher.async_register_callback(callback)
        stop = watcher.async_start()
        # No await between start and the event: watches must already be installed
        # by the time async_start() returns, otherwise this event is lost.
        (tmp_path / "test").touch()
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        assert called
        unregister()
        stop()


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

    async def flaky_run_watcher(self: AIOUSBWatcher, inotify: Any) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError("transient inotify failure")
        await real_run_watcher(self, inotify)

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
        stop()  # type: ignore[unreachable]


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

    def flaky_add_watch(self, directory, mask):
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


@pytest.mark.asyncio
@pytest.mark.skipif(
    platform != "linux", reason="Inotify not available on this platform"
)
async def test_watch_paths_climb_to_existing_ancestor(tmp_path: Path) -> None:
    missing = tmp_path / "a" / "b" / "usb"
    assert impl._get_watch_paths(missing) == [tmp_path]


@pytest.mark.asyncio
@pytest.mark.skipif(
    platform != "linux", reason="Inotify not available on this platform"
)
async def test_aiousbwatcher_closes_inotify_when_watching_fails(
    tmp_path: Path,
) -> None:
    closed = False

    def close(self: Any) -> None:
        nonlocal closed
        closed = True

    def add_watches(inotify: Any) -> None:
        raise OSError("boom")

    with patch("aiousbwatcher.impl._PATH", str(tmp_path)):
        watcher = AIOUSBWatcher()
        with (
            patch.object(watcher, "_add_watches", add_watches),
            patch.object(impl.Inotify, "close", close),
            pytest.raises(OSError, match="boom"),
        ):
            watcher._make_inotify()
        assert closed


@pytest.mark.asyncio
@pytest.mark.skipif(
    platform != "linux", reason="Inotify not available on this platform"
)
async def test_aiousbwatcher_recovers_when_reopening_inotify_fails(
    tmp_path: Path,
) -> None:
    """A failure to re-create the Inotify after an error must not kill the watcher."""
    called: bool = False

    def callback() -> None:
        nonlocal called
        called = True

    runs: int = 0
    reopens: int = 0
    real_run_watcher = AIOUSBWatcher._run_watcher
    real_make_inotify = AIOUSBWatcher._make_inotify

    async def flaky_run_watcher(self: AIOUSBWatcher, inotify: Any) -> None:
        nonlocal runs
        runs += 1
        if runs == 1:
            raise OSError("transient inotify failure")
        await real_run_watcher(self, inotify)

    def flaky_make_inotify(self: AIOUSBWatcher) -> Any:
        nonlocal reopens
        reopens += 1
        if reopens == 2:
            raise OSError("cannot reopen inotify")
        return real_make_inotify(self)

    with (
        patch("aiousbwatcher.impl._PATH", str(tmp_path)),
        patch.object(impl, "_AUTO_RECOVER_TIME", 0),
        patch.object(AIOUSBWatcher, "_run_watcher", flaky_run_watcher),
        patch.object(AIOUSBWatcher, "_make_inotify", flaky_make_inotify),
    ):
        watcher = AIOUSBWatcher()
        watcher.async_register_callback(callback)
        stop = watcher.async_start()
        # Run 1 fails, the first reopen fails too, the next one succeeds.
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        assert reopens >= 3
        (tmp_path / "test").touch()
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        assert called
        stop()


@pytest.mark.asyncio
@pytest.mark.skipif(
    platform != "linux", reason="Inotify not available on this platform"
)
async def test_aiousbwatcher_ignores_events_outside_the_mask(tmp_path: Path) -> None:
    """An event with no overlap with the watch mask must not fire callbacks."""
    called: bool = False

    def callback() -> None:
        nonlocal called
        called = True

    class _Event:
        path = None
        mask = impl.Mask.MODIFY

    class _FakeInotify:
        async def __aiter__(self) -> Any:
            yield _Event()

    with patch("aiousbwatcher.impl._PATH", str(tmp_path)):
        watcher = AIOUSBWatcher()
        watcher.async_register_callback(callback)
        await watcher._run_watcher(_FakeInotify())
        assert not called


@pytest.mark.asyncio
@pytest.mark.skipif(
    platform != "linux", reason="Inotify not available on this platform"
)
async def test_aiousbwatcher_moved_in_directory_is_watched(tmp_path: Path) -> None:
    """A tree renamed into the watched path must be watched, not just reported."""
    events: list[None] = []
    watched = tmp_path / "watched"
    watched.mkdir()
    staging = tmp_path / "staging"
    (staging / "sub").mkdir(parents=True)

    with patch("aiousbwatcher.impl._PATH", str(watched)):
        watcher = AIOUSBWatcher()
        unregister = watcher.async_register_callback(lambda: events.append(None))
        stop = watcher.async_start()
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        assert not events

        # Atomically move an already-populated tree in, as udev does.
        staging.rename(watched / "003")
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        assert events  # MOVED_TO on the watched dir itself
        events.clear()

        # Events *inside* the moved-in tree must reach us as well. This is what
        # breaks when only CREATE triggers a re-walk: the assertion above still
        # passes, so the blind subtree is invisible to a smoke test.
        (watched / "003" / "sub" / "dev").touch()
        await asyncio.sleep(_INOTIFY_WAIT_TIME)
        assert events

        unregister()
        stop()
