from __future__ import annotations

import base64
import os
from pathlib import Path

import aiohttp
import discord
from discord.ext import commands

import config
import database


class EmojiLoader(commands.Cog):
    """Loads Phosphor SVG icons as application emojis and caches their IDs."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.cache: dict[str, str] = {}

    async def cog_load(self) -> None:
        pass

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        await self._load_cached_emojis()
        await self._register_missing_emojis()

    async def _load_cached_emojis(self) -> None:
        import aiosqlite
        db = await database.get_db()
        async with db.execute("SELECT name, emoji_id FROM emojis") as cur:
            async for row in cur:
                self.cache[row["name"]] = row["emoji_id"]
        print(f"  ✦ Loaded {len(self.cache)} cached emoji IDs from DB")

    async def _register_missing_emojis(self) -> None:
        phosphor_dir = Path(config.PHOSPHOR_DIR)
        if not phosphor_dir.exists():
            print("  ✦ No phosphor/ directory found — skipping emoji registration")
            return

        svg_files = list(phosphor_dir.glob("*.svg"))
        if not svg_files:
            print("  ✦ No SVGs found in phosphor/ — skipping emoji registration")
            return

        app_id = self.bot.application_id
        if app_id is None:
            print("  ✦ application_id not available yet — skipping emoji registration")
            return

        headers = {
            "Authorization": f"Bot {config.BOT_TOKEN}",
            "Content-Type": "application/json",
        }

        registered = 0
        failed = 0

        async with aiohttp.ClientSession() as session:
            existing = await self._fetch_app_emojis(session, app_id, headers)
            existing_names = {e["name"] for e in existing}

            for svg_path in svg_files:
                name = svg_path.stem.replace("-", "_").lower()
                if name in self.cache or name in existing_names:
                    continue

                svg_bytes = svg_path.read_bytes()
                # Discord requires PNG/GIF/WEBP — attempt SVG upload and fall back
                b64 = base64.b64encode(svg_bytes).decode()
                image_data = f"data:image/svg+xml;base64,{b64}"

                payload = {"name": name, "image": image_data}

                async with session.post(
                    f"https://discord.com/api/v10/applications/{app_id}/emojis",
                    json=payload,
                    headers=headers,
                ) as resp:
                    if resp.status in (200, 201):
                        data = await resp.json()
                        emoji_id = str(data["id"])
                        self.cache[name] = emoji_id
                        await database.set_emoji(name, emoji_id)
                        registered += 1
                    else:
                        # SVG not supported — store fallback marker
                        failed += 1

        if registered:
            print(f"  ✦ Registered {registered} new application emojis")
        if failed:
            print(f"  ✦ {failed} SVGs could not be registered (Discord requires PNG/GIF/WEBP) — using Unicode fallbacks")

    async def _fetch_app_emojis(
        self,
        session: aiohttp.ClientSession,
        app_id: int,
        headers: dict[str, str],
    ) -> list[dict]:
        async with session.get(
            f"https://discord.com/api/v10/applications/{app_id}/emojis",
            headers=headers,
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                items = data.get("items", data) if isinstance(data, dict) else data
                for item in items:
                    name = item["name"]
                    emoji_id = str(item["id"])
                    self.cache[name] = emoji_id
                    await database.set_emoji(name, emoji_id)
                return items if isinstance(items, list) else []
        return []

    def get(self, name: str) -> str:
        """Return a formatted application emoji or Unicode fallback."""
        clean = name.replace("-", "_").lower()
        emoji_id = self.cache.get(clean)
        if emoji_id:
            return f"<:{clean}:{emoji_id}>"
        return config.FALLBACK_EMOJIS.get(clean, "✨")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EmojiLoader(bot))
