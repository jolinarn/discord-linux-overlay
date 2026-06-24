import sys

import dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

from PyQt6.QtCore import QThread, pyqtSignal

_DEST = "org.freedesktop.portal.Desktop"
_PATH = "/org/freedesktop/portal/desktop"
_SHORTCUTS_IFACE = "org.freedesktop.portal.GlobalShortcuts"
_REQUEST_IFACE = "org.freedesktop.portal.Request"
_SESSION_IFACE = "org.freedesktop.portal.Session"


class PortalHotkeyThread(QThread):
    triggered = pyqtSignal()

    def __init__(self, hotkey_str: str = "Ctrl+Shift+O"):
        super().__init__()
        self._hotkey = self._convert_trigger(hotkey_str)
        self._loop = None
        self._session_handle = None

    @staticmethod
    def _convert_trigger(hotkey_str: str) -> str:
        parts = []
        for p in hotkey_str.split("+"):
            p = p.strip()
            low = p.lower()
            if low in ("ctrl", "control"):
                parts.append("Control_L")
            elif low == "shift":
                parts.append("Shift_L")
            elif low == "alt":
                parts.append("Alt_L")
            elif low in ("super", "meta"):
                parts.append("Super_L")
            else:
                parts.append(p.lower())
        return "+".join(parts)

    def run(self):
        DBusGMainLoop(set_as_default=True)
        bus = dbus.SessionBus()
        sender = bus.get_unique_name().replace(".", "_").lstrip(":")

        portal = bus.get_object(_DEST, _PATH)
        shortcuts = dbus.Interface(portal, _SHORTCUTS_IFACE)

        # Create session
        session_token = "discord_overlay"
        request_path = f"{_PATH}/request/{sender}/{session_token}_session"

        session_ready = {"handle": None}

        def on_session_response(response, results):
            if response == 0:
                session_ready["handle"] = str(results.get("session_handle", ""))

        bus.add_signal_receiver(
            on_session_response,
            signal_name="Response",
            dbus_interface=_REQUEST_IFACE,
            path=request_path,
        )

        try:
            shortcuts.CreateSession(dbus.Dictionary({
                "handle_token": dbus.String(f"{session_token}_session", variant_level=1),
                "session_handle_token": dbus.String(session_token, variant_level=1),
            }, signature="sv"))
        except dbus.DBusException as e:
            print(f"[overlay] Portal GlobalShortcuts unavailable: {e}", file=sys.stderr)
            return

        # Process events until session is ready
        ctx = GLib.MainContext.default()
        for _ in range(50):
            ctx.iteration(False)
            if session_ready["handle"]:
                break
            import time
            time.sleep(0.01)

        self._session_handle = session_ready["handle"]
        if not self._session_handle:
            self._session_handle = f"{_PATH}/session/{sender}/{session_token}"

        # Bind shortcuts
        bind_result = {"done": False}

        def on_bind_response(response, results):
            bind_result["done"] = True
            if response != 0:
                print("[overlay] Portal BindShortcuts denied by user", file=sys.stderr)
                return
            shortcuts_list = results.get("shortcuts", [])
            for sid, props in shortcuts_list:
                trigger = str(props.get("trigger_description", ""))
                if not trigger:
                    print(
                        f"[overlay] Shortcut '{sid}' has no trigger assigned. "
                        "Set it in System Settings > Shortcuts > Global Shortcuts.",
                        file=sys.stderr,
                    )

        bind_request_path = f"{_PATH}/request/{sender}/{session_token}_bind"
        bus.add_signal_receiver(
            on_bind_response,
            signal_name="Response",
            dbus_interface=_REQUEST_IFACE,
            path=bind_request_path,
        )

        try:
            shortcuts.BindShortcuts(
                dbus.ObjectPath(self._session_handle),
                dbus.Array([
                    dbus.Struct([
                        dbus.String("toggle-lock"),
                        dbus.Dictionary({
                            "description": dbus.String("Toggle overlay lock", variant_level=1),
                            "preferred_trigger": dbus.String(self._hotkey, variant_level=1),
                        }, signature="sv"),
                    ], signature="sa{sv}"),
                ], signature="(sa{sv})"),
                dbus.String(""),
                dbus.Dictionary({
                    "handle_token": dbus.String(f"{session_token}_bind", variant_level=1),
                }, signature="sv"),
            )
        except dbus.DBusException as e:
            print(f"[overlay] Portal BindShortcuts failed: {e}", file=sys.stderr)
            return

        for _ in range(50):
            ctx.iteration(False)
            if bind_result["done"]:
                break
            import time
            time.sleep(0.01)

        # Listen for activated on the session path
        bus.add_signal_receiver(
            self._on_activated,
            signal_name="Activated",
            dbus_interface=_SHORTCUTS_IFACE,
            path=self._session_handle,
        )

        self._loop = GLib.MainLoop()
        self._loop.run()

    def _on_activated(self, session_handle, shortcut_id, timestamp, options):
        if shortcut_id == "toggle-lock":
            self.triggered.emit()

    def stop(self):
        if self._session_handle:
            try:
                bus = dbus.SessionBus()
                session = bus.get_object(_DEST, self._session_handle)
                dbus.Interface(session, _SESSION_IFACE).Close()
            except Exception:
                pass
            self._session_handle = None
        if self._loop:
            self._loop.quit()
        self.wait(2000)
