(usage)=

# Usage

Assuming that you've followed the {ref}`installations steps <installation>`, you're now ready to use this package.

`AIOUSBWatcher` watches `/dev/bus/usb` and invokes your callbacks whenever a USB
device is plugged in or unplugged.

## Quick start

```python
import asyncio

from aiousbwatcher import AIOUSBWatcher, InotifyNotAvailableError


async def main() -> None:
    # AIOUSBWatcher must be created from within a running event loop.
    watcher = AIOUSBWatcher()

    def on_change() -> None:
        print("USB devices changed")

    # Register a callback; keep the returned handle to unregister later.
    unregister = watcher.async_register_callback(on_change)

    try:
        # Start watching; keep the returned handle to stop later.
        stop = watcher.async_start()
    except InotifyNotAvailableError:
        # Raised on platforms where inotify is unavailable (e.g. non-Linux).
        return

    # ... run your application; on_change() fires on every add/remove ...
    await asyncio.sleep(60)

    unregister()
    stop()


asyncio.run(main())
```

## API

### `AIOUSBWatcher()`

Create a watcher. It must be constructed from within a running asyncio event
loop, as it binds to the loop at construction time.

### `async_register_callback(callback) -> Callable[[], None]`

Register a zero-argument `callback` to be invoked whenever a USB device is added
or removed. Returns a callable that unregisters this callback when called.

You may register a callback before or after calling {func}`async_start`.
Exceptions raised inside a callback are logged and do not stop other callbacks
or the watcher.

### `async_start() -> Callable[[], None]`

Start watching. Returns a callable that stops the watcher when called. Raises
`RuntimeError` if the watcher is already running, and `InotifyNotAvailableError`
if inotify is not available on the current platform.

### `InotifyNotAvailableError`

Raised by {func}`async_start` when inotify cannot be used (for example, on
non-Linux platforms).
