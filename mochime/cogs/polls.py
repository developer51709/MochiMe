from __future__ import annotations

import json

import discord
from discord import app_commands
from discord.ext import commands

import config
import database
from cogs.emoji_loader import EmojiLoader

_OPTION_EMOJIS = ["🅰️", "🅱️", "🅾️", "🆎"]
_OPTION_COLORS = [
    config.PASTEL_PINK,
    config.PASTEL_PURPLE,
    config.PASTEL_BLUE,
    config.PASTEL_PEACH,
]


def _cv2(*items: discord.ui.Component) -> discord.ui.LayoutView:
    lv = discord.ui.LayoutView()
    for item in items:
        lv.add_item(item)
    return lv


def _progress_bar(count: int, total: int, length: int = 10) -> str:
    frac = count / total if total > 0 else 0.0
    n = round(frac * length)
    return "▓" * n + "░" * (length - n)


def _build_poll_view(
    message_id: str,
    question: str,
    options: list[str],
    counts: list[int],
    *,
    active: bool = True,
) -> discord.ui.LayoutView:
    """Build the full CV2 poll layout with vote counts and buttons inside the container."""
    loader_emoji = _OPTION_EMOJIS
    total = sum(counts)
    sparkle = "✨"
    chart = "📊"

    # Build the results text
    result_lines: list[str] = []
    for i, (opt, count) in enumerate(zip(options, counts)):
        bar = _progress_bar(count, total)
        pct = (count / total * 100) if total > 0 else 0.0
        emoji = loader_emoji[i] if i < len(loader_emoji) else f"`{i + 1}.`"
        result_lines.append(
            f"{emoji} **{opt}**\n{bar} `{count}` vote{'s' if count != 1 else ''} ({pct:.0f}%)"
        )

    footer_votes = f"{total} vote{'s' if total != 1 else ''} total"
    footer = f"-# {sparkle} {footer_votes}" + (" · poll closed" if not active else "")

    # Vote buttons (one per option), disabled when poll is inactive
    buttons = [
        discord.ui.Button(
            label=opt[:80],
            emoji=loader_emoji[i] if i < len(loader_emoji) else None,
            style=discord.ButtonStyle.primary,
            custom_id=f"poll_vote:{message_id}:{i}",
            disabled=not active,
        )
        for i, opt in enumerate(options)
    ]

    container = discord.ui.Container(
        discord.ui.TextDisplay(
            f"## {chart} Poll\n\n**{question}**"
        ),
        discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
        discord.ui.TextDisplay("\n\n".join(result_lines)),
        discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
        discord.ui.ActionRow(*buttons),
        discord.ui.TextDisplay(footer),
        accent_color=discord.Color(config.PASTEL_BLUE),
    )

    lv = discord.ui.LayoutView(timeout=None)
    lv.add_item(container)
    return lv


