import signal
import subprocess
import sys

from PyQt6.QtWidgets import QApplication

from .config import FirstRunDialog, load_config
from .overlay import OverlayWindow
from .rpc import DiscordRPCThread
from .tray import TrayIcon


def _send_signal(sig: int):
    result = subprocess.run(
        ["pkill", f"-{sig}", "-f", "python.*discord_overlay"],
        capture_output=True,
    )
    sys.exit(0 if result.returncode == 0 else 1)


def main():
    if "--toggle-lock" in sys.argv:
        _send_signal(signal.SIGUSR1)
    if "--toggle" in sys.argv:
        _send_signal(signal.SIGUSR2)

    app = QApplication(sys.argv)
    app.setApplicationName("Discord Voice Overlay")
    app.setQuitOnLastWindowClosed(False)

    config = load_config()

    if not config.get("client_id") or not config.get("client_secret"):
        dialog = FirstRunDialog(config)
        if dialog.exec() == 0:
            sys.exit(0)

    overlay = OverlayWindow(config)
    tray = TrayIcon(overlay, config)

    rpc = DiscordRPCThread(config)
    rpc.connected.connect(overlay.on_connected)
    rpc.disconnected.connect(overlay.on_disconnected)
    rpc.voice_channel.connect(overlay.on_voice_channel)
    rpc.voice_state.connect(overlay.on_voice_state)
    rpc.speaking_start.connect(overlay.on_speaking_start)
    rpc.speaking_stop.connect(overlay.on_speaking_stop)
    rpc.error.connect(overlay.on_error)

    app.aboutToQuit.connect(rpc.stop)

    # Signal handlers for external control
    signal.signal(signal.SIGUSR1, lambda *_: overlay.set_locked(not overlay.locked))
    signal.signal(signal.SIGUSR2, lambda *_: overlay.toggle_visibility())

    tray.show()
    rpc.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
