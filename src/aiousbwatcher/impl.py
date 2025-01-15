from __future__ import annotations

import asyncio
import logging
from collections.abc import Generator
from functools import partial
from pathlib import Path
from typing import Callable

from asyncinotify import Inotify, Mask

_BASE_MASK = (
    Mask.MOVED_FROM | Mask.MOVED_TO | Mask.CREATE | Mask.DELETE_SELF | Mask.IGNORED
)
_PATH = "/dev/bus/usb"

_LOGGER = logging.getLogger(__name__)


def _get_directories_recursive_gen(path: Path) -> Generator[Path, None, None]:
    if path.is_dir():
        yield path
        for child in path.iterdir():
            yield from _get_directories_recursive_gen(child)


def _get_directories_recursive(path: Path) -> list[Path]:
    return list(_get_directories_recursive_gen(path))


async def _async_get_directories_recursive(
    loop: asyncio.AbstractEventLoop, path: Path
) -> list[Path]:
    return await loop.run_in_executor(None, _get_directories_recursive, path)


class AIOUSBWatcher:
    """A watcher for USB devices that uses asyncio."""

    def __init__(self) -> None:
        self._inotify = Inotify()
        self._path = Path(_PATH)
        self._mask = Mask.CREATE | _BASE_MASK
        self._loop = asyncio.get_running_loop()
        self._task: asyncio.Task[None] | None = None
        self._callbacks: set[Callable[[], None]] = set()

    def async_start(self) -> Callable[[], None]:
        """Start the watcher."""
        if self._task is not None:
            raise RuntimeError("Watcher already started")
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
        with Inotify() as inotify:
            for directory in await _async_get_directories_recursive(
                self._loop, self._path
            ):
                inotify.add_watch(directory, self._mask)

            async for event in inotify:
                # Add subdirectories to watch if a new directory is added.
                if Mask.CREATE in event.mask and event.path is not None:
                    for directory in await _async_get_directories_recursive(
                        self._loop, event.path
                    ):
                        inotify.add_watch(directory, self._mask)

                # If there is at least some overlap, assume the user wants this event.
                if event.mask & self._mask:
                    self._async_call_callbacks()

    def _async_unregister_callback(self, callback: Callable[[], None]) -> None:
        self._callbacks.remove(callback)

    def _async_call_callbacks(self) -> None:
        for callback in self._callbacks:
            try:
                callback()
            except Exception as e:
                _LOGGER.exception("Error calling callback %s", callback, exc_info=e)
