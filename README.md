# asyncio usb device watcher

<p align="center">
  <a href="https://github.com/bluetooth-devices/aiousbwatcher/actions/workflows/ci.yml?query=branch%3Amain">
    <img src="https://img.shields.io/github/actions/workflow/status/bluetooth-devices/aiousbwatcher/ci.yml?branch=main&label=CI&logo=github&style=flat-square" alt="CI Status" >
  </a>
  <a href="https://aiousbwatcher.readthedocs.io">
    <img src="https://img.shields.io/readthedocs/aiousbwatcher.svg?logo=read-the-docs&logoColor=fff&style=flat-square" alt="Documentation Status">
  </a>
  <a href="https://codecov.io/gh/bluetooth-devices/aiousbwatcher">
    <img src="https://img.shields.io/codecov/c/github/bluetooth-devices/aiousbwatcher.svg?logo=codecov&logoColor=fff&style=flat-square" alt="Test coverage percentage">
  </a>
</p>
<p align="center">
  <a href="https://github.com/astral-sh/uv">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json" alt="uv">
  </a>
  <a href="https://github.com/astral-sh/ruff">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff">
  </a>
  <a href="https://github.com/pre-commit/pre-commit">
    <img src="https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white&style=flat-square" alt="pre-commit">
  </a>
</p>
<p align="center">
  <a href="https://pypi.org/project/aiousbwatcher/">
    <img src="https://img.shields.io/pypi/v/aiousbwatcher.svg?logo=python&logoColor=fff&style=flat-square" alt="PyPI Version">
  </a>
  <img src="https://img.shields.io/pypi/pyversions/aiousbwatcher.svg?style=flat-square&logo=python&amp;logoColor=fff" alt="Supported Python versions">
  <img src="https://img.shields.io/pypi/l/aiousbwatcher.svg?style=flat-square" alt="License">
</p>

---

**Documentation**: <a href="https://aiousbwatcher.readthedocs.io" target="_blank">https://aiousbwatcher.readthedocs.io </a>

**Source Code**: <a href="https://github.com/bluetooth-devices/aiousbwatcher" target="_blank">https://github.com/bluetooth-devices/aiousbwatcher </a>

---

Watch for USB devices to be plugged and unplugged

## Installation

Install this via pip (or your favourite package manager):

`pip install aiousbwatcher`

## Usage

```python
import asyncio

from aiousbwatcher import AIOUSBWatcher, InotifyNotAvailableError


async def main() -> None:
    def _callback() -> None:
        # A USB device was plugged in or unplugged; rescan as needed.
        print("USB devices changed")

    watcher = AIOUSBWatcher()
    unregister = watcher.async_register_callback(_callback)

    try:
        stop = watcher.async_start()
    except InotifyNotAvailableError:
        # inotify is only available on Linux.
        return

    # ... run your application ...
    await asyncio.sleep(60)

    unregister()
    stop()


asyncio.run(main())
```

`async_register_callback` returns a callable that unregisters that callback, and
`async_start` returns a callable that stops the watcher. Callbacks take no
arguments — they signal _that_ something changed, not _what_; rescan your
devices to find the details.

### Debouncing event bursts

Plugging in a single USB device churns `/dev/bus/usb` with several events, so a
naive callback fires multiple times per physical change. If your callback does
expensive work (such as a full device rescan), pass `debounce` to coalesce a
burst into a single invocation that fires once events have been quiet for the
given number of seconds:

```python
watcher = AIOUSBWatcher(debounce=0.5)
```

With `debounce=None` (the default) every event fires the callbacks immediately.

## Contributors ✨

Thanks goes to these wonderful people ([emoji key](https://allcontributors.org/docs/en/emoji-key)):

<!-- prettier-ignore-start -->
<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- markdownlint-disable -->
<!-- markdownlint-enable -->
<!-- ALL-CONTRIBUTORS-LIST:END -->
<!-- prettier-ignore-end -->

This project follows the [all-contributors](https://github.com/all-contributors/all-contributors) specification. Contributions of any kind welcome!

## Credits

[![Copier](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/copier-org/copier/master/img/badge/badge-grayscale-inverted-border-orange.json)](https://github.com/copier-org/copier)

This package was created with
[Copier](https://copier.readthedocs.io/) and the
[browniebroke/pypackage-template](https://github.com/browniebroke/pypackage-template)
project template.
