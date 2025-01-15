__version__ = "1.1.0"

from .impl import AIOUSBWatcher, InotifyNotAvailableError

__all__ = ["AIOUSBWatcher", "InotifyNotAvailableError"]
