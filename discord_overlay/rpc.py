import json
import os
import socket
import struct
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from PyQt6.QtCore import QThread, pyqtSignal

OP_HANDSHAKE = 0
OP_FRAME = 1
OP_CLOSE = 2
OP_PING = 3
OP_PONG = 4


class DiscordRPCThread(QThread):
    connected = pyqtSignal()
    disconnected = pyqtSignal()
    voice_channel = pyqtSignal(dict)
    voice_state = pyqtSignal(dict)
    speaking_start = pyqtSignal(str)
    speaking_stop = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, config: dict):
        super().__init__()
        self._config = config
        self._sock: socket.socket | None = None
        self._running = True
        self._current_channel_id: str | None = None

    # --- public ---

    def stop(self):
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass

    # --- thread entry ---

    def run(self):
        backoff = 1.0
        while self._running:
            try:
                self._connect()
                self._handshake()
                self._authenticate()
                self.connected.emit()
                backoff = 1.0
                self._get_initial_voice_state()
                self._subscribe_global()
                self._read_loop()
            except Exception as e:
                if not self._running:
                    return
                print(f"[overlay] Error: {e}", file=sys.stderr)
                self.error.emit(str(e))
                self.disconnected.emit()
            finally:
                if self._sock:
                    try:
                        self._sock.close()
                    except OSError:
                        pass
                    self._sock = None
                self._current_channel_id = None

            if not self._running:
                return
            self.msleep(int(backoff * 1000))
            backoff = min(backoff * 2, 30.0)

    # --- IPC socket ---

    def _find_ipc_socket(self) -> str:
        runtime_dir = os.environ.get(
            "XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"
        )
        search_dirs = [
            runtime_dir,
            os.path.join(runtime_dir, "snap.discord"),
            os.path.join(runtime_dir, "app", "com.discordapp.Discord"),
        ]
        for d in search_dirs:
            for i in range(10):
                path = os.path.join(d, f"discord-ipc-{i}")
                if os.path.exists(path):
                    return path
        raise FileNotFoundError(
            "Discord IPC socket not found. Is Discord running?"
        )

    def _connect(self):
        path = self._find_ipc_socket()
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.connect(path)

    def _send(self, opcode: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        header = struct.pack("<II", opcode, len(body))
        self._sock.sendall(header + body)

    def _recv(self) -> tuple[int, dict]:
        header = self._recv_exact(8)
        opcode, length = struct.unpack("<II", header)
        body = self._recv_exact(length)
        return opcode, json.loads(body)

    def _recv_exact(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self._sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("Discord IPC connection closed")
            buf += chunk
        return buf

    # --- auth flow ---

    def _handshake(self):
        self._send(OP_HANDSHAKE, {
            "v": 1,
            "client_id": self._config["client_id"],
        })
        op, data = self._recv()
        if op == OP_CLOSE:
            raise ConnectionError(
                f"Discord rejected handshake: {data.get('data', {}).get('message', data)}"
            )

    def _authenticate(self):
        token = self._config.get("access_token", "")
        expires = self._config.get("token_expires_at", 0)

        if token and time.time() < expires:
            try:
                self._send_authenticate(token)
                return
            except Exception:
                pass

        refresh = self._config.get("refresh_token", "")
        if refresh:
            try:
                token_data = self._refresh_token(refresh)
                self._store_token(token_data)
                self._send_authenticate(token_data["access_token"])
                return
            except Exception:
                pass

        nonce = str(uuid.uuid4())
        self._send(OP_FRAME, {
            "cmd": "AUTHORIZE",
            "args": {
                "client_id": self._config["client_id"],
                "scopes": ["rpc", "rpc.voice.read"],
            },
            "nonce": nonce,
        })
        op, data = self._recv()
        if data.get("evt") == "ERROR":
            raise ConnectionError(
                f"Authorization failed: {data.get('data', {}).get('message', data)}"
            )

        code = data.get("data", {}).get("code", "")
        if not code:
            raise ConnectionError("No auth code received from Discord")

        try:
            token_data = self._exchange_code(code)
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            raise ConnectionError(f"Token exchange failed ({e.code}): {body}")
        self._store_token(token_data)
        self._send_authenticate(token_data["access_token"])

    def _send_authenticate(self, token: str):
        nonce = str(uuid.uuid4())
        self._send(OP_FRAME, {
            "cmd": "AUTHENTICATE",
            "args": {"access_token": token},
            "nonce": nonce,
        })
        op, data = self._recv()
        if data.get("evt") == "ERROR":
            raise ConnectionError(
                f"Authentication failed: {data.get('data', {}).get('message', data)}"
            )

    _HTTP_HEADERS = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "DiscordLinuxOverlay/0.1.0",
    }

    def _exchange_code(self, code: str) -> dict:
        body = urllib.parse.urlencode({
            "grant_type": "authorization_code",
            "code": code,
            "client_id": self._config["client_id"],
            "client_secret": self._config["client_secret"],
            "redirect_uri": "http://localhost",
        }).encode()
        req = urllib.request.Request(
            "https://discord.com/api/oauth2/token",
            data=body,
            headers=self._HTTP_HEADERS,
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())

    def _refresh_token(self, refresh: str) -> dict:
        body = urllib.parse.urlencode({
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "client_id": self._config["client_id"],
            "client_secret": self._config["client_secret"],
        }).encode()
        req = urllib.request.Request(
            "https://discord.com/api/oauth2/token",
            data=body,
            headers=self._HTTP_HEADERS,
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())

    def _store_token(self, token_data: dict):
        self._config["access_token"] = token_data["access_token"]
        self._config["refresh_token"] = token_data.get("refresh_token", "")
        self._config["token_expires_at"] = time.time() + token_data.get("expires_in", 604800)
        from . import config as cfg_mod
        cfg_mod.save_config(self._config)

    # --- voice subscriptions ---

    def _get_initial_voice_state(self):
        nonce = str(uuid.uuid4())
        self._send(OP_FRAME, {
            "cmd": "GET_SELECTED_VOICE_CHANNEL",
            "nonce": nonce,
        })
        op, data = self._recv()
        channel = data.get("data")
        if channel and channel.get("id"):
            self.voice_channel.emit(channel)
            self._current_channel_id = channel["id"]
            self._subscribe_channel_events(channel["id"])
        else:
            self.voice_channel.emit({})

    def _subscribe_global(self):
        self._send(OP_FRAME, {
            "cmd": "SUBSCRIBE",
            "evt": "VOICE_CHANNEL_SELECT",
            "nonce": str(uuid.uuid4()),
        })
        self._recv()

    def _subscribe_channel_events(self, channel_id: str):
        for evt in [
            "VOICE_STATE_CREATE",
            "VOICE_STATE_UPDATE",
            "VOICE_STATE_DELETE",
            "SPEAKING_START",
            "SPEAKING_STOP",
        ]:
            self._send(OP_FRAME, {
                "cmd": "SUBSCRIBE",
                "evt": evt,
                "args": {"channel_id": channel_id},
                "nonce": str(uuid.uuid4()),
            })
            self._recv()

    def _unsubscribe_channel_events(self, channel_id: str):
        for evt in [
            "VOICE_STATE_CREATE",
            "VOICE_STATE_UPDATE",
            "VOICE_STATE_DELETE",
            "SPEAKING_START",
            "SPEAKING_STOP",
        ]:
            try:
                self._send(OP_FRAME, {
                    "cmd": "UNSUBSCRIBE",
                    "evt": evt,
                    "args": {"channel_id": channel_id},
                    "nonce": str(uuid.uuid4()),
                })
                self._recv()
            except Exception:
                pass

    # --- event loop ---

    def _read_loop(self):
        while self._running:
            opcode, data = self._recv()

            if opcode == OP_CLOSE:
                raise ConnectionError("Discord closed the connection")
            if opcode == OP_PING:
                self._send(OP_PONG, data)
                continue
            if opcode != OP_FRAME:
                continue

            evt = data.get("evt")
            payload = data.get("data", {})

            if evt == "VOICE_CHANNEL_SELECT":
                channel_id = payload.get("channel_id")
                if self._current_channel_id:
                    self._unsubscribe_channel_events(self._current_channel_id)
                    self._current_channel_id = None

                if channel_id:
                    nonce = str(uuid.uuid4())
                    self._send(OP_FRAME, {
                        "cmd": "GET_CHANNEL",
                        "args": {"channel_id": channel_id},
                        "nonce": nonce,
                    })
                    _, ch_data = self._recv()
                    channel_info = ch_data.get("data", {})
                    if channel_info.get("id"):
                        self._current_channel_id = channel_info["id"]
                        self.voice_channel.emit(channel_info)
                        self._subscribe_channel_events(channel_info["id"])
                else:
                    self.voice_channel.emit({})

            elif evt == "VOICE_STATE_CREATE":
                self.voice_state.emit({"event": "create", **payload})
            elif evt == "VOICE_STATE_UPDATE":
                self.voice_state.emit({"event": "update", **payload})
            elif evt == "VOICE_STATE_DELETE":
                self.voice_state.emit({"event": "delete", **payload})
            elif evt == "SPEAKING_START":
                uid = payload.get("user_id", "")
                if uid:
                    self.speaking_start.emit(uid)
            elif evt == "SPEAKING_STOP":
                uid = payload.get("user_id", "")
                if uid:
                    self.speaking_stop.emit(uid)
