from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config
from cogs.emoji_loader import EmojiLoader


def _cv2(*items: discord.ui.Component) -> discord.ui.LayoutView:
    lv = discord.ui.LayoutView()
    for item in items:
        lv.add_item(item)
    return lv


# ─── category data ─────────────────────────────────────────────────────────────
# Each entry: ("`usage`", "description")
# Slash-command equivalent is noted in the footer of each category page.

CATEGORIES: dict[str, dict] = {
    "general": {
        "label": "🌸 General",
        "description": "Core bot commands",
        "color": config.PASTEL_PINK,
        "commands": [
            ("`help`",    "Show this help menu"),
            ("`ping`",    "Check bot latency"),
            ("`about`",   "About MochiMe"),
            ("`info`",    "Server information"),
            ("`user [@user]`", "View a member's MochiMe profile"),
        ],
    },
    "roleplay": {
        "label": "🎀 Roleplay",
        "description": "Cute anime-GIF roleplay actions",
        "color": config.PASTEL_PURPLE,
        "commands": [
            ("`hug @user`",    "Give someone a warm hug 🫂"),
            ("`pat @user`",    "Gently pat someone 🫶"),
            ("`kiss @user`",   "Give someone a sweet kiss 💋"),
            ("`bonk @user`",   "Bonk someone on the head 🔨"),
            ("`blush`",        "Express your blush 😳"),
            ("`cuddle @user`", "Cuddle with someone 🥰"),
            ("`poke @user`",   "Poke someone playfully 👉"),
        ],
    },
    "levels": {
        "label": "🌟 Levels & XP",
        "description": "XP system — earn points by chatting",
        "color": config.PASTEL_LAVENDER,
        "commands": [
            ("`rank [@user]`",  "See your (or someone else's) rank card"),
            ("`leaderboard`",   "Top 10 XP leaderboard for this server"),
        ],
        "notes": (
            "**How XP works**\n"
            "You earn **15–25 XP** per message with a 60 s cooldown.\n"
            "Formula: Level `n` = `n² × 100` total XP (e.g. Level 5 = 2,500 XP).\n"
            "Level-up announcements are posted in the channel where you levelled up."
        ),
    },
    "fun": {
        "label": "🎲 Fun",
        "description": "Lighthearted games and randomness",
        "color": config.PASTEL_YELLOW,
        "commands": [
            ("`8ball <question>`",   "Ask the magic 8-ball 🔮"),
            ("`coinflip`",           "Flip a coin 🪙"),
            ("`choose <a, b, ...>`", "Let MochiMe pick from your options 🌸"),
            ("`roll [dice]`",        "Roll dice — e.g. `d6`, `2d20`, `d100` 🎲"),
        ],
    },
    "polls": {
        "label": "📊 Polls",
        "description": "Create live community polls",
        "color": config.PASTEL_BLUE,
        "commands": [
            ("`poll <question> <opt1> <opt2> [opt3] [opt4]`", "Create a poll with 2–4 options"),
            ("`endpoll <message_id>`",                        "Close a poll you created"),
        ],
        "notes": (
            "Polls show **live vote counts** and percentage bars.\n"
            "Each member can vote **once** — clicking again shows their current choice.\n"
            "Copy a poll's **Message ID** (Developer Mode) to use `endpoll`."
        ),
    },
    "moderation": {
        "label": "🛡️ Moderation",
        "description": "Server moderation tools (requires permissions)",
        "color": config.PASTEL_PEACH,
        "commands": [
            ("`ban @user [reason]`",  "Ban a member · requires **Ban Members**"),
            ("`kick @user [reason]`", "Kick a member · requires **Kick Members**"),
            ("`mute @user [reason]`", "Timeout a member · requires **Moderate Members**"),
            ("`warn @user [reason]`", "Issue a formal warning · requires **Manage Messages**"),
        ],
        "notes": (
            "All actions post a confirmation card with an **Undo** button.\n"
            "Bans, kicks, mutes, and warns are logged to your configured log channel."
        ),
    },
    "setup": {
        "label": "⚙️ Server Setup",
        "description": "Admin configuration (requires Manage Server)",
        "color": config.PASTEL_GREEN,
        "commands": [
            ("`server`",                   "View server stats panel"),
            ("`settings`",                 "Open server configuration panel"),
            ("`setrp #channel`",           "Set the designated RP channel"),
            ("`setlog #channel`",          "Set the moderation log channel"),
            ("`setmodrole @role`",         "Set the moderator role"),
            ("`setwelcome`",               "Open the welcome-message setup wizard"),
            ("`setwelcomechannel #ch`",    "Set the channel for welcome cards"),
            ("`setwelcomeimage`",          "Upload a banner image for welcome cards (slash only)"),
            ("`welcometest`",              "Preview the welcome card as yourself"),
            ("`togglewelcome`",            "Enable or disable the welcome system"),
            ("`cosmetics`",               "Browse server cosmetics"),
            ("`pets`",                    "Browse server pets"),
        ],
    },
    "context": {
        "label": "🖱️ Context Menus",
        "description": "Right-click commands on users & messages",
        "color": config.PASTEL_PINK,
        "commands": [
            ("`Right-click user → ✨ Mochi Profile`",  "View a member's full profile card"),
            ("`Right-click user → 📌 View RP Stats`",  "See someone's roleplay action stats"),
            ("`Right-click user → 🛡️ Mod History`",   "View a member's moderation history"),
            ("`Right-click msg  → 🌐 Translate`",      "Translate any message to 25 languages"),
        ],
        "notes": (
            "Context menus appear in the **Apps** sub-menu when you right-click "
            "(desktop) or long-press (mobile) a user or message."
        ),
    },
}


