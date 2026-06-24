from __future__ import annotations

import aiosqlite
import config


_db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        _db = await aiosqlite.connect(config.DB_PATH)
        _db.row_factory = aiosqlite.Row
    return _db


async def init_db() -> None:
    db = await get_db()
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS user_levels (
            user_id   TEXT NOT NULL,
            guild_id  TEXT NOT NULL,
            xp        INTEGER NOT NULL DEFAULT 0,
            level     INTEGER NOT NULL DEFAULT 0,
            messages  INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, guild_id)
        );

        CREATE TABLE IF NOT EXISTS polls (
            message_id  TEXT PRIMARY KEY,
            channel_id  TEXT NOT NULL,
            guild_id    TEXT NOT NULL,
            author_id   TEXT NOT NULL,
            question    TEXT NOT NULL,
            options     TEXT NOT NULL,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            active      INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS poll_votes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id  TEXT NOT NULL,
            user_id     TEXT NOT NULL,
            option_idx  INTEGER NOT NULL,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (message_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS emojis (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            name      TEXT    NOT NULL UNIQUE,
            emoji_id  TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS moderation_logs (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id     TEXT    NOT NULL,
            moderator_id TEXT    NOT NULL,
            target_id    TEXT    NOT NULL,
            action       TEXT    NOT NULL,
            reason       TEXT,
            created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS user_settings (
            user_id          TEXT PRIMARY KEY,
            rp_notifications INTEGER NOT NULL DEFAULT 1,
            cosmetic_id      TEXT,
            created_at       TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS server_settings (
            guild_id          TEXT PRIMARY KEY,
            rp_channel_id     TEXT,
            log_channel_id    TEXT,
            mod_role_id       TEXT,
            welcome_enabled   INTEGER NOT NULL DEFAULT 0,
            welcome_channel_id TEXT,
            welcome_title     TEXT,
            welcome_message   TEXT,
            welcome_image_url TEXT,
            welcome_color     TEXT,
            created_at        TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS rp_stats (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   TEXT NOT NULL,
            action    TEXT NOT NULL,
            target_id TEXT,
            guild_id  TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS giveaways (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id        TEXT    NOT NULL UNIQUE,
            channel_id        TEXT    NOT NULL,
            guild_id          TEXT    NOT NULL,
            host_id           TEXT    NOT NULL,
            prize             TEXT    NOT NULL,
            description       TEXT,
            winner_count      INTEGER NOT NULL DEFAULT 1,
            ends_at           TEXT    NOT NULL,
            ended             INTEGER NOT NULL DEFAULT 0,
            cancelled         INTEGER NOT NULL DEFAULT 0,
            required_role_ids TEXT    NOT NULL DEFAULT '[]',
            bonus_role_ids    TEXT    NOT NULL DEFAULT '[]',
            min_account_age   INTEGER NOT NULL DEFAULT 0,
            min_server_age    INTEGER NOT NULL DEFAULT 0,
            winners           TEXT
        );

        CREATE TABLE IF NOT EXISTS giveaway_entries (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT    NOT NULL,
            user_id    TEXT    NOT NULL,
            entries    INTEGER NOT NULL DEFAULT 1,
            entered_at TEXT    NOT NULL DEFAULT (datetime('now')),
            UNIQUE (message_id, user_id)
        );
    """)
    await db.commit()

    # ── schema migrations for existing databases ───────────────────────────
    # SQLite has no ADD COLUMN IF NOT EXISTS; wrap each ALTER in try/except.
    _migrations = [
        "ALTER TABLE server_settings ADD COLUMN welcome_channel_id TEXT",
        "ALTER TABLE server_settings ADD COLUMN welcome_title TEXT",
        "ALTER TABLE server_settings ADD COLUMN welcome_message TEXT",
        "ALTER TABLE server_settings ADD COLUMN welcome_image_url TEXT",
        "ALTER TABLE server_settings ADD COLUMN welcome_color TEXT",
    ]
    for stmt in _migrations:
        try:
            await db.execute(stmt)
        except Exception:
            pass  # column already exists
    await db.commit()


async def get_emoji(name: str) -> str | None:
    db = await get_db()
    async with db.execute("SELECT emoji_id FROM emojis WHERE name = ?", (name,)) as cur:
        row = await cur.fetchone()
        return row["emoji_id"] if row else None


async def set_emoji(name: str, emoji_id: str) -> None:
    db = await get_db()
    await db.execute(
        "INSERT INTO emojis (name, emoji_id) VALUES (?, ?) "
        "ON CONFLICT(name) DO UPDATE SET emoji_id = excluded.emoji_id",
        (name, emoji_id),
    )
    await db.commit()


async def log_moderation(
    guild_id: str,
    moderator_id: str,
    target_id: str,
    action: str,
    reason: str | None = None,
) -> None:
    db = await get_db()
    await db.execute(
        "INSERT INTO moderation_logs (guild_id, moderator_id, target_id, action, reason) "
        "VALUES (?, ?, ?, ?, ?)",
        (guild_id, moderator_id, target_id, action, reason),
    )
    await db.commit()


async def log_rp(
    user_id: str,
    action: str,
    target_id: str | None = None,
    guild_id: str | None = None,
) -> None:
    db = await get_db()
    await db.execute(
        "INSERT INTO rp_stats (user_id, action, target_id, guild_id) VALUES (?, ?, ?, ?)",
        (user_id, action, target_id, guild_id),
    )
    await db.commit()


async def get_server_settings(guild_id: str) -> aiosqlite.Row | None:
    db = await get_db()
    async with db.execute(
        "SELECT * FROM server_settings WHERE guild_id = ?", (guild_id,)
    ) as cur:
        return await cur.fetchone()


async def upsert_server_settings(guild_id: str, **kwargs: str | int) -> None:
    if not kwargs:
        return
    db = await get_db()
    cols = ", ".join(kwargs.keys())
    placeholders = ", ".join(["?"] * len(kwargs))
    updates = ", ".join(f"{k} = excluded.{k}" for k in kwargs)
    await db.execute(
        f"INSERT INTO server_settings (guild_id, {cols}) VALUES (?, {placeholders}) "
        f"ON CONFLICT(guild_id) DO UPDATE SET {updates}",
        (guild_id, *kwargs.values()),
    )
    await db.commit()


async def close_db() -> None:
    global _db
    if _db is not None:
        await _db.close()
        _db = None


# ── levels ────────────────────────────────────────────────────────────────────

import math as _math


def _level_from_xp(xp: int) -> int:
    return int(_math.isqrt(xp // 100))


def _xp_for_level(level: int) -> int:
    return level * level * 100


async def get_user_level(user_id: str, guild_id: str) -> aiosqlite.Row | None:
    db = await get_db()
    async with db.execute(
        "SELECT * FROM user_levels WHERE user_id = ? AND guild_id = ?",
        (user_id, guild_id),
    ) as cur:
        return await cur.fetchone()


async def add_user_xp(
    user_id: str, guild_id: str, xp_gain: int
) -> tuple[int, int, bool]:
    """Add XP, update level. Returns (new_xp, new_level, leveled_up)."""
    db = await get_db()

    row = await get_user_level(user_id, guild_id)
    old_level = row["level"] if row else 0
    old_xp = row["xp"] if row else 0

    new_xp = old_xp + xp_gain
    new_level = _level_from_xp(new_xp)

    await db.execute(
        """
        INSERT INTO user_levels (user_id, guild_id, xp, level, messages)
        VALUES (?, ?, ?, ?, 1)
        ON CONFLICT(user_id, guild_id) DO UPDATE SET
            xp       = excluded.xp,
            level    = excluded.level,
            messages = messages + 1
        """,
        (user_id, guild_id, new_xp, new_level),
    )
    await db.commit()
    return new_xp, new_level, new_level > old_level


async def get_guild_leaderboard(guild_id: str, limit: int = 10) -> list[aiosqlite.Row]:
    db = await get_db()
    async with db.execute(
        "SELECT * FROM user_levels WHERE guild_id = ? ORDER BY xp DESC LIMIT ?",
        (guild_id, limit),
    ) as cur:
        return await cur.fetchall()


async def get_user_rank(user_id: str, guild_id: str) -> int:
    db = await get_db()
    async with db.execute(
        """
        SELECT COUNT(*) + 1 AS rank FROM user_levels
        WHERE guild_id = ? AND xp > (
            SELECT COALESCE(xp, 0) FROM user_levels
            WHERE user_id = ? AND guild_id = ?
        )
        """,
        (guild_id, user_id, guild_id),
    ) as cur:
        row = await cur.fetchone()
        return row[0] if row else 1


# ── polls ─────────────────────────────────────────────────────────────────────

import json as _json


async def create_poll(
    message_id: str,
    channel_id: str,
    guild_id: str,
    author_id: str,
    question: str,
    options: list[str],
) -> None:
    db = await get_db()
    await db.execute(
        "INSERT INTO polls (message_id, channel_id, guild_id, author_id, question, options) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (message_id, channel_id, guild_id, author_id, question, _json.dumps(options)),
    )
    await db.commit()


async def get_poll(message_id: str) -> aiosqlite.Row | None:
    db = await get_db()
    async with db.execute(
        "SELECT * FROM polls WHERE message_id = ?", (message_id,)
    ) as cur:
        return await cur.fetchone()


async def get_user_vote(message_id: str, user_id: str) -> int | None:
    db = await get_db()
    async with db.execute(
        "SELECT option_idx FROM poll_votes WHERE message_id = ? AND user_id = ?",
        (message_id, user_id),
    ) as cur:
        row = await cur.fetchone()
        return row["option_idx"] if row else None


async def cast_vote(message_id: str, user_id: str, option_idx: int) -> bool:
    """Record a vote. Returns True if successful, False if user already voted."""
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO poll_votes (message_id, user_id, option_idx) VALUES (?, ?, ?)",
            (message_id, user_id, option_idx),
        )
        await db.commit()
        return True
    except Exception:
        return False


async def get_vote_counts(message_id: str, num_options: int) -> list[int]:
    db = await get_db()
    counts = [0] * num_options
    async with db.execute(
        "SELECT option_idx, COUNT(*) AS cnt FROM poll_votes "
        "WHERE message_id = ? GROUP BY option_idx",
        (message_id,),
    ) as cur:
        async for row in cur:
            idx = row["option_idx"]
            if 0 <= idx < num_options:
                counts[idx] = row["cnt"]
    return counts


# ── giveaways ─────────────────────────────────────────────────────────────────


async def create_giveaway(
    *,
    message_id: str,
    channel_id: str,
    guild_id: str,
    host_id: str,
    prize: str,
    description: str | None,
    winner_count: int,
    ends_at: str,
    required_role_ids: str,
    bonus_role_ids: str,
    min_account_age: int,
    min_server_age: int,
) -> None:
    db = await get_db()
    await db.execute(
        """
        INSERT INTO giveaways
            (message_id, channel_id, guild_id, host_id, prize, description,
             winner_count, ends_at, required_role_ids, bonus_role_ids,
             min_account_age, min_server_age)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            message_id, channel_id, guild_id, host_id, prize, description,
            winner_count, ends_at, required_role_ids, bonus_role_ids,
            min_account_age, min_server_age,
        ),
    )
    await db.commit()


async def get_giveaway(message_id: str) -> aiosqlite.Row | None:
    db = await get_db()
    async with db.execute(
        "SELECT * FROM giveaways WHERE message_id = ?", (message_id,)
    ) as cur:
        return await cur.fetchone()


async def get_active_giveaways() -> list[aiosqlite.Row]:
    db = await get_db()
    async with db.execute(
        "SELECT * FROM giveaways WHERE ended = 0 AND cancelled = 0"
    ) as cur:
        return await cur.fetchall()


async def end_giveaway(message_id: str, winners_json: str) -> None:
    db = await get_db()
    await db.execute(
        "UPDATE giveaways SET ended = 1, winners = ? WHERE message_id = ?",
        (winners_json, message_id),
    )
    await db.commit()


async def cancel_giveaway(message_id: str) -> None:
    db = await get_db()
    await db.execute(
        "UPDATE giveaways SET ended = 1, cancelled = 1 WHERE message_id = ?",
        (message_id,),
    )
    await db.commit()


async def add_giveaway_entry(message_id: str, user_id: str, entries: int) -> None:
    db = await get_db()
    await db.execute(
        """
        INSERT INTO giveaway_entries (message_id, user_id, entries)
        VALUES (?, ?, ?)
        ON CONFLICT(message_id, user_id) DO UPDATE SET entries = excluded.entries
        """,
        (message_id, user_id, entries),
    )
    await db.commit()


async def get_giveaway_entry(message_id: str, user_id: str) -> aiosqlite.Row | None:
    db = await get_db()
    async with db.execute(
        "SELECT * FROM giveaway_entries WHERE message_id = ? AND user_id = ?",
        (message_id, user_id),
    ) as cur:
        return await cur.fetchone()


async def get_giveaway_entries(message_id: str) -> list[aiosqlite.Row]:
    db = await get_db()
    async with db.execute(
        "SELECT * FROM giveaway_entries WHERE message_id = ? ORDER BY entered_at ASC",
        (message_id,),
    ) as cur:
        return await cur.fetchall()


async def count_giveaway_entries(message_id: str) -> int:
    db = await get_db()
    async with db.execute(
        "SELECT COUNT(*) AS cnt FROM giveaway_entries WHERE message_id = ?",
        (message_id,),
    ) as cur:
        row = await cur.fetchone()
        return row["cnt"] if row else 0
