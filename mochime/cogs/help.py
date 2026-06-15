from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config
from cogs.emoji_loader import EmojiLoader


CATEGORIES: dict[str, dict] = {
    "general": {
        "label": "🌸 General",
        "description": "Basic bot commands",
        "color": config.PASTEL_PINK,
        "commands": [
            ("`mochi help`", "Shows this help menu"),
            ("`mochi ping`", "Check bot latency"),
            ("`mochi about`", "About MochiMe"),
            ("`mochi info`", "Server information"),
        ],
    },
    "roleplay": {
        "label": "🎀 Roleplay",
        "description": "Cute roleplay actions",
        "color": config.PASTEL_PURPLE,
        "commands": [
            ("`mochi hug @user`", "Give someone a warm hug"),
            ("`mochi pat @user`", "Gently pat someone"),
            ("`mochi kiss @user`", "Give someone a sweet kiss"),
            ("`mochi bonk @user`", "Bonk someone on the head"),
            ("`mochi blush`", "Express your blush"),
            ("`mochi cuddle @user`", "Cuddle with someone"),
            ("`mochi poke @user`", "Poke someone"),
        ],
    },
    "moderation": {
        "label": "🛡️ Moderation",
        "description": "Server moderation tools",
        "color": config.PASTEL_PEACH,
        "commands": [
            ("`mochi ban @user [reason]`", "Ban a member"),
            ("`mochi kick @user [reason]`", "Kick a member"),
            ("`mochi mute @user [reason]`", "Timeout a member"),
            ("`mochi warn @user [reason]`", "Warn a member"),
        ],
    },
    "utility": {
        "label": "⚙️ Utility",
        "description": "Handy utility commands",
        "color": config.PASTEL_BLUE,
        "commands": [
            ("`mochi server`", "Show server stats"),
            ("`mochi user @user`", "Show user info"),
            ("`mochi settings`", "Configure MochiMe for this server"),
        ],
    },
    "about": {
        "label": "✨ About",
        "description": "About MochiMe",
        "color": config.PASTEL_YELLOW,
        "commands": [
            ("`mochi about`", "Learn about MochiMe"),
            ("`mochi invite`", "Get the bot invite link"),
            ("`mochi support`", "Join the support server"),
        ],
    },
}


def build_main_container(emoji_loader: EmojiLoader) -> discord.ui.Container:
    sparkle = emoji_loader.get("sparkle")
    flower = emoji_loader.get("flower")
    ribbon = emoji_loader.get("ribbon")

    return discord.ui.Container(
        discord.ui.TextDisplay(
            f"# {sparkle} MochiMe Help {sparkle}\n"
            f"{flower} *A cute pastel bot for your server* {flower}\n\n"
            "Select a category below to explore commands."
        ),
        discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
        discord.ui.TextDisplay(
            f"{ribbon} **Categories** — use the menu to browse"
        ),
        accent_color=discord.Color(config.PASTEL_PINK),
    )


def build_category_container(key: str, emoji_loader: EmojiLoader) -> discord.ui.Container:
    cat = CATEGORIES[key]
    sparkle = emoji_loader.get("sparkle")

    lines = [f"## {cat['label']}\n*{cat['description']}*\n"]
    for cmd, desc in cat["commands"]:
        lines.append(f"**{cmd}** — {desc}")

    lines.append(f"\n*All commands also work as slash commands!* {sparkle}")

    return discord.ui.Container(
        discord.ui.TextDisplay("\n".join(lines)),
        accent_color=discord.Color(cat["color"]),
    )


