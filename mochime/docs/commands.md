# 📖 MochiMe — Command Reference

All commands work as both `mochi <command>` (prefix) and `/command` (slash).  
Slash commands support autocomplete for arguments.

---

## 🎀 Roleplay

All RP commands embed a live animated GIF and log the action to the database.  
Target is optional — commands without a target act on the sender.

| Command | Alias | Description |
|---|---|---|
| `mochi hug [@user]` | `/hug` | Give someone a warm hug 🫂 |
| `mochi pat [@user]` | `/pat` | Pat someone on the head gently 🌸 |
| `mochi kiss [@user]` | `/kiss` | Give someone a sweet kiss 💋 |
| `mochi bonk [@user]` | `/bonk` | Bonk someone on the head 🔨 |
| `mochi blush` | `/blush` | Express your blush (no target needed) 😳 |
| `mochi cuddle [@user]` | `/cuddle` | Cuddle with someone warmly 🥰 |
| `mochi poke [@user]` | `/poke` | Poke someone playfully 👉 |

### Right-click context menu (RP)

Right-click any server member → **Apps** → choose an action:

| Menu entry | Action |
|---|---|
| 🫂 Hug | Hug that user |
| 🌸 Pat | Pat that user |
| 💋 Kiss | Kiss that user |
| 🔨 Bonk | Bonk that user |
| 🥰 Cuddle | Cuddle with that user |
| 👉 Poke | Poke that user |

---

## 🛡️ Moderation

All moderation commands show a CV2 confirmation panel before acting.  
Actions are logged to the `moderation_logs` table.

| Command | Permission | Description |
|---|---|---|
| `mochi ban @user [reason]` | Ban Members | Permanently ban a member |
| `mochi kick @user [reason]` | Kick Members | Kick a member from the server |
| `mochi mute @user [mins] [reason]` | Moderate Members | Timeout a member (default 10 min, max 40320) |
| `mochi warn @user [reason]` | Manage Messages | Issue a warning (DMs the user, logs it) |

---

## 🌸 General

| Command | Description |
|---|---|
| `mochi help` | CV2 help menu with category select |
| `mochi ping` | Bot latency in milliseconds |
| `mochi about` | About MochiMe + invite link |
| `mochi info` | Current server stats |
| `mochi user [@user]` | User profile with RP stats (defaults to yourself) |

---

## ⚙️ Server Management

Requires **Manage Server** permission for all settings commands.

| Command | Description |
|---|---|
| `mochi server` | View the full server management panel |
| `mochi settings` | Show the settings overview |
| `mochi setrp #channel` | Set the designated RP room channel |
| `mochi setlog #channel` | Set the moderation log channel |
| `mochi setmodrole @role` | Set the moderator role |
| `mochi cosmetics` | Browse available server cosmetics |
| `mochi pets` | Browse server-bound companion pets |

---

## ✨ Application (User-Install) Commands

These context menus work even when MochiMe isn't added to a server, as long as
the user has installed the app via **User Settings → Authorised Apps**.

| Menu entry | Ephemeral | Description |
|---|---|---|
| ✨ Mochi Profile | ✅ | Full user profile: RP stats, join date, roles |
| 📌 View RP Stats | ✅ | Given vs. received breakdown for all RP actions |
| 🛡️ Mod History | ✅ | Last 10 moderation actions (mod-only) |

---

## 💬 Notes

- **CV2 only** — All responses use Discord Components v2 (no legacy embeds).
- **Case-insensitive** — `Mochi HUG`, `mochi hug`, `MOCHI HUG` all work.
- **Hybrid** — Prefix commands and slash commands share the same handler.
- **No cooldowns** — Commands have no enforced cooldown.
