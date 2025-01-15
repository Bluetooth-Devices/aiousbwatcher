__version__ = "0.0.0"

from .impl import AIOUSBWatcher, InotifyNotAvailableError

__all__ = ["AIOUSBWatcher", "InotifyNotAvailableError"]
