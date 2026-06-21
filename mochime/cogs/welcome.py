"""
welcome.py — Guild join intro + member welcome system.

Events
  on_guild_join   — cute CV2 introduction sent to the system / first channel
  on_member_join  — configurable CV2 welcome card

Commands (all require Manage Guild)
  setwelcome          — modal wizard: title, message, image URL, color
  setwelcomechannel   — pick the channel that receives welcome cards
  setwelcomeimage     — slash-only: upload a banner image file
  welcometest         — preview the current welcome card for yourself
  togglewelcome       — enable / disable the welcome system

Template variables for title + message:
  {user}      member mention
  {username}  member display name
  {server}    guild name
  {count}     current member count
"""
from __future__ import annotations

import re

import discord
from discord import app_commands
from discord.ext import commands

import config
import console
import database

import patches  # noqa: F401
from patches import FileInput

log = console.get_logger("cogs.welcome")


def _cv2(*items: discord.ui.Component) -> discord.ui.LayoutView:
    lv = discord.ui.LayoutView()
    for item in items:
        lv.add_item(item)
    return lv


# ─── template helpers ─────────────────────────────────────────────────────────

def _render(template: str, member: discord.Member, guild: discord.Guild) -> str:
    try:
        return template.format(
            user=member.mention,
            username=member.display_name,
            server=guild.name,
            count=guild.member_count,
        )
    except (KeyError, ValueError):
        return template


def _parse_color(hex_str: str | None) -> int:
    if not hex_str:
        return config.PASTEL_PINK
    clean = re.sub(r"[^0-9a-fA-F]", "", hex_str)
    try:
        return int(clean[:6], 16)
    except ValueError:
        return config.PASTEL_PINK


# ─── welcome card builder ──────────────────────────────────────────────────────

def _build_welcome_card(
    member: discord.Member,
    guild: discord.Guild,
    title: str,
    message: str,
    image_url: str | None,
    color: int,
    loader,
) -> discord.ui.Container:
    flower  = loader.get("flower")  if loader else "🌸"
    sparkle = loader.get("sparkle") if loader else "✨"

    rendered_title   = _render(title,   member, guild)
    rendered_message = _render(message, member, guild)

    joined_ts = int(member.joined_at.timestamp()) if member.joined_at else None
    ts_line   = f"\n-# Joined <t:{joined_ts}:R>" if joined_ts else ""

    children: list = [
        discord.ui.Section(
            discord.ui.TextDisplay(
                f"## {flower} {rendered_title}\n\n"
                f"{rendered_message}"
                f"{ts_line}"
            ),
            accessory=discord.ui.Thumbnail(
                media=discord.UnfurledMediaItem(url=str(member.display_avatar.url))
            ),
        ),
    ]

    if image_url:
        children.append(
            discord.ui.MediaGallery(
                discord.MediaGalleryItem(
                    media=discord.UnfurledMediaItem(url=image_url)
                )
            )
        )

    children.append(
        discord.ui.TextDisplay(
            f"-# {sparkle} {guild.name}  ·  {guild.member_count} members"
        )
    )

    return discord.ui.Container(*children, accent_color=discord.Color(color))


# ─── setup modal ──────────────────────────────────────────────────────────────

