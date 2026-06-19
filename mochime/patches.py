"""
patches.py — Runtime monkey-patches for stale discord.py behaviour.

Applied once in bot.py before any cog is loaded.

Patches
  1. CommandTree.add_command    — context-menu limit 5 → 12 (Discord's real limit)
  2. discord.ui.AttachmentInput — new class; adds image-URL-validated TextInput to
                                   discord.ui for use in Modal subclasses.
"""
from __future__ import annotations

import discord

import console

log = console.get_logger("mochime.patches")

DISCORD_REAL_LIMIT = 12


# ─── patch 1: context-menu limit ──────────────────────────────────────────────

def _patch_context_menu_limit() -> bool:
    """
    discord.py ≤ 2.7.x has `_context_menu_add_helper` as a nested closure
    inside `CommandTree.add_command` that raises CommandLimitReached(limit=5)
    even though Discord now allows 12 per type.
    """
    try:
        from discord.app_commands import CommandTree
        from discord.app_commands.commands import ContextMenu
        from discord.app_commands.errors import (
            CommandAlreadyRegistered,
            CommandLimitReached,
        )
        from discord.utils import MISSING as _MISSING
    except ImportError:
        return False

    if getattr(CommandTree.add_command, "_mochime_patched", False):
        return False

    _original = CommandTree.add_command

    def _patched_add_command(
        self: CommandTree,
        command,
        /,
        *,
        guild=None,
        guilds=_MISSING,
        override: bool = False,
    ) -> None:
        try:
            return _original(self, command, guild=guild, guilds=guilds, override=override)
        except CommandLimitReached as exc:
            if exc.limit != 5 or not isinstance(command, ContextMenu):
                raise

            type_val = command.type.value
            total = sum(
                1
                for (_, g, t) in self._context_menus
                if g is None and t == type_val
            )

            if total < DISCORD_REAL_LIMIT:
                key = (command.name, None, type_val)
                if key in self._context_menus and not override:
                    raise CommandAlreadyRegistered(command.name, None)
                self._context_menus[key] = command
                return

            raise CommandLimitReached(
                guild_id=None,
                limit=DISCORD_REAL_LIMIT,
                type=command.type,
            ) from exc

    _patched_add_command._mochime_patched = True        # type: ignore[attr-defined]
    _patched_add_command.__doc__ = _original.__doc__
    CommandTree.add_command = _patched_add_command      # type: ignore[method-assign]
    return True


# ─── patch 2: AttachmentInput ──────────────────────────────────────────────────
#
# discord.py has no discord.ui.AttachmentInput class.  We add one here at
# *module-import time* so that Modal subclasses which reference
# discord.ui.AttachmentInput at class-body evaluation time find it immediately.

class AttachmentInput(discord.ui.TextInput):
    """
    A discord.ui.TextInput subclass that validates its value as a direct
    image URL.  Use it as a field inside a discord.ui.Modal exactly like
    a normal TextInput.

    Properties
      image_url     — validated URL or None if empty / invalid
      error_message — human-readable failure string or None if valid
    """

    _IMAGE_EXTS: tuple[str, ...] = (".png", ".jpg", ".jpeg", ".gif", ".webp")
    _TRUSTED_HOSTS: tuple[str, ...] = (
        "cdn.discordapp.com",
        "media.discordapp.net",
        "i.imgur.com",
        "i.ibb.co",
        "tenor.com",
        "giphy.com",
    )

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("label", "Banner Image URL (optional)")
        kwargs.setdefault(
            "placeholder",
            "https://  — paste a direct image link (.png .jpg .gif .webp)",
        )
        kwargs.setdefault("required", False)
        kwargs.setdefault("max_length", 500)
        super().__init__(**kwargs)

    @property
    def image_url(self) -> str | None:
        val = (self.value or "").strip()
        if not val:
            return None
        return val if self._is_valid(val) else None

    @classmethod
    def _is_valid(cls, url: str) -> bool:
        if not url.startswith("https://"):
            return False
        path = url.lower().split("?")[0].split("#")[0]
        if any(path.endswith(ext) for ext in cls._IMAGE_EXTS):
            return True
        return any(host in url for host in cls._TRUSTED_HOSTS)

    def error_message(self) -> str | None:
        val = (self.value or "").strip()
        if not val:
            return None
        if not val.startswith("https://"):
            return "Image URL must start with https://"
        if not self._is_valid(val):
            return "Please provide a direct image URL (.png .jpg .gif .webp)"
        return None


discord.ui.AttachmentInput = AttachmentInput  # type: ignore[attr-defined]


# ─── apply_all ────────────────────────────────────────────────────────────────

def apply_all() -> None:
    """Apply every registered patch.  Call once before loading any cog."""
    if _patch_context_menu_limit():
        log.info(
            "Patched CommandTree.add_command — context-menu limit 5 → %d",
            DISCORD_REAL_LIMIT,
        )
    else:
        log.info("Context-menu limit patch not needed (already patched or not required)")

    log.info("discord.ui.AttachmentInput registered (%s)", AttachmentInput.__name__)
