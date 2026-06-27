"""
patches.py — Runtime monkey-patches for stale discord.py behaviour.

Applied once in bot.py before any cog is loaded.

Patches
  1. CommandTree.add_command    — context-menu limit 5 → 12 (Discord's real limit)
  2. discord.ui.FileInput       — Convenience wrapper over the native
                                   discord.ui.Label (type 18) + discord.ui.FileUpload
                                   (type 19) API that discord.py 2.7 already ships.
                                   After on_submit, read .attachment (first file) or
                                   .attachments (all files) — both return native
                                   discord.Attachment objects.

Implementation note for FileInput
───────────────────────────────────
discord.py 2.7.x already has discord.ui.Label and discord.ui.FileUpload.
Modal.to_components() emits Label items DIRECTLY (not wrapped in an action row),
which matches the Discord API requirement:

  {
    "type": 18,            // ComponentType.LABEL — outer wrapper (discord.ui.Label)
    "label": "...",
    "description": "...",  // optional
    "component": {
      "type": 19,          // ComponentType.FILE_UPLOAD (discord.ui.FileUpload)
      "custom_id": "...",
      "min_values": 0,
      "max_values": 1,
      "required": false
    }
  }

FileInput subclasses Label and owns an inner FileUpload so callers get the
familiar .attachment / .attachments surface without knowing about the split.
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


# ─── patch 2: FileInput ────────────────────────────────────────────────────────
#
# discord.py 2.7 ships discord.ui.Label (type 18) and discord.ui.FileUpload
# (type 19) natively.  Modal.to_components() already emits Label items directly
# (no action-row wrapper), matching the Discord API requirement exactly.
#
# FileInput is a thin convenience wrapper: it subclasses Label and owns an
# inner FileUpload so call-sites only interact with one object and can read
# .attachment / .attachments after on_submit fires.


class FileInput(discord.ui.Label):
    """
    A file-upload field for use inside discord.ui.Modal subclasses.

    Wraps discord.ui.Label (type 18) + discord.ui.FileUpload (type 19) using
    the API that discord.py 2.7 already ships natively.  The serialised payload
    matches the official Discord docs exactly:

        {
          "type": 18,               // ComponentType.LABEL
          "label": "...",
          "description": "...",     // optional
          "component": {
            "type": 19,             // ComponentType.FILE_UPLOAD
            "custom_id": "...",
            "min_values": 0,
            "max_values": 1,
            "required": false
          }
        }

    Parameters
    ----------
    label:       str       — label shown above the file picker (required)
    description: str|None  — helper text shown below the label (optional)
    custom_id:   str       — stable ID for the inner FileUpload (auto-generated)
    required:    bool      — whether a file must be uploaded before submitting
    min_values:  int       — minimum number of files the user must upload (0–10)
    max_values:  int       — maximum number of files the user may upload (1–10)

    Properties
    ----------
    attachment   — first discord.Attachment, or None if nothing was uploaded
    attachments  — list of all discord.Attachment objects (empty list if none)
    """

    def __init__(
        self,
        *,
        label: str = "Upload File",
        description: str | None = None,
        custom_id: str = discord.utils.MISSING,
        required: bool = False,
        min_values: int = 0,
        max_values: int = 1,
    ) -> None:
        kw: dict = {}
        if custom_id is not discord.utils.MISSING:
            kw["custom_id"] = custom_id

        upload = discord.ui.FileUpload(
            required=required,
            min_values=min_values,
            max_values=max_values,
            **kw,
        )
        super().__init__(
            text=label,
            component=upload,
            description=description,
        )

    # ── public API ─────────────────────────────────────────────────────────────

    @property
    def attachment(self) -> discord.Attachment | None:
        """The first uploaded file, or None if the user uploaded nothing."""
        values: list[discord.Attachment] = self.component.values  # type: ignore[union-attr]
        return values[0] if values else None

    @property
    def attachments(self) -> list[discord.Attachment]:
        """All uploaded files as a list (empty list if none)."""
        return list(self.component.values)  # type: ignore[union-attr]


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
        "discord.ui.FileInput registered — native Label(18) + FileUpload(19) wrapper"
    )
