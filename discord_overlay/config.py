import json
import os
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

CONFIG_DIR = Path(
    os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
) / "discord-overlay"
CONFIG_PATH = CONFIG_DIR / "config.json"

_DEFAULTS = {
    "client_id": "",
    "client_secret": "",
    "access_token": "",
    "refresh_token": "",
    "token_expires_at": 0,
    "position": "bottom-left",
    "offset_x": 10,
    "offset_y": 10,
    "max_users": 10,
    "opacity": 0.85,
    "show_channel_name": True,
    "lock_hotkey": "Ctrl+Shift+O",
}


def load_config() -> dict:
    cfg = dict(_DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH) as f:
                stored = json.load(f)
            cfg.update(stored)
        except (json.JSONDecodeError, OSError):
            pass
    return cfg


def save_config(cfg: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)
    os.chmod(CONFIG_PATH, 0o600)


class FirstRunDialog(QDialog):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self._config = config
        self.setWindowTitle("Discord Overlay Setup")
        self.setFixedWidth(480)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        heading = QLabel("Discord Application Setup")
        heading.setFont(QFont("Sans", 14, QFont.Weight.Bold))
        layout.addWidget(heading)

        instructions = QLabel(
            "To use this overlay, you need a Discord Application.\n\n"
            "1. Go to discord.com/developers/applications\n"
            "2. Click 'New Application' and give it a name\n"
            "3. Copy the Application ID (Client ID) below\n"
            "4. Go to OAuth2 in the sidebar\n"
            "5. Copy the Client Secret\n"
            "6. Add redirect URI: http://localhost\n"
            "7. Save changes"
        )
        instructions.setWordWrap(True)
        instructions.setFont(QFont("Sans", 10))
        layout.addWidget(instructions)

        layout.addSpacing(8)

        id_label = QLabel("Client ID:")
        id_label.setFont(QFont("Sans", 10))
        layout.addWidget(id_label)
        self._id_input = QLineEdit()
        self._id_input.setPlaceholderText("e.g. 123456789012345678")
        layout.addWidget(self._id_input)

        secret_label = QLabel("Client Secret:")
        secret_label.setFont(QFont("Sans", 10))
        layout.addWidget(secret_label)
        self._secret_input = QLineEdit()
        self._secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._secret_input.setPlaceholderText("e.g. AbCdEfGhIjKlMnOpQrStUvWxYz")
        layout.addWidget(self._secret_input)

        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: #f04747;")
        layout.addWidget(self._error_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

    def _on_save(self):
        client_id = self._id_input.text().strip()
        client_secret = self._secret_input.text().strip()

        if not client_id or not client_secret:
            self._error_label.setText("Both fields are required.")
            return

        if not client_id.isdigit():
            self._error_label.setText("Client ID should be a number.")
            return

        self._config["client_id"] = client_id
        self._config["client_secret"] = client_secret
        save_config(self._config)
        self.accept()