class CategorySelect(discord.ui.Select):
    def __init__(self, emoji_loader: EmojiLoader) -> None:
        self.emoji_loader = emoji_loader
        options = [
            discord.SelectOption(
                label=cat["label"],
                value=key,
                description=cat["description"],
            )
            for key, cat in CATEGORIES.items()
        ]
        super().__init__(
            placeholder="🌸 Choose a category...",
            options=options,
            custom_id="help_category_select",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        selected = self.values[0]
        cat_container = build_category_container(selected, self.emoji_loader)
        select_row = discord.ui.ActionRow(CategorySelect(self.emoji_loader))

        await interaction.response.edit_message(
            components=[cat_container, select_row],
        )


class HelpView(discord.ui.View):
    def __init__(self, emoji_loader: EmojiLoader) -> None:
        super().__init__(timeout=300)
        self.emoji_loader = emoji_loader

    def build_components(self) -> list[discord.ui.Component]:
        main = build_main_container(self.emoji_loader)
        row = discord.ui.ActionRow(CategorySelect(self.emoji_loader))
        return [main, row]


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _get_emoji_loader(self) -> EmojiLoader:
        cog = self.bot.get_cog("EmojiLoader")
        assert isinstance(cog, EmojiLoader)
        return cog

    @commands.hybrid_command(name="help", description="Show the MochiMe help menu")
    async def help_cmd(self, ctx: commands.Context) -> None:
        loader = self._get_emoji_loader()
        view = HelpView(loader)
        components = view.build_components()
        await ctx.send(
            components=components,
            flags=discord.MessageFlags(is_components_v2=True),
        )

    @commands.hybrid_command(name="ping", description="Check the bot's latency")
    async def ping(self, ctx: commands.Context) -> None:
        loader = self._get_emoji_loader()
        ms = round(self.bot.latency * 1000)
        sparkle = loader.get("sparkle")
        container = discord.ui.Container(
            discord.ui.TextDisplay(
                f"# {sparkle} Pong!\n"
                f"**Latency:** `{ms}ms`"
            ),
            accent_color=discord.Color(config.PASTEL_GREEN),
        )
        await ctx.send(
            components=[container],
            flags=discord.MessageFlags(is_components_v2=True),
        )

    @commands.hybrid_command(name="about", description="About MochiMe")
    async def about(self, ctx: commands.Context) -> None:
        loader = self._get_emoji_loader()
        flower = loader.get("flower")
        ribbon = loader.get("ribbon")
        sparkle = loader.get("sparkle")
        heart = loader.get("heart")

        container = discord.ui.Container(
            discord.ui.TextDisplay(
                f"# {flower} MochiMe {flower}\n"
                f"*A cute, pastel Discord bot with a Nekotina-style command system.*\n\n"
                f"{ribbon} **Prefix:** `mochi ` (or use slash commands `/`)\n"
                f"{sparkle} **Features:** Roleplay, Moderation, Utilities\n"
                f"{heart} **Made with:** discord.py · aiosqlite · Phosphor Icons\n\n"
                "Use `mochi help` to explore all commands!"
            ),
            discord.ui.Separator(),
            discord.ui.ActionRow(
                discord.ui.Button(
                    label="Add to Server",
                    style=discord.ButtonStyle.link,
                    url=f"https://discord.com/oauth2/authorize?client_id={self.bot.application_id}&scope=bot+applications.commands",
                ),
            ),
            accent_color=discord.Color(config.PASTEL_PURPLE),
        )
        await ctx.send(
            components=[container],
            flags=discord.MessageFlags(is_components_v2=True),
        )

    @commands.hybrid_command(name="info", description="Show server information")
    @commands.guild_only()
    async def info(self, ctx: commands.Context) -> None:
        loader = self._get_emoji_loader()
        guild = ctx.guild
        if guild is None:
            await ctx.send("This command can only be used in a server.", ephemeral=True)
            return

        sparkle = loader.get("sparkle")
        star = loader.get("star")

        container = discord.ui.Container(
            discord.ui.TextDisplay(
                f"# {sparkle} {guild.name}\n\n"
                f"{star} **Members:** `{guild.member_count}`\n"
                f"{star} **Channels:** `{len(guild.channels)}`\n"
                f"{star} **Roles:** `{len(guild.roles)}`\n"
                f"{star} **Owner:** {guild.owner.mention if guild.owner else 'Unknown'}\n"
                f"{star} **Created:** <t:{int(guild.created_at.timestamp())}:R>"
            ),
            accent_color=discord.Color(config.PASTEL_BLUE),
        )
        await ctx.send(
            components=[container],
            flags=discord.MessageFlags(is_components_v2=True),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Help(bot))
