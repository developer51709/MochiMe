"""
translate.py — Message translation context menu.

Right-click any message → "🌐 Translate" → pick a target language.
Works as a user-installed app in any server or DM.
Uses the Google Translate public endpoint (no API key required).
"""
from __future__ import annotations

import urllib.parse

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

import config
import console
from cogs.emoji_loader import EmojiLoader

log = console.get_logger("cogs.translate")

# ─── language table (25 entries — Discord select menu max) ────────────────────

LANGUAGES: list[tuple[str, str, str]] = [
    ("en",    "🇬🇧", "English"),
    ("es",    "🇪🇸", "Spanish"),
    ("fr",    "🇫🇷", "French"),
    ("de",    "🇩🇪", "German"),
    ("it",    "🇮🇹", "Italian"),
    ("pt",    "🇧🇷", "Portuguese"),
    ("ru",    "🇷🇺", "Russian"),
    ("ja",    "🇯🇵", "Japanese"),
    ("ko",    "🇰🇷", "Korean"),
    ("zh-CN", "🇨🇳", "Chinese (Simplified)"),
    ("zh-TW", "🇹🇼", "Chinese (Traditional)"),
    ("ar",    "🇸🇦", "Arabic"),
    ("hi",    "🇮🇳", "Hindi"),
    ("nl",    "🇳🇱", "Dutch"),
    ("pl",    "🇵🇱", "Polish"),
    ("tr",    "🇹🇷", "Turkish"),
    ("sv",    "🇸🇪", "Swedish"),
    ("no",    "🇳🇴", "Norwegian"),
    ("da",    "🇩🇰", "Danish"),
    ("fi",    "🇫🇮", "Finnish"),
    ("el",    "🇬🇷", "Greek"),
    ("cs",    "🇨🇿", "Czech"),
    ("ro",    "🇷🇴", "Romanian"),
    ("uk",    "🇺🇦", "Ukrainian"),
    ("id",    "🇮🇩", "Indonesian"),
]

_LANG_BY_CODE: dict[str, tuple[str, str]] = {
    code: (flag, name) for code, flag, name in LANGUAGES
}

_TRANSLATE_URL = (
    "https://translate.googleapis.com/translate_a/single"
    "?client=gtx&sl=auto&tl={tl}&dt=t&q={q}"
)

_MAX_CHARS = 1500


# ─── translation helper ───────────────────────────────────────────────────────

async def _translate(text: str, target_lang: str) -> tuple[str, str]:
    """
    Translate *text* to *target_lang* using the Google Translate public API.
    Returns (translated_text, detected_source_lang_code).
    Raises RuntimeError on failure.
    """
    encoded = urllib.parse.quote(text)
    url = _TRANSLATE_URL.format(tl=target_lang, q=encoded)

    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            if resp.status != 200:
                raise RuntimeError(f"HTTP {resp.status}")
            data = await resp.json(content_type=None)

    chunks = data[0] or []
    translated = "".join(part[0] for part in chunks if part and part[0])
    detected = data[2] if len(data) > 2 and data[2] else "?"
    return translated, detected


# ─── CV2 builders ─────────────────────────────────────────────────────────────

def _lang_select(channel_id: int, message_id: int) -> discord.ui.ActionRow:
    select = discord.ui.Select(
        placeholder="🌐 Translate to…",
        custom_id=f"translate_lang:{channel_id}:{message_id}",
        options=[
            discord.SelectOption(label=name, value=code, emoji=flag)
            for code, flag, name in LANGUAGES
        ],
    )
    return discord.ui.ActionRow(select)


def _picker_view(
    original_text: str,
    channel_id: int,
    message_id: int,
) -> discord.ui.LayoutView:
    """Ephemeral CV2 layout — language select inside the container."""
    preview = original_text[:200] + ("…" if len(original_text) > 200 else "")

    container = discord.ui.Container(
        discord.ui.TextDisplay(
            "## 🌐 Translate Message\n\n"
            f"**Original text:**\n> {preview}\n\n"
            "-# Choose a target language from the menu below."
        ),
        discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
        _lang_select(channel_id, message_id),
        accent_color=discord.Color(config.PASTEL_BLUE),
    )

    lv = discord.ui.LayoutView(timeout=120)
    lv.add_item(container)
    return lv


def _loading_view() -> discord.ui.LayoutView:
    container = discord.ui.Container(
        discord.ui.TextDisplay("## 🌐 Translating…\n-# Please wait a moment~"),
        accent_color=discord.Color(config.PASTEL_BLUE),
    )
    lv = discord.ui.LayoutView()
    lv.add_item(container)
    return lv


