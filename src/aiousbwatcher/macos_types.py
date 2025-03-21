import objc
from Foundation import NSBundle

kIOMasterPortDefault = 0

kIOUSBDeviceClassName = b"IOUSBDevice"

kIOFirstPublishNotification = b"IOServiceFirstPublish"
kIOPublishNotification = b"IOServicePublish"
kIOMatchedNotification = b"IOServiceMatched"
kIOFirstMatchNotification = b"IOServiceFirstMatch"
kIOTerminatedNotification = b"IOServiceTerminate"


objc.loadBundleFunctions(
    bundle=NSBundle.bundleWithIdentifier_("com.apple.framework.IOKit"),
    module_globals=globals(),
    functionInfo=[
        ("IOServiceMatching", b"^{__CFDictionary=}*"),
        (
            "IOServiceAddMatchingNotification",
            b"i^{_IONotificationPort}*^{__CFDictionary=}^?^vo^I",
            "",
            {
                "arguments": {
                    3: {
                        "callable": {
                            "arguments": {
                                0: {"type": b"^v"},
                                1: {"type": b"I"},
                            },
                            "retval": {"type": b"v"},
                        }
                    }
                }
            },
        ),
        (
            "IONotificationPortCreate",
            b"^{_IONotificationPort}I",
            "",
            {
                "arguments": {
                    0: {"type": "I"},
                },
                "retval": {
                    "already_retained": True,
                },
            },
        ),
        (
            "IONotificationPortGetRunLoopSource",
            b"^{__CFRunLoopSource=}^{_IONotificationPort}",
        ),
        ("IOIteratorNext", b"II"),
        ("IOObjectRelease", b"II"),
    ],
    skip_undefined=False,
)

__all__ = [
    # Injected into the scope by pyobjc
    "IOServiceMatching",
    "IOServiceAddMatchingNotification",
    "IONotificationPortCreate",
    "IONotificationPortGetRunLoopSource",
    "IOIteratorNext",
    "IOObjectRelease",
    # Exported
    "kIOMasterPortDefault",
    "kIOFirstPublishNotification",
    "kIOPublishNotification",
    "kIOMatchedNotification",
    "kIOFirstMatchNotification",
    "kIOTerminatedNotification",
    "kIOUSBDeviceClassName",
]
