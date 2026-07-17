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

_LOGGER = logging.getLogger(__name__)


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
        self._task = self._loop.create_task(self._watcher())
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

    async def _watcher(self) -> None:
        mask = (
            Mask.CREATE
            | Mask.MOVED_FROM
            | Mask.MOVED_TO
            | Mask.CREATE
            | Mask.DELETE_SELF
            | Mask.DELETE
            | Mask.IGNORED
        )

        with Inotify() as inotify:
            await self._async_add_watches(inotify, mask)

            async for event in inotify:
                if event.path is not None and not self._is_relevant(event.path):
                    continue

                # Watch anything new: a subdirectory, or the watched path itself
                # being created after a mount or an unplug/replug of the bus.
                if Mask.CREATE in event.mask:
                    await self._async_add_watches(inotify, mask)

                # If there is at least some overlap, assume the user wants this event.
                if event.mask & mask:
                    self._async_call_callbacks()

    def _is_relevant(self, path: Path) -> bool:
        """Return True for events on the watched path, its tree, or its ancestors."""
        return (
            path == self._path
            or self._path in path.parents
            or path in self._path.parents
        )

    async def _async_add_watches(self, inotify: Inotify, mask: Mask) -> None:
        """Watch the path's tree and the nearest existing ancestor of it."""
        for directory in await self._loop.run_in_executor(
            None, _get_watch_paths, self._path
        ):
            inotify.add_watch(directory, mask)

    def _async_unregister_callback(self, callback: Callable[[], None]) -> None:
        self._callbacks.remove(callback)

    def _async_call_callbacks(self) -> None:
        for callback in self._callbacks:
            try:
                callback()
            except Exception as e:
                _LOGGER.exception("Error calling callback %s", callback, exc_info=e)
