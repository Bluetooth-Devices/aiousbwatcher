from __future__ import annotations

import asyncio
import logging
import warnings
from functools import partial
from pathlib import Path
from typing import Callable

_INOTIFY_EXCEPTION: Exception | None = None
try:
    with warnings.catch_warnings(action="ignore", category=UserWarning):
        from asyncinotify._ffi import libc  # noqa: F401
    from asyncinotify import Inotify, Mask
except Exception as ex:
    _INOTIFY_EXCEPTION = ex
    Mask = Inotify = None


_PATH = "/dev/bus/usb"

# How long to wait before restarting the watcher after an unexpected OSError.
# USB hotplug churns /dev/bus/usb constantly, so a transient failure should
# self-heal rather than permanently stop the watcher.
_AUTO_RECOVER_TIME = 5

_LOGGER = logging.getLogger(__name__)

# Guarded because Mask is None when inotify is unavailable (non-Linux / missing
# backend). async_start() raises InotifyNotAvailableError before _MASK is used.
_MASK: Mask = (
    (
        Mask.CREATE
        | Mask.MOVED_FROM
        | Mask.MOVED_TO
        | Mask.DELETE_SELF
        | Mask.DELETE
        | Mask.IGNORED
    )
    if Mask is not None
    else None
)


class InotifyNotAvailableError(Exception):
    """Raised when inotify is not available on the platform."""


def _get_watch_paths(path: Path) -> list[Path]:
    """Return the nearest existing ancestor of path plus every directory under it."""
    # The ancestor is watched so the watcher notices path itself being created or
    # replaced; path's tree is empty when path does not exist yet.
    ancestor = path.parent
    while not ancestor.is_dir() and ancestor.parent != ancestor:
        ancestor = ancestor.parent
    return [ancestor, *(dirpath for dirpath, dirnames, filenames in path.walk())]


class AIOUSBWatcher:
    """A watcher for USB devices that uses asyncio."""

    def __init__(self) -> None:
        self._path = Path(_PATH)
        self._loop = asyncio.get_running_loop()
        self._task: asyncio.Task[None] | None = None
        self._callbacks: set[Callable[[], None]] = set()

    def async_start(self) -> Callable[[], None]:
        """Start the watcher."""
        if self._task is not None:
            raise RuntimeError("Watcher already started")
        if _INOTIFY_EXCEPTION is not None:
            raise InotifyNotAvailableError(
                "Inotify not available on this platform"
            ) from _INOTIFY_EXCEPTION
        # Install the initial watches synchronously so the watcher is guaranteed
        # to be observing before async_start() returns. Deferring this to the
        # task would leave a window in which USB changes are silently missed.
        self._task = self._loop.create_task(self._watcher(self._make_inotify()))
        return self._async_stop

    def async_register_callback(
        self, callback: Callable[[], None]
    ) -> Callable[[], None]:
        """Register callback that will be called when a USB device is added/removed."""
        self._callbacks.add(callback)
        return partial(self._async_unregister_callback, callback)

    def _async_stop(self) -> None:
        """Stop the watcher."""
        assert self._task is not None  # noqa
        self._task.cancel()
        self._task = None

    def _make_inotify(self) -> Inotify:
        """Return an Inotify already watching the path's tree and its ancestor."""
        inotify = Inotify()
        try:
            self._add_watches(inotify)
        except BaseException:
            inotify.close()
            raise
        return inotify

    def _add_watches(self, inotify: Inotify) -> None:
        """Add a watch for each path, skipping any that have vanished."""
        # USB hotplug races mean a directory discovered by the walk can disappear
        # before we get to watch it. Skip those rather than crashing the watcher.
        for directory in _get_watch_paths(self._path):
            try:
                inotify.add_watch(directory, _MASK)
            except OSError as ex:
                _LOGGER.debug("Could not watch %s: %s", directory, ex)

    async def _watcher(self, inotify: Inotify | None) -> None:
        """Run the watcher, auto-recovering from transient OS errors."""
        while True:
            try:
                if inotify is None:
                    inotify = await self._loop.run_in_executor(None, self._make_inotify)
                await self._run_watcher(inotify)
            except asyncio.CancelledError:
                raise
            except OSError as ex:
                _LOGGER.warning(
                    "USB watcher stopped unexpectedly (%s); restarting in %s seconds",
                    ex,
                    _AUTO_RECOVER_TIME,
                )
            finally:
                if inotify is not None:
                    inotify.close()
                    inotify = None
            await asyncio.sleep(_AUTO_RECOVER_TIME)

    async def _run_watcher(self, inotify: Inotify) -> None:
        async for event in inotify:
            if event.path is not None and not self._is_relevant(event.path):
                continue

            # Watch anything new: a subdirectory, the watched path itself being
            # created after a mount or an unplug/replug of the bus, or a tree
            # renamed into place. udev populates a directory before moving it
            # in, so MOVED_TO must trigger a re-walk as well -- otherwise the
            # moved-in subtree goes unwatched and every event inside it is lost.
            if event.mask & (Mask.CREATE | Mask.MOVED_TO):
                await self._loop.run_in_executor(None, self._add_watches, inotify)

            # If there is at least some overlap, assume the user wants this event.
            if event.mask & _MASK:
                self._async_call_callbacks()

    def _is_relevant(self, path: Path) -> bool:
        """Return True for events on the watched path, its tree, or its ancestors."""
        return (
            path == self._path
            or self._path in path.parents
            or path in self._path.parents
        )

    def _async_unregister_callback(self, callback: Callable[[], None]) -> None:
        self._callbacks.discard(callback)

    def _async_call_callbacks(self) -> None:
        for callback in self._callbacks:
            try:
                callback()
            except Exception as e:
                _LOGGER.exception("Error calling callback %s", callback, exc_info=e)
