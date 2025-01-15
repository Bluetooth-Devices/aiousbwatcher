__version__ = "0.2.0"

from .impl import AIOUSBWatcher, InotifyNotAvailableError

__all__ = ["AIOUSBWatcher", "InotifyNotAvailableError"]
