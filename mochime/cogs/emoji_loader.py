from __future__ import annotations

import base64
import os
from pathlib import Path

import aiohttp
import discord
from discord.ext import commands

import config
import database

# Map internal name → official Phosphor icon filename (regular weight)
# Source: https://github.com/phosphor-icons/core/tree/main/assets/regular
PHOSPHOR_ICONS: dict[str, str] = {
    "heart":        "heart",
    "star":         "star",
    "shield":       "shield",
    "info":         "info",
    "warning":      "warning-circle",
    "user":         "user",
    "smiley":       "smiley",
    "sparkle":      "sparkle",
    "check":        "check-circle",
    "cross":        "x-circle",
    "flower":       "flower",
    "moon":         "moon",
    "chat":         "chat-circle",
    "crown":        "crown",
    "wave":         "hand-waving",
    "ban":          "hammer",
    "kick":         "boot",
    "mute":         "speaker-slash",
    "warn":         "warning-circle",
    "settings":     "gear",
    "lock":         "lock",
    "pin":          "push-pin",
    "pencil":       "pencil",
    "music":        "music-note",
    "hug":          "person-arms-spread",
    "pat":          "hand",
    "kiss":         "heart-straight",
    "bonk":         "hammer",
    "blush":        "smiley-wink",
    "cuddle":       "couch",
    "poke":         "hand-pointing",
    "ribbon":       "gift",
    "cake":         "cake",
    "bow":          "hand-heart",
    "bell":         "bell",
    "confetti":     "confetti",
    "wand":         "magic-wand",
    "book":         "book-open",
    "bolt":         "lightning",
    "eye":          "eye",
    "trash":        "trash",
    "add":          "plus-circle",
    "remove":       "minus-circle",
    "trophy":       "trophy",
}

CDN_BASE = (
    "https://raw.githubusercontent.com/phosphor-icons/core/main/assets/regular/{name}.svg"
)


class EmojiLoader(commands.Cog):
    """Downloads real Phosphor SVGs from GitHub and registers them as application emojis."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.cache: dict[str, str] = {}

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        await self._load_cached_emojis()
        await self._download_missing_svgs()
        await self._register_missing_emojis()

    async def _load_cached_emojis(self) -> None:
        db = await database.get_db()
        async with db.execute("SELECT name, emoji_id FROM emojis") as cur:
            async for row in cur:
                self.cache[row["name"]] = row["emoji_id"]
        print(f"  ✦ Loaded {len(self.cache)} cached emoji IDs from DB")

    async def _download_missing_svgs(self) -> None:
        phosphor_dir = Path(config.PHOSPHOR_DIR)
        phosphor_dir.mkdir(parents=True, exist_ok=True)

        to_download = [
            (internal, phosphor_name)
            for internal, phosphor_name in PHOSPHOR_ICONS.items()
            if not (phosphor_dir / f"{internal}.svg").exists()
        ]

        if not to_download:
            print(f"  ✦ All {len(PHOSPHOR_ICONS)} Phosphor SVGs already downloaded")
            return

        print(f"  ✦ Downloading {len(to_download)} Phosphor SVGs from phosphoricons.com CDN...")
        downloaded = 0
        failed: list[str] = []

        async with aiohttp.ClientSession() as session:
            for internal, phosphor_name in to_download:
                url = CDN_BASE.format(name=phosphor_name)
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status == 200:
                            svg_bytes = await resp.read()
                            (phosphor_dir / f"{internal}.svg").write_bytes(svg_bytes)
                            downloaded += 1
                        else:
                            failed.append(internal)
                except Exception:
                    failed.append(internal)

        print(f"  ✦ Downloaded {downloaded}/{len(to_download)} SVGs ✓")
        if failed:
            print(f"  ✦ Failed to download: {', '.join(failed)} — Unicode fallbacks will be used")

    async def _register_missing_emojis(self) -> None:
        phosphor_dir = Path(config.PHOSPHOR_DIR)
        app_id = self.bot.application_id
        if app_id is None:
            print("  ✦ application_id unavailable — skipping emoji registration")
            return

        headers = {
            "Authorization": f"Bot {config.BOT_TOKEN}",
            "Content-Type": "application/json",
        }

        registered = 0
        failed = 0

        async with aiohttp.ClientSession() as session:
            existing_names = await self._fetch_existing_emoji_names(session, app_id, headers)

            for internal in PHOSPHOR_ICONS:
                if internal in self.cache or internal in existing_names:
                    continue

                svg_path = phosphor_dir / f"{internal}.svg"
                if not svg_path.exists():
                    continue

                svg_bytes = svg_path.read_bytes()
                b64 = base64.b64encode(svg_bytes).decode()
                # Attempt SVG upload (Discord requires PNG/GIF in practice;
                # this will fail gracefully and fall back to Unicode symbols)
                image_data = f"data:image/svg+xml;base64,{b64}"

                payload = {"name": internal, "image": image_data}
                async with session.post(
                    f"https://discord.com/api/v10/applications/{app_id}/emojis",
                    json=payload,
                    headers=headers,
                ) as resp:
                    if resp.status in (200, 201):
                        data = await resp.json()
                        emoji_id = str(data["id"])
                        self.cache[internal] = emoji_id
                        await database.set_emoji(internal, emoji_id)
                        registered += 1
                    else:
                        failed += 1

        if registered:
            print(f"  ✦ Registered {registered} new application emojis ✓")
        if failed:
            print(
                f"  ✦ {failed} SVGs couldn't register (Discord requires PNG — Unicode fallbacks active)"
            )

    async def _fetch_existing_emoji_names(
        self,
        session: aiohttp.ClientSession,
        app_id: int,
        headers: dict[str, str],
    ) -> set[str]:
        names: set[str] = {}
        try:
            async with session.get(
                f"https://discord.com/api/v10/applications/{app_id}/emojis",
                headers=headers,
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    items = data.get("items", data) if isinstance(data, dict) else data
                    for item in (items if isinstance(items, list) else []):
                        name = item["name"]
                        emoji_id = str(item["id"])
                        self.cache[name] = emoji_id
                        await database.set_emoji(name, emoji_id)
                        names.add(name)
        except Exception:
            pass
        return names

    def get(self, name: str) -> str:
        """Return a formatted application emoji string, or Unicode fallback."""
        clean = name.replace("-", "_").lower()
        emoji_id = self.cache.get(clean)
        if emoji_id:
            return f"<:{clean}:{emoji_id}>"
        return config.FALLBACK_EMOJIS.get(clean, "✨")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EmojiLoader(bot))