# ─── UI builders ───────────────────────────────────────────────────────────────

def _category_select() -> discord.ui.ActionRow:
    return discord.ui.ActionRow(
        discord.ui.Select(
            placeholder="🌸 Choose a category…",
            custom_id="help_category_select",
            options=[
                discord.SelectOption(
                    label=cat["label"],
                    value=key,
                    description=cat["description"],
                )
                for key, cat in CATEGORIES.items()
            ],
        )
    )


def build_main_container() -> discord.ui.Container:
    cats_overview = "  ·  ".join(cat["label"] for cat in CATEGORIES.values())

    return discord.ui.Container(
        discord.ui.TextDisplay(
            "# ✨ MochiMe Help ✨\n"
            "🌸 *A cute pastel bot for your Discord server*\n\n"
            + cats_overview + "\n\n"
            "Select a category below to explore commands."
        ),
        discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
        discord.ui.TextDisplay(
            "-# All commands work as both `mochi <cmd>` **prefix** and `/cmd` **slash**.\n"
            "-# Type `/` in any channel to see the full slash-command list."
        ),
        discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
        _category_select(),
        accent_color=discord.Color(config.PASTEL_PINK),
    )


def build_category_container(key: str) -> discord.ui.Container:
    cat = CATEGORIES[key]
    sparkle = "✨"

    cmd_lines = "\n".join(
        f"**{cmd}**\n{desc}" for cmd, desc in cat["commands"]
    )

    notes_block = ""
    if notes := cat.get("notes"):
        notes_block = f"\n\n{notes}"

    footer = f"-# {sparkle} All commands work as `mochi <cmd>` prefix **or** `/cmd` slash."

    return discord.ui.Container(
        discord.ui.TextDisplay(
            f"## {cat['label']}\n"
            f"*{cat['description']}*\n\n"
            + cmd_lines
            + notes_block
        ),
        discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
        discord.ui.TextDisplay(footer),
        discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
        _category_select(),
        accent_color=discord.Color(cat["color"]),
    )


# ─── cog ───────────────────────────────────────────────────────────────────────

