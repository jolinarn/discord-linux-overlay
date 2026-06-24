from PyQt6.QtGui import QAction, QCursor, QIcon
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon


class TrayIcon(QSystemTrayIcon):
    def __init__(self, overlay, config: dict):
        super().__init__()
        self._overlay = overlay
        self._config = config

        icon = QIcon.fromTheme("discord", QIcon.fromTheme("audio-headphones"))
        self.setIcon(icon)
        self.setToolTip("Discord Voice Overlay")

        self._menu = self._build_menu()
        self.setContextMenu(self._menu)
        self.activated.connect(self._on_activated)
        self._overlay.lock_changed.connect(self._on_lock_changed)

    def _build_menu(self) -> QMenu:
        menu = QMenu()

        self._toggle_action = QAction("Toggle Overlay", menu)
        self._toggle_action.triggered.connect(self._overlay.toggle_visibility)
        menu.addAction(self._toggle_action)

        self._lock_action = QAction("Unlock Position", menu)
        self._lock_action.triggered.connect(self._toggle_lock)
        menu.addAction(self._lock_action)

        menu.addSeparator()

        pos_menu = menu.addMenu("Position")
        for pos in ["top-left", "top-right", "bottom-left", "bottom-right"]:
            label = pos.replace("-", " ").title()
            action = QAction(label, pos_menu)
            action.triggered.connect(lambda _, p=pos: self._overlay.set_position(p))
            pos_menu.addAction(action)

        self._screen_menu = menu.addMenu("Screen")
        self._screen_menu.aboutToShow.connect(self._populate_screens)

        menu.addSeparator()

        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(QApplication.quit)
        menu.addAction(quit_action)

        return menu

    def _toggle_lock(self):
        locked = not self._overlay.locked
        self._overlay.set_locked(locked)
        self._lock_action.setText("Unlock Position" if locked else "Lock Position")

    def _on_lock_changed(self, locked: bool):
        self._lock_action.setText("Unlock Position" if locked else "Lock Position")

    def _populate_screens(self):
        self._screen_menu.clear()
        current = self._config.get("screen", "")
        for screen in QApplication.screens():
            name = screen.name()
            geo = screen.geometry()
            label = f"{name} ({geo.width()}x{geo.height()})"
            if name == current:
                label += " *"
            action = QAction(label, self._screen_menu)
            action.triggered.connect(lambda _, s=screen: self._overlay.set_screen(s))
            self._screen_menu.addAction(action)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._menu.popup(QCursor.pos())
