import os
import threading
import urllib.request
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QPixmap

CACHE_DIR = Path(
    os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")
) / "discord-overlay" / "avatars"

_CDN = "https://cdn.discordapp.com"
_HEADERS = {"User-Agent": "DiscordLinuxOverlay/0.1.0"}


class AvatarManager(QObject):
    avatar_ready = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._pixmaps: dict[str, QPixmap] = {}
        self._pending: set[str] = set()

    def get(self, user_id: str) -> QPixmap | None:
        return self._pixmaps.get(user_id)

    def request(self, user_id: str, avatar_hash: str | None):
        if user_id in self._pixmaps or user_id in self._pending:
            return

        cached = CACHE_DIR / f"{user_id}.png"
        if cached.exists():
            pm = QPixmap(str(cached))
            if not pm.isNull():
                self._pixmaps[user_id] = pm
                return

        self._pending.add(user_id)
        t = threading.Thread(
            target=self._download, args=(user_id, avatar_hash), daemon=True
        )
        t.start()

    def _download(self, user_id: str, avatar_hash: str | None):
        try:
            if avatar_hash:
                ext = "gif" if avatar_hash.startswith("a_") else "png"
                url = f"{_CDN}/avatars/{user_id}/{avatar_hash}.png?size=64"
            else:
                index = (int(user_id) >> 22) % 6
                url = f"{_CDN}/embed/avatars/{index}.png?size=64"

            req = urllib.request.Request(url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = resp.read()

            path = CACHE_DIR / f"{user_id}.png"
            with open(path, "wb") as f:
                f.write(data)

            pm = QPixmap(str(path))
            if not pm.isNull():
                self._pixmaps[user_id] = pm
        except Exception:
            pass
        finally:
            self._pending.discard(user_id)
            self.avatar_ready.emit(user_id)

    def clear(self):
        self._pixmaps.clear()
        self._pending.clear()
