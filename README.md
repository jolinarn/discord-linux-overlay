# Discord Linux Overlay

A transparent, click-through voice overlay for Discord on Linux. Shows who's in your voice channel with their profile pictures and highlights speakers in real-time — just like Discord's native overlay, but for Linux.

Works on both X11 and Wayland (KDE Plasma).

Built with PyQt6. No Electron, no browser, no bloat.

## Features

- **Discord-style UI** — dark panel with rounded avatars, matching Discord's native overlay look
- **Profile pictures** — downloads and caches user avatars from Discord
- **Speaking indicators** — green ring around avatar when someone talks
- **X11 + Wayland** — works on both, with layer-shell support on KDE Plasma Wayland
- **Click-through** — interact with your game right through the overlay
- **Draggable** — unlock, drag anywhere on screen, lock back in place (X11)
- **Screen selection** — pick which monitor to display on (Wayland)
- **Mute/deafen icons** — see who's muted or deafened at a glance
- **Auto-hide** — appears when you join voice, disappears when you leave
- **Auto-reconnect** — reconnects automatically if Discord restarts
- **CLI controls** — toggle lock and visibility from terminal or keyboard shortcuts

## Requirements

- Linux (X11 or Wayland)
- Python 3.10+
- PyQt6
- Discord desktop app (not browser)

**X11 only:** `xprop`, `libXfixes` (usually pre-installed)

**Wayland only:** `dbus-python`, `PyGObject`, `layer-shell-qt` (for KDE Plasma)

### Arch / CachyOS

```bash
# X11
sudo pacman -S python-pyqt6 xorg-xprop

# Wayland (KDE Plasma)
sudo pacman -S python-pyqt6 python-dbus python-gobject layer-shell-qt
```

### Ubuntu / Debian

```bash
# X11
sudo apt install python3-pyqt6 x11-utils

# Wayland (KDE Plasma)
sudo apt install python3-pyqt6 python3-dbus python3-gi layer-shell-qt
```

### pip

```bash
pip install PyQt6 dbus-python PyGObject
```

## Setup

### 1. Create a Discord Application

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
2. Click **New Application**, name it whatever you want
3. On the **General Information** page, copy the **Application ID** (this is your Client ID)
4. Go to **OAuth2** in the sidebar
5. Copy the **Client Secret**
6. Under **Redirects**, add: `http://localhost`
7. Click **Save Changes**

### 2. Run the overlay

```bash
cd discord-linux-overlay
python -m discord_overlay
```

On first run, a setup dialog will ask for your Client ID and Client Secret. These are stored locally at `~/.config/discord-overlay/config.json` and never sent anywhere except Discord's API.

After entering credentials, Discord will show an authorization popup — click **Authorize**.

### 3. Join a voice channel

The overlay appears automatically when you join a voice channel and hides when you leave.

## Usage

### Moving the overlay

The overlay is click-through by default. To reposition it:

```bash
# Unlock — a blue border appears, drag the overlay wherever you want
python -m discord_overlay --toggle-lock

# Lock — click-through is re-enabled
python -m discord_overlay --toggle-lock
```

### Toggle visibility

```bash
python -m discord_overlay --toggle
```

### Convenience script

A wrapper script is included so you can run commands from anywhere:

```bash
# Symlink to your PATH (one-time setup)
ln -sf ~/discord-linux-overlay/overlay-ctl ~/.local/bin/discord-overlay

# Then use from anywhere
discord-overlay --toggle-lock
discord-overlay --toggle
```

### KDE keyboard shortcuts

Bind these commands to keyboard shortcuts for quick in-game access:

1. System Settings → Shortcuts → Custom Shortcuts
2. Add new → Global Shortcut → Command/URL
3. Set a trigger key (e.g. `Super+Shift+D`)
4. Set the action to the command above

### System tray

Right-click the tray icon for quick access to:

- **Toggle Overlay** — show/hide
- **Unlock/Lock Position** — toggle click-through for dragging (X11)
- **Position** — snap to a corner (top-left, top-right, bottom-left, bottom-right)
- **Screen** — pick which monitor to display on (Wayland)

## Configuration

Config is stored at `~/.config/discord-overlay/config.json`:

| Key | Default | Description |
|-----|---------|-------------|
| `position` | `bottom-left` | Overlay corner position |
| `offset_x` | `10` | Horizontal offset from screen edge |
| `offset_y` | `10` | Vertical offset from screen edge |
| `max_users` | `10` | Max users shown in overlay |
| `opacity` | `0.85` | Background opacity |
| `show_channel_name` | `true` | Show voice channel name |
| `screen` | (primary) | Monitor name, e.g. `DP-1` (Wayland) |
| `lock_hotkey` | `Ctrl+Shift+O` | Global hotkey to toggle lock |

## Troubleshooting

**"Discord IPC socket not found"**
- Make sure Discord desktop app is running (not the browser version)
- If using Flatpak Discord, the socket path may differ — open an issue

**Authorization popup doesn't appear**
- Make sure Discord is focused / not minimized
- Try restarting Discord

**Overlay doesn't appear**
- Join a voice channel first — the overlay auto-hides when not in voice
- Try toggling visibility: `python -m discord_overlay --toggle`

**Click-through not working (X11)**
- Make sure `libXfixes` is installed: `pacman -Qs libxfixes` or `apt list --installed 2>/dev/null | grep libxfixes`

**Overlay stuck on wrong monitor (Wayland)**
- Right-click the tray icon → Screen → pick the correct monitor

**Hotkey not working (Wayland)**
- The XDG GlobalShortcuts portal registers the shortcut, but KDE may require you to assign the key in System Settings → Shortcuts → Global Shortcuts

**Token exchange fails (403 / error 1010)**
- This is Cloudflare blocking the request — usually resolves on retry
- Delete `~/.config/discord-overlay/config.json` and re-run setup if it persists

## License

MIT
