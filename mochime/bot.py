from __future__ import annotations

import asyncio
import os
import sys

import discord
from discord.ext import commands

import config
import database

COGS = [
    "cogs.emoji_loader",
    "cogs.help",
    "cogs.rp",
    "cogs.moderation",
    "cogs.application",
    "cogs.server_features",
]


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
        print(config.BOOT_BANNER)
        print("  ✦ Initialising database...")
        await database.init_db()
        print("  ✦ Loading cogs...")
        for cog in COGS:
            await self.load_extension(cog)
            print(f"    ↳ {cog} ✓")
        print("  ✦ Syncing slash commands...")
        await self.tree.sync()
        print("  ✦ Slash commands synced globally ✓")

    async def on_ready(self) -> None:
        assert self.user is not None
        print(f"\n  ✦ Logged in as {self.user} (ID: {self.user.id})")
        print(f"  ✦ Prefix: {config.PREFIX!r}")
        print(f"  ✦ Guilds: {len(self.guilds)}")
        print("\n  🌸 MochiMe is ready! 🌸\n")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name="mochi help 🌸",
            )
        )

    async def on_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.NotOwner):
            return
        if isinstance(error, (commands.MissingPermissions, commands.BotMissingPermissions)):
            return
        if isinstance(error, commands.NoPrivateMessage):
            loader = self.get_cog("EmojiLoader")
            cross = loader.get("cross") if loader else "❌"
            container = discord.ui.Container(
                discord.ui.TextDisplay(
                    f"## {cross} Server Only\nThis command can only be used in a server."
                ),
                accent_color=discord.Color(0xFFCDB3),
            )
            await ctx.send(
                components=[container],
                flags=discord.MessageFlags(is_components_v2=True),
            )
            return
        raise error

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        await self.process_commands(message)

    async def close(self) -> None:
        await database.close_db()
        await super().close()


async def main() -> None:
    token = config.BOT_TOKEN
    if not token:
        print("ERROR: BOT_TOKEN environment variable is not set.")
        print("  Set it with: export BOT_TOKEN=your_token_here")
        sys.exit(1)

    bot = MochiMe()
    async with bot:
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