class Polls(commands.Cog):
    """Create community polls with live vote tracking~ 📊"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _loader(self) -> EmojiLoader:
        cog = self.bot.get_cog("EmojiLoader")
        assert isinstance(cog, EmojiLoader)
        return cog

    # ── /poll ──────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="poll", description="Create a community poll 📊")
    @app_commands.describe(
        question="The question to ask",
        option1="First option",
        option2="Second option",
        option3="Third option (optional)",
        option4="Fourth option (optional)",
    )
    @commands.guild_only()
    async def poll(
        self,
        ctx: commands.Context,
        question: str,
        option1: str,
        option2: str,
        option3: str | None = None,
        option4: str | None = None,
    ) -> None:
        options: list[str] = [option1, option2]
        if option3:
            options.append(option3)
        if option4:
            options.append(option4)

        counts = [0] * len(options)

        # We need the message_id before we can store the poll, so send first then store.
        # Use a placeholder message_id of "0" and update after send.
        assert ctx.guild is not None
        assert ctx.channel is not None

        # Build initial view with a placeholder ID — we'll update the message_id after send
        placeholder_id = "pending"
        lv = _build_poll_view(placeholder_id, question, options, counts)

        # For slash commands we need to send() first to get the message object
        msg = await ctx.send(view=lv)

        if msg is None:
            # Slash command: fetch the original response message
            try:
                msg = await ctx.interaction.original_response()  # type: ignore[union-attr]
            except Exception:
                return

        # Now rebuild with the real message_id and re-edit the message
        real_id = str(msg.id)
        lv_real = _build_poll_view(real_id, question, options, counts)
        try:
            await msg.edit(view=lv_real)
        except Exception:
            pass

        # Persist to DB
        await database.create_poll(
            message_id=real_id,
            channel_id=str(ctx.channel.id),
            guild_id=str(ctx.guild.id),
            author_id=str(ctx.author.id),
            question=question,
            options=options,
        )

    # ── /endpoll ───────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="endpoll", description="Close a poll you created 📊")
    @app_commands.describe(message_id="ID of the poll message to close")
    @commands.guild_only()
    async def endpoll(self, ctx: commands.Context, message_id: str) -> None:
        loader = self._loader()
        cross = loader.get("cross")
        check = loader.get("check")

        row = await database.get_poll(message_id)
        if not row:
            container = discord.ui.Container(
                discord.ui.TextDisplay(
                    f"## {cross} Poll not found\n"
                    "Make sure you provided the correct message ID~ 🌸"
                ),
                accent_color=discord.Color(config.PASTEL_PEACH),
            )
            await ctx.send(view=_cv2(container), ephemeral=True)
            return

        if str(ctx.author.id) != row["author_id"]:
            container = discord.ui.Container(
                discord.ui.TextDisplay(
                    f"## {cross} Not your poll\n"
                    "Only the poll creator can close it~ 🌸"
                ),
                accent_color=discord.Color(config.PASTEL_PEACH),
            )
            await ctx.send(view=_cv2(container), ephemeral=True)
            return

        if not row["active"]:
            container = discord.ui.Container(
                discord.ui.TextDisplay(
                    f"## {cross} Already closed\nThis poll is already closed~ 🌸"
                ),
                accent_color=discord.Color(config.PASTEL_PEACH),
            )
            await ctx.send(view=_cv2(container), ephemeral=True)
            return

        options = json.loads(row["options"])
        counts = await database.get_vote_counts(message_id, len(options))

        # Disable buttons on the original message
        try:
            channel = self.bot.get_channel(int(row["channel_id"]))
            if isinstance(channel, discord.TextChannel):
                poll_msg = await channel.fetch_message(int(message_id))
                closed_lv = _build_poll_view(
                    message_id, row["question"], options, counts, active=False
                )
                await poll_msg.edit(view=closed_lv)
        except Exception:
            pass

        # Mark as inactive in DB
        db = await database.get_db()
        await db.execute(
            "UPDATE polls SET active = 0 WHERE message_id = ?", (message_id,)
        )
        await db.commit()

        container = discord.ui.Container(
            discord.ui.TextDisplay(
                f"## {check} Poll closed\nThe poll has been closed and voting is now disabled~ 🌸"
            ),
            accent_color=discord.Color(config.PASTEL_GREEN),
        )
        await ctx.send(view=_cv2(container), ephemeral=True)

    # ── poll vote handler ──────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction) -> None:
        if interaction.type != discord.InteractionType.component:
            return
        data = interaction.data or {}
        custom_id: str = data.get("custom_id", "")
        if not custom_id.startswith("poll_vote:"):
            return

        parts = custom_id.split(":")
        if len(parts) != 3:
            return
        _, message_id, option_idx_str = parts

        try:
            option_idx = int(option_idx_str)
        except ValueError:
            return

        loader = self._loader()
        cross = loader.get("cross")
        check = loader.get("check")
        sparkle = loader.get("sparkle")

        row = await database.get_poll(message_id)
        if not row or not row["active"]:
            await interaction.response.send_message(
                f"{cross} This poll is no longer accepting votes~ 🌸",
                ephemeral=True,
            )
            return

        options = json.loads(row["options"])
        if option_idx < 0 or option_idx >= len(options):
            return

        # Check if already voted
        existing = await database.get_user_vote(message_id, str(interaction.user.id))
        if existing is not None:
            chosen = options[existing] if existing < len(options) else "an option"
            await interaction.response.send_message(
                f"{cross} You already voted for **{chosen}**! Each person can only vote once~ 🌸",
                ephemeral=True,
            )
            return

        # Record vote
        success = await database.cast_vote(message_id, str(interaction.user.id), option_idx)
        if not success:
            await interaction.response.send_message(
                f"{cross} Couldn't record your vote~ please try again 🌸",
                ephemeral=True,
            )
            return

        # Acknowledge to voter
        await interaction.response.send_message(
            f"{check} Your vote for **{options[option_idx]}** has been recorded! {sparkle}",
            ephemeral=True,
        )

        # Update the poll message with new counts
        counts = await database.get_vote_counts(message_id, len(options))
        updated_lv = _build_poll_view(message_id, row["question"], options, counts)

        try:
            if interaction.message:
                await interaction.message.edit(view=updated_lv)
        except discord.HTTPException:
            pass

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


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Polls(bot))
