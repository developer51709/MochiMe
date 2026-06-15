from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config
import database
from cogs.emoji_loader import EmojiLoader


COSMETICS: dict[str, dict[str, str]] = {
    "sakura": {"name": "Sakura Bloom", "desc": "Soft pink petals drift around you", "emoji": "flower"},
    "moonlight": {"name": "Moonlight Glow", "desc": "A gentle silver aura surrounds you", "emoji": "moon"},
    "ribbon": {"name": "Ribbon Trim", "desc": "Cute ribbons accent your display name", "emoji": "ribbon"},
    "star": {"name": "Stardust", "desc": "A faint sparkle follows your messages", "emoji": "star"},
}

PETS: dict[str, dict[str, str]] = {
    "mochi_cat": {"name": "Mochi Cat", "desc": "A soft, round little cat", "emoji": "smiley"},
    "cloud_bunny": {"name": "Cloud Bunny", "desc": "A fluffy cloud-white bunny", "emoji": "sparkle"},
    "moon_fox": {"name": "Moon Fox", "desc": "A silvery fox that glows at night", "emoji": "moon"},
}


class ServerFeatures(commands.Cog):
    """Features that unlock when MochiMe is added to a server."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _loader(self) -> EmojiLoader:
        cog = self.bot.get_cog("EmojiLoader")
        assert isinstance(cog, EmojiLoader)
        return cog

    def _require_guild(self, ctx: commands.Context) -> bool:
        return ctx.guild is not None

    @commands.hybrid_command(name="server", description="Show MochiMe server panel")
    @commands.guild_only()
    async def server_panel(self, ctx: commands.Context) -> None:
        loader = self._loader()
        guild = ctx.guild
        assert guild is not None

        settings = await database.get_server_settings(str(guild.id))
        sparkle = loader.get("sparkle")
        star = loader.get("star")
        ribbon = loader.get("ribbon")
        shield = loader.get("shield")
        flower = loader.get("flower")

        rp_channel = f"<#{settings['rp_channel_id']}>" if settings and settings["rp_channel_id"] else "Not set"
        log_channel = f"<#{settings['log_channel_id']}>" if settings and settings["log_channel_id"] else "Not set"
        mod_role = f"<@&{settings['mod_role_id']}>" if settings and settings["mod_role_id"] else "Not set"

        container = discord.ui.Container(
            discord.ui.TextDisplay(
                f"## {sparkle} {guild.name} — Mochi Panel\n\n"
                f"{star} **Members:** `{guild.member_count}`\n"
                f"{flower} **RP Channel:** {rp_channel}\n"
                f"{shield} **Log Channel:** {log_channel}\n"
                f"{ribbon} **Mod Role:** {mod_role}\n\n"
                "*Use `/settings` to configure these options.*"
            ),
            discord.ui.Separator(divider=True),
            discord.ui.TextDisplay(
                f"## {ribbon} Unlocked Features\n"
                f"{flower} RP Rooms\n"
                f"{sparkle} Shared Cosmetics\n"
                f"{star} Server-Bound Pets\n"
                f"{shield} Moderation Panels\n"
                f"{ribbon} Server Settings"
            ),
            accent_color=discord.Color(config.PASTEL_BLUE),
        )
        await ctx.send(
            components=[container],
            flags=discord.MessageFlags(is_components_v2=True),
        )

    @commands.hybrid_command(name="settings", description="Configure MochiMe for this server")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def settings(self, ctx: commands.Context) -> None:
        loader = self._loader()
        guild = ctx.guild
        assert guild is not None

        sparkle = loader.get("sparkle")
        ribbon = loader.get("ribbon")

        container = discord.ui.Container(
            discord.ui.TextDisplay(
                f"## {sparkle} Server Settings\n\n"
                f"{ribbon} Use the options below to configure MochiMe.\n\n"
                "**Available settings:**\n"
                "• `setrp #channel` — Set the RP channel\n"
                "• `setlog #channel` — Set the moderation log channel\n"
                "• `setmodrole @role` — Set the moderator role"
            ),
            accent_color=discord.Color(config.PASTEL_PURPLE),
        )
        await ctx.send(
            components=[container],
            flags=discord.MessageFlags(is_components_v2=True),
        )

    @commands.hybrid_command(name="setrp", description="Set the RP channel")
    @app_commands.describe(channel="The channel to designate as RP room")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def set_rp_channel(
        self, ctx: commands.Context, channel: discord.TextChannel
    ) -> None:
        loader = self._loader()
        assert ctx.guild
        await database.upsert_server_settings(str(ctx.guild.id), rp_channel_id=str(channel.id))
        flower = loader.get("flower")
        check = loader.get("check")
        container = discord.ui.Container(
            discord.ui.TextDisplay(
                f"## {flower} RP Channel Set!\n{check} {channel.mention} is now the RP room."
            ),
            accent_color=discord.Color(config.PASTEL_GREEN),
        )
        await ctx.send(
            components=[container],
            flags=discord.MessageFlags(is_components_v2=True),
        )

    @commands.hybrid_command(name="setlog", description="Set the moderation log channel")
    @app_commands.describe(channel="The channel for moderation logs")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def set_log_channel(
        self, ctx: commands.Context, channel: discord.TextChannel
    ) -> None:
        loader = self._loader()
        assert ctx.guild
        await database.upsert_server_settings(str(ctx.guild.id), log_channel_id=str(channel.id))
        shield = loader.get("shield")
        check = loader.get("check")
        container = discord.ui.Container(
            discord.ui.TextDisplay(
                f"## {shield} Log Channel Set!\n{check} {channel.mention} is now the mod log."
            ),
            accent_color=discord.Color(config.PASTEL_GREEN),
        )
        await ctx.send(
            components=[container],
            flags=discord.MessageFlags(is_components_v2=True),
        )

    @commands.hybrid_command(name="setmodrole", description="Set the moderator role")
    @app_commands.describe(role="The role to designate as moderators")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def set_mod_role(self, ctx: commands.Context, role: discord.Role) -> None:
        loader = self._loader()
        assert ctx.guild
        await database.upsert_server_settings(str(ctx.guild.id), mod_role_id=str(role.id))
        shield = loader.get("shield")
        check = loader.get("check")
        container = discord.ui.Container(
            discord.ui.TextDisplay(
                f"## {shield} Mod Role Set!\n{check} {role.mention} is now the moderator role."
            ),
            accent_color=discord.Color(config.PASTEL_GREEN),
        )
        await ctx.send(
            components=[container],
            flags=discord.MessageFlags(is_components_v2=True),
        )

    @commands.hybrid_command(name="cosmetics", description="Browse server cosmetics")
    @commands.guild_only()
    async def cosmetics(self, ctx: commands.Context) -> None:
        loader = self._loader()
        ribbon = loader.get("ribbon")
        sparkle = loader.get("sparkle")

        lines = [f"## {ribbon} Server Cosmetics\n*Shared cosmetics for this server*\n"]
        for key, cos in COSMETICS.items():
            icon = loader.get(cos["emoji"])
            lines.append(f"{icon} **{cos['name']}** — {cos['desc']}")

        lines.append(f"\n{sparkle} *More cosmetics coming soon!*")

        container = discord.ui.Container(
            discord.ui.TextDisplay("\n".join(lines)),
            accent_color=discord.Color(config.PASTEL_PEACH),
        )
        await ctx.send(
            components=[container],
            flags=discord.MessageFlags(is_components_v2=True),
        )

    @commands.hybrid_command(name="pets", description="Browse server-bound pets")
    @commands.guild_only()
    async def pets(self, ctx: commands.Context) -> None:
        loader = self._loader()
        flower = loader.get("flower")
        sparkle = loader.get("sparkle")

        lines = [f"## {flower} Server Pets\n*Adorable server-bound companions*\n"]
        for key, pet in PETS.items():
            icon = loader.get(pet["emoji"])
            lines.append(f"{icon} **{pet['name']}** — {pet['desc']}")

        lines.append(f"\n{sparkle} *Pets are server-bound and unique to each server!*")

        container = discord.ui.Container(
            discord.ui.TextDisplay("\n".join(lines)),
            accent_color=discord.Color(config.PASTEL_GREEN),
        )
        await ctx.send(
            components=[container],
            flags=discord.MessageFlags(is_components_v2=True),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ServerFeatures(bot))
