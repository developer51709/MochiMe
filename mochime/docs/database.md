# 🗄️ MochiMe — Database Reference

MochiMe uses a local **SQLite** database (`mochime.db`) managed via `aiosqlite`.
All schema creation happens automatically on first startup.

---

## Tables

### `emojis`

Caches Phosphor application emoji IDs so they don't need to be re-fetched
from the Discord API on every startup.

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `name` | TEXT UNIQUE | Internal emoji name (e.g. `heart`) |
| `emoji_id` | TEXT | Discord application emoji snowflake ID |

---

### `moderation_logs`

Stores every moderation action for audit and history lookup.

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `guild_id` | TEXT | Snowflake ID of the server |
| `moderator_id` | TEXT | Snowflake ID of the moderator |
| `target_id` | TEXT | Snowflake ID of the target user |
| `action` | TEXT | `ban` · `kick` · `mute:10m` · `warn` |
| `reason` | TEXT | Reason string (nullable) |
| `created_at` | TEXT | UTC timestamp (`datetime('now')`) |

---

### `user_settings`

Per-user preferences. Currently stores cosmetic choices and notification flags.

| Column | Type | Description |
|---|---|---|
| `user_id` | TEXT PK | Snowflake ID of the user |
| `rp_notifications` | INTEGER | `1` = receive RP DM notifications |
| `cosmetic_id` | TEXT | Active cosmetic key (nullable) |
| `created_at` | TEXT | UTC timestamp |

---

### `server_settings`

Per-server configuration set via `mochi setrp`, `mochi setlog`, etc.

| Column | Type | Description |
|---|---|---|
| `guild_id` | TEXT PK | Snowflake ID of the server |
| `rp_channel_id` | TEXT | Channel ID for the RP room |
| `log_channel_id` | TEXT | Channel ID for moderation logs |
| `mod_role_id` | TEXT | Role ID for moderators |
| `welcome_enabled` | INTEGER | `1` = welcome messages on |
| `created_at` | TEXT | UTC timestamp |

---

### `rp_stats`

Tracks every roleplay action for profile stats and leaderboards.

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `user_id` | TEXT | Who performed the action |
| `action` | TEXT | `hug` · `pat` · `kiss` · etc. |
| `target_id` | TEXT | Who was targeted (nullable) |
| `guild_id` | TEXT | Server where it happened (nullable for DMs) |
| `created_at` | TEXT | UTC timestamp |

---

## Helper Functions (`database.py`)

| Function | Description |
|---|---|
| `init_db()` | Create all tables if they don't exist |
| `get_db()` | Return the singleton aiosqlite connection |
| `close_db()` | Close the connection (called on shutdown) |
| `get_emoji(name)` | Look up an emoji ID by name |
| `set_emoji(name, emoji_id)` | Insert or update an emoji record |
| `log_moderation(...)` | Write a moderation log entry |
| `log_rp(...)` | Write an RP stat entry |
| `get_server_settings(guild_id)` | Fetch a server's config row |
| `upsert_server_settings(guild_id, **kwargs)` | Insert or update server config |

---

## Querying the Database Directly

```bash
# Open the SQLite shell
sqlite3 mochime.db

# Recent moderation actions
SELECT * FROM moderation_logs ORDER BY created_at DESC LIMIT 20;

# RP leaderboard
SELECT user_id, action, COUNT(*) AS total
FROM rp_stats
GROUP BY user_id, action
ORDER BY total DESC
LIMIT 10;

# Server settings
SELECT * FROM server_settings;

# All cached emojis
SELECT name, emoji_id FROM emojis ORDER BY name;
```
