import ctypes
import time

from PyQt6.QtCore import QThread, pyqtSignal

_x11 = ctypes.cdll.LoadLibrary("libX11.so.6")

_x11.XOpenDisplay.restype = ctypes.c_void_p
_x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
_x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
_x11.XDefaultRootWindow.restype = ctypes.c_ulong
_x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
_x11.XGrabKey.argtypes = [
    ctypes.c_void_p, ctypes.c_int, ctypes.c_uint,
    ctypes.c_ulong, ctypes.c_int, ctypes.c_int, ctypes.c_int,
]
_x11.XUngrabKey.argtypes = [
    ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.c_ulong,
]
_x11.XKeysymToKeycode.restype = ctypes.c_ubyte
_x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
_x11.XNextEvent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_x11.XPending.restype = ctypes.c_int
_x11.XPending.argtypes = [ctypes.c_void_p]
_x11.XFlush.argtypes = [ctypes.c_void_p]

_KEY_PRESS = 2
_GRAB_MODE_ASYNC = 1
_SHIFT = 1
_LOCK = 2
_CTRL = 4
_ALT = 8
_NUM_LOCK = 16
_SUPER = 64

_LOCK_MASKS = [0, _LOCK, _NUM_LOCK, _LOCK | _NUM_LOCK]

_KEYSYMS = {
    **{chr(c): c for c in range(0x61, 0x7B)},  # a-z
    **{f"f{n}": 0xFFBE + n - 1 for n in range(1, 13)},  # f1-f12
    "grave": 0x60, "backquote": 0x60,
    "space": 0x20, "escape": 0xFF1B,
}

_MODIFIERS = {
    "ctrl": _CTRL, "control": _CTRL,
    "shift": _SHIFT, "alt": _ALT,
    "super": _SUPER, "meta": _SUPER,
}


def _parse_hotkey(hotkey_str: str):
    parts = [p.strip().lower() for p in hotkey_str.split("+")]
    mods = 0
    keysym = None
    for part in parts:
        if part in _MODIFIERS:
            mods |= _MODIFIERS[part]
        elif part in _KEYSYMS:
            keysym = _KEYSYMS[part]
        else:
            raise ValueError(f"Unknown key: {part}")
    if keysym is None:
        raise ValueError(f"No key found in hotkey: {hotkey_str}")
    return mods, keysym


class GlobalHotkeyThread(QThread):
    triggered = pyqtSignal()

    def __init__(self, hotkey_str: str = "Ctrl+Shift+O"):
        super().__init__()
        self._hotkey_str = hotkey_str
        self._modifiers, self._keysym = _parse_hotkey(hotkey_str)
        self._running = False

    def run(self):
        display = _x11.XOpenDisplay(None)
        if not display:
            return

        root = _x11.XDefaultRootWindow(display)
        keycode = _x11.XKeysymToKeycode(display, self._keysym)
        if not keycode:
            _x11.XCloseDisplay(display)
            return

        for mask in _LOCK_MASKS:
            _x11.XGrabKey(
                display, keycode, self._modifiers | mask,
                root, False, _GRAB_MODE_ASYNC, _GRAB_MODE_ASYNC,
            )
        _x11.XFlush(display)

        self._running = True
        event_buf = ctypes.create_string_buffer(192)

        while self._running:
            while _x11.XPending(display) > 0:
                _x11.XNextEvent(display, event_buf)
                event_type = ctypes.c_int.from_buffer_copy(event_buf[:4]).value
                if event_type == _KEY_PRESS:
                    self.triggered.emit()
            time.sleep(0.05)

        for mask in _LOCK_MASKS:
            _x11.XUngrabKey(display, keycode, self._modifiers | mask, root)
        _x11.XCloseDisplay(display)

    def stop(self):
        self._running = False
        self.wait(2000)
