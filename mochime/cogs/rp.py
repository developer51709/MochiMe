from __future__ import annotations

import random

import discord
from discord import app_commands
from discord.ext import commands

import config
import database
from cogs.emoji_loader import EmojiLoader


RP_LINES: dict[str, list[str]] = {
    "hug": [
        "{author} wraps their arms around {target} in a warm, cozy hug! 🫂",
        "{author} rushes over and squeezes {target} tight~ so soft!",
        "A big fluffy hug from {author} lands on {target}! 💕",
    ],
    "pat": [
        "{author} gently pats {target} on the head~ *pat pat* 🌸",
        "{author} gives {target} the softest headpats ever! ✨",
        "*pat pat* — {author} tenderly pats {target}~ you did well!",
    ],
    "kiss": [
        "{author} places a sweet little kiss on {target}'s cheek 💋",
        "Mwah! {author} gives {target} the softest kiss~ 🩷",
        "{author} sneaks a gentle kiss onto {target}'s forehead~ ✨",
    ],
    "bonk": [
        "{author} gently bonks {target} on the head! *bonk* 🔨",
        "Bop! {author} gives {target} a light bonk~ behave! 💫",
        "{author} reaches over and— *bonk* — right on {target}'s head!",
    ],
    "blush": [
        "{author} turns bright red and hides their face~ 😳",
        "O-oh... {author} is blushing so hard right now! 🌸",
        "{author}'s cheeks turn the softest shade of pink~ 💕",
    ],
    "cuddle": [
        "{author} curls up and cuddles with {target}~ so warm! 🥰",
        "Soft and cozy — {author} pulls {target} in for a long cuddle~ 💤",
        "{author} snuggles right up to {target}~ 🌙",
    ],
    "poke": [
        "{author} pokes {target}~ hey, are you there? 👉",
        "*poke poke* — {author} nudges {target} playfully!",
        "{author} gives {target} a curious little poke~ 🌸",
    ],
}

RP_COLORS: dict[str, int] = {
    "hug": config.PASTEL_PINK,
    "pat": config.PASTEL_PURPLE,
    "kiss": config.PASTEL_PINK,
    "bonk": config.PASTEL_PEACH,
    "blush": config.PASTEL_PINK,
    "cuddle": config.PASTEL_PURPLE,
    "poke": config.PASTEL_BLUE,
}

RP_EMOJI_KEYS: dict[str, str] = {
    "hug": "hug",
    "pat": "pat",
    "kiss": "kiss",
    "bonk": "bonk",
    "blush": "blush",
    "cuddle": "cuddle",
    "poke": "poke",
}


def _build_rp_container(
    action: str,
    author: discord.Member | discord.User,
    target: discord.Member | discord.User | None,
    emoji_loader: EmojiLoader,
) -> discord.ui.Container:
    icon = emoji_loader.get(RP_EMOJI_KEYS[action])
    sparkle = emoji_loader.get("sparkle")
    ribbon = emoji_loader.get("ribbon")
    color = RP_COLORS.get(action, config.PASTEL_PINK)

    lines = RP_LINES[action]
    text = random.choice(lines).format(
        author=author.mention,
        target=target.mention if target else "the air",
    )

    footer = f"{ribbon} *+1 {action} added to {author.display_name}'s stats!*"

    return discord.ui.Container(
        discord.ui.TextDisplay(f"## {icon} {action.title()} {sparkle}\n\n{text}\n\n{footer}"),
        accent_color=discord.Color(color),
    )


class RP(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _loader(self) -> EmojiLoader:
        cog = self.bot.get_cog("EmojiLoader")
        assert isinstance(cog, EmojiLoader)
        return cog

    async def _send_rp(
        self,
        ctx: commands.Context,
        action: str,
        target: discord.Member | None = None,
    ) -> None:
        loader = self._loader()
        container = _build_rp_container(action, ctx.author, target, loader)
        await database.log_rp(
            str(ctx.author.id),
            action,
            str(target.id) if target else None,
            str(ctx.guild.id) if ctx.guild else None,
        )
        await ctx.send(
            components=[container],
            flags=discord.MessageFlags(is_components_v2=True),
        )

    async def _send_rp_interaction(
        self,
        interaction: discord.Interaction,
        action: str,
        target: discord.Member | None = None,
    ) -> None:
        loader = self._loader()
        container = _build_rp_container(action, interaction.user, target, loader)
        await database.log_rp(
            str(interaction.user.id),
            action,
            str(target.id) if target else None,
            str(interaction.guild_id) if interaction.guild_id else None,
        )
        await interaction.response.send_message(
            components=[container],
            flags=discord.MessageFlags(is_components_v2=True),
        )

    @commands.hybrid_command(name="hug", description="Give someone a warm hug! 🫂")
    @app_commands.describe(target="Who to hug")
    async def hug(self, ctx: commands.Context, target: discord.Member | None = None) -> None:
        await self._send_rp(ctx, "hug", target)

    @commands.hybrid_command(name="pat", description="Pat someone on the head~ 🌸")
    @app_commands.describe(target="Who to pat")
    async def pat(self, ctx: commands.Context, target: discord.Member | None = None) -> None:
        await self._send_rp(ctx, "pat", target)

    @commands.hybrid_command(name="kiss", description="Give someone a sweet kiss 💋")
    @app_commands.describe(target="Who to kiss")
    async def kiss(self, ctx: commands.Context, target: discord.Member | None = None) -> None:
        await self._send_rp(ctx, "kiss", target)

    @commands.hybrid_command(name="bonk", description="Bonk someone on the head! 🔨")
    @app_commands.describe(target="Who to bonk")
    async def bonk(self, ctx: commands.Context, target: discord.Member | None = None) -> None:
        await self._send_rp(ctx, "bonk", target)

    @commands.hybrid_command(name="blush", description="Express your blush 😳")
    async def blush(self, ctx: commands.Context) -> None:
        await self._send_rp(ctx, "blush")

    @commands.hybrid_command(name="cuddle", description="Cuddle with someone 🥰")
    @app_commands.describe(target="Who to cuddle with")
    async def cuddle(self, ctx: commands.Context, target: discord.Member | None = None) -> None:
        await self._send_rp(ctx, "cuddle", target)

    @commands.hybrid_command(name="poke", description="Poke someone playfully 👉")
    @app_commands.describe(target="Who to poke")
    async def poke(self, ctx: commands.Context, target: discord.Member | None = None) -> None:
        await self._send_rp(ctx, "poke", target)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RP(bot))
