from PyQt6.QtCore import Qt, QPoint, QRectF, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import QApplication, QWidget

from . import x11
from .avatars import AvatarManager

PANEL_WIDTH = 200
USER_HEIGHT = 36
HEADER_HEIGHT = 24
PADDING = 10
AVATAR_SIZE = 28
RADIUS = 8
MARGIN = 4
RING_WIDTH = 2.0

BG_COLOR = QColor(30, 31, 34, 150)
TEXT_COLOR = QColor(219, 222, 225)
DIM_COLOR = QColor(148, 155, 164)
SPEAKING_COLOR = QColor(35, 165, 90)
MUTED_COLOR = QColor(242, 63, 67)
DISCONNECT_COLOR = QColor(240, 160, 60)

STATUS_HEIGHT = 20


class OverlayWindow(QWidget):
    lock_changed = pyqtSignal(bool)

    def __init__(self, config: dict):
        super().__init__()
        self._config = config
        self._channel_name = ""
        self._users: dict[str, dict] = {}
        self._speaking_timers: dict[str, QTimer] = {}
        self._status_msg = ""
        self._avatars = AvatarManager()
        self._avatars.avatar_ready.connect(self._on_avatar_ready)
        self._locked = True
        self._was_connected = False
        self._drag_pos: QPoint | None = None
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
        w = PANEL_WIDTH + 2 * MARGIN
        h = self._calculate_height()
        self.setFixedSize(w, h)

        # If user dragged to a custom position, keep it
        cx = self._config.get("custom_x")
        cy = self._config.get("custom_y")
        if cx is not None and cy is not None:
            self.move(cx, cy)
            return

        screen = QApplication.primaryScreen()
        if not screen:
            return
        geo = screen.geometry()
        pos = self._config.get("position", "bottom-left")
        ox = self._config.get("offset_x", 10)
        oy = self._config.get("offset_y", 10)

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
        h = MARGIN * 2 + PADDING
        if self._channel_name:
            h += HEADER_HEIGHT
        h += n * USER_HEIGHT
        if self._status_msg:
            h += STATUS_HEIGHT
        if n > 0:
            h += PADDING
        return max(h, MARGIN * 2 + HEADER_HEIGHT + PADDING * 2)

    # --- slots ---

    def _on_avatar_ready(self, user_id: str):
        if user_id in self._users:
            self.update()

    def on_connected(self):
        self._was_connected = True
        self._status_msg = ""
        self.update()

    def on_disconnected(self):
        if not self._was_connected:
            return
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
            avatar_hash = user.get("avatar")
            self._users[uid] = {
                "username": nick,
                "avatar_hash": avatar_hash,
                "speaking": False,
                "muted": vs.get("mute", False),
                "deafened": vs.get("deaf", False),
                "self_mute": vs.get("self_mute", False),
                "self_deaf": vs.get("self_deaf", False),
            }
            self._avatars.request(uid, avatar_hash)
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
            avatar_hash = user.get("avatar")
            self._users[uid] = {
                "username": nick,
                "avatar_hash": avatar_hash,
                "speaking": False,
                "muted": data.get("mute", False),
                "deafened": data.get("deaf", False),
                "self_mute": data.get("self_mute", False),
                "self_deaf": data.get("self_deaf", False),
            }
            self._avatars.request(uid, avatar_hash)
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
        if not self._was_connected:
            return
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
        self._config.pop("custom_x", None)
        self._config.pop("custom_y", None)
        from . import config as cfg_mod
        cfg_mod.save_config(self._config)
        self._reposition()

    @property
    def locked(self) -> bool:
        return self._locked

    def set_locked(self, locked: bool):
        self._locked = locked
        wid = int(self.winId())
        if locked:
            x11.set_click_through(wid)
        else:
            x11.remove_click_through(wid)
        self.lock_changed.emit(locked)
        self.update()

    def mousePressEvent(self, event):
        if not self._locked and event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if not self._locked and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if not self._locked and event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = None
            # Save custom position
            p = self.pos()
            self._config["custom_x"] = p.x()
            self._config["custom_y"] = p.y()
            from . import config as cfg_mod
            cfg_mod.save_config(self._config)
            event.accept()

    # --- painting ---

    def paintEvent(self, _):
        if not self._channel_name and not self._users and not self._status_msg:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        panel = QRectF(MARGIN, MARGIN, PANEL_WIDTH, self.height() - 2 * MARGIN)
        bg_path = QPainterPath()
        bg_path.addRoundedRect(panel, RADIUS, RADIUS)
        p.fillPath(bg_path, QBrush(BG_COLOR))

        if not self._locked:
            p.setPen(QPen(QColor(88, 101, 242, 200), 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(panel.adjusted(0.5, 0.5, -0.5, -0.5), RADIUS, RADIUS)

        y = MARGIN + PADDING
        x = MARGIN + PADDING

        if self._channel_name:
            p.setPen(QPen(DIM_COLOR))
            f = QFont("Sans", 8, QFont.Weight.DemiBold)
            f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.5)
            p.setFont(f)
            p.drawText(
                int(x), int(y),
                int(PANEL_WIDTH - PADDING * 2), HEADER_HEIGHT,
                Qt.AlignmentFlag.AlignVCenter,
                self._channel_name.upper(),
            )
            y += HEADER_HEIGHT

        max_users = self._config.get("max_users", 10)
        for i, (uid, user) in enumerate(self._users.items()):
            if i >= max_users:
                break
            self._paint_user(p, uid, x, y, user)
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

    def _paint_user(self, p: QPainter, uid: str, x: float, y: float, user: dict):
        speaking = user["speaking"]
        muted = user["muted"] or user["self_mute"]
        deafened = user["deafened"] or user["self_deaf"]

        avatar_y = y + (USER_HEIGHT - AVATAR_SIZE) / 2
        avatar_rect = QRectF(x, avatar_y, AVATAR_SIZE, AVATAR_SIZE)

        # avatar image (circular clip)
        pixmap = self._avatars.get(uid)
        if pixmap:
            clip = QPainterPath()
            clip.addEllipse(avatar_rect)
            p.save()
            p.setClipPath(clip)
            scaled = pixmap.scaled(
                AVATAR_SIZE, AVATAR_SIZE,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            p.drawPixmap(avatar_rect.toRect(), scaled)
            p.restore()
        else:
            # fallback: colored initial
            hue = hash(user["username"]) % 360
            bg = QColor.fromHsv(hue, 100, 140)
            circle = QPainterPath()
            circle.addEllipse(avatar_rect)
            p.fillPath(circle, QBrush(bg))
            p.setPen(QPen(QColor(255, 255, 255)))
            p.setFont(QFont("Sans", 10, QFont.Weight.Bold))
            p.drawText(avatar_rect.toRect(), Qt.AlignmentFlag.AlignCenter,
                       user["username"][0].upper())

        # speaking ring
        if speaking:
            p.setPen(QPen(SPEAKING_COLOR, RING_WIDTH))
            p.setBrush(Qt.BrushStyle.NoBrush)
            ring = avatar_rect.adjusted(-1, -1, 1, 1)
            p.drawEllipse(ring)

        # username
        text_x = x + AVATAR_SIZE + 10
        text_color = SPEAKING_COLOR if speaking else TEXT_COLOR
        if muted or deafened:
            text_color = DIM_COLOR
        p.setPen(QPen(text_color))
        p.setFont(QFont("Sans", 9, QFont.Weight.Medium))

        name = user["username"]
        if len(name) > 16:
            name = name[:15] + "…"

        text_w = int(PANEL_WIDTH - AVATAR_SIZE - PADDING * 2 - 24)
        p.drawText(
            int(text_x), int(y), text_w, USER_HEIGHT,
            Qt.AlignmentFlag.AlignVCenter, name,
        )

        # mute/deafen indicator
        if deafened or muted:
            icon_x = x + PANEL_WIDTH - PADDING * 2 - 12
            icon_cy = y + USER_HEIGHT / 2
            self._draw_status_icon(p, icon_x, icon_cy, deafened)

    def _draw_status_icon(self, p: QPainter, x: float, cy: float, deafened: bool):
        p.setPen(QPen(MUTED_COLOR, 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        if deafened:
            # headphone shape
            p.drawArc(QRectF(x, cy - 5, 10, 8), 0, 180 * 16)
            p.drawLine(int(x), int(cy - 1), int(x), int(cy + 4))
            p.drawLine(int(x + 10), int(cy - 1), int(x + 10), int(cy + 4))
        else:
            # mic shape
            p.drawRoundedRect(QRectF(x + 2, cy - 5, 6, 8), 3, 3)
            p.drawLine(int(x + 5), int(cy + 3), int(x + 5), int(cy + 5))
        # slash
        p.setPen(QPen(MUTED_COLOR, 2.0))
        p.drawLine(int(x), int(cy + 5), int(x + 10), int(cy - 5))
