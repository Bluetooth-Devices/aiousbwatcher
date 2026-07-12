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

# Guarded because Mask is None when inotify is unavailable (non-Linux / missing
# backend). async_start() raises InotifyNotAvailableError before _MASK is used.
_MASK = (
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


def _get_directories_recursive(path: Path) -> list[Path]:
    return [dirpath for dirpath, dirnames, filenames in path.walk()]


async def _async_get_directories_recursive(
    loop: asyncio.AbstractEventLoop, path: Path
) -> list[Path]:
    return await loop.run_in_executor(None, _get_directories_recursive, path)


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
        inotify = Inotify()
        try:
            for directory in _get_directories_recursive(self._path):
                inotify.add_watch(directory, _MASK)
        except BaseException:
            inotify.close()
            raise
        self._task = self._loop.create_task(self._watcher(inotify))
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

    async def _watcher(self, inotify: Inotify) -> None:
        try:
            async for event in inotify:
                # Add subdirectories to watch if a new directory is added.
                if Mask.CREATE in event.mask and event.path is not None:
                    for directory in await _async_get_directories_recursive(
                        self._loop, event.path
                    ):
                        inotify.add_watch(directory, _MASK)

                # If there is at least some overlap, assume the user wants this event.
                if event.mask & _MASK:
                    self._async_call_callbacks()
        finally:
            inotify.close()

    def _async_unregister_callback(self, callback: Callable[[], None]) -> None:
        self._callbacks.remove(callback)

    def _async_call_callbacks(self) -> None:
        for callback in self._callbacks:
            try:
                callback()
            except Exception as e:
                _LOGGER.exception("Error calling callback %s", callback, exc_info=e)
