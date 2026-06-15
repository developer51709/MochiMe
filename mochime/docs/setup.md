# 🛠️ MochiMe — Setup Guide

---

## Requirements

| Requirement | Minimum | Recommended |
|---|---|---|
| Python | 3.10 | 3.11+ |
| discord.py | 2.4.0 | 2.7+ |
| aiosqlite | 0.20.0 | latest |
| aiohttp | 3.9.0 | latest |
| Discord Bot Token | — | — |

---

## Getting a Discord Bot Token

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
2. Click **New Application** → give it a name (e.g. `MochiMe`)
3. Go to **Bot** → click **Reset Token** → copy the token
4. Under **Privileged Gateway Intents**, enable:
   - ✅ Server Members Intent
   - ✅ Message Content Intent
5. Under **Installation** → **Default Install Settings**:
   - Guild: `bot`, `applications.commands`
   - User: `applications.commands` (for user-install app commands)

---

## Platform-specific Setup

### Android (Termux)

```bash
# 1. Install Python
pkg update && pkg install python git

# 2. Clone MochiMe
git clone https://github.com/you/mochime
cd mochime

# 3. Run setup (detects Termux automatically)
python -m mochime --setup

# 4. Start the bot
python -m mochime

# Optional: run in background, survive terminal close
nohup python -m mochime > mochime.log 2>&1 &

# Optional: keep screen awake while bot runs
termux-wake-lock
```

To auto-start on device boot, install the **Termux:Boot** add-on from F-Droid,
then create `~/.termux/boot/start-mochime.sh`:
```bash
#!/data/data/com.termux/files/usr/bin/bash
cd ~/mochime && python -m mochime >> ~/mochime.log 2>&1 &
```

---

### Windows

```powershell
# 1. Install Python 3.11+ from python.org
# 2. Clone or download MochiMe, then open PowerShell in that folder

# 3. Run setup
python -m mochime --setup

# 4. Start the bot
python -m mochime

# Run without a console window (background)
pythonw -m mochime
```

To run on startup, add a shortcut to `%AppData%\Microsoft\Windows\Start Menu\Programs\Startup`.

---

### Linux

```bash
# 1. Ensure Python 3.10+ is installed
python3 --version   # or: sudo apt install python3.11

# 2. Clone MochiMe
git clone https://github.com/you/mochime && cd mochime

# 3. Run setup
python3 -m mochime --setup

# 4. Start the bot
python3 -m mochime

# Run in background with tmux (recommended)
tmux new -s mochime
python3 -m mochime
# Ctrl+B, D  to detach
```

**Systemd service** (always-on, auto-restart):

Create `/etc/systemd/system/mochime.service`:
```ini
[Unit]
Description=MochiMe Discord Bot
After=network-online.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/home/youruser/mochime
ExecStart=python3 -m mochime
Restart=on-failure
RestartSec=5
Environment=BOT_TOKEN=your_token_here

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable --now mochime
sudo systemctl status mochime
```

---

### macOS

```bash
brew install python@3.11
git clone https://github.com/you/mochime && cd mochime
python3 -m mochime --setup
python3 -m mochime
```

---

## Inviting the bot to a server

Use this URL (replace `CLIENT_ID` with your app's ID from the Developer Portal):

```
https://discord.com/oauth2/authorize?client_id=CLIENT_ID&scope=bot+applications.commands&permissions=8
```

---

## Environment Variables

| Variable | Description |
|---|---|
| `BOT_TOKEN` | Your Discord bot token (**required**) |
| `NO_COLOR` | Set to any value to disable coloured console output |
| `FORCE_COLOR` | Set to any value to force colours even in pipes |

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: discord` | Run `python -m mochime --setup` |
| `discord.errors.LoginFailure` | BOT_TOKEN is invalid — reset it in the Dev Portal |
| Slash commands not appearing | Wait up to 1 hour for global sync, or use guild sync |
| Emojis showing as Unicode | Discord rejected SVG uploads — this is expected, fallbacks are active |
| `python: command not found` | Use `python3` instead, or install Python |
