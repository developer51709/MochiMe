from __future__ import annotations

import datetime

import discord
from discord import app_commands
from discord.ext import commands

import config
import database
from cogs.emoji_loader import EmojiLoader


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


class ConfirmView(discord.ui.View):
    def __init__(
        self,
        emoji_loader: EmojiLoader,
        action: str,
        target: discord.Member,
        reason: str,
        callback,
    ) -> None:
        super().__init__(timeout=60)
        self.emoji_loader = emoji_loader
        self.action = action
        self.target = target
        self.reason = reason
        self._callback = callback
        self.confirmed = False

    def confirmation_components(self) -> list[discord.ui.Component]:
        warning = self.emoji_loader.get("warning")
        shield = self.emoji_loader.get("shield")
        cross = self.emoji_loader.get("cross")

        container = discord.ui.Container(
            discord.ui.TextDisplay(
                f"## {warning} Confirm {self.action}\n\n"
                f"{shield} **Target:** {self.target.mention} (`{self.target}`)\n"
                f"{shield} **Reason:** {self.reason}\n\n"
                "Are you sure you want to do this?"
            ),
            discord.ui.Separator(),
            discord.ui.ActionRow(
                discord.ui.Button(
                    label=f"Confirm {self.action}",
                    style=discord.ButtonStyle.danger,
                    custom_id="mod_confirm",
                ),
                discord.ui.Button(
                    label="Cancel",
                    style=discord.ButtonStyle.secondary,
                    custom_id="mod_cancel",
                ),
            ),
            accent_color=discord.Color(config.PASTEL_PEACH),
        )
        return [container]

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger, custom_id="mod_confirm")
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.confirmed = True
        self.stop()
        await self._callback(interaction)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, custom_id="mod_cancel")
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        cross = self.emoji_loader.get("cross")
        self.stop()
        cancel_container = discord.ui.Container(
            discord.ui.TextDisplay(f"## {cross} Cancelled\nNo action was taken."),
            accent_color=discord.Color(config.PASTEL_BLUE),
        )
        await interaction.response.edit_message(
            components=[cancel_container],
        )


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _loader(self) -> EmojiLoader:
        cog = self.bot.get_cog("EmojiLoader")
        assert isinstance(cog, EmojiLoader)
        return cog

    async def _send_cv2(
        self,
        ctx: commands.Context,
        components: list[discord.ui.Component],
        view: discord.ui.View | None = None,
    ) -> discord.Message:
        return await ctx.send(
            components=components,
            view=view,
            flags=discord.MessageFlags(components_v2=True),
        )

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
                await interaction.response.edit_message(components=[success])
            except discord.Forbidden:
                cross = loader.get("cross")
                err = discord.ui.Container(
                    discord.ui.TextDisplay(
                        f"## {cross} Failed\nI don't have permission to ban that member."
                    ),
                    accent_color=discord.Color(config.PASTEL_PEACH),
                )
                await interaction.response.edit_message(components=[err])

        view = ConfirmView(loader, "Ban", target, reason, do_ban)
        await self._send_cv2(ctx, view.confirmation_components(), view)

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
                await interaction.response.edit_message(components=[success])
            except discord.Forbidden:
                cross = loader.get("cross")
                err = discord.ui.Container(
                    discord.ui.TextDisplay(
                        f"## {cross} Failed\nI don't have permission to kick that member."
                    ),
                    accent_color=discord.Color(config.PASTEL_PEACH),
                )
                await interaction.response.edit_message(components=[err])

        view = ConfirmView(loader, "Kick", target, reason, do_kick)
        await self._send_cv2(ctx, view.confirmation_components(), view)

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
                await interaction.response.edit_message(components=[success])
            except discord.Forbidden:
                cross = loader.get("cross")
                err = discord.ui.Container(
                    discord.ui.TextDisplay(
                        f"## {cross} Failed\nI can't timeout that member."
                    ),
                    accent_color=discord.Color(config.PASTEL_PEACH),
                )
                await interaction.response.edit_message(components=[err])

        view = ConfirmView(loader, f"Mute ({duration}m)", target, reason, do_mute)
        await self._send_cv2(ctx, view.confirmation_components(), view)

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
                await target.send(
                    components=[dm_container],
                    flags=discord.MessageFlags(components_v2=True),
                )
            except discord.Forbidden:
                pass
            await interaction.response.edit_message(components=[success])

        view = ConfirmView(loader, "Warn", target, reason, do_warn)
        await self._send_cv2(ctx, view.confirmation_components(), view)

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

        await ctx.send(
            components=[container],
            flags=discord.MessageFlags(components_v2=True),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))
