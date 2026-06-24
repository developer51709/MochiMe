from __future__ import annotations

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


class Application(commands.Cog):
    """User-installable app commands and additional context menus."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._ctx_menus: list[app_commands.ContextMenu] = []
        self._register_context_menus()

    def _loader(self) -> EmojiLoader:
        cog = self.bot.get_cog("EmojiLoader")
        assert isinstance(cog, EmojiLoader)
        return cog

    def _register_context_menus(self) -> None:
        menus = [
            app_commands.ContextMenu(name="✨ Mochi Profile",    callback=self._ctx_profile),
            app_commands.ContextMenu(name="📌 View RP Stats",    callback=self._ctx_rp_stats),
            app_commands.ContextMenu(name="🛡️ Mod History",     callback=self._ctx_mod_history),
        ]
        for menu in menus:
            self.bot.tree.add_command(menu)
            self._ctx_menus.append(menu)

    async def cog_unload(self) -> None:
        for menu in self._ctx_menus:
            self.bot.tree.remove_command(menu.name, type=menu.type)

    async def _ctx_profile(
        self, interaction: discord.Interaction, member: discord.Member
    ) -> None:
        loader = self._loader()
        sparkle = loader.get("sparkle")
        star = loader.get("star")
        ribbon = loader.get("ribbon")
        heart = loader.get("heart")
        flower = loader.get("flower")

        db = await database.get_db()
        async with db.execute(
            "SELECT action, COUNT(*) as cnt FROM rp_stats WHERE user_id = ? GROUP BY action ORDER BY cnt DESC",
            (str(member.id),),
        ) as cur:
            stats = [(row["action"], row["cnt"]) async for row in cur]

        lines = [f"## {sparkle} {member.display_name}'s Profile\n"]
        if stats:
            lines.append(f"{ribbon} **RP Stats**")
            for action, cnt in stats:
                icon = loader.get(action)
                lines.append(f"  {icon} `{action.title()}` — **{cnt}**×")
        else:
            lines.append(f"{heart} *No RP stats yet!*")

        if member.joined_at:
            lines.append(f"\n{star} **Joined:** <t:{int(member.joined_at.timestamp())}:R>")
        lines.append(f"{flower} **Roles:** {len(member.roles) - 1}")

        is_in_guild = interaction.guild is not None
        invite_btn = discord.ui.Button(
            label="Add MochiMe to Your Server",
            style=discord.ButtonStyle.link,
            url=f"https://discord.com/oauth2/authorize?client_id={self.bot.application_id}&scope=bot+applications.commands",
        ) if not is_in_guild else discord.ui.Button(
            label="MochiMe is here 🌸",
            style=discord.ButtonStyle.secondary,
            disabled=True,
            custom_id="already_here",
        )

        container = discord.ui.Container(
            discord.ui.TextDisplay("\n".join(lines)),
            discord.ui.Separator(),
            discord.ui.ActionRow(invite_btn),
            accent_color=discord.Color(config.PASTEL_PURPLE),
        )
        await interaction.response.send_message(
            view=_cv2(container),
            ephemeral=True,
        )

    async def _ctx_rp_stats(
        self, interaction: discord.Interaction, member: discord.Member
    ) -> None:
        loader = self._loader()
        ribbon = loader.get("ribbon")
        heart = loader.get("heart")
        trophy = loader.get("trophy")
        sparkle = loader.get("sparkle")

        db = await database.get_db()

        async with db.execute(
            "SELECT action, COUNT(*) as cnt FROM rp_stats WHERE user_id = ? GROUP BY action ORDER BY cnt DESC",
            (str(member.id),),
        ) as cur:
            given = [(row["action"], row["cnt"]) async for row in cur]

        async with db.execute(
            "SELECT action, COUNT(*) as cnt FROM rp_stats WHERE target_id = ? GROUP BY action ORDER BY cnt DESC",
            (str(member.id),),
        ) as cur:
            received = [(row["action"], row["cnt"]) async for row in cur]

        lines = [f"## {ribbon} {member.display_name}'s RP Stats\n"]

        if given:
            lines.append(f"{trophy} **Given**")
            for action, cnt in given[:5]:
                icon = loader.get(action)
                lines.append(f"  {icon} `{action.title()}` — **{cnt}**×")
        else:
            lines.append(f"{heart} *No actions given yet!*")

        lines.append("")

        if received:
            lines.append(f"{sparkle} **Received**")
            for action, cnt in received[:5]:
                icon = loader.get(action)
                lines.append(f"  {icon} `{action.title()}` — **{cnt}**×")
        else:
            lines.append(f"{heart} *No actions received yet!*")

        container = discord.ui.Container(
            discord.ui.TextDisplay("\n".join(lines)),
            accent_color=discord.Color(config.PASTEL_PINK),
        )
        await interaction.response.send_message(
            view=_cv2(container),
            ephemeral=True,
        )

    async def _ctx_mod_history(
        self, interaction: discord.Interaction, member: discord.Member
    ) -> None:
        loader = self._loader()

        if interaction.guild and isinstance(interaction.user, discord.Member):
            if not interaction.user.guild_permissions.moderate_members:
                cross = loader.get("cross")
                container = discord.ui.Container(
                    discord.ui.TextDisplay(
                        f"## {cross} Access Denied\n"
                        "You need the **Moderate Members** permission to view mod history."
                    ),
                    accent_color=discord.Color(config.PASTEL_PEACH),
                )
                await interaction.response.send_message(
                    view=_cv2(container),
                    ephemeral=True,
                )
                return

        shield = loader.get("shield")
        warning = loader.get("warning")
        sparkle = loader.get("sparkle")

        db = await database.get_db()
        guild_id = str(interaction.guild_id) if interaction.guild_id else None

        query = (
            "SELECT action, reason, created_at FROM moderation_logs "
            "WHERE target_id = ?"
            + (" AND guild_id = ?" if guild_id else "")
            + " ORDER BY created_at DESC LIMIT 10"
        )
        params = (str(member.id), guild_id) if guild_id else (str(member.id),)

        async with db.execute(query, params) as cur:
            logs = [(row["action"], row["reason"], row["created_at"]) async for row in cur]

        lines = [f"## {shield} Mod History — {member.display_name}\n"]
        if logs:
            for action, reason, created_at in logs:
                icon = loader.get("warning") if action.startswith("warn") else loader.get("ban")
                lines.append(f"{icon} **{action.title()}** — {reason or 'No reason'} *(logged {created_at[:10]})*")
        else:
            lines.append(f"{sparkle} *No moderation history found.*")

        container = discord.ui.Container(
            discord.ui.TextDisplay("\n".join(lines)),
            accent_color=discord.Color(config.PASTEL_BLUE),
        )
        await interaction.response.send_message(
            view=_cv2(container),
            ephemeral=True,
        )

    @commands.hybrid_command(name="user", description="Show a user's MochiMe profile")
    @app_commands.describe(member="The user to look up (defaults to yourself)")
    async def user_profile(
        self, ctx: commands.Context, member: discord.Member | None = None
    ) -> None:
        await ctx.defer()
        target: discord.Member | discord.User = member or ctx.author
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
                lines.append(f"  {icon} `{action.title()}` — **{cnt}**×")
        else:
            lines.append(f"{heart} *No RP actions yet!*")

        if isinstance(target, discord.Member) and target.joined_at:
            lines.append(f"\n{star} **Joined:** <t:{int(target.joined_at.timestamp())}:R>")

        container = discord.ui.Container(
            discord.ui.TextDisplay("\n".join(lines)),
            accent_color=discord.Color(config.PASTEL_PURPLE),
        )
        await ctx.send(view=_cv2(container))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Application(bot))
