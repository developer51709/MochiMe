"""
patches.py — Runtime monkey-patches for stale discord.py behaviour.

Applied once in bot.py before any cog is loaded.
"""
from __future__ import annotations

import console

log = console.get_logger("mochime.patches")

# Discord's actual current limit per context-menu type (User / Message).
# discord.py 2.x still enforces the stale limit of 5; patch it to 12.
DISCORD_REAL_LIMIT = 12


def _patch_context_menu_limit() -> bool:
    """
    discord.py ≤ 2.7.x has `_context_menu_add_helper` as a nested closure
    inside `CommandTree.add_command` that raises CommandLimitReached(limit=5)
    even though Discord now allows 12 per type.

    Strategy: wrap `CommandTree.add_command` so that when the stale limit is
    hit for a context menu we check against DISCORD_REAL_LIMIT ourselves and
    insert directly into the internal `_context_menus` dict if we're still
    within bounds.  Any other CommandLimitReached (slash commands at 100, etc.)
    is re-raised untouched.
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

    # Guard: don't double-patch across hot-reloads
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
            # Only intercept the stale context-menu limit of 5.
            if exc.limit != 5 or not isinstance(command, ContextMenu):
                raise

            # Count how many of this type are already registered globally.
            type_val = command.type.value
            total = sum(
                1
                for (_, g, t) in self._context_menus
                if g is None and t == type_val
            )

            if total < DISCORD_REAL_LIMIT:
                # Within Discord's real limit — bypass and add directly.
                key = (command.name, None, type_val)
                if key in self._context_menus and not override:
                    raise CommandAlreadyRegistered(command.name, None)
                self._context_menus[key] = command
                return

            # Genuinely over the real limit — re-raise with correct number.
            raise CommandLimitReached(
                guild_id=None,
                limit=DISCORD_REAL_LIMIT,
                type=command.type,
            ) from exc

    _patched_add_command._mochime_patched = True        # type: ignore[attr-defined]
    _patched_add_command.__doc__ = _original.__doc__
    CommandTree.add_command = _patched_add_command      # type: ignore[method-assign]
    return True


def apply_all() -> None:
    """Apply every registered patch. Call this before loading any cog."""
    if _patch_context_menu_limit():
        log.info(
            "Patched CommandTree.add_command — context-menu limit 5 → %d",
            DISCORD_REAL_LIMIT,
        )
    else:
        log.info(
            "Context-menu limit patch not needed (already ≥ %d or already patched)",
            DISCORD_REAL_LIMIT,
        )
