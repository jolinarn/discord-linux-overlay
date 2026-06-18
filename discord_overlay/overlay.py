from PyQt6.QtCore import Qt, QRectF, QTimer
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
)
from PyQt6.QtWidgets import QApplication, QWidget

from . import x11

PANEL_WIDTH = 220
USER_HEIGHT = 32
HEADER_HEIGHT = 28
PADDING = 8
AVATAR_SIZE = 24
RADIUS = 12
GLOW_PAD = 6

BG_COLOR = QColor(10, 8, 20, 210)
BORDER_COLOR = QColor(114, 137, 218, 160)
TEXT_COLOR = QColor(200, 208, 232)
DIM_COLOR = QColor(100, 100, 140)
SPEAKING_COLOR = QColor(67, 181, 129)
MUTED_COLOR = QColor(240, 71, 71, 180)
DISCONNECT_COLOR = QColor(240, 160, 60)

STATUS_HEIGHT = 20


class OverlayWindow(QWidget):
    def __init__(self, config: dict):
        super().__init__()
        self._config = config
        self._channel_name = ""
        self._users: dict[str, dict] = {}
        self._speaking_timers: dict[str, QTimer] = {}
        self._status_msg = ""
        self._setup_window()

    def _setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.X11BypassWindowManagerHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._reposition()

    def setup_x11(self):
        wid = int(self.winId())
        x11.set_click_through(wid)
        x11.set_blur_behind(wid)

    def _reposition(self):
        screen = QApplication.primaryScreen()
        if not screen:
            return
        geo = screen.geometry()
        pos = self._config.get("position", "bottom-left")
        ox = self._config.get("offset_x", 10)
        oy = self._config.get("offset_y", 10)
        w = PANEL_WIDTH + 2 * GLOW_PAD
        h = self._calculate_height()
        self.setFixedSize(w, h)

        if "left" in pos:
            x = geo.x() + ox
        else:
            x = geo.x() + geo.width() - w - ox
        if "top" in pos:
            y = geo.y() + oy
        else:
            y = geo.y() + geo.height() - h - oy

        self.move(x, y)

    def _calculate_height(self):
        n = min(len(self._users), self._config.get("max_users", 10))
        h = GLOW_PAD * 2 + PADDING * 2
        if self._channel_name:
            h += HEADER_HEIGHT
        h += n * USER_HEIGHT
        if self._status_msg:
            h += STATUS_HEIGHT
        return max(h, GLOW_PAD * 2 + HEADER_HEIGHT + PADDING * 2)

    # --- slots ---

    def on_connected(self):
        self._status_msg = ""
        self.update()

    def on_disconnected(self):
        self._status_msg = "Reconnecting..."
        self._reposition()
        if not self.isVisible() and self._channel_name:
            self.show()
            self.setup_x11()
        self.update()

    def on_voice_channel(self, data: dict):
        if not data or not data.get("id"):
            self._channel_name = ""
            self._users.clear()
            for t in self._speaking_timers.values():
                t.stop()
            self._speaking_timers.clear()
            self.hide()
            return

        self._channel_name = data.get("name", "Voice Channel")
        self._users.clear()
        for vs in data.get("voice_states", []):
            user = vs.get("user", {})
            uid = user.get("id", "")
            if not uid:
                continue
            nick = vs.get("nick") or user.get("global_name") or user.get("username", "?")
            self._users[uid] = {
                "username": nick,
                "avatar_hash": user.get("avatar"),
                "speaking": False,
                "muted": vs.get("mute", False),
                "deafened": vs.get("deaf", False),
                "self_mute": vs.get("self_mute", False),
                "self_deaf": vs.get("self_deaf", False),
            }
        self._reposition()
        self.show()
        self.setup_x11()
        self.update()

    def on_voice_state(self, data: dict):
        event = data.get("event")
        user = data.get("user", {})
        uid = user.get("id", "")
        if not uid:
            return

        if event == "create":
            nick = data.get("nick") or user.get("global_name") or user.get("username", "?")
            self._users[uid] = {
                "username": nick,
                "avatar_hash": user.get("avatar"),
                "speaking": False,
                "muted": data.get("mute", False),
                "deafened": data.get("deaf", False),
                "self_mute": data.get("self_mute", False),
                "self_deaf": data.get("self_deaf", False),
            }
        elif event == "update" and uid in self._users:
            nick = data.get("nick") or user.get("global_name") or user.get("username")
            if nick:
                self._users[uid]["username"] = nick
            self._users[uid]["muted"] = data.get("mute", False)
            self._users[uid]["deafened"] = data.get("deaf", False)
            self._users[uid]["self_mute"] = data.get("self_mute", False)
            self._users[uid]["self_deaf"] = data.get("self_deaf", False)
        elif event == "delete":
            self._users.pop(uid, None)
            if uid in self._speaking_timers:
                self._speaking_timers.pop(uid).stop()

        self._reposition()
        self.update()

    def on_speaking_start(self, user_id: str):
        if user_id in self._users:
            self._users[user_id]["speaking"] = True
            if user_id in self._speaking_timers:
                self._speaking_timers[user_id].stop()
            self.update()

    def on_speaking_stop(self, user_id: str):
        if user_id not in self._users:
            return
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda uid=user_id: self._clear_speaking(uid))
        timer.start(300)
        self._speaking_timers[user_id] = timer

    def _clear_speaking(self, user_id: str):
        if user_id in self._users:
            self._users[user_id]["speaking"] = False
            self.update()
        self._speaking_timers.pop(user_id, None)

    def on_error(self, msg: str):
        self._status_msg = msg
        self._reposition()
        if not self.isVisible():
            self.show()
            self.setup_x11()
        self.update()

    def toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.setup_x11()

    def set_position(self, position: str):
        self._config["position"] = position
        from . import config as cfg_mod
        cfg_mod.save_config(self._config)
        self._reposition()

    # --- painting ---

    def paintEvent(self, _):
        if not self._channel_name and not self._users and not self._status_msg:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        gp = GLOW_PAD
        panel = QRectF(gp, gp, self.width() - 2 * gp, self.height() - 2 * gp)

        path = QPainterPath()
        path.addRoundedRect(panel, RADIUS, RADIUS)
        p.fillPath(path, QBrush(BG_COLOR))

        p.setPen(QPen(BORDER_COLOR, 1.0))
        p.drawRoundedRect(panel.adjusted(0.5, 0.5, -0.5, -0.5), RADIUS, RADIUS)

        y = gp + PADDING
        x = gp + PADDING

        if self._channel_name:
            p.setPen(QPen(DIM_COLOR))
            p.setFont(QFont("Sans", 8))
            p.drawText(
                int(x), int(y),
                int(PANEL_WIDTH - PADDING * 2), HEADER_HEIGHT,
                Qt.AlignmentFlag.AlignVCenter,
                f"\U0001f50a {self._channel_name}",
            )
            y += HEADER_HEIGHT

        max_users = self._config.get("max_users", 10)
        for i, (uid, user) in enumerate(self._users.items()):
            if i >= max_users:
                break
            self._paint_user(p, x, y, user)
            y += USER_HEIGHT

        if self._status_msg:
            p.setPen(QPen(DISCONNECT_COLOR))
            p.setFont(QFont("Sans", 7))
            p.drawText(
                int(x), int(y),
                int(PANEL_WIDTH - PADDING * 2), STATUS_HEIGHT,
                Qt.AlignmentFlag.AlignVCenter,
                self._status_msg,
            )

        p.end()

    def _paint_user(self, p: QPainter, x: float, y: float, user: dict):
        speaking = user["speaking"]
        muted = user["muted"] or user["self_mute"]
        deafened = user["deafened"] or user["self_deaf"]

        avatar_y = y + (USER_HEIGHT - AVATAR_SIZE) / 2
        avatar_rect = QRectF(x, avatar_y, AVATAR_SIZE, AVATAR_SIZE)

        if speaking:
            glow = QColor(SPEAKING_COLOR)
            glow.setAlpha(60)
            p.setBrush(QBrush(glow))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(avatar_rect.adjusted(-3, -3, 3, 3))

        hue = hash(user["username"]) % 360
        avatar_bg = QColor.fromHsv(hue, 120, 180)
        if speaking:
            avatar_bg = SPEAKING_COLOR

        avatar_path = QPainterPath()
        avatar_path.addEllipse(avatar_rect)
        p.fillPath(avatar_path, QBrush(avatar_bg))

        p.setPen(QPen(QColor(255, 255, 255)))
        p.setFont(QFont("Sans", 10, QFont.Weight.Bold))
        p.drawText(avatar_rect.toRect(), Qt.AlignmentFlag.AlignCenter,
                   user["username"][0].upper())

        text_x = x + AVATAR_SIZE + 8
        text_color = SPEAKING_COLOR if speaking else TEXT_COLOR
        if muted or deafened:
            text_color = DIM_COLOR
        p.setPen(QPen(text_color))
        p.setFont(QFont("Sans", 9))

        name = user["username"]
        if len(name) > 18:
            name = name[:17] + "…"

        text_w = int(PANEL_WIDTH - AVATAR_SIZE - PADDING * 3 - 20)
        p.drawText(
            int(text_x), int(y), text_w, USER_HEIGHT,
            Qt.AlignmentFlag.AlignVCenter, name,
        )

        icon_x = x + PANEL_WIDTH - PADDING * 2 - 14
        icon_cy = y + USER_HEIGHT / 2
        if deafened:
            self._draw_icon(p, icon_x, icon_cy, MUTED_COLOR, deafened=True)
        elif muted:
            self._draw_icon(p, icon_x, icon_cy, MUTED_COLOR, deafened=False)

    def _draw_icon(self, p: QPainter, x: float, cy: float, color: QColor, deafened: bool):
        p.setPen(QPen(color, 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        if deafened:
            p.drawEllipse(QRectF(x, cy - 5, 10, 10))
        else:
            p.drawRoundedRect(QRectF(x + 2, cy - 5, 6, 10), 2, 2)
        p.drawLine(int(x), int(cy + 6), int(x + 10), int(cy - 6))
