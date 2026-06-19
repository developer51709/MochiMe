from __future__ import annotations

import math
import random
import time

import discord
from discord import app_commands
from discord.ext import commands

import config
import database
from cogs.emoji_loader import EmojiLoader

XP_MIN = 15
XP_MAX = 25
XP_COOLDOWN = 60.0  # seconds between XP gains per user per guild

RANK_MEDALS = ["🥇", "🥈", "🥉"]


def _level_from_xp(xp: int) -> int:
    return int(math.isqrt(xp // 100))


def _xp_for_level(level: int) -> int:
    return level * level * 100


def _progress_bar(filled: int, total: int, length: int = 12) -> str:
    if total == 0:
        frac = 0.0
    else:
        frac = min(filled / total, 1.0)
    n = round(frac * length)
    return "▓" * n + "░" * (length - n)


def _cv2(*items: discord.ui.Component) -> discord.ui.LayoutView:
    lv = discord.ui.LayoutView()
    for item in items:
        lv.add_item(item)
    return lv


class Levels(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # (user_id, guild_id) → unix timestamp of last XP gain
        self._cooldowns: dict[tuple[str, str], float] = {}

    def _loader(self) -> EmojiLoader:
        cog = self.bot.get_cog("EmojiLoader")
        assert isinstance(cog, EmojiLoader)
        return cog

    # ── XP listener ───────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return
        if not message.content and not message.attachments:
            return

        uid = str(message.author.id)
        gid = str(message.guild.id)
        key = (uid, gid)
        now = time.monotonic()

        if now - self._cooldowns.get(key, 0) < XP_COOLDOWN:
            return

        self._cooldowns[key] = now
        xp_gain = random.randint(XP_MIN, XP_MAX)
        new_xp, new_level, leveled_up = await database.add_user_xp(uid, gid, xp_gain)

        if leveled_up and new_level > 0:
            await self._send_levelup(message, new_level, new_xp)

    async def _send_levelup(
        self,
        message: discord.Message,
        level: int,
        xp: int,
    ) -> None:
        loader = self._loader()
        confetti = loader.get("confetti")
        level_up = loader.get("level_up")
        sparkle = loader.get("sparkle")
        ribbon = loader.get("ribbon")

        xp_next = _xp_for_level(level + 1)

        container = discord.ui.Container(
            discord.ui.Section(
                discord.ui.TextDisplay(
                    f"## {confetti} Level up!\n\n"
                    f"{message.author.mention} just reached **Level {level}**! {level_up}\n\n"
                    f"{ribbon} Keep chatting to keep climbing~ {sparkle}"
                ),
                accessory=discord.ui.Thumbnail(
                    media=discord.UnfurledMediaItem(
                        url=str(message.author.display_avatar.url)
                    )
                ),
            ),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay(
                f"-# Next level at **{xp_next:,} XP** — you have **{xp:,} XP** now"
            ),
            accent_color=discord.Color(config.PASTEL_YELLOW),
        )
        try:
            await message.channel.send(view=_cv2(container))
        except discord.HTTPException:
            pass

    # ── /rank ──────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="rank", description="See your XP rank card 🌸")
    @app_commands.describe(member="Whose rank to check (default: yourself)")
    @commands.guild_only()
    async def rank(
        self, ctx: commands.Context, member: discord.Member | None = None
    ) -> None:
        target = member or ctx.author
        assert ctx.guild is not None

        loader = self._loader()
        bolt = loader.get("bolt")
        trophy = loader.get("trophy")
        sparkle = loader.get("sparkle")
        ribbon = loader.get("ribbon")
        rank_e = loader.get("rank")
        chart = loader.get("chart")

        uid = str(target.id)
        gid = str(ctx.guild.id)

        row = await database.get_user_level(uid, gid)
        xp = row["xp"] if row else 0
        level = row["level"] if row else 0
        messages = row["messages"] if row else 0
        server_rank = await database.get_user_rank(uid, gid)

        xp_current_level = _xp_for_level(level)
        xp_next_level = _xp_for_level(level + 1)
        xp_in_level = xp - xp_current_level
        xp_needed = xp_next_level - xp_current_level
        bar = _progress_bar(xp_in_level, xp_needed)

        container = discord.ui.Container(
            discord.ui.Section(
                discord.ui.TextDisplay(
                    f"## {rank_e} {target.display_name}'s Rank\n\n"
                    f"{trophy} **Level:** `{level}`\n"
                    f"{bolt} **Total XP:** `{xp:,}`\n"
                    f"{chart} **Messages:** `{messages:,}`\n"
                    f"{sparkle} **Server Rank:** `#{server_rank}`\n\n"
                    f"**Progress to Level {level + 1}:**\n"
                    f"{bar}  `{xp_in_level:,} / {xp_needed:,} XP`"
                ),
                accessory=discord.ui.Thumbnail(
                    media=discord.UnfurledMediaItem(
                        url=str(target.display_avatar.url)
                    )
                ),
            ),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay(
                f"-# {ribbon} {ctx.guild.name} leaderboard  ·  use `/leaderboard` to see the top 10"
            ),
            accent_color=discord.Color(config.PASTEL_PURPLE),
        )
        await ctx.send(view=_cv2(container))

    # ── /leaderboard ───────────────────────────────────────────────────────────

    @commands.hybrid_command(
        name="leaderboard", aliases=["lb"], description="Top 10 XP leaderboard for this server 🏆"
    )
    @commands.guild_only()
    async def leaderboard(self, ctx: commands.Context) -> None:
        assert ctx.guild is not None

        loader = self._loader()
        trophy = loader.get("trophy")
        sparkle = loader.get("sparkle")
        ribbon = loader.get("ribbon")

        rows = await database.get_guild_leaderboard(str(ctx.guild.id), limit=10)

        if not rows:
            container = discord.ui.Container(
                discord.ui.TextDisplay(
                    f"## {trophy} Leaderboard\n\n"
                    "No one has earned XP yet~ Start chatting to climb the ranks! 🌸"
                ),
                accent_color=discord.Color(config.PASTEL_YELLOW),
            )
            await ctx.send(view=_cv2(container))
            return

        lines: list[str] = []
        for i, row in enumerate(rows):
            medal = RANK_MEDALS[i] if i < 3 else f"`{i + 1}.`"
            try:
                user = self.bot.get_user(int(row["user_id"])) or await self.bot.fetch_user(
                    int(row["user_id"])
                )
                name = user.display_name
            except Exception:
                name = f"User {row['user_id']}"
            lines.append(
                f"{medal} **{name}** — Level `{row['level']}` · `{row['xp']:,} XP`"
            )

        container = discord.ui.Container(
            discord.ui.TextDisplay(
                f"## {trophy} {ctx.guild.name} Leaderboard\n\n" + "\n".join(lines)
            ),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay(
                f"-# {sparkle} Earn XP by chatting · use `/rank` to see your full card"
            ),
            accent_color=discord.Color(config.PASTEL_YELLOW),
        )
        await ctx.send(view=_cv2(container))

    async def cog_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        original = error
        while hasattr(original, "original"):
            original = original.original  # type: ignore[union-attr]
        if isinstance(original, discord.NotFound) and getattr(original, "code", None) == 10062:
            return

        loader = self._loader()
        cross = loader.get("cross")
        container = discord.ui.Container(
            discord.ui.TextDisplay(
                f"## {cross} Oops!\nSomething went wrong~ please try again 🌸"
            ),
            accent_color=discord.Color(config.PASTEL_PEACH),
        )
        lv = discord.ui.LayoutView()
        lv.add_item(container)
        try:
            await ctx.send(view=lv, ephemeral=True)
        except discord.HTTPException:
            pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Levels(bot))
