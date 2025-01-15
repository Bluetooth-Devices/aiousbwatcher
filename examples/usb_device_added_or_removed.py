import asyncio

from aiousbwatcher import AIOUSBWatcher, InotifyNotAvailableError


async def main() -> None:
    """Main entry point of the program."""
    try:
        watcher = AIOUSBWatcher()
        cancel = watcher.async_start()
    except InotifyNotAvailableError as ex:
        print(ex)
        return

    watcher.async_register_callback(lambda: print("USB device added/removed"))
    event = asyncio.Event()
    try:
        await event.wait()
    finally:
        cancel()


if __name__ == "__main__":
    asyncio.run(main())