class Help(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _loader(self) -> EmojiLoader:
        cog = self.bot.get_cog("EmojiLoader")
        assert isinstance(cog, EmojiLoader)
        return cog

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction) -> None:
        if interaction.type != discord.InteractionType.component:
            return
        data = interaction.data or {}
        if data.get("custom_id") != "help_category_select":
            return
        values = data.get("values", [])
        if not values or values[0] not in CATEGORIES:
            return

        container = build_category_container(values[0])
        lv = discord.ui.LayoutView()
        lv.add_item(container)
        await interaction.response.edit_message(view=lv)

    @commands.hybrid_command(name="help", description="Show the MochiMe help menu 🌸")
    async def help_cmd(self, ctx: commands.Context) -> None:
        lv = discord.ui.LayoutView(timeout=300)
        lv.add_item(build_main_container())
        await ctx.send(view=lv)

    @commands.hybrid_command(name="ping", description="Check the bot's latency")
    async def ping(self, ctx: commands.Context) -> None:
        loader = self._loader()
        ms = round(self.bot.latency * 1000)
        sparkle = loader.get("sparkle")
        color = (
            config.PASTEL_GREEN if ms < 100
            else config.PASTEL_YELLOW if ms < 200
            else config.PASTEL_PEACH
        )
        container = discord.ui.Container(
            discord.ui.TextDisplay(
                f"## {sparkle} Pong!\n\n"
                f"**Latency:** `{ms} ms`"
            ),
            accent_color=discord.Color(color),
        )
        await ctx.send(view=_cv2(container))

    @commands.hybrid_command(name="about", description="About MochiMe 🌸")
    async def about(self, ctx: commands.Context) -> None:
        loader = self._loader()
        flower   = loader.get("flower")
        ribbon   = loader.get("ribbon")
        sparkle  = loader.get("sparkle")
        heart    = loader.get("heart")
        trophy   = loader.get("trophy")
        dice     = loader.get("dice")
        chart    = loader.get("chart")
        shield   = loader.get("shield")
        settings = loader.get("settings")

        container = discord.ui.Container(
            discord.ui.Section(
                discord.ui.TextDisplay(
                    f"# {flower} MochiMe {flower}\n"
                    f"*A cute, pastel Discord bot built with discord.py.*\n\n"
                    f"{ribbon} **Prefix:** `mochi ` · slash commands also supported\n"
                    f"{heart} **Roleplay** — anime GIF actions with 7 commands\n"
                    f"{trophy} **Levels & XP** — earn XP by chatting, climb the leaderboard\n"
                    f"{dice} **Fun** — 8-ball, coinflip, choose, dice roller\n"
                    f"{chart} **Polls** — live-updating community polls\n"
                    f"{shield} **Moderation** — ban, kick, mute, warn with audit log\n"
                    f"{settings} **Server Setup** — welcome cards, channels, roles\n\n"
                    f"{sparkle} Use `mochi help` or `/help` to explore everything!"
                ),
                accessory=discord.ui.Thumbnail(
                    media=discord.UnfurledMediaItem(
                        url=str(self.bot.user.display_avatar.url) if self.bot.user else ""
                    )
                ),
            ),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
            discord.ui.ActionRow(
                discord.ui.Button(
                    label="Add to Server",
                    style=discord.ButtonStyle.link,
                    url=(
                        f"https://discord.com/oauth2/authorize"
                        f"?client_id={self.bot.application_id}"
                        f"&scope=bot+applications.commands"
                    ),
                    emoji="🌸",
                ),
            ),
            accent_color=discord.Color(config.PASTEL_PURPLE),
        )
        await ctx.send(view=_cv2(container))

    @commands.hybrid_command(name="info", description="Show server information")
    @commands.guild_only()
    async def info(self, ctx: commands.Context) -> None:
        loader = self._loader()
        guild = ctx.guild
        if guild is None:
            await ctx.send("This command can only be used in a server.", ephemeral=True)
            return

        sparkle = loader.get("sparkle")
        star    = loader.get("star")
        shield  = loader.get("shield")
        ribbon  = loader.get("ribbon")
        flower  = loader.get("flower")

        text_ch  = len([c for c in guild.channels if isinstance(c, discord.TextChannel)])
        voice_ch = len([c for c in guild.channels if isinstance(c, discord.VoiceChannel)])
        bots     = sum(1 for m in guild.members if m.bot) if guild.members else "?"

        container = discord.ui.Container(
            discord.ui.Section(
                discord.ui.TextDisplay(
                    f"## {sparkle} {guild.name}\n\n"
                    f"{star} **Members:** `{guild.member_count}`  ·  Bots: `{bots}`\n"
                    f"{ribbon} **Channels:** `{text_ch}` text  ·  `{voice_ch}` voice\n"
                    f"{shield} **Roles:** `{len(guild.roles)}`\n"
                    f"{flower} **Owner:** {guild.owner.mention if guild.owner else 'Unknown'}\n"
                    f"{star} **Created:** <t:{int(guild.created_at.timestamp())}:D> "
                    f"(<t:{int(guild.created_at.timestamp())}:R>)"
                ),
                accessory=discord.ui.Thumbnail(
                    media=discord.UnfurledMediaItem(
                        url=str(guild.icon.url) if guild.icon else str(ctx.author.display_avatar.url)
                    )
                ),
            ),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay(
                f"-# {sparkle} ID: `{guild.id}`  ·  Boost level: `{guild.premium_tier}`  ·  "
                f"Boosts: `{guild.premium_subscription_count}`"
            ),
            accent_color=discord.Color(config.PASTEL_BLUE),
        )
        await ctx.send(view=_cv2(container))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Help(bot))
