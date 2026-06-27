"""
patches.py — Runtime monkey-patches for stale discord.py behaviour.

Applied once in bot.py before any cog is loaded.

Patches
  1. CommandTree.add_command    — context-menu limit 5 → 12 (Discord's real limit)
  2. discord.ui.FileInput       — Discord's native file-upload modal component.
                                   Per the Discord API docs, a file-upload field
                                   inside a modal is serialised as a LABEL wrapper
                                   (type 18) whose "component" key holds the inner
                                   FILE_UPLOAD object (type 19).  After on_submit,
                                   read .attachment (or .attachments for multi)
                                   for the uploaded file proxy (url, filename, …).

Implementation note for FileInput
───────────────────────────────────
Discord API modal component structure (from official docs):
  {
    "type": 18,            // ComponentType.LABEL — the outer wrapper
    "label": "...",
    "description": "...",  // optional
    "component": {
      "type": 19,          // ComponentType.FILE_UPLOAD — the inner picker
      "custom_id": "...",
      "min_values": 1,
      "max_values": 1,
      "required": true
    }
  }

discord.py 2.7.x routes unknown component types through the normal
_refresh → item._handle_submit(interaction, component, resolved) pipeline,
matching items by custom_id.  So we only need to implement _handle_submit
to pull attachments out of interaction.data["resolved"]["attachments"].
"""
from __future__ import annotations

import discord

import console

log = console.get_logger("mochime.patches")

DISCORD_REAL_LIMIT = 12

# Component types for Discord's file-upload modal support.
# Neither is present in discord.py's ComponentType enum as of 2.7.x.
_LABEL_TYPE: int       = 18   # ComponentType.LABEL  — outer wrapper
_FILE_UPLOAD_TYPE: int = 19   # ComponentType.FILE_UPLOAD — inner picker


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
    fires, read .attachment (single) or .attachments (list) for uploaded files.

    Serialised per the official Discord API docs as a LABEL wrapper (type 18)
    containing a FILE_UPLOAD component (type 19):

        {
          "type": 18,
          "label": "...",
          "description": "...",   # optional
          "component": {
            "type": 19,
            "custom_id": "...",
            "min_values": 1,
            "max_values": 1,
            "required": true
          }
        }

    Parameters
    ----------
    label:       str       — label shown above the file picker (required)
    description: str|None  — helper text shown below the label (optional)
    custom_id:   str       — stable ID (auto-generated if omitted)
    required:    bool      — whether the field must be filled before submitting
    min_values:  int       — minimum number of files (default 1)
    max_values:  int       — maximum number of files (default 1)
    row:         int|None  — row hint (passed to TextInput base, unused by Discord)

    Properties
    ----------
    attachment   — first _AttachmentProxy, or None if nothing was uploaded
    attachments  — list of all _AttachmentProxy objects (empty list if none)
    """

    def __init__(
        self,
        *,
        label: str = "Upload File",
        description: str | None = None,
        custom_id: str = discord.utils.MISSING,
        required: bool = False,
        min_values: int = 1,
        max_values: int = 1,
        row: int | None = None,
    ) -> None:
        super().__init__(
            label=label,
            custom_id=custom_id,  # type: ignore[arg-type]
            required=required,
            row=row,
        )
        self._description: str | None = description
        self._min_values: int = min_values
        self._max_values: int = max_values
        self._attachments: list[_AttachmentProxy] = []

    # ── component serialisation ────────────────────────────────────────────────

    def to_dict(self) -> dict:                              # type: ignore[override]
        """
        Return the payload Discord expects for a file-upload field inside a
        modal — a LABEL wrapper (type 18) with an inner FILE_UPLOAD (type 19).
        """
        inner: dict = {
            "type":       _FILE_UPLOAD_TYPE,
            "custom_id":  self.custom_id,
            "required":   self.required,
            "min_values": self._min_values,
            "max_values": self._max_values,
        }
        outer: dict = {
            "type":      _LABEL_TYPE,
            "label":     self.label,
            "component": inner,
        }
        if self._description is not None:
            outer["description"] = self._description
        return outer

    # ── called by Modal._refresh for every matched component on submission ─────
    #
    # discord.py's Modal._refresh walks submitted components and for any type
    # that isn't an action-row (1) or container (18) it finds the item by
    # custom_id and calls item._handle_submit(interaction, component, resolved).
    # The submitted value for a FILE_UPLOAD is the attachment ID (or a list of
    # IDs for multi-upload), resolved via interaction.data["resolved"]["attachments"].

    def _handle_submit(
        self,
        interaction: discord.Interaction,
        data: dict,
        resolved: dict,
    ) -> None:
        self._attachments = []
        raw_resolved = (interaction.data or {}).get("resolved") or {}
        raw_attachments: dict = raw_resolved.get("attachments") or {}

        # "value" may be a single ID string or a list of ID strings
        value = data.get("value") or data.get("values") or []
        if isinstance(value, str):
            value = [value]

        for attachment_id in value:
            raw = raw_attachments.get(str(attachment_id))
            if raw:
                self._attachments.append(_AttachmentProxy(raw))

    # ── public API ─────────────────────────────────────────────────────────────

    @property
    def attachment(self) -> _AttachmentProxy | None:
        """The first uploaded file, or None if the user left this optional field empty."""
        return self._attachments[0] if self._attachments else None

    @property
    def attachments(self) -> list[_AttachmentProxy]:
        """All uploaded files as a list (empty if none uploaded)."""
        return list(self._attachments)

    @property                                               # type: ignore[override]
    def value(self) -> str:
        """Always empty — use .attachment / .attachments instead."""
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
        "discord.ui.FileInput registered — LABEL wrapper type %d, FILE_UPLOAD inner type %d",
        _LABEL_TYPE,
        _FILE_UPLOAD_TYPE,
    )
