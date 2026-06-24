from __future__ import annotations

import random
import re

import discord
from discord import app_commands
from discord.ext import commands

import config
from cogs.emoji_loader import EmojiLoader

_8BALL_POSITIVE = [
    "It is certain~ ✨",
    "Without a doubt! 💕",
    "Most definitely! 🌸",
    "Signs point to yes! 🌟",
    "You can count on it! 🎀",
    "Absolutely, yes! 💗",
    "It is decidedly so~ 🌸",
    "As I see it, yes! ✨",
]

_8BALL_NEUTRAL = [
    "Ask again later~ 🌙",
    "Hmm, I'm not sure right now... 🤔",
    "Cannot predict right now~ 🌸",
    "My crystal ball is cloudy today... 🔮",
    "Concentrate and ask again~ ✨",
    "Reply hazy, try again~ 💭",
]

_8BALL_NEGATIVE = [
    "Don't count on it~ 🌸",
    "My sources say no... 💔",
    "Very doubtful~ 😔",
    "Outlook not so good... 🌧️",
    "The stars say no~ 🌙",
    "I don't think so... 🌸",
]

_COIN_SIDES = [
    ("Heads!", "🌕"),
    ("Tails!", "🌑"),
]

_DICE_RE = re.compile(r"^(\d+)?d(\d+)$", re.IGNORECASE)


def _cv2(*items: discord.ui.Component) -> discord.ui.LayoutView:
    lv = discord.ui.LayoutView()
    for item in items:
        lv.add_item(item)
    return lv


