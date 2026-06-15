from __future__ import annotations

import base64
import io
from pathlib import Path

import aiohttp
import discord
from discord.ext import commands

import config
import console
import database

log = console.get_logger("cogs.emoji_loader")

# Map internal name → official Phosphor icon filename (regular weight)
# Source: https://github.com/phosphor-icons/core/tree/main/assets/regular
PHOSPHOR_ICONS: dict[str, str] = {
    "heart":    "heart",
    "star":     "star",
    "shield":   "shield",
    "info":     "info",
    "warning":  "warning-circle",
    "user":     "user",
    "smiley":   "smiley",
    "sparkle":  "sparkle",
    "check":    "check-circle",
    "cross":    "x-circle",
    "flower":   "flower",
    "moon":     "moon",
    "chat":     "chat-circle",
    "crown":    "crown",
    "wave":     "hand-waving",
    "ban":      "hammer",
    "kick":     "boot",
    "mute":     "speaker-slash",
    "warn":     "warning-circle",
    "settings": "gear",
    "lock":     "lock",
    "pin":      "push-pin",
    "pencil":   "pencil",
    "music":    "music-note",
    "hug":      "person-arms-spread",
    "pat":      "hand",
    "kiss":     "heart-straight",
    "bonk":     "hammer",
    "blush":    "smiley-wink",
    "cuddle":   "couch",
    "poke":     "hand-pointing",
    "ribbon":   "gift",
    "cake":     "cake",
    "bow":      "hand-heart",
    "bell":     "bell",
    "confetti": "confetti",
    "wand":     "magic-wand",
    "book":     "book-open",
    "bolt":     "lightning",
    "eye":      "eye",
    "trash":    "trash",
    "add":      "plus-circle",
    "remove":   "minus-circle",
    "trophy":   "trophy",
}

CDN_BASE = (
    "https://raw.githubusercontent.com/phosphor-icons/core"
    "/main/assets/regular/{name}.svg"
)

# ── PNG conversion ────────────────────────────────────────────────────────────

# Pink tint applied to every Phosphor SVG before rasterisation.
# Phosphor icons use fill="currentColor"; we replace that token so cairosvg
# renders the icon in this colour instead of black.
_ICON_COLOR = "#E879A8"

# Pillow fallback circle colour (used only when cairosvg is unavailable)
_PALETTE_PINK: tuple[int, int, int] = (232, 121, 168)  # matches _ICON_COLOR

# Check cairosvg availability once at import time
_HAS_CAIRO: bool = False
try:
    import cairosvg as _cairosvg
    _HAS_CAIRO = True
except ImportError:
    pass

# Check Pillow availability once at import time
_HAS_PILLOW: bool = False
try:
    from PIL import Image as _Image, ImageDraw as _ImageDraw
    _HAS_PILLOW = True
except ImportError:
    pass


def _pillow_icon(name: str, size: int = 128) -> bytes:
    """
    Create a pink circle PNG using Pillow.
    Used when cairosvg is not available or conversion fails.
    """
    from PIL import Image, ImageDraw  # noqa: PLC0415

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    pad = 4
    draw.ellipse((pad, pad, size - pad - 1, size - pad - 1), fill=(*_PALETTE_PINK, 255))

    ip = size // 3
    draw.ellipse(
        (ip, ip, size - ip - 1, size - ip - 1),
        fill=(255, 255, 255, 55),
    )

    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _tint_svg(svg_bytes: bytes) -> bytes:
    """Replace currentColor with _ICON_COLOR so icons render pink."""
    return svg_bytes.replace(b"currentColor", _ICON_COLOR.encode())


