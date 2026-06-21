"""
patches.py — Runtime monkey-patches for stale discord.py behaviour.

Applied once in bot.py before any cog is loaded.

Patches
  1. CommandTree.add_command    — context-menu limit 5 → 12 (Discord's real limit)
  2. discord.ui.FileInput       — Discord's native file-upload modal component
                                   (component type 11; not yet in discord.py).
                                   After on_submit, read .attachment for the
                                   uploaded file proxy (url, filename, etc.).
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
# We add it here as discord.ui.FileInput so Modal subclasses that reference it
# at class-body evaluation time find the class immediately on import of patches.
#
# How it works
# ────────────
#   • FileInput.to_dict() serialises as {"type": _FILE_INPUT_TYPE, ...} instead
#     of the usual TextInput type-4 shape.  Discord renders this as a file
#     picker in the modal UI.
#
#   • When the user submits the modal, Discord puts the attachment ID in the
#     component's "value" field and the full attachment object in
#     interaction.data["resolved"]["attachments"][attachment_id].
#
#   • _patch_modal_file_input() wraps Modal._invoke so that, after discord.py's
#     normal _refresh_component pass (which sets _pending_id on each FileInput),
#     but BEFORE on_submit is called, we resolve each FileInput's attachment
#     from the interaction's resolved data.
#
#   • Consumers read  item.attachment  (an _AttachmentProxy or None).


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
        self.id:           str       = data.get("id", "")
        self.filename:     str       = data.get("filename", "")
        self.url:          str       = data.get("url", "")
        self.proxy_url:    str       = data.get("proxy_url", self.url)
        self.size:         int       = data.get("size", 0)
        self.content_type: str       = data.get("content_type", "")
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

    Drop-in replacement for discord.ui.TextInput in Modal class bodies.
    After on_submit fires, read .attachment for the uploaded file.

    Parameters
    ----------
    label:      str  — label shown above the file picker
    custom_id:  str  — stable ID (auto-generated if omitted)
    required:   bool — whether the field must be filled before submitting

    Properties
    ----------
    attachment  — _AttachmentProxy with .url .filename .content_type .size
                  (and .is_image helper), or None if the user left the field empty.
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
        self._pending_id:  str | None             = None
        self._attachment:  _AttachmentProxy | None = None

    # ── component serialisation ────────────────────────────────────────────────

    def to_dict(self) -> dict:                              # type: ignore[override]
        """Return the component payload Discord expects for a file-upload field."""
        return {
            "type":      _FILE_INPUT_TYPE,
            "custom_id": self.custom_id,
            "label":     self.label,
            "required":  self.required,
        }

    # ── called by Modal._invoke with the raw submitted component dict ──────────

    def _refresh_component(self, component: dict) -> None:  # type: ignore[override]
        self._pending_id = component.get("value")

    # ── internal: resolve attachment from interaction resolved data ────────────

    def _resolve(self, attachments_map: dict[str, dict]) -> None:
        self._attachment = None
        if self._pending_id:
            raw = attachments_map.get(str(self._pending_id))
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


def _patch_modal_file_input() -> bool:
    """
    Wrap Modal._invoke so that FileInput attachments are resolved from
    interaction.data["resolved"]["attachments"] BEFORE on_submit is called.

    discord.py's _invoke normally does:
        for each submitted component → call item._refresh_component(data)
        await self.on_submit(interaction)

    Our wrapper inserts a resolution pass between those two steps.
    """
    from discord.ui import Modal

    if getattr(Modal._invoke, "_mochime_file_input_patched", False):
        return False

    _orig_invoke = Modal._invoke

    async def _patched_invoke(
        self: Modal, interaction: discord.Interaction
    ) -> None:
        # ── Step 1: pre-resolve FileInput items before the original invoke ──
        raw_data = interaction.data or {}
        resolved = raw_data.get("resolved") or {}
        attachments_map: dict[str, dict] = resolved.get("attachments") or {}

        # Walk submitted components to match custom_ids and set _pending_id
        for action_row in raw_data.get("components", []):
            for component in action_row.get("components", []):
                cid = component.get("custom_id")
                for child in self.children:
                    if isinstance(child, FileInput) and child.custom_id == cid:
                        child._pending_id = component.get("value")
                        child._resolve(attachments_map)

        # ── Step 2: run the original _invoke (re-calls _refresh_component on
        #           all items, then calls on_submit — that's fine because
        #           our _resolve has already set .attachment before on_submit)
        await _orig_invoke(self, interaction)

    _patched_invoke._mochime_file_input_patched = True  # type: ignore[attr-defined]
    Modal._invoke = _patched_invoke                      # type: ignore[method-assign]
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

    if _patch_modal_file_input():
        log.info(
            "Patched Modal._invoke — FileInput resolution enabled (component type %d)",
            _FILE_INPUT_TYPE,
        )
    else:
        log.info("Modal FileInput patch not needed (already patched)")

    log.info("discord.ui.FileInput registered (%s)", FileInput.__name__)