class Fun(commands.Cog):
    """Lighthearted fun commands for any server~ 🎀"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _loader(self) -> EmojiLoader:
        cog = self.bot.get_cog("EmojiLoader")
        assert isinstance(cog, EmojiLoader)
        return cog

    # ── /fun group ────────────────────────────────────────────────────────────

    @commands.hybrid_group(name="fun", description="Fun games and randomness~ 🎲", invoke_without_command=True)
    async def fun_group(self, ctx: commands.Context) -> None:
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    # ── /fun 8ball ────────────────────────────────────────────────────────────

    @fun_group.command(name="8ball", description="Ask the magic 8-ball a question 🔮")
    @app_commands.describe(question="Your question for the 8-ball")
    async def eight_ball(self, ctx: commands.Context, *, question: str) -> None:
        loader = self._loader()
        crystal = loader.get("crystal_ball")
        ribbon = loader.get("ribbon")
        sparkle = loader.get("sparkle")

        tier = random.randint(0, 2)
        if tier == 0:
            answer = random.choice(_8BALL_POSITIVE)
            color = config.PASTEL_GREEN
        elif tier == 1:
            answer = random.choice(_8BALL_NEUTRAL)
            color = config.PASTEL_YELLOW
        else:
            answer = random.choice(_8BALL_NEGATIVE)
            color = config.PASTEL_PEACH

        q_display = question if len(question) <= 200 else question[:200] + "…"

        container = discord.ui.Container(
            discord.ui.TextDisplay(
                f"## {crystal} Magic 8-Ball\n\n"
                f"{ribbon} *{q_display}*\n\n"
                f"**{sparkle} {answer}**"
            ),
            accent_color=discord.Color(color),
        )
        await ctx.send(view=_cv2(container))

    # ── /fun coinflip ─────────────────────────────────────────────────────────

    @fun_group.command(name="coinflip", description="Flip a coin~ 🪙")
    async def coinflip(self, ctx: commands.Context) -> None:
        loader = self._loader()
        coin = loader.get("coin")
        sparkle = loader.get("sparkle")

        label, emoji = random.choice(_COIN_SIDES)

        container = discord.ui.Container(
            discord.ui.TextDisplay(
                f"## {coin} Coin Flip\n\n"
                f"{emoji} **{label}** {sparkle}"
            ),
            accent_color=discord.Color(config.PASTEL_YELLOW),
        )
        await ctx.send(view=_cv2(container))

    # ── /fun choose ───────────────────────────────────────────────────────────

    @fun_group.command(name="choose", description="Can't decide? Let MochiMe pick for you! 🌸")
    @app_commands.describe(choices="Comma-separated options (e.g. pizza, sushi, ramen)")
    async def choose(self, ctx: commands.Context, *, choices: str) -> None:
        loader = self._loader()
        sparkle = loader.get("sparkle")
        ribbon = loader.get("ribbon")

        options = [c.strip() for c in choices.split(",") if c.strip()]
        if len(options) < 2:
            cross = loader.get("cross")
            container = discord.ui.Container(
                discord.ui.TextDisplay(
                    f"## {cross} Not enough options!\n"
                    "Give me at least two choices separated by commas~ 🌸"
                ),
                accent_color=discord.Color(config.PASTEL_PEACH),
            )
            await ctx.send(view=_cv2(container), ephemeral=True)
            return

        picked = random.choice(options)
        others = [f"`{o}`" for o in options if o != picked]
        others_text = (
            f"\n\n{ribbon} *Other options were: {', '.join(others)}*" if others else ""
        )

        container = discord.ui.Container(
            discord.ui.TextDisplay(
                f"## {sparkle} MochiMe picks…\n\n"
                f"**{picked}** {sparkle}"
                f"{others_text}"
            ),
            accent_color=discord.Color(config.PASTEL_PINK),
        )
        await ctx.send(view=_cv2(container))

    # ── /fun roll ─────────────────────────────────────────────────────────────

    @fun_group.command(name="roll", description="Roll some dice! 🎲")
    @app_commands.describe(dice="Dice to roll — e.g. d6, 2d20, d100 (default: d6)")
    async def roll(self, ctx: commands.Context, dice: str = "d6") -> None:
        loader = self._loader()
        dice_e = loader.get("dice")
        sparkle = loader.get("sparkle")
        ribbon = loader.get("ribbon")

        m = _DICE_RE.match(dice.strip())
        if not m:
            cross = loader.get("cross")
            container = discord.ui.Container(
                discord.ui.TextDisplay(
                    f"## {cross} Invalid dice format\n"
                    "Use formats like `d6`, `2d20`, or `d100`~ 🌸"
                ),
                accent_color=discord.Color(config.PASTEL_PEACH),
            )
            await ctx.send(view=_cv2(container), ephemeral=True)
            return

        num_dice = int(m.group(1) or 1)
        sides = int(m.group(2))

        if num_dice < 1 or num_dice > 20:
            cross = loader.get("cross")
            container = discord.ui.Container(
                discord.ui.TextDisplay(
                    f"## {cross} Too many dice!\nRoll between 1 and 20 dice at a time~ 🌸"
                ),
                accent_color=discord.Color(config.PASTEL_PEACH),
            )
            await ctx.send(view=_cv2(container), ephemeral=True)
            return

        if sides < 2 or sides > 1000:
            cross = loader.get("cross")
            container = discord.ui.Container(
                discord.ui.TextDisplay(
                    f"## {cross} Invalid die size!\nChoose between d2 and d1000~ 🌸"
                ),
                accent_color=discord.Color(config.PASTEL_PEACH),
            )
            await ctx.send(view=_cv2(container), ephemeral=True)
            return

        rolls = [random.randint(1, sides) for _ in range(num_dice)]
        total = sum(rolls)

        rolls_text = "  ·  ".join(f"`{r}`" for r in rolls)
        total_line = f"\n\n**Total:** `{total}`" if num_dice > 1 else ""
        color = config.PASTEL_PURPLE if total == num_dice * sides else (
            config.PASTEL_PEACH if total == num_dice else config.PASTEL_BLUE
        )

        container = discord.ui.Container(
            discord.ui.TextDisplay(
                f"## {dice_e} Rolling {num_dice}d{sides}\n\n"
                f"{rolls_text}{total_line}\n\n"
                f"{ribbon} *{_roll_flavour(total, num_dice, sides)}* {sparkle}"
            ),
            accent_color=discord.Color(color),
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

        if isinstance(error, commands.MissingRequiredArgument):
            container = discord.ui.Container(
                discord.ui.TextDisplay(
                    f"## {cross} Missing argument\n"
                    f"`{error.param.name}` is required~ 🌸"
                ),
                accent_color=discord.Color(config.PASTEL_PEACH),
            )
        else:
            container = discord.ui.Container(
                discord.ui.TextDisplay(
                    f"## {cross} Something went wrong\nPlease try again~ 🌸"
                ),
                accent_color=discord.Color(config.PASTEL_PEACH),
            )

        lv = discord.ui.LayoutView()
        lv.add_item(container)
        try:
            await ctx.send(view=lv, ephemeral=True)
        except discord.HTTPException:
            pass


def _roll_flavour(total: int, num: int, sides: int) -> str:
    if total == num * sides:
        return "Maximum roll! You're on fire~ 🔥"
    if total == num:
        return "Ouch, all ones... better luck next time~"
    if total >= num * sides * 0.8:
        return "Great roll! 🌟"
    if total <= num * sides * 0.2:
        return "That was rough... 🌧️"
    return "Not bad~ keep rolling!"


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Fun(bot))
