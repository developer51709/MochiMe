"""
patches.py — Runtime monkey-patches for stale discord.py behaviour.

Applied once in bot.py before any cog is loaded.

Patches
  1. CommandTree.add_command    — context-menu limit 5 → 12 (Discord's real limit)
  2. discord.ui.AttachmentInput — new class; adds image-URL-validated TextInput to
                                   discord.ui for use in Modal subclasses.
  3. CV2 send forwarder         — discord.py 2.7.x high-level send methods do not
                                   accept `components=` or `flags=`; CV2 items must
                                   go through LayoutView.  This patch intercepts
                                   `components=[...]` on Context.send,
                                   Messageable.send, InteractionResponse.send_message,
                                   and Webhook.send, converts them to a LayoutView,
                                   and strips the now-redundant flags= kwarg so all
                                   existing cog code works without modification.
"""
from __future__ import annotations

import discord

import console

log = console.get_logger("mochime.patches")

# Discord's actual current limit per context-menu type (User / Message).
# discord.py 2.x still enforces the stale limit of 5; patch it to 12.
DISCORD_REAL_LIMIT = 12


# ─── patch 1: context-menu limit ──────────────────────────────────────────────

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
# *module-import time* (not inside apply_all) so that Modal subclasses which
# reference discord.ui.AttachmentInput at class-body evaluation time — i.e.
# cogs/welcome.py — find it as soon as `import patches` executes.
#
# AttachmentInput is a TextInput subclass and therefore works inside any
# discord.ui.Modal without further patching.  The "attachment" behaviour is
# purely client-side: it validates that the submitted value is a direct image
# URL and exposes image_url / error_message helpers.

class AttachmentInput(discord.ui.TextInput):
    """
    A discord.ui.TextInput subclass that validates its value as a direct
    image URL.  Use it as a field inside a discord.ui.Modal exactly like
    a normal TextInput.

    discord.py has no built-in AttachmentInput; this class is the runtime
    patch that adds the concept.  The complementary `/setwelcomeimage` slash
    command accepts a real discord.Attachment for file-upload flows.

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
        """Returns the validated URL, or None if the field is empty or invalid."""
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
        """Returns a human-readable error string, or None if the value is valid."""
        val = (self.value or "").strip()
        if not val:
            return None
        if not val.startswith("https://"):
            return "Image URL must start with https://"
        if not self._is_valid(val):
            return "Please provide a direct image URL (.png .jpg .gif .webp)"
        return None


# Expose in discord.ui namespace so code can write `discord.ui.AttachmentInput`
discord.ui.AttachmentInput = AttachmentInput  # type: ignore[attr-defined]


# ─── patch 3: CV2 send forwarder ──────────────────────────────────────────────

def _patch_cv2_send() -> bool:
    """
    discord.py 2.7.x high-level send methods (Context.send, Messageable.send,
    InteractionResponse.send_message, Webhook.send) do not accept a raw
    `components=` kwarg — CV2 items must be added to a LayoutView and passed
    via `view=`.  The `components_v2` MessageFlag is then set automatically by
    discord.py when the view's `has_components_v2()` returns True.

    This patch wraps all four send targets so that cog code written as:

        await ctx.send(components=[container],
                       flags=discord.MessageFlags(components_v2=True))

    is silently converted to:

        lv = discord.ui.LayoutView(); lv.add_item(container)
        await ctx.send(view=lv)

    No cog code needs to change.  Non-CV2 calls pass through unmodified.
    If both `components=` and `view=` are present (prefix-command edge case),
    the LayoutView replaces the plain View; the caller must handle interactive
    buttons inside the LayoutView itself.
    """
    _SENTINEL = "_mochime_cv2_patched"

    if getattr(discord.abc.Messageable.send, _SENTINEL, False):
        return False  # already applied (hot-reload guard)

    def _make_layout_view(items: list) -> discord.ui.LayoutView:
        lv = discord.ui.LayoutView()
        for item in items:
            lv.add_item(item)
        return lv

    def _wrap(original):
        async def _patched(self, content=None, **kwargs):
            cv2_items = kwargs.pop("components", None)
            kwargs.pop("flags", None)          # LayoutView sets flags automatically

            if cv2_items is not None:
                kwargs.pop("view", None)       # discard any plain View passed alongside
                kwargs["view"] = _make_layout_view(cv2_items)

            return await original(self, content, **kwargs)

        setattr(_patched, _SENTINEL, True)
        _patched.__name__    = getattr(original, "__name__",    "_patched")
        _patched.__qualname__ = getattr(original, "__qualname__", "_patched")
        _patched.__doc__     = original.__doc__
        return _patched

    from discord.ext.commands import Context
    Context.send                             = _wrap(Context.send)                             # type: ignore[method-assign]
    discord.abc.Messageable.send             = _wrap(discord.abc.Messageable.send)             # type: ignore[method-assign]
    discord.InteractionResponse.send_message = _wrap(discord.InteractionResponse.send_message) # type: ignore[method-assign]
    discord.InteractionResponse.edit_message = _wrap(discord.InteractionResponse.edit_message) # type: ignore[method-assign]
    discord.Webhook.send                     = _wrap(discord.Webhook.send)                     # type: ignore[method-assign]

    return True


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

    # AttachmentInput is already attached at module level; just confirm.
    log.info("discord.ui.AttachmentInput registered (%s)", AttachmentInput.__name__)

    if _patch_cv2_send():
        log.info(
            "Patched CV2 send forwarder — components= → LayoutView on "
            "Context.send / Messageable.send / InteractionResponse.send_message"
            " / InteractionResponse.edit_message / Webhook.send"
        )
    else:
        log.info("CV2 send forwarder already applied")