class WelcomeSetupModal(discord.ui.Modal, title="Welcome Message Setup"):
    welcome_title = discord.ui.TextInput(
        label="Welcome Title",
        placeholder="Use {user}, {server}, {count}",
        default="Welcome to {server}! \U0001f338",
        max_length=100,
    )
    welcome_message = discord.ui.TextInput(
        label="Welcome Message",
        placeholder="We're so happy you're here, {user}! ✨",
        default=(
            "We're so happy you're here, {user}! \u2728\n"
            "You are member **#{count}** — enjoy your stay!"
        ),
        style=discord.TextStyle.paragraph,
        max_length=500,
    )
    image_file: FileInput = FileInput(
        label="Banner Image (optional)",
        required=False,
    )
    color_hex = discord.ui.TextInput(
        label="Accent color hex (optional — e.g. FFB3C6)",
        placeholder="FFB3C6",
        default="FFB3C6",
        max_length=6,
        required=False,
    )

    def __init__(self, bot: commands.Bot, guild_id: str) -> None:
        super().__init__()
        self.bot      = bot
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        attachment = self.image_file.attachment

        # If something was uploaded but it isn't an image, reject it.
        if attachment and not attachment.is_image:
            await interaction.followup.send(
                "⚠️ That file doesn't look like an image.\n"
                "Please attach a PNG, JPG, GIF, or WebP file and try again.",
                ephemeral=True,
            )
            return

        title   = self.welcome_title.value.strip()
        message = self.welcome_message.value.strip()
        img     = attachment.url if attachment else ""
        color   = _parse_color(self.color_hex.value.strip())

        await database.upsert_server_settings(
            self.guild_id,
            welcome_title     = title,
            welcome_message   = message,
            welcome_image_url = img,
            welcome_color     = str(color),
            welcome_enabled   = 1,
        )

        loader = self.bot.get_cog("EmojiLoader")
        check  = loader.get("check") if loader else "✅"

        guild  = self.bot.get_guild(int(self.guild_id))
        member = interaction.user

        if guild and isinstance(member, discord.Member):
            card = _build_welcome_card(
                member, guild, title, message, img or None, color, loader
            )
            preview_children: list = [
                discord.ui.TextDisplay(
                    f"{check} **Welcome message saved!**\n"
                    "-# Here's a preview of what new members will see:"
                ),
                discord.ui.Separator(),
                card,
            ]
        else:
            preview_children = [
                discord.ui.TextDisplay(
                    f"{check} **Welcome message saved!**\n"
                    "Use `welcometest` in your server to preview it."
                )
            ]

        info = discord.ui.Container(
            *preview_children,
            accent_color=discord.Color(config.PASTEL_GREEN),
        )
        await interaction.followup.send(
            view=_cv2(info),
            ephemeral=True,
        )

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        log.error("WelcomeSetupModal error: %s", error)
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "Something went wrong saving your welcome message. Please try again.",
                ephemeral=True,
            )


# ─── helper view for prefix modal trigger ─────────────────────────────────────