def _svg_to_png(svg_bytes: bytes, name: str, size: int = 128) -> bytes:
    """
    Convert SVG bytes → PNG bytes (pink-tinted).

    Priority:
      1. cairosvg  — perfect vector fidelity (needs libcairo system package)
      2. Pillow    — pink circle placeholder (pure-Python, always available)
      3. Minimal 1×1 transparent PNG — absolute last resort
    """
    tinted = _tint_svg(svg_bytes)

    if _HAS_CAIRO:
        try:
            return _cairosvg.svg2png(  # type: ignore[union-attr]
                bytestring=tinted,
                output_width=size,
                output_height=size,
            )
        except Exception as exc:
            log.debug("cairosvg failed for %s: %s — trying Pillow", name, exc)

    if _HAS_PILLOW:
        try:
            return _pillow_icon(name, size)
        except Exception as exc:
            log.debug("Pillow fallback failed for %s: %s", name, exc)

    # Absolute last resort: 1×1 transparent PNG (valid, but invisible)
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
        b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )


# ── Cog ──────────────────────────────────────────────────────────────────────

class EmojiLoader(commands.Cog):
    """Downloads Phosphor SVGs, converts them to PNG, and registers app emojis."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.cache: dict[str, str] = {}

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        await self._load_cached_emojis()
        await self._download_missing_svgs()

        # Detect a color refresh: DB has IDs from a previous registration but
        # PNGs were deleted (e.g. to force a re-tint).  Clear the stale Discord
        # emojis and DB entries so they get re-uploaded with the new color.
        phosphor_dir = Path(config.PHOSPHOR_DIR)
        pngs_missing = not any(
            (phosphor_dir / f"{name}.png").exists() for name in PHOSPHOR_ICONS
        )
        if pngs_missing and self.cache:
            log.info("Color refresh detected — clearing stale Discord emojis…")
            await self._clear_discord_emojis()

        await self._convert_missing_pngs()
        await self._register_missing_emojis()

    # ── Step 1: load from DB cache ──────────────────────────────────────────

    async def _load_cached_emojis(self) -> None:
        db = await database.get_db()
        async with db.execute("SELECT name, emoji_id FROM emojis") as cur:
            async for row in cur:
                self.cache[row["name"]] = row["emoji_id"]
        log.info("Loaded %d cached emoji IDs from DB", len(self.cache))

    # ── Step 2: download SVGs ───────────────────────────────────────────────

    async def _download_missing_svgs(self) -> None:
        phosphor_dir = Path(config.PHOSPHOR_DIR)
        phosphor_dir.mkdir(parents=True, exist_ok=True)

        to_download = [
            (internal, phosphor_name)
            for internal, phosphor_name in PHOSPHOR_ICONS.items()
            if not (phosphor_dir / f"{internal}.svg").exists()
        ]

        if not to_download:
            log.info("All %d Phosphor SVGs already on disk", len(PHOSPHOR_ICONS))
            return

        log.info("Downloading %d Phosphor SVGs…", len(to_download))
        downloaded = 0
        failed: list[str] = []

        async with aiohttp.ClientSession() as session:
            for internal, phosphor_name in to_download:
                url = CDN_BASE.format(name=phosphor_name)
                try:
                    async with session.get(
                        url, timeout=aiohttp.ClientTimeout(total=10)
                    ) as resp:
                        if resp.status == 200:
                            (phosphor_dir / f"{internal}.svg").write_bytes(
                                await resp.read()
                            )
                            downloaded += 1
                        else:
                            failed.append(internal)
                except Exception:
                    failed.append(internal)

        log.info("Downloaded %d/%d SVGs", downloaded, len(to_download))
        if failed:
            log.warning("SVG download failed for: %s", ", ".join(failed))

    # ── Step 3: convert SVGs → PNGs ─────────────────────────────────────────

    async def _convert_missing_pngs(self) -> None:
        """Convert any SVG that doesn't yet have a matching .png file."""
        phosphor_dir = Path(config.PHOSPHOR_DIR)
        converted = 0
        skipped = 0

        for internal in PHOSPHOR_ICONS:
            svg_path = phosphor_dir / f"{internal}.svg"
            png_path = phosphor_dir / f"{internal}.png"

            if png_path.exists():
                continue
            if not svg_path.exists():
                skipped += 1
                continue

            try:
                png_bytes = _svg_to_png(svg_path.read_bytes(), internal)
                png_path.write_bytes(png_bytes)
                converted += 1
            except Exception as exc:
                log.warning("PNG conversion failed for %s: %s", internal, exc)
                skipped += 1

        if converted:
            method = "cairosvg" if _HAS_CAIRO else "Pillow (pink circle icons)"
            log.info("Converted %d SVGs → PNG (pink) via %s", converted, method)
        if skipped:
            log.debug("Skipped %d icons (no SVG source)", skipped)

    # ── Step 4: register with Discord ──────────────────────────────────────

    async def _register_missing_emojis(self) -> None:
        phosphor_dir = Path(config.PHOSPHOR_DIR)
        app_id = self.bot.application_id
        if app_id is None:
            log.warning("application_id unavailable — skipping emoji registration")
            return

        headers = {
            "Authorization": f"Bot {config.BOT_TOKEN}",
            "Content-Type": "application/json",
        }

        registered = 0
        failed: list[str] = []

        async with aiohttp.ClientSession() as session:
            existing = await self._fetch_existing_emojis(session, app_id, headers)

            for internal in PHOSPHOR_ICONS:
                if internal in self.cache or internal in existing:
                    continue

                png_path = phosphor_dir / f"{internal}.png"
                if not png_path.exists():
                    continue

                b64 = base64.b64encode(png_path.read_bytes()).decode()
                payload = {
                    "name": internal,
                    "image": f"data:image/png;base64,{b64}",
                }

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
                        body = await resp.text()
                        log.debug(
                            "Emoji upload failed for %s: HTTP %d — %s",
                            internal, resp.status, body[:120],
                        )
                        failed.append(internal)

        if registered:
            log.info("Registered %d new application emojis", registered)
        if failed:
            log.warning(
                "%d emoji(s) rejected by Discord: %s",
                len(failed), ", ".join(failed),
            )

    async def _clear_discord_emojis(self) -> None:
        """
        Delete every registered app emoji from Discord and wipe the DB cache.
        Called when PNGs are missing but the DB still holds old emoji IDs,
        which means we need to re-upload everything with a new icon color.
        """
        app_id = self.bot.application_id
        if app_id is None:
            return

        headers = {
            "Authorization": f"Bot {config.BOT_TOKEN}",
            "Content-Type": "application/json",
        }

        deleted = 0
        async with aiohttp.ClientSession() as session:
            for name, emoji_id in list(self.cache.items()):
                try:
                    async with session.delete(
                        f"https://discord.com/api/v10/applications/{app_id}/emojis/{emoji_id}",
                        headers=headers,
                    ) as resp:
                        if resp.status in (200, 204):
                            deleted += 1
                        else:
                            log.debug(
                                "Failed to delete emoji %s (%s): HTTP %d",
                                name, emoji_id, resp.status,
                            )
                except Exception as exc:
                    log.debug("Error deleting emoji %s: %s", name, exc)

        # Clear in-memory cache and DB
        self.cache.clear()
        db = await database.get_db()
        await db.execute("DELETE FROM emojis")
        await db.commit()
        log.info("Cleared %d Discord app emojis for color refresh", deleted)

    async def _fetch_existing_emojis(
        self,
        session: aiohttp.ClientSession,
        app_id: int,
        headers: dict[str, str],
    ) -> set[str]:
        names: set[str] = set()
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

    # ── Public helper ───────────────────────────────────────────────────────

    def get(self, name: str) -> str:
        """Return a formatted application emoji string, or Unicode fallback."""
        clean = name.replace("-", "_").lower()
        emoji_id = self.cache.get(clean)
        if emoji_id:
            return f"<:{clean}:{emoji_id}>"
        return config.FALLBACK_EMOJIS.get(clean, "✨")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EmojiLoader(bot))
