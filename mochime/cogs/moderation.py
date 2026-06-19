from __future__ import annotations

import datetime
import secrets

import discord
from discord import app_commands
from discord.ext import commands

import config
import database
from cogs.emoji_loader import EmojiLoader


def _cv2(*items: discord.ui.Component) -> discord.ui.LayoutView:
    lv = discord.ui.LayoutView()
    for item in items:
        lv.add_item(item)
    return lv


def _missing_perm_container(emoji_loader: EmojiLoader, perm: str) -> discord.ui.Container:
    cross = emoji_loader.get("cross")
    return discord.ui.Container(
        discord.ui.TextDisplay(
            f"## {cross} Missing Permission\n"
            f"You need the **{perm}** permission to use this command."
        ),
        accent_color=discord.Color(config.PASTEL_PEACH),
    )


def _success_container(
    emoji_loader: EmojiLoader,
    action: str,
    target: discord.Member,
    reason: str,
    moderator: discord.Member | discord.User,
) -> discord.ui.Container:
    check = emoji_loader.get("check")
    shield = emoji_loader.get("shield")
    ribbon = emoji_loader.get("ribbon")
    return discord.ui.Container(
        discord.ui.TextDisplay(
            f"## {shield} {action} Successful\n\n"
            f"{check} **Target:** {target.mention} (`{target}`)\n"
            f"{check} **Reason:** {reason}\n"
            f"{ribbon} **Moderator:** {moderator.mention}\n"
            f"{ribbon} **When:** <t:{int(datetime.datetime.utcnow().timestamp())}:R>"
        ),
        accent_color=discord.Color(config.PASTEL_GREEN),
    )


def _confirm_container(
    emoji_loader: EmojiLoader,
    action: str,
    target: discord.Member,
    reason: str,
    token: str,
) -> discord.ui.Container:
    warning = emoji_loader.get("warning")
    shield = emoji_loader.get("shield")
    return discord.ui.Container(
        discord.ui.TextDisplay(
            f"## {warning} Confirm {action}\n\n"
            f"{shield} **Target:** {target.mention} (`{target}`)\n"
            f"{shield} **Reason:** {reason}\n\n"
            "Are you sure you want to do this?"
        ),
        discord.ui.Separator(),
        discord.ui.ActionRow(
            discord.ui.Button(
                label="Confirm",
                style=discord.ButtonStyle.danger,
                custom_id=f"mod_confirm:{token}",
            ),
            discord.ui.Button(
                label="Cancel",
                style=discord.ButtonStyle.secondary,
                custom_id=f"mod_cancel:{token}",
            ),
        ),
        accent_color=discord.Color(config.PASTEL_PEACH),
    )


