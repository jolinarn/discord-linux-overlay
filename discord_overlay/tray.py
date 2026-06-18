from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon


class TrayIcon(QSystemTrayIcon):
    def __init__(self, overlay, config: dict):
        super().__init__()
        self._overlay = overlay
        self._config = config

        icon = QIcon.fromTheme("discord", QIcon.fromTheme("audio-headphones"))
        self.setIcon(icon)
        self.setToolTip("Discord Voice Overlay")

        self._build_menu()
        self.activated.connect(self._on_activated)

    def _build_menu(self):
        menu = QMenu()

        self._toggle_action = QAction("Toggle Overlay", menu)
        self._toggle_action.triggered.connect(self._overlay.toggle_visibility)
        menu.addAction(self._toggle_action)

        menu.addSeparator()

        pos_menu = menu.addMenu("Position")
        for pos in ["top-left", "top-right", "bottom-left", "bottom-right"]:
            label = pos.replace("-", " ").title()
            action = QAction(label, pos_menu)
            action.triggered.connect(lambda _, p=pos: self._overlay.set_position(p))
            pos_menu.addAction(action)

        menu.addSeparator()

        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(QApplication.quit)
        menu.addAction(quit_action)

        self.setContextMenu(menu)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._overlay.toggle_visibility()
