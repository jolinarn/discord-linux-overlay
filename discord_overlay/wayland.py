import ctypes
import os

from PyQt6 import sip
from PyQt6.QtGui import QRegion
from PyQt6.QtWidgets import QApplication

_lib = None
_ANCHOR_TOP = 1
_ANCHOR_BOTTOM = 2
_ANCHOR_LEFT = 4
_ANCHOR_RIGHT = 8
_LAYER_OVERLAY = 3
_KB_NONE = 0

_POSITION_ANCHORS = {
    "top-left": _ANCHOR_TOP | _ANCHOR_LEFT,
    "top-right": _ANCHOR_TOP | _ANCHOR_RIGHT,
    "bottom-left": _ANCHOR_BOTTOM | _ANCHOR_LEFT,
    "bottom-right": _ANCHOR_BOTTOM | _ANCHOR_RIGHT,
}


class _CQMargins(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_int),
        ("top", ctypes.c_int),
        ("right", ctypes.c_int),
        ("bottom", ctypes.c_int),
    ]


def _load_lib():
    global _lib
    if _lib is not None:
        return _lib
    try:
        _lib = ctypes.cdll.LoadLibrary("libLayerShellQtInterface.so.6")
    except OSError:
        _lib = False
    return _lib


def _get_layer_window(widget):
    lib = _load_lib()
    if not lib:
        return None, None
    win = widget.windowHandle()
    if not win:
        return None, None
    ptr = sip.unwrapinstance(win)
    get_fn = lib._ZN12LayerShellQt6Window3getEP7QWindow
    get_fn.restype = ctypes.c_void_p
    get_fn.argtypes = [ctypes.c_void_p]
    lsw = get_fn(ptr)
    if not lsw:
        return None, None
    return lib, lsw


def is_wayland() -> bool:
    app = QApplication.instance()
    if app:
        return app.platformName() == "wayland"
    return os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"


def has_layer_shell() -> bool:
    return bool(_load_lib())


def setup_layer_shell(widget, position: str = "bottom-left",
                      offset_x: int = 10, offset_y: int = 10,
                      screen_name: str = ""):
    widget.winId()
    lib, lsw = _get_layer_window(widget)
    if not lsw:
        return False

    fn = lib._ZN12LayerShellQt6Window8setLayerENS0_5LayerE
    fn.argtypes = [ctypes.c_void_p, ctypes.c_int]
    fn(lsw, _LAYER_OVERLAY)

    anchors = _POSITION_ANCHORS.get(position, _ANCHOR_BOTTOM | _ANCHOR_LEFT)
    fn = lib._ZN12LayerShellQt6Window10setAnchorsE6QFlagsINS0_6AnchorEE
    fn.argtypes = [ctypes.c_void_p, ctypes.c_int]
    fn(lsw, anchors)

    margins = _build_margins(position, offset_x, offset_y)
    fn = lib._ZN12LayerShellQt6Window10setMarginsERK8QMargins
    fn.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    fn(lsw, ctypes.byref(margins))

    fn = lib._ZN12LayerShellQt6Window16setExclusiveZoneEi
    fn.argtypes = [ctypes.c_void_p, ctypes.c_int]
    fn(lsw, 0)

    fn = lib._ZN12LayerShellQt6Window24setKeyboardInteractivityENS0_21KeyboardInteractivityE
    fn.argtypes = [ctypes.c_void_p, ctypes.c_int]
    fn(lsw, _KB_NONE)

    fn = lib._ZN12LayerShellQt6Window17setActivateOnShowEb
    fn.argtypes = [ctypes.c_void_p, ctypes.c_bool]
    fn(lsw, False)

    _set_screen(widget, lib, lsw, screen_name)

    return True


def update_position(widget, position: str, offset_x: int = 10, offset_y: int = 10):
    lib, lsw = _get_layer_window(widget)
    if not lsw:
        return False

    anchors = _POSITION_ANCHORS.get(position, _ANCHOR_BOTTOM | _ANCHOR_LEFT)
    fn = lib._ZN12LayerShellQt6Window10setAnchorsE6QFlagsINS0_6AnchorEE
    fn.argtypes = [ctypes.c_void_p, ctypes.c_int]
    fn(lsw, anchors)

    margins = _build_margins(position, offset_x, offset_y)
    fn = lib._ZN12LayerShellQt6Window10setMarginsERK8QMargins
    fn.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    fn(lsw, ctypes.byref(margins))

    return True


def update_screen(widget, screen):
    lib, lsw = _get_layer_window(widget)
    if not lsw:
        return False
    win = widget.windowHandle()
    if win:
        win.setScreen(screen)
    ptr = sip.unwrapinstance(screen)
    fn = lib._ZN12LayerShellQt6Window9setScreenEP7QScreen
    fn.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    fn(lsw, ptr)
    return True


def _set_screen(widget, lib, lsw, screen_name: str = ""):
    screen = None
    if screen_name:
        for s in QApplication.screens():
            if s.name() == screen_name:
                screen = s
                break
    if not screen:
        screen = QApplication.primaryScreen()
    if not screen:
        return
    win = widget.windowHandle()
    if win:
        win.setScreen(screen)
    ptr = sip.unwrapinstance(screen)
    fn = lib._ZN12LayerShellQt6Window9setScreenEP7QScreen
    fn.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    fn(lsw, ptr)


def _build_margins(position: str, offset_x: int, offset_y: int) -> _CQMargins:
    left = top = right = bottom = 0
    if "left" in position:
        left = offset_x
    else:
        right = offset_x
    if "top" in position:
        top = offset_y
    else:
        bottom = offset_y
    return _CQMargins(left, top, right, bottom)


def set_click_through(widget) -> bool:
    win = widget.windowHandle()
    if not win:
        return False
    win.setMask(QRegion(-1, -1, 1, 1))
    return True


def remove_click_through(widget) -> bool:
    win = widget.windowHandle()
    if not win:
        return False
    win.setMask(QRegion())
    return True