def _disabled_confirm_container(
    emoji_loader: EmojiLoader,
    action: str,
    target: discord.Member,
    reason: str,
) -> discord.ui.Container:
    warning = emoji_loader.get("warning")
    shield = emoji_loader.get("shield")
    return discord.ui.Container(
        discord.ui.TextDisplay(
            f"## {warning} Confirm {action}\n\n"
            f"{shield} **Target:** {target.mention} (`{target}`)\n"
            f"{shield} **Reason:** {reason}\n\n"
            "Are you sure you want to do this?"
        ),
        discord.ui.Separator(),
        discord.ui.ActionRow(
            discord.ui.Button(
                label="Confirm",
                style=discord.ButtonStyle.danger,
                custom_id="mod_confirm:disabled",
                disabled=True,
            ),
            discord.ui.Button(
                label="Cancel",
                style=discord.ButtonStyle.secondary,
                custom_id="mod_cancel:disabled",
                disabled=True,
            ),
        ),
        accent_color=discord.Color(config.PASTEL_PEACH),
    )


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # Maps token → {"callback", "loader", "action", "target", "reason"}
        self._pending: dict[str, dict] = {}

    def _loader(self) -> EmojiLoader:
        cog = self.bot.get_cog("EmojiLoader")
        assert isinstance(cog, EmojiLoader)
        return cog

    async def _send_confirm(
        self,
        ctx: commands.Context,
        loader: EmojiLoader,
        action: str,
        target: discord.Member,
        reason: str,
        callback,
    ) -> None:
        token = secrets.token_hex(8)
        self._pending[token] = {
            "callback": callback,
            "loader": loader,
            "action": action,
            "target": target,
            "reason": reason,
        }
        container = _confirm_container(loader, action, target, reason, token)
        lv = discord.ui.LayoutView(timeout=60)
        lv.add_item(container)
        await ctx.send(view=lv)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction) -> None:
        if interaction.type != discord.InteractionType.component:
            return
        data = interaction.data or {}
        custom_id: str = data.get("custom_id", "")

        if custom_id.startswith("mod_confirm:") or custom_id.startswith("mod_cancel:"):
            await self._handle_confirm_interaction(interaction, custom_id)

    async def _handle_confirm_interaction(
        self, interaction: discord.Interaction, custom_id: str
    ) -> None:
        parts = custom_id.split(":", 1)
        if len(parts) != 2:
            return
        action_type, token = parts

        if token == "disabled":
            return

        pending = self._pending.pop(token, None)
        if pending is None:
            await interaction.response.send_message(
                "This confirmation has already been handled or expired~ 🌸",
                ephemeral=True,
            )
            return

        loader: EmojiLoader = pending["loader"]
        action: str = pending["action"]
        target: discord.Member = pending["target"]
        reason: str = pending["reason"]

        # Disable the buttons on the original message first
        if interaction.message:
            disabled_container = _disabled_confirm_container(loader, action, target, reason)
            disabled_lv = discord.ui.LayoutView()
            disabled_lv.add_item(disabled_container)
            try:
                await interaction.message.edit(view=disabled_lv)
            except Exception:
                pass

        if action_type == "mod_cancel":
            cross = loader.get("cross")
            cancel_container = discord.ui.Container(
                discord.ui.TextDisplay(f"## {cross} Cancelled\nNo action was taken."),
                accent_color=discord.Color(config.PASTEL_BLUE),
            )
            await interaction.response.send_message(view=_cv2(cancel_container), ephemeral=True)
            return

        # mod_confirm
        await pending["callback"](interaction)

    # ── moderation commands ───────────────────────────────────────────────────

    @commands.hybrid_command(name="ban", description="Ban a member from the server")
    @app_commands.describe(target="Member to ban", reason="Reason for the ban")
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    async def ban(
        self,
        ctx: commands.Context,
        target: discord.Member,
        *,
        reason: str = "No reason provided",
    ) -> None:
        loader = self._loader()

        async def do_ban(interaction: discord.Interaction) -> None:
            assert ctx.guild
            try:
                await target.ban(reason=f"[MochiMe] {reason} | Mod: {ctx.author}")
                await database.log_moderation(
                    str(ctx.guild.id), str(ctx.author.id), str(target.id), "ban", reason
                )
                success = _success_container(loader, "Ban", target, reason, ctx.author)
                await interaction.response.send_message(view=_cv2(success), ephemeral=True)
            except discord.Forbidden:
                cross = loader.get("cross")
                err = discord.ui.Container(
                    discord.ui.TextDisplay(
                        f"## {cross} Failed\nI don't have permission to ban that member."
                    ),
                    accent_color=discord.Color(config.PASTEL_PEACH),
                )
                await interaction.response.send_message(view=_cv2(err), ephemeral=True)

        await self._send_confirm(ctx, loader, "Ban", target, reason, do_ban)

    @commands.hybrid_command(name="kick", description="Kick a member from the server")
    @app_commands.describe(target="Member to kick", reason="Reason for the kick")
    @commands.guild_only()
    @commands.has_permissions(kick_members=True)
    async def kick(
        self,
        ctx: commands.Context,
        target: discord.Member,
        *,
        reason: str = "No reason provided",
    ) -> None:
        loader = self._loader()

        async def do_kick(interaction: discord.Interaction) -> None:
            assert ctx.guild
            try:
                await target.kick(reason=f"[MochiMe] {reason} | Mod: {ctx.author}")
                await database.log_moderation(
                    str(ctx.guild.id), str(ctx.author.id), str(target.id), "kick", reason
                )
                success = _success_container(loader, "Kick", target, reason, ctx.author)
                await interaction.response.send_message(view=_cv2(success), ephemeral=True)
            except discord.Forbidden:
                cross = loader.get("cross")
                err = discord.ui.Container(
                    discord.ui.TextDisplay(
                        f"## {cross} Failed\nI don't have permission to kick that member."
                    ),
                    accent_color=discord.Color(config.PASTEL_PEACH),
                )
                await interaction.response.send_message(view=_cv2(err), ephemeral=True)

        await self._send_confirm(ctx, loader, "Kick", target, reason, do_kick)

    @commands.hybrid_command(name="mute", description="Timeout a member (up to 28 days)")
    @app_commands.describe(
        target="Member to mute",
        duration="Duration in minutes (default 10)",
        reason="Reason for the mute",
    )
    @commands.guild_only()
    @commands.has_permissions(moderate_members=True)
    async def mute(
        self,
        ctx: commands.Context,
        target: discord.Member,
        duration: int = 10,
        *,
        reason: str = "No reason provided",
    ) -> None:
        loader = self._loader()

        async def do_mute(interaction: discord.Interaction) -> None:
            assert ctx.guild
            try:
                until = discord.utils.utcnow() + datetime.timedelta(minutes=duration)
                await target.timeout(until, reason=f"[MochiMe] {reason} | Mod: {ctx.author}")
                await database.log_moderation(
                    str(ctx.guild.id), str(ctx.author.id), str(target.id),
                    f"mute:{duration}m", reason,
                )
                check = loader.get("check")
                shield = loader.get("shield")
                success = discord.ui.Container(
                    discord.ui.TextDisplay(
                        f"## {shield} Mute Successful\n\n"
                        f"{check} **Target:** {target.mention}\n"
                        f"{check} **Duration:** `{duration}` minutes\n"
                        f"{check} **Reason:** {reason}\n"
                        f"{check} **Ends:** <t:{int(until.timestamp())}:R>"
                    ),
                    accent_color=discord.Color(config.PASTEL_GREEN),
                )
                await interaction.response.send_message(view=_cv2(success), ephemeral=True)
            except discord.Forbidden:
                cross = loader.get("cross")
                err = discord.ui.Container(
                    discord.ui.TextDisplay(
                        f"## {cross} Failed\nI can't timeout that member."
                    ),
                    accent_color=discord.Color(config.PASTEL_PEACH),
                )
                await interaction.response.send_message(view=_cv2(err), ephemeral=True)

        await self._send_confirm(ctx, loader, f"Mute ({duration}m)", target, reason, do_mute)

    @commands.hybrid_command(name="warn", description="Warn a member")
    @app_commands.describe(target="Member to warn", reason="Reason for the warning")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def warn(
        self,
        ctx: commands.Context,
        target: discord.Member,
        *,
        reason: str = "No reason provided",
    ) -> None:
        loader = self._loader()

        async def do_warn(interaction: discord.Interaction) -> None:
            assert ctx.guild
            await database.log_moderation(
                str(ctx.guild.id), str(ctx.author.id), str(target.id), "warn", reason
            )
            warning = loader.get("warning")
            ribbon = loader.get("ribbon")
            success = discord.ui.Container(
                discord.ui.TextDisplay(
                    f"## {warning} Warning Issued\n\n"
                    f"{ribbon} **Target:** {target.mention}\n"
                    f"{ribbon} **Reason:** {reason}\n"
                    f"{ribbon} **Moderator:** {ctx.author.mention}\n\n"
                    "*This warning has been logged.*"
                ),
                accent_color=discord.Color(config.PASTEL_YELLOW),
            )
            try:
                dm_container = discord.ui.Container(
                    discord.ui.TextDisplay(
                        f"## {warning} You received a warning\n\n"
                        f"**Server:** {ctx.guild.name}\n"
                        f"**Reason:** {reason}"
                    ),
                    accent_color=discord.Color(config.PASTEL_YELLOW),
                )
                await target.send(view=_cv2(dm_container))
            except discord.Forbidden:
                pass
            await interaction.response.send_message(view=_cv2(success), ephemeral=True)

        await self._send_confirm(ctx, loader, "Warn", target, reason, do_warn)

    @ban.error
    @kick.error
    @mute.error
    @warn.error
    async def mod_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        loader = self._loader()
        cross = loader.get("cross")

        if isinstance(error, commands.MissingPermissions):
            perm = error.missing_permissions[0].replace("_", " ").title()
            container = _missing_perm_container(loader, perm)
        elif isinstance(error, commands.MissingRequiredArgument):
            container = discord.ui.Container(
                discord.ui.TextDisplay(
                    f"## {cross} Missing Argument\n`{error.param.name}` is required."
                ),
                accent_color=discord.Color(config.PASTEL_PEACH),
            )
        elif isinstance(error, commands.BadArgument):
            container = discord.ui.Container(
                discord.ui.TextDisplay(
                    f"## {cross} Bad Argument\nCouldn't find that member."
                ),
                accent_color=discord.Color(config.PASTEL_PEACH),
            )
        else:
            return

        await ctx.send(view=_cv2(container))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))
