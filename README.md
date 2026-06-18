# Discord Linux Overlay

A transparent, click-through voice overlay for Discord on Linux (X11). Shows who's in your voice channel and highlights speakers in real-time.

Built with PyQt6. No Electron, no browser, no bloat.

## Features

- Transparent, always-on-top overlay that doesn't steal focus
- Click-through — interact with your game right through it
- Real-time speaking indicators (green glow)
- Mute/deafen status icons
- Auto-hides when not in a voice channel
- Auto-reconnects if Discord restarts
- System tray icon with position controls
- Configurable corner placement

## Requirements

- Linux with X11 (Wayland not supported)
- Python 3.10+
- PyQt6
- Discord desktop app (not browser)
- `xprop` (usually pre-installed)

### Arch / CachyOS

```bash
sudo pacman -S python-pyqt6 xorg-xprop
```

### Ubuntu / Debian

```bash
sudo apt install python3-pyqt6 x11-utils
```

### pip

```bash
pip install PyQt6
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
cd discord-overlay
python -m discord_overlay
```

On first run, a setup dialog will ask for your Client ID and Client Secret. These are stored locally at `~/.config/discord-overlay/config.json` and never sent anywhere except Discord's API.

After entering credentials, Discord will show an authorization popup — click **Authorize**.

### 3. Join a voice channel

The overlay appears automatically when you join a voice channel and hides when you leave.

## Usage

- **System tray icon**: right-click for options, left-click to toggle visibility
- **Position**: change via tray menu (top-left, top-right, bottom-left, bottom-right)

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

## Troubleshooting

**"Discord IPC socket not found"**
- Make sure Discord desktop app is running (not the browser version)
- If using Flatpak Discord, the socket path may differ — open an issue

**Authorization popup doesn't appear**
- Make sure Discord is focused / not minimized
- Try restarting Discord

**Overlay doesn't appear**
- Join a voice channel first — the overlay auto-hides when not in voice
- Check the system tray icon — left-click to toggle visibility

**Click-through not working**
- Requires X11. Wayland is not supported
- Make sure `libXfixes` is installed: `pacman -Qs libxfixes` or `apt list --installed 2>/dev/null | grep libxfixes`

## License

MIT
