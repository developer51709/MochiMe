from __future__ import annotations

import asyncio
import sys

import discord
from discord.ext import commands

import config
import console
import database

COGS = [
    "cogs.emoji_loader",
    "cogs.help",
    "cogs.rp",
    "cogs.moderation",
    "cogs.application",
    "cogs.server_features",
]

log = console.get_logger("mochime")


class MochiMe(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        super().__init__(
            command_prefix=commands.when_mentioned_or(config.PREFIX),
            intents=intents,
            help_command=None,
            case_insensitive=True,
            description="A cute pastel Discord bot 🌸",
        )

    async def setup_hook(self) -> None:
        console.setup_logging()
        console.print_banner()

        console.step("Database")
        await database.init_db()
        console.ok("Database initialised")

        console.step("Cogs")
        for cog in COGS:
            await self.load_extension(cog)
            console.ok(f"Loaded  {cog}")

        console.step("Slash commands")
        synced = await self.tree.sync()
        console.ok(f"Synced {len(synced)} slash commands globally")

    async def on_ready(self) -> None:
        assert self.user is not None
        console.step("Ready")
        console.ok(f"Logged in as  {self.user}  (ID: {self.user.id})")
        console.info(f"Serving {len(self.guilds)} guild(s)")
        console.info(f"Prefix  {config.PREFIX!r}  ·  Slash commands active")
        print()

        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name="mochi help 🌸",
            )
        )

    async def on_command(self, ctx: commands.Context) -> None:
        guild = ctx.guild.name if ctx.guild else "DM"
        log.info("cmd  %-18s  user=%-20s  guild=%s",
                 ctx.command, str(ctx.author), guild)

    async def on_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        if isinstance(error, (commands.CommandNotFound, commands.NotOwner)):
            return
        if isinstance(
            error,
            (commands.MissingPermissions, commands.BotMissingPermissions),
        ):
            return
        if isinstance(error, commands.NoPrivateMessage):
            loader = self.get_cog("EmojiLoader")
            cross = loader.get("cross") if loader else "❌"
            container = discord.ui.Container(
                discord.ui.TextDisplay(
                    f"## {cross} Server Only\n"
                    "This command can only be used in a server."
                ),
                accent_color=discord.Color(0xFFCDB3),
            )
            await ctx.send(
                components=[container],
                flags=discord.MessageFlags(is_components_v2=True),
            )
            return
        log.error("Unhandled error in command %s: %s", ctx.command, error)

    async def on_app_command_completion(
        self,
        interaction: discord.Interaction,
        command: discord.app_commands.Command | discord.app_commands.ContextMenu,
    ) -> None:
        guild = interaction.guild.name if interaction.guild else "DM"
        log.info("slash %-18s  user=%-20s  guild=%s",
                 f"/{command.name}", str(interaction.user), guild)

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        await self.process_commands(message)

    async def close(self) -> None:
        log.info("Shutting down…")
        await database.close_db()
        await super().close()


async def main() -> None:
    token = config.BOT_TOKEN
    if not token:
        console.fail("BOT_TOKEN is not set.")
        console.info("Run  python -m mochime --setup  to configure it.")
        sys.exit(1)

    bot = MochiMe()
    async with bot:
        await bot.start(token)
