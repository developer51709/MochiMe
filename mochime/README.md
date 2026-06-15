# 🌸 MochiMe

> A cute, pastel Discord bot with a Nekotina-style command system — built with discord.py and Components v2 UI.

[![Python](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square)](https://python.org)
[![discord.py](https://img.shields.io/badge/discord.py-2.4%2B-5865F2?style=flat-square)](https://discordpy.readthedocs.io)
[![License](https://img.shields.io/badge/license-MIT-pink?style=flat-square)](LICENSE)
[![Termux](https://img.shields.io/badge/Termux-friendly-brightgreen?style=flat-square)](https://termux.dev)

---

## ✨ Features

- **Components v2 UI** — All messages use Discord's CV2 containers, no legacy embeds
- **Dual command system** — Every command works as both `mochi <cmd>` prefix and `/slash`
- **6 right-click context menus** — Hug, Pat, Kiss, Bonk, Cuddle, Poke directly from any user
- **Animated RP GIFs** — All roleplay commands embed live anime GIFs
- **Phosphor Icons** — 44 real Phosphor icons auto-downloaded and registered as app emojis
- **SQLite database** — Logs moderation actions, RP stats, server settings
- **Termux-friendly** — Pure Python, no compiled libraries, runs on Android

---

## 🚀 Quick Start

### 1. Clone / download

```bash
git clone https://github.com/you/mochime
cd mochime
```

### 2. Run setup (auto-detects your platform)

```bash
python -m mochime --setup
```

This will:
- Check your Python version (3.10+ required)
- Install all dependencies
- Prompt for your Discord bot token if not set
- Print platform-specific tips (Termux, Windows, Linux)

### 3. Start the bot

```bash
python -m mochime
```

---

## 📱 Termux (Android)

```bash
pkg update && pkg install python git
git clone https://github.com/you/mochime && cd mochime
python -m mochime --setup
python -m mochime
```

Keep it running in the background:
```bash
nohup python -m mochime &
```

---

## ⚙️ Configuration

| Variable | Description | Required |
|---|---|---|
| `BOT_TOKEN` | Your Discord bot token | ✅ |

Set it in your shell:
```bash
export BOT_TOKEN=your_token_here
```
Or let `--setup` save it to a `.env` file automatically.

### Bot permissions required

| Permission | Reason |
|---|---|
| `Send Messages` | Send CV2 responses |
| `Use Application Commands` | Slash commands |
| `Manage Messages` | Moderation |
| `Ban Members` | `mochi ban` |
| `Kick Members` | `mochi kick` |
| `Moderate Members` | `mochi mute` |
| `Read Message History` | Context menus |

---

## 🌸 Commands

### Roleplay
| Command | Description |
|---|---|
| `mochi hug [@user]` | Give someone a warm hug 🫂 |
| `mochi pat [@user]` | Pat someone on the head 🌸 |
| `mochi kiss [@user]` | Give someone a sweet kiss 💋 |
| `mochi bonk [@user]` | Bonk someone on the head 🔨 |
| `mochi blush` | Express your blush 😳 |
| `mochi cuddle [@user]` | Cuddle with someone 🥰 |
| `mochi poke [@user]` | Poke someone 👉 |

### Moderation
| Command | Permissions |
|---|---|
| `mochi ban @user [reason]` | Ban Members |
| `mochi kick @user [reason]` | Kick Members |
| `mochi mute @user [mins] [reason]` | Moderate Members |
| `mochi warn @user [reason]` | Manage Messages |

### General
| Command | Description |
|---|---|
| `mochi help` | Interactive CV2 help menu |
| `mochi ping` | Check bot latency |
| `mochi about` | About MochiMe |
| `mochi info` | Server information |
| `mochi user [@user]` | User profile + RP stats |

### Server Management
| Command | Permissions |
|---|---|
| `mochi server` | View server panel |
| `mochi settings` | Show settings overview |
| `mochi setrp #channel` | Set RP channel |
| `mochi setlog #channel` | Set mod log channel |
| `mochi setmodrole @role` | Set moderator role |
| `mochi cosmetics` | Browse server cosmetics |
| `mochi pets` | Browse server pets |

### Right-click Context Menus
Right-click any user → **Apps** →
- `🫂 Hug` · `🌸 Pat` · `💋 Kiss` · `🔨 Bonk` · `🥰 Cuddle` · `👉 Poke`
- `✨ Mochi Profile` · `📌 View RP Stats` · `🛡️ Mod History`

---

## 📁 File Structure

```
mochime/
├── __main__.py          Entry point  (python -m mochime)
├── bot.py               MochiMe bot class
├── config.py            Prefix, colours, fallback emojis
├── console.py           Coloured logging + ASCII banner
├── database.py          SQLite helpers (aiosqlite)
├── setup_env.py         Cross-platform setup wizard
├── requirements.txt     Pinned dependencies
├── assets/
│   └── phosphor/        Auto-downloaded Phosphor SVGs (44 icons)
├── cogs/
│   ├── emoji_loader.py  Downloads + registers app emojis
│   ├── help.py          CV2 help menu with select menu
│   ├── rp.py            Roleplay commands + animated GIFs
│   ├── moderation.py    Ban/kick/mute/warn with CV2 panels
│   ├── application.py   User-install app commands + context menus
│   └── server_features.py  Server-locked features
└── docs/
    ├── commands.md      Full command reference
    ├── setup.md         Detailed setup guide
    ├── cv2-ui.md        Components v2 UI guide
    └── database.md      Database schema reference
```

---

## 🗄️ Database

MochiMe uses a local SQLite file (`mochime.db`) with these tables:

| Table | Purpose |
|---|---|
| `emojis` | Cached Phosphor application emoji IDs |
| `moderation_logs` | All ban/kick/mute/warn actions |
| `user_settings` | Per-user preferences |
| `server_settings` | Per-server config (channels, roles) |
| `rp_stats` | Roleplay action history |

---

## 🔧 Stack

- **[discord.py 2.7+](https://discordpy.readthedocs.io)** — Bot framework with CV2 support
- **[aiosqlite](https://aiosqlite.omnilib.dev)** — Async SQLite
- **[aiohttp](https://docs.aiohttp.org)** — HTTP client (GIF fetching, emoji CDN)
- **[Phosphor Icons](https://phosphoricons.com)** — MIT-licensed icon library

---

## 📄 License

MIT — see [LICENSE](LICENSE).