def _result_view(
    original: str,
    translated: str,
    source_code: str,
    target_code: str,
) -> discord.ui.LayoutView:
    """CV2 layout showing the translation result."""
    src_flag, src_name = _LANG_BY_CODE.get(source_code, ("🌐", source_code.upper()))
    tgt_flag, tgt_name = _LANG_BY_CODE.get(target_code, ("🌐", target_code.upper()))

    orig_preview = original[:300] + ("…" if len(original) > 300 else "")
    trans_display = translated[:_MAX_CHARS] + ("…" if len(translated) > _MAX_CHARS else "")

    container = discord.ui.Container(
        discord.ui.TextDisplay(
            f"## 🌐 Translation\n\n"
            f"{src_flag} **{src_name}** → {tgt_flag} **{tgt_name}**\n\n"
            f"**Original:**\n> {orig_preview}\n\n"
            f"**Translation:**\n{trans_display}"
        ),
        discord.ui.Separator(),
        discord.ui.TextDisplay("-# Translated with Google Translate"),
        accent_color=discord.Color(config.PASTEL_BLUE),
    )

    lv = discord.ui.LayoutView()
    lv.add_item(container)
    return lv


def _error_view(message: str, loader: "EmojiLoader | None" = None) -> discord.ui.LayoutView:
    cross = loader.get("cross") if loader else "❌"
    container = discord.ui.Container(
        discord.ui.TextDisplay(f"## {cross} Translation Failed\n{message}"),
        accent_color=discord.Color(config.PASTEL_PEACH),
    )
    lv = discord.ui.LayoutView()
    lv.add_item(container)
    return lv


# ─── cog ──────────────────────────────────────────────────────────────────────

class Translate(commands.Cog):
    """Message context menu: translate any message into a chosen language."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # Cache: (user_id, message_id) → original text; consumed on first use.
        self._pending: dict[tuple[int, int], str] = {}
        self._ctx_menus: list[app_commands.ContextMenu] = []
        self._register_context_menus()

    def _loader(self) -> "EmojiLoader | None":
        return self.bot.get_cog("EmojiLoader")  # type: ignore[return-value]

    def _register_context_menus(self) -> None:
        _installs = app_commands.AppInstallationType(guild=True, user=True)
        _contexts = app_commands.AppCommandContext(
            guild=True, dm_channel=True, private_channel=True
        )
        menu = app_commands.ContextMenu(
            name="🌐 Translate",
            callback=self._ctx_translate,
            allowed_installs=_installs,
            allowed_contexts=_contexts,
        )
        self.bot.tree.add_command(menu)
        self._ctx_menus.append(menu)

    async def cog_unload(self) -> None:
        for menu in self._ctx_menus:
            self.bot.tree.remove_command(menu.name, type=menu.type)

    # ── context menu handler ──────────────────────────────────────────────────

    async def _ctx_translate(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        text = message.content.strip()
        if not text:
            await interaction.response.send_message(
                "That message has no text to translate~ 🌸",
                ephemeral=True,
            )
            return

        key = (interaction.user.id, message.id)
        self._pending[key] = text

        lv = _picker_view(text, message.channel.id, message.id)
        await interaction.response.send_message(view=lv, ephemeral=True)

    # ── select interaction handler ────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction) -> None:
        if interaction.type != discord.InteractionType.component:
            return
        data = interaction.data or {}
        custom_id: str = data.get("custom_id", "")
        if not custom_id.startswith("translate_lang:"):
            return

        parts = custom_id.split(":")
        if len(parts) != 3:
            return
        _, channel_id_str, message_id_str = parts

        values = data.get("values", [])
        if not values:
            return
        target_lang = values[0]

        try:
            message_id = int(message_id_str)
        except ValueError:
            return

        # Retrieve cached original text
        key = (interaction.user.id, message_id)
        original = self._pending.pop(key, None)

        loader = self._loader()

        if original is None:
            try:
                channel_id = int(channel_id_str)
                channel = self.bot.get_channel(channel_id)
                if channel and isinstance(channel, discord.TextChannel):
                    msg = await channel.fetch_message(message_id)
                    original = msg.content.strip()
            except Exception:
                pass

        if not original:
            await interaction.response.edit_message(
                view=_error_view("Couldn't retrieve the original message text.", loader)
            )
            return

        # Show loading state
        await interaction.response.edit_message(view=_loading_view())

        try:
            translated, detected = await _translate(original, target_lang)
        except Exception as exc:
            log.error("Translation failed: %s", exc)
            await interaction.edit_original_response(
                view=_error_view(
                    "The translation service is currently unavailable. Please try again later.",
                    loader,
                )
            )
            return

        if not translated:
            await interaction.edit_original_response(
                view=_error_view("Received an empty translation.", loader)
            )
            return

        await interaction.edit_original_response(
            view=_result_view(original, translated, detected, target_lang)
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Translate(bot))
