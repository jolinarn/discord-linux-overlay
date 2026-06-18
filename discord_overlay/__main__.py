import sys

from PyQt6.QtWidgets import QApplication

from .config import FirstRunDialog, load_config
from .overlay import OverlayWindow
from .rpc import DiscordRPCThread
from .tray import TrayIcon


def main():
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

    tray.show()
    rpc.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
