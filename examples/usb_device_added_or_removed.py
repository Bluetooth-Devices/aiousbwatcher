import asyncio

from aiousbwatcher import AIOUSBWatcher, InotifyNotAvailableError


async def main() -> None:
    """Main entry point of the program."""
    try:
        watcher = AIOUSBWatcher()
        watcher.async_start()
    except InotifyNotAvailableError as ex:
        print(ex)
        return

    watcher.async_register_callback(lambda: print("USB device added/removed"))
    event = asyncio.Event()
    await event.wait()


if __name__ == "__main__":
    asyncio.run(main())
