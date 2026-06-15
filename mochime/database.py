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
