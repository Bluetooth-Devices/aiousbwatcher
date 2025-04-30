import asyncio
import enum
import threading
import warnings
from typing import Self

import objc
from CoreFoundation import (
    CFRunLoopAddSource,
    CFRunLoopGetCurrent,
    CFRunLoopRun,
    CFRunLoopStop,
    kCFRunLoopDefaultMode,
)

from .macos_types import (
    IOIteratorNext,
    IONotificationPortCreate,
    IONotificationPortGetRunLoopSource,
    IOObjectRelease,
    IOServiceAddMatchingNotification,
    IOServiceMatching,
    kIOMasterPortDefault,
    kIOMatchedNotification,
    kIOTerminatedNotification,
    kIOUSBDeviceClassName,
)


def _consume_iterator(io_iterator):
    """Required to "arm" the io_iterator for future notifications."""
    while True:
        obj = IOIteratorNext(io_iterator)
        if not obj:
            break

        IOObjectRelease(obj)


class MacosUsbEvent(enum.Enum):
    ADDED = "ADDED"
    REMOVED = "REMOVED"


class MacosUsbNotifier:
    def __init__(self) -> None:
        self._loop = None
        self._cf_run_loop = None
        self._queue = asyncio.Queue()
        self._thread = None

    async def __aenter__(self) -> Self:
        self._loop = asyncio.get_running_loop()
        self._thread = threading.Thread(target=self._cf_run_loop_thread)
        self._thread.start()

        print("Starting?")

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._cf_run_loop is not None:
            CFRunLoopStop(self._cf_run_loop)

        if self._thread is not None:
            self._thread.join()
            self._thread = None

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> MacosUsbEvent:
        try:
            return await self._queue.get()
        except asyncio.CancelledError:
            raise StopAsyncIteration

    def _cf_run_loop_thread(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", objc.ObjCPointerWarning)
            port = IONotificationPortCreate(kIOMasterPortDefault)

        @objc.callbackFor(IOServiceAddMatchingNotification)
        def device_added_callback(refCon, iterator):
            _consume_iterator(iterator)
            self._loop.call_soon_threadsafe(
                self._queue.put_nowait,
                MacosUsbEvent.ADDED,
            )

        @objc.callbackFor(IOServiceAddMatchingNotification)
        def device_removed_callback(refCon, iterator):
            _consume_iterator(iterator)
            self._loop.call_soon_threadsafe(
                self._queue.put_nowait,
                MacosUsbEvent.REMOVED,
            )

        # Device add
        _, add_iter = IOServiceAddMatchingNotification(
            port,
            kIOMatchedNotification,
            IOServiceMatching(kIOUSBDeviceClassName),
            device_added_callback,
            0,  # refCon
            None,
        )
        _consume_iterator(add_iter)

        # Device remove
        _, remove_iter = IOServiceAddMatchingNotification(
            port,
            kIOTerminatedNotification,
            IOServiceMatching(kIOUSBDeviceClassName),
            device_removed_callback,
            0,  # refCon
            None,
        )
        _consume_iterator(remove_iter)

        # Add notification port to run loop
        src = IONotificationPortGetRunLoopSource(port)
        self._cf_run_loop = CFRunLoopGetCurrent()
        CFRunLoopAddSource(self._cf_run_loop, src, kCFRunLoopDefaultMode)

        # Run the CFRunLoop until stop
        # installMachInterrupt()  # TODO: ctrl-c breaks without this but also with this
        CFRunLoopRun()


async def main():
    while True:
        async with MacosUsbNotifier() as notifier:
            print("Waiting for USB events. Ctrl+C to exit.")
            async for event in notifier:
                print("Got USB event:", event)
                break


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
