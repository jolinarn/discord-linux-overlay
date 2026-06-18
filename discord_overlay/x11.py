import ctypes
import ctypes.util
import subprocess

_x11 = ctypes.cdll.LoadLibrary("libX11.so.6")
_xfixes = ctypes.cdll.LoadLibrary("libXfixes.so.3")

_x11.XOpenDisplay.restype = ctypes.c_void_p
_x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
_x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
_x11.XFlush.argtypes = [ctypes.c_void_p]

_xfixes.XFixesQueryExtension.restype = ctypes.c_int
_xfixes.XFixesQueryExtension.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_int),
    ctypes.POINTER(ctypes.c_int),
]
_xfixes.XFixesQueryVersion.restype = ctypes.c_int
_xfixes.XFixesQueryVersion.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_int),
    ctypes.POINTER(ctypes.c_int),
]
_xfixes.XFixesCreateRegion.restype = ctypes.c_ulong
_xfixes.XFixesCreateRegion.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int]
_xfixes.XFixesSetWindowShapeRegion.argtypes = [
    ctypes.c_void_p,
    ctypes.c_ulong,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_ulong,
]
_xfixes.XFixesDestroyRegion.argtypes = [ctypes.c_void_p, ctypes.c_ulong]

_SHAPE_INPUT = 2


def set_click_through(window_id: int) -> bool:
    display = _x11.XOpenDisplay(None)
    if not display:
        return False
    try:
        event_base = ctypes.c_int()
        error_base = ctypes.c_int()
        if not _xfixes.XFixesQueryExtension(
            display, ctypes.byref(event_base), ctypes.byref(error_base)
        ):
            return False
        major = ctypes.c_int(5)
        minor = ctypes.c_int(0)
        _xfixes.XFixesQueryVersion(display, ctypes.byref(major), ctypes.byref(minor))
        region = _xfixes.XFixesCreateRegion(display, None, 0)
        _xfixes.XFixesSetWindowShapeRegion(
            display, window_id, _SHAPE_INPUT, 0, 0, region
        )
        _xfixes.XFixesDestroyRegion(display, region)
        _x11.XFlush(display)
        return True
    finally:
        _x11.XCloseDisplay(display)


def remove_click_through(window_id: int) -> bool:
    display = _x11.XOpenDisplay(None)
    if not display:
        return False
    try:
        event_base = ctypes.c_int()
        error_base = ctypes.c_int()
        if not _xfixes.XFixesQueryExtension(
            display, ctypes.byref(event_base), ctypes.byref(error_base)
        ):
            return False
        major = ctypes.c_int(5)
        minor = ctypes.c_int(0)
        _xfixes.XFixesQueryVersion(display, ctypes.byref(major), ctypes.byref(minor))
        # passing 0 (None) as region resets input shape to default
        _xfixes.XFixesSetWindowShapeRegion(
            display, window_id, _SHAPE_INPUT, 0, 0, 0
        )
        _x11.XFlush(display)
        return True
    finally:
        _x11.XCloseDisplay(display)


def set_window_type_notification(window_id: int):
    subprocess.run(
        [
            "xprop", "-id", str(window_id),
            "-f", "_NET_WM_WINDOW_TYPE", "32a",
            "-set", "_NET_WM_WINDOW_TYPE", "_NET_WM_WINDOW_TYPE_NOTIFICATION",
        ],
        capture_output=True,
    )


def set_blur_behind(window_id: int):
    subprocess.run(
        [
            "xprop", "-id", str(window_id),
            "-f", "_KDE_NET_WM_BLUR_BEHIND_REGION", "32c",
            "-set", "_KDE_NET_WM_BLUR_BEHIND_REGION", "0",
        ],
        capture_output=True,
    )
