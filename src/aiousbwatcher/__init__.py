__version__ = "0.3.0"

from .impl import AIOUSBWatcher, InotifyNotAvailableError

__all__ = ["AIOUSBWatcher", "InotifyNotAvailableError"]
