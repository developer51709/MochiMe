from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config
import database
from cogs.emoji_loader import EmojiLoader


class Application(commands.Cog):
    """User-installable application commands — work anywhere the user has the app installed."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._ctx_menus: list[app_commands.ContextMenu] = []
        self._register_context_menus()

    def _loader(self) -> EmojiLoader:
        cog = self.bot.get_cog("EmojiLoader")
        assert isinstance(cog, EmojiLoader)
        return cog

    def _register_context_menus(self) -> None:
        hug_menu = app_commands.ContextMenu(name="🫂 Hug", callback=self._ctx_hug)
        pat_menu = app_commands.ContextMenu(name="🌸 Pat", callback=self._ctx_pat)
        profile_menu = app_commands.ContextMenu(name="✨ MochiMe Profile", callback=self._ctx_profile)

        for menu in (hug_menu, pat_menu, profile_menu):
            self.bot.tree.add_command(menu)
            self._ctx_menus.append(menu)

    async def cog_unload(self) -> None:
        for menu in self._ctx_menus:
            self.bot.tree.remove_command(menu.name, type=menu.type)

    async def _ctx_hug(self, interaction: discord.Interaction, member: discord.Member) -> None:
        loader = self._loader()
        hug_e = loader.get("hug")
        sparkle = loader.get("sparkle")

        container = discord.ui.Container(
            discord.ui.TextDisplay(
                f"## {hug_e} Hug! {sparkle}\n\n"
                f"{interaction.user.mention} wraps their arms around {member.mention} "
                "in a warm, cozy hug! 💕"
            ),
            accent_color=discord.Color(config.PASTEL_PINK),
        )
        await interaction.response.send_message(
            components=[container],
            flags=discord.MessageFlags(is_components_v2=True),
        )
        await database.log_rp(str(interaction.user.id), "hug", str(member.id))

    async def _ctx_pat(self, interaction: discord.Interaction, member: discord.Member) -> None:
        loader = self._loader()
        pat_e = loader.get("pat")
        flower = loader.get("flower")

        container = discord.ui.Container(
            discord.ui.TextDisplay(
                f"## {pat_e} Pat! {flower}\n\n"
                f"{interaction.user.mention} gently pats {member.mention} on the head~ "
                "*pat pat* 🌸"
            ),
            accent_color=discord.Color(config.PASTEL_PURPLE),
        )
        await interaction.response.send_message(
            components=[container],
            flags=discord.MessageFlags(is_components_v2=True),
        )
        await database.log_rp(str(interaction.user.id), "pat", str(member.id))

    async def _ctx_profile(
        self, interaction: discord.Interaction, member: discord.Member
    ) -> None:
        loader = self._loader()
        sparkle = loader.get("sparkle")
        star = loader.get("star")
        heart = loader.get("heart")
        ribbon = loader.get("ribbon")

        db = await database.get_db()
        async with db.execute(
            "SELECT action, COUNT(*) as cnt FROM rp_stats WHERE user_id = ? GROUP BY action",
            (str(member.id),),
        ) as cur:
            stats = {row["action"]: row["cnt"] async for row in cur}

        lines = [f"## {sparkle} {member.display_name}'s Mochi Profile\n"]
        if stats:
            lines.append(f"{ribbon} **RP Stats**")
            for action, cnt in stats.items():
                icon = loader.get(action)
                lines.append(f"{icon} **{action.title()}:** `{cnt}`")
        else:
            lines.append(f"{heart} *No RP stats yet — try `mochi hug @someone`!*")

        lines.append(f"\n{star} **Joined:** <t:{int(member.joined_at.timestamp())}:R>" if member.joined_at else "")

        is_in_guild = interaction.guild is not None
        if not is_in_guild:
            lines.append(
                f"\n{ribbon} *Some features require MochiMe to be added to a server.*"
            )

        container = discord.ui.Container(
            discord.ui.TextDisplay("\n".join(lines)),
            discord.ui.Separator(divider=True),
            discord.ui.ActionRow(
                discord.ui.Button(
                    label="Add MochiMe to Your Server",
                    style=discord.ButtonStyle.link,
                    url=f"https://discord.com/oauth2/authorize?client_id={self.bot.application_id}&scope=bot+applications.commands",
                ) if not is_in_guild else discord.ui.Button(
                    label="Bot is already here 🌸",
                    style=discord.ButtonStyle.secondary,
                    disabled=True,
                    custom_id="already_here",
                ),
            ),
            accent_color=discord.Color(config.PASTEL_PURPLE),
        )
        await interaction.response.send_message(
            components=[container],
            flags=discord.MessageFlags(is_components_v2=True),
            ephemeral=True,
        )

    @commands.hybrid_command(name="user", description="Show a user's MochiMe profile")
    @app_commands.describe(member="The user to look up (defaults to yourself)")
    async def user_profile(
        self, ctx: commands.Context, member: discord.Member | None = None
    ) -> None:
        target = member or ctx.author
        if not isinstance(target, discord.Member):
            target = ctx.author

        loader = self._loader()
        sparkle = loader.get("sparkle")
        star = loader.get("star")
        ribbon = loader.get("ribbon")
        heart = loader.get("heart")

        db = await database.get_db()
        async with db.execute(
            "SELECT action, COUNT(*) as cnt FROM rp_stats WHERE user_id = ? GROUP BY action",
            (str(target.id),),
        ) as cur:
            stats = {row["action"]: row["cnt"] async for row in cur}

        lines = [f"## {sparkle} {target.display_name}\n"]
        if stats:
            lines.append(f"{ribbon} **RP Stats**")
            for action, cnt in stats.items():
                icon = loader.get(action)
                lines.append(f"{icon} `{action.title()}` — **{cnt}** times")
        else:
            lines.append(f"{heart} *No RP actions yet!*")

        if isinstance(target, discord.Member) and target.joined_at:
            lines.append(f"\n{star} **Joined:** <t:{int(target.joined_at.timestamp())}:R>")

        container = discord.ui.Container(
            discord.ui.TextDisplay("\n".join(lines)),
            accent_color=discord.Color(config.PASTEL_PURPLE),
        )
        await ctx.send(
            components=[container],
            flags=discord.MessageFlags(is_components_v2=True),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Application(bot))
