from __future__ import annotations

import asyncio
import sys

import discord
from discord.ext import commands

import config
import console
import database
import patches

COGS = [
    "cogs.emoji_loader",
    "cogs.help",
    "cogs.rp",
    "cogs.translate",
    "cogs.moderation",
    "cogs.application",
    "cogs.server_features",
    "cogs.welcome",
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

        console.step("Patches")
        patches.apply_all()

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
        # Always ignore these
        if isinstance(error, (commands.CommandNotFound, commands.NotOwner)):
            return

        # Cog-level or command-level handler already took care of it
        if hasattr(ctx.command, "on_error"):
            return

        # Unwrap HybridCommandError / CommandInvokeError to the root cause
        original: BaseException = error
        while hasattr(original, "original"):
            original = original.original  # type: ignore[union-attr]

        # Interaction token expired — Discord dropped it, nothing we can send
        if isinstance(original, discord.NotFound) and getattr(original, "code", None) == 10062:
            log.warning("Interaction expired: cmd=%s user=%s", ctx.command, ctx.author)
            return

        # Already handled by a cog-level error handler (cog_command_error)
        if ctx.cog is not None and hasattr(ctx.cog, "cog_command_error"):
            return

        from cogs.emoji_loader import EmojiLoader as _EL
        _loader = self.get_cog("EmojiLoader")
        cross = _loader.get("cross") if isinstance(_loader, _EL) else "❌"  # type: ignore[union-attr]
        ribbon = _loader.get("ribbon") if isinstance(_loader, _EL) else "🌸"  # type: ignore[union-attr]

        container: discord.ui.Container | None = None

        if isinstance(error, commands.NoPrivateMessage):
            container = discord.ui.Container(
                discord.ui.TextDisplay(
                    f"## {cross} Server only\n"
                    "This command can only be used inside a server."
                ),
                accent_color=discord.Color(config.PASTEL_PEACH),
            )
        elif isinstance(error, commands.MissingPermissions):
            perm = error.missing_permissions[0].replace("_", " ").title()
            container = discord.ui.Container(
                discord.ui.TextDisplay(
                    f"## {cross} Missing permission\n"
                    f"You need the **{perm}** permission to use this command."
                ),
                accent_color=discord.Color(config.PASTEL_PEACH),
            )
        elif isinstance(error, commands.BotMissingPermissions):
            perm = error.missing_permissions[0].replace("_", " ").title()
            container = discord.ui.Container(
                discord.ui.TextDisplay(
                    f"## {cross} I'm missing permissions\n"
                    f"I need the **{perm}** permission to do that."
                ),
                accent_color=discord.Color(config.PASTEL_PEACH),
            )
        elif isinstance(error, commands.CommandOnCooldown):
            container = discord.ui.Container(
                discord.ui.TextDisplay(
                    f"## {cross} Slow down!\n"
                    f"Try again in `{error.retry_after:.1f}s`~ {ribbon}"
                ),
                accent_color=discord.Color(config.PASTEL_PEACH),
            )
        elif isinstance(error, commands.DisabledCommand):
            container = discord.ui.Container(
                discord.ui.TextDisplay(
                    f"## {cross} Command disabled\n"
                    "This command is currently unavailable."
                ),
                accent_color=discord.Color(config.PASTEL_PEACH),
            )
        elif isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument,
                                commands.HybridCommandError, commands.CommandInvokeError)):
            # These should be handled by the owning cog; log and bail quietly
            log.error("Unhandled error in command %s: %s", ctx.command, original)
            return
        else:
            log.error("Unhandled error in command %s: %s", ctx.command, error)
            return

        if container is not None:
            lv = discord.ui.LayoutView()
            lv.add_item(container)
            try:
                await ctx.send(view=lv, ephemeral=True)
            except discord.HTTPException:
                pass

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