class _OpenModalView(discord.ui.View):
    def __init__(self, modal: WelcomeSetupModal) -> None:
        super().__init__(timeout=120)
        self.modal = modal

    @discord.ui.button(
        label="Open Setup Wizard",
        style=discord.ButtonStyle.primary,
        emoji="🌸",
        custom_id="open_welcome_modal",
    )
    async def open_modal(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.send_modal(self.modal)
        self.stop()

    async def on_timeout(self) -> None:
        self.stop()


# ─── cog ──────────────────────────────────────────────────────────────────────

class Welcome(commands.Cog):
    """Guild join introduction and per-server member welcome system."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _loader(self):
        return self.bot.get_cog("EmojiLoader")

    # ── on_guild_join ────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        channel = guild.system_channel
        if channel is None or not channel.permissions_for(guild.me).send_messages:
            channel = None
            for ch in guild.text_channels:
                if ch.permissions_for(guild.me).send_messages:
                    channel = ch
                    break

        if channel is None:
            log.warning("on_guild_join: no writable channel in %s", guild.name)
            return

        loader = self._loader()

        def e(name: str) -> str:
            return loader.get(name) if loader else config.FALLBACK_EMOJIS.get(name, "✨")

        sparkle = e("sparkle")
        heart   = e("heart")
        flower  = e("flower")
        ribbon  = e("ribbon")
        shield  = e("shield")
        star    = e("star")
        wave    = e("wave")

        container = discord.ui.Container(
            discord.ui.Section(
                discord.ui.TextDisplay(
                    f"## {wave} Hey there, **{guild.name}**!\n\n"
                    f"{heart} I'm **MochiMe** — a cute pastel Discord bot with anime GIFs, "
                    f"roleplay commands, moderation tools, welcome messages, and a beautiful "
                    f"Components v2 UI.\n\n"
                    f"{sparkle} *Thanks for adding me!* {sparkle}"
                ),
                accessory=discord.ui.Thumbnail(
                    media=discord.UnfurledMediaItem(
                        url=str(guild.me.display_avatar.url)
                    )
                ),
            ),
            discord.ui.Separator(),
            discord.ui.TextDisplay(
                f"## {ribbon} Quick Setup\n\n"
                f"{flower} **Welcome messages**\n"
                f"  `/setwelcome` — configure the welcome card\n"
                f"  `/setwelcomechannel` — pick the welcome channel\n\n"
                f"{shield} **Moderation**\n"
                f"  `/setlog #channel` — moderation log\n"
                f"  `/setmodrole @role` — moderator role\n\n"
                f"{star} **Browse everything**\n"
                f"  `mochi help` or `/help` — full command list"
            ),
            discord.ui.Separator(),
            discord.ui.TextDisplay(
                f"-# {sparkle} Prefix: `mochi `  ·  Slash commands also supported  ·  "
                f"Use `mochi help` to explore!"
            ),
            accent_color=discord.Color(config.PASTEL_PINK),
        )

        try:
            await channel.send(view=_cv2(container))
            log.info("Sent guild-join intro to #%s in %s", channel.name, guild.name)
        except discord.Forbidden:
            log.warning(
                "on_guild_join: missing perms in #%s (%s)", channel.name, guild.name
            )
        except Exception as exc:
            log.error("on_guild_join error in %s: %s", guild.name, exc)

    # ── on_member_join ───────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        guild    = member.guild
        settings = await database.get_server_settings(str(guild.id))

        if not settings or not settings["welcome_enabled"]:
            return

        welcome_ch_id = settings["welcome_channel_id"]
        if not welcome_ch_id and guild.system_channel:
            welcome_ch_id = str(guild.system_channel.id)
        if not welcome_ch_id:
            return

        channel = guild.get_channel(int(welcome_ch_id))
        if not isinstance(channel, discord.TextChannel):
            return
        if not channel.permissions_for(guild.me).send_messages:
            return

        title   = settings["welcome_title"]     or "Welcome to {server}! \U0001f338"
        message = settings["welcome_message"]   or "We're so happy you're here, {user}! ✨"
        img     = settings["welcome_image_url"] or None
        color   = _parse_color(settings["welcome_color"])
        loader  = self._loader()

        card = _build_welcome_card(member, guild, title, message, img, color, loader)

        try:
            await channel.send(view=_cv2(card))
        except discord.Forbidden:
            log.warning(
                "on_member_join: missing perms in #%s (%s)", channel.name, guild.name
            )
        except Exception as exc:
            log.error("on_member_join error in %s: %s", guild.name, exc)

    # ── setwelcome ────────────────────────────────────────────────────────────

    @commands.hybrid_command(
        name="setwelcome",
        description="Open the welcome message setup wizard",
    )
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def setwelcome(self, ctx: commands.Context) -> None:
        assert ctx.guild
        modal = WelcomeSetupModal(self.bot, str(ctx.guild.id))

        if ctx.interaction:
            await ctx.interaction.response.send_modal(modal)
        else:
            view = _OpenModalView(modal)
            await ctx.send(
                "🌸 Click **Open Setup Wizard** to configure your welcome message!",
                view=view,
            )

    # ── setwelcomechannel ─────────────────────────────────────────────────────

    @commands.hybrid_command(
        name="setwelcomechannel",
        description="Set the channel where welcome messages are sent",
    )
    @app_commands.describe(channel="The channel to send welcome messages in")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def setwelcomechannel(
        self, ctx: commands.Context, channel: discord.TextChannel
    ) -> None:
        assert ctx.guild
        await database.upsert_server_settings(
            str(ctx.guild.id), welcome_channel_id=str(channel.id)
        )
        loader    = self._loader()
        check     = loader.get("check")  if loader else "✅"
        flower    = loader.get("flower") if loader else "🌸"
        container = discord.ui.Container(
            discord.ui.TextDisplay(
                f"## {flower} Welcome Channel Set!\n"
                f"{check} New member cards will now appear in {channel.mention}."
            ),
            accent_color=discord.Color(config.PASTEL_GREEN),
        )
        await ctx.send(view=_cv2(container))

    # ── setwelcomeimage (slash-only — discord.Attachment upload) ─────────────

    @app_commands.command(
        name="setwelcomeimage",
        description="Upload a banner image file for welcome messages",
    )
    @app_commands.describe(image="The image file to use as the welcome banner")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setwelcomeimage(
        self, interaction: discord.Interaction, image: discord.Attachment
    ) -> None:
        assert interaction.guild
        loader = self._loader()

        if not image.content_type or not image.content_type.startswith("image/"):
            cross = loader.get("cross") if loader else "❌"
            err   = discord.ui.Container(
                discord.ui.TextDisplay(
                    f"## {cross} Not an image\n"
                    "Please attach a PNG, JPG, GIF, or WebP file."
                ),
                accent_color=discord.Color(config.PASTEL_PEACH),
            )
            await interaction.response.send_message(
                view=_cv2(err),
                ephemeral=True,
            )
            return

        await database.upsert_server_settings(
            str(interaction.guild.id), welcome_image_url=image.url
        )

        check  = loader.get("check")  if loader else "✅"
        flower = loader.get("flower") if loader else "🌸"

        confirm = discord.ui.Container(
            discord.ui.TextDisplay(
                f"## {flower} Welcome Banner Updated!\n"
                f"{check} This image will now appear in welcome cards."
            ),
            discord.ui.MediaGallery(
                discord.MediaGalleryItem(
                    media=discord.UnfurledMediaItem(url=image.url)
                )
            ),
            accent_color=discord.Color(config.PASTEL_GREEN),
        )
        await interaction.response.send_message(
            view=_cv2(confirm),
            ephemeral=True,
        )
        log.info(
            "Welcome banner updated in %s by %s",
            interaction.guild.name,
            interaction.user,
        )

    # ── welcometest ───────────────────────────────────────────────────────────

    @commands.hybrid_command(
        name="welcometest",
        description="Preview the welcome card as if you just joined",
    )
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def welcometest(self, ctx: commands.Context) -> None:
        assert ctx.guild
        assert isinstance(ctx.author, discord.Member)

        settings = await database.get_server_settings(str(ctx.guild.id))
        loader   = self._loader()

        title   = (settings and settings["welcome_title"])     or "Welcome to {server}! \U0001f338"
        message = (settings and settings["welcome_message"])   or "We're so happy you're here, {user}! ✨"
        img     = (settings and settings["welcome_image_url"]) or None
        color   = _parse_color(settings["welcome_color"] if settings else None)

        card = _build_welcome_card(
            ctx.author, ctx.guild, title, message, img, color, loader
        )

        if settings and settings["welcome_enabled"]:
            status_line = "✅ Welcome system is **enabled**."
        else:
            status_line = (
                "⚠️ Welcome system is currently **disabled** — "
                "use `togglewelcome` to enable it."
            )

        wrapper = discord.ui.Container(
            discord.ui.TextDisplay(f"-# Preview mode — {status_line}"),
            discord.ui.Separator(),
            card,
            accent_color=discord.Color(config.PASTEL_PURPLE),
        )
        await ctx.send(view=_cv2(wrapper))

    # ── togglewelcome ─────────────────────────────────────────────────────────

    @commands.hybrid_command(
        name="togglewelcome",
        description="Enable or disable the member welcome system",
    )
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def togglewelcome(self, ctx: commands.Context) -> None:
        assert ctx.guild
        settings = await database.get_server_settings(str(ctx.guild.id))
        current  = bool(settings and settings["welcome_enabled"])
        new_val  = 0 if current else 1

        await database.upsert_server_settings(
            str(ctx.guild.id), welcome_enabled=new_val
        )

        loader = self._loader()
        check  = loader.get("check")  if loader else "✅"
        cross  = loader.get("cross")  if loader else "❌"
        flower = loader.get("flower") if loader else "🌸"
        color  = config.PASTEL_GREEN if new_val else config.PASTEL_PEACH
        icon   = check if new_val else cross
        status = "**enabled** ✅" if new_val else "**disabled** ❌"

        container = discord.ui.Container(
            discord.ui.TextDisplay(
                f"## {flower} Welcome Messages {status}\n"
                f"{icon} Member welcome cards are now {status}."
            ),
            accent_color=discord.Color(color),
        )
        await ctx.send(view=_cv2(container))


# ─── setup ────────────────────────────────────────────────────────────────────

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Welcome(bot))
