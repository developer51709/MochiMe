"""
patches.py — Runtime monkey-patches for stale discord.py behaviour.

Applied once in bot.py before any cog is loaded.

Patches
  1. CommandTree.add_command    — context-menu limit 5 → 12 (Discord's real limit)
  2. discord.ui.FileInput       — Discord's native file-upload modal component
                                   (component type 11; not yet in discord.py).
                                   After on_submit, read .attachment for the
                                   uploaded file proxy (url, filename, etc.).

Implementation note for FileInput
───────────────────────────────────
discord.py 2.7.x already routes unknown component types through the normal
_refresh → item._handle_submit(interaction, component, resolved) pipeline
(anything that isn't an action-row type 1 or container type 18 falls through
to the else-branch that matches by custom_id).  So no patching of Modal
internals is required — FileInput just implements _handle_submit to pull the
attachment out of interaction.data["resolved"]["attachments"].
"""
from __future__ import annotations

import discord

import console

log = console.get_logger("mochime.patches")

DISCORD_REAL_LIMIT = 12

# Component type Discord uses for file-upload fields inside modals.
# Not yet present in discord.py's ComponentType enum as of 2.7.x.
_FILE_INPUT_TYPE: int = 11


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


# ─── patch 2: FileInput ────────────────────────────────────────────────────────
#
# discord.py has no native support for Discord's file-upload modal component.
# We register discord.ui.FileInput here so that Modal subclasses referencing
# it at class-body evaluation time find the class immediately on import.


class _AttachmentProxy:
    """
    Lightweight stand-in for discord.Attachment returned by FileInput.
    Exposes the same key attributes without needing a ConnectionState.
    """

    __slots__ = (
        "id",
        "filename",
        "url",
        "proxy_url",
        "size",
        "content_type",
        "height",
        "width",
    )

    def __init__(self, data: dict) -> None:
        self.id:           str        = data.get("id", "")
        self.filename:     str        = data.get("filename", "")
        self.url:          str        = data.get("url", "")
        self.proxy_url:    str        = data.get("proxy_url", self.url)
        self.size:         int        = data.get("size", 0)
        self.content_type: str        = data.get("content_type", "")
        self.height:       int | None = data.get("height")
        self.width:        int | None = data.get("width")

    def __repr__(self) -> str:
        return f"<Attachment filename={self.filename!r} url={self.url!r}>"

    def __bool__(self) -> bool:
        return bool(self.url)

    @property
    def is_image(self) -> bool:
        return self.content_type.startswith("image/")


class FileInput(discord.ui.TextInput):
    """
    A native file-upload field for use inside discord.ui.Modal subclasses.
    discord.py does not yet implement this component; we patch it in.

    Drop-in for discord.ui.TextInput in Modal class bodies.  After on_submit
    fires, read .attachment for the uploaded file.

    Parameters
    ----------
    label:      str  — label shown above the file picker (required)
    custom_id:  str  — stable ID (auto-generated if omitted)
    required:   bool — whether the field must be filled before submitting

    Properties
    ----------
    attachment  — _AttachmentProxy with .url .filename .content_type .size
                  (and .is_image), or None if the user left the field empty.
    """

    def __init__(
        self,
        *,
        label: str = "Upload File",
        custom_id: str = discord.utils.MISSING,
        required: bool = False,
        row: int | None = None,
    ) -> None:
        super().__init__(
            label=label,
            custom_id=custom_id,  # type: ignore[arg-type]
            required=required,
            row=row,
        )
        self._attachment: _AttachmentProxy | None = None

    # ── component serialisation ────────────────────────────────────────────────

    def to_dict(self) -> dict:                              # type: ignore[override]
        """Return the payload Discord expects for a file-upload field."""
        return {
            "type":      _FILE_INPUT_TYPE,
            "custom_id": self.custom_id,
            "label":     self.label,
            "required":  self.required,
        }

    # ── called by Modal._refresh for every matched component on submission ─────
    #
    # discord.py's Modal._refresh walks submitted components and for any type
    # that isn't an action-row (1) or container (18) it finds the item by
    # custom_id and calls item._handle_submit(interaction, component, resolved).
    # We override that here; no patching of Modal internals required.

    def _handle_submit(
        self,
        interaction: discord.Interaction,
        data: dict,
        resolved: dict,
    ) -> None:
        self._attachment = None
        attachment_id = data.get("value")
        if not attachment_id:
            return
        raw_resolved = (interaction.data or {}).get("resolved") or {}
        raw_attachments: dict = raw_resolved.get("attachments") or {}
        raw = raw_attachments.get(str(attachment_id))
        if raw:
            self._attachment = _AttachmentProxy(raw)

    # ── public API ─────────────────────────────────────────────────────────────

    @property
    def attachment(self) -> _AttachmentProxy | None:
        """The uploaded file, or None if the user left this optional field empty."""
        return self._attachment

    @property                                               # type: ignore[override]
    def value(self) -> str:
        """Always empty — use .attachment instead."""
        return ""


discord.ui.FileInput = FileInput  # type: ignore[attr-defined]


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

    log.info(
        "discord.ui.FileInput registered — component type %d, _handle_submit override",
        _FILE_INPUT_TYPE,
    )
