from __future__ import annotations

import random

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

import config
import database
from cogs.emoji_loader import EmojiLoader

NEKOS_BEST_BASE = "https://nekos.best/api/v2/{action}"
WAIFU_PICS_BASE = "https://api.waifu.pics/sfw/{action}"

_NEKOS_ACTION_MAP: dict[str, str] = {
    "hug":    "hug",
    "pat":    "pat",
    "kiss":   "kiss",
    "bonk":   "slap",
    "blush":  "blush",
    "cuddle": "cuddle",
    "poke":   "poke",
}

_BACK_LABELS: dict[str, tuple[str, str]] = {
    "hug":    ("Hug back",    "🫂"),
    "pat":    ("Pat back",    "🌸"),
    "kiss":   ("Kiss back",   "💋"),
    "bonk":   ("Bonk back",   "🔨"),
    "cuddle": ("Cuddle back", "🥰"),
    "poke":   ("Poke back",   "👉"),
}

# Actions available in the context-menu select (blush is self-only)
_SELECT_ACTIONS: list[tuple[str, str, str]] = [
    ("hug",    "Hug",    "🫂"),
    ("pat",    "Pat",    "🌸"),
    ("kiss",   "Kiss",   "💋"),
    ("bonk",   "Bonk",   "🔨"),
    ("cuddle", "Cuddle", "🥰"),
    ("poke",   "Poke",   "👉"),
]

RP_LINES: dict[str, list[str]] = {
    "hug": [
        "{author} wraps their arms around {target} in a warm, cozy hug! 🫂",
        "{author} rushes over and squeezes {target} tight~ so soft!",
        "A big fluffy hug from {author} lands on {target}! 💕",
        "{author} pulls {target} close and holds them gently~ you okay? 🌸",
    ],
    "pat": [
        "{author} gently pats {target} on the head~ *pat pat* 🌸",
        "{author} gives {target} the softest headpats ever! ✨",
        "*pat pat* — {author} tenderly pats {target}~ you did well!",
        "{author} reaches over and pats {target} reassuringly~ 💜",
    ],
    "kiss": [
        "{author} places a sweet little kiss on {target}'s cheek 💋",
        "Mwah! {author} gives {target} the softest kiss~ 🩷",
        "{author} sneaks a gentle kiss onto {target}'s forehead~ ✨",
        "{author} kisses {target} sweetly on the cheek~ 💕",
    ],
    "bonk": [
        "{author} gently bonks {target} on the head! *bonk* 🔨",
        "Bop! {author} gives {target} a light bonk~ behave! 💫",
        "{author} reaches over and— *bonk* — right on {target}'s head!",
        "No misbehaving! {author} bonks {target}~ 🌸",
    ],
    "blush": [
        "{author} turns bright red and hides their face~ 😳",
        "O-oh... {author} is blushing so hard right now! 🌸",
        "{author}'s cheeks turn the softest shade of pink~ 💕",
        "{author} goes full tomato from embarrassment~ 🍅",
    ],
    "cuddle": [
        "{author} curls up and cuddles with {target}~ so warm! 🥰",
        "Soft and cozy — {author} pulls {target} in for a long cuddle~ 💤",
        "{author} snuggles right up to {target}~ 🌙",
        "{author} and {target} cuddle together~ so adorable! 💗",
    ],
    "poke": [
        "{author} pokes {target}~ hey, are you there? 👉",
        "*poke poke* — {author} nudges {target} playfully!",
        "{author} gives {target} a curious little poke~ 🌸",
        "Heyyy~ {author} pokes {target} repeatedly until they respond!",
    ],
}

RP_COLORS: dict[str, int] = {
    "hug":    config.PASTEL_PINK,
    "pat":    config.PASTEL_PURPLE,
    "kiss":   config.PASTEL_PINK,
    "bonk":   config.PASTEL_PEACH,
    "blush":  config.PASTEL_PINK,
    "cuddle": config.PASTEL_PURPLE,
    "poke":   config.PASTEL_BLUE,
}

RP_EMOJI_KEYS: dict[str, str] = {
    "hug":    "hug",
    "pat":    "pat",
    "kiss":   "kiss",
    "bonk":   "bonk",
    "blush":  "blush",
    "cuddle": "cuddle",
    "poke":   "poke",
}

_INSTALLS = app_commands.allowed_installs(guilds=True, users=True)
_CONTEXTS = app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)


async def _fetch_gif(action: str) -> str | None:
    nekos_action = _NEKOS_ACTION_MAP.get(action, action)
    async with aiohttp.ClientSession() as session:
        try:
            url = NEKOS_BEST_BASE.format(action=nekos_action)
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("results", [])
                    if results:
                        return results[0].get("url")
        except Exception:
            pass

        try:
            url = WAIFU_PICS_BASE.format(action=action)
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("url")
        except Exception:
            pass

    return None


def _build_rp_container(
    action: str,
    author: discord.Member | discord.User,
    target: discord.Member | discord.User | None,
    emoji_loader: EmojiLoader,
    gif_url: str | None = None,
    back_button: discord.ui.Button | None = None,
) -> discord.ui.Container:
    """Build the RP result container, optionally embedding a back-button inside it."""
    icon = emoji_loader.get(RP_EMOJI_KEYS[action])
    sparkle = emoji_loader.get("sparkle")
    ribbon = emoji_loader.get("ribbon")
    color = RP_COLORS.get(action, config.PASTEL_PINK)

    text = random.choice(RP_LINES[action]).format(
        author=author.mention,
        target=target.mention if target else "the air",
    )
    footer = f"{ribbon} *+1 {action} added to stats!*"

    children: list[discord.ui.Component] = [
        discord.ui.TextDisplay(f"## {icon} {action.title()} {sparkle}\n\n{text}"),
    ]

    if gif_url:
        children.append(
            discord.ui.MediaGallery(
                discord.MediaGalleryItem(media=discord.UnfurledMediaItem(url=gif_url))
            )
        )

    children.append(discord.ui.Separator())
    children.append(discord.ui.TextDisplay(footer))

    if back_button is not None:
        children.append(discord.ui.ActionRow(back_button))

    return discord.ui.Container(*children, accent_color=discord.Color(color))


def _build_rp_view(
    action: str,
    author: discord.Member | discord.User,
    target: discord.Member | discord.User | None,
    gif_url: str | None,
    emoji_loader: EmojiLoader,
    *,
    include_back: bool = True,
) -> discord.ui.LayoutView:
    """Build the full LayoutView for an RP result, back-button inside the container."""
    back_button: discord.ui.Button | None = None

    if include_back and target is not None and target.id != author.id and action in _BACK_LABELS:
        label, emoji = _BACK_LABELS[action]
        back_button = discord.ui.Button(
            label=label,
            emoji=emoji,
            style=discord.ButtonStyle.primary,
            custom_id=f"rp_back:{action}:{author.id}:{target.id}",
        )

    container = _build_rp_container(action, author, target, emoji_loader, gif_url, back_button)
    lv = discord.ui.LayoutView(timeout=None)
    lv.add_item(container)
    return lv


def _build_action_picker(
    target: discord.Member | discord.User,
    emoji_loader: EmojiLoader,
) -> discord.ui.LayoutView:
    """Ephemeral CV2 layout — action select inside the container."""
    flower = emoji_loader.get("flower")
    sparkle = emoji_loader.get("sparkle")

    select = discord.ui.Select(
        placeholder="🌸 Pick an action…",
        custom_id=f"rp_action_select:{target.id}",
        options=[
            discord.SelectOption(label=label, value=action, emoji=emoji)
            for action, label, emoji in _SELECT_ACTIONS
        ],
    )

    container = discord.ui.Container(
        discord.ui.Section(
            discord.ui.TextDisplay(
                f"## {flower} Choose an action\n\n"
                f"What would you like to do with {target.mention}? {sparkle}"
            ),
            accessory=discord.ui.Thumbnail(
                media=discord.UnfurledMediaItem(url=str(target.display_avatar.url))
            ),
        ),
        discord.ui.Separator(),
        discord.ui.ActionRow(select),
        accent_color=discord.Color(config.PASTEL_PINK),
    )

    lv = discord.ui.LayoutView(timeout=120)
    lv.add_item(container)
    return lv


class RP(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._ctx_menus: list[app_commands.ContextMenu] = []
        self._register_context_menus()

    def _loader(self) -> EmojiLoader:
        cog = self.bot.get_cog("EmojiLoader")
        assert isinstance(cog, EmojiLoader)
        return cog

    def _register_context_menus(self) -> None:
        _installs = app_commands.AppInstallationType(guild=True, user=True)
        _contexts = app_commands.AppCommandContext(
            guild=True, dm_channel=True, private_channel=True
        )
        menu = app_commands.ContextMenu(
            name="🌸 Actions",
            callback=self._ctx_actions,
            allowed_installs=_installs,
            allowed_contexts=_contexts,
        )
        self.bot.tree.add_command(menu)
        self._ctx_menus.append(menu)

    async def cog_unload(self) -> None:
        for menu in self._ctx_menus:
            self.bot.tree.remove_command(menu.name, type=menu.type)

    # ── context menu ──────────────────────────────────────────────────────────

    async def _ctx_actions(
        self, interaction: discord.Interaction, member: discord.User
    ) -> None:
        if member.id == interaction.user.id:
            await interaction.response.send_message(
                "You can't pick an action targeting yourself~ 🌸",
                ephemeral=True,
            )
            return

        loader = self._loader()
        lv = _build_action_picker(member, loader)
        await interaction.response.send_message(view=lv, ephemeral=True)

    # ── persistent interaction handler ────────────────────────────────────────

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction) -> None:
        if interaction.type != discord.InteractionType.component:
            return
        data = interaction.data or {}
        custom_id: str = data.get("custom_id", "")

        if custom_id.startswith("rp_action_select:"):
            await self._handle_action_select(interaction, custom_id, data)
        elif custom_id.startswith("rp_back:"):
            await self._handle_back_button(interaction, custom_id)

    async def _handle_action_select(
        self,
        interaction: discord.Interaction,
        custom_id: str,
        data: dict,
    ) -> None:
        parts = custom_id.split(":")
        if len(parts) != 2:
            return
        target_id_str = parts[1]

        values = data.get("values", [])
        if not values:
            return
        action = values[0]
        if action not in RP_LINES:
            return

        try:
            target = await self.bot.fetch_user(int(target_id_str))
        except Exception:
            await interaction.response.send_message(
                "Couldn't find that user~ 🌸", ephemeral=True
            )
            return

        loader = self._loader()
        sparkle = loader.get("sparkle")

        # Update the ephemeral picker to confirm dispatch
        ack_container = discord.ui.Container(
            discord.ui.TextDisplay(
                f"{sparkle} Sending your **{action}** to {target.mention}…"
            ),
            accent_color=discord.Color(config.PASTEL_PINK),
        )
        ack_lv = discord.ui.LayoutView()
        ack_lv.add_item(ack_container)
        await interaction.response.edit_message(view=ack_lv)

        gif_url = await _fetch_gif(action)
        await database.log_rp(
            str(interaction.user.id),
            action,
            target_id_str,
            str(interaction.guild_id) if interaction.guild_id else None,
        )
        lv = _build_rp_view(action, interaction.user, target, gif_url, loader)
        await interaction.followup.send(view=lv, ephemeral=False)

    async def _handle_back_button(
        self,
        interaction: discord.Interaction,
        custom_id: str,
    ) -> None:
        parts = custom_id.split(":")
        if len(parts) != 4:
            return
        _, action, author_id_str, target_id_str = parts

        if str(interaction.user.id) != target_id_str:
            await interaction.response.send_message(
                "This button is only for the person who was targeted~ 🌸",
                ephemeral=True,
            )
            return

        loader = self._loader()

        # Disable the button on the original message
        if interaction.message is not None:
            try:
                orig_author = await self.bot.fetch_user(int(author_id_str))
            except Exception:
                orig_author = interaction.user

            disabled_btn = discord.ui.Button(
                label=_BACK_LABELS[action][0],
                emoji=_BACK_LABELS[action][1],
                style=discord.ButtonStyle.secondary,
                custom_id=custom_id,
                disabled=True,
            )
            orig_container = _build_rp_container(
                action, orig_author, interaction.user, loader, back_button=disabled_btn
            )
            disabled_lv = discord.ui.LayoutView(timeout=None)
            disabled_lv.add_item(orig_container)
            try:
                await interaction.message.edit(view=disabled_lv)
            except Exception:
                pass

        try:
            new_target = await self.bot.fetch_user(int(author_id_str))
        except Exception:
            new_target = None

        gif_url = await _fetch_gif(action)
        await database.log_rp(
            str(interaction.user.id),
            action,
            author_id_str,
            str(interaction.guild_id) if interaction.guild_id else None,
        )
        # Reply without back-button to stop the chain
        lv = _build_rp_view(
            action, interaction.user, new_target, gif_url, loader, include_back=False
        )
        await interaction.response.send_message(view=lv)

    # ── cog-level error handler ───────────────────────────────────────────────

    async def cog_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        # Unwrap HybridCommandError / CommandInvokeError to get the real cause
        original: BaseException = error
        while hasattr(original, "original"):
            original = original.original  # type: ignore[union-attr]

        # Interaction expired (10062) — Discord already dropped the token,
        # there is no channel to respond to, so just log and return silently.
        if isinstance(original, discord.NotFound) and getattr(original, "code", None) == 10062:
            import console as _console
            _console.get_logger("cogs.rp").warning(
                "Interaction expired: cmd=%s user=%s", ctx.command, ctx.author
            )
            return

        loader = self._loader()
        cross = loader.get("cross")
        ribbon = loader.get("ribbon")

        if isinstance(error, commands.MissingRequiredArgument):
            container = discord.ui.Container(
                discord.ui.TextDisplay(
                    f"## {cross} Missing argument\n"
                    f"`{error.param.name}` is required for this command.\n\n"
                    f"{ribbon} *Example:* `mochi {ctx.command} @user`"
                ),
                accent_color=discord.Color(config.PASTEL_PEACH),
            )
        elif isinstance(error, commands.BadArgument):
            container = discord.ui.Container(
                discord.ui.TextDisplay(
                    f"## {cross} Couldn't find that user\n"
                    "Make sure you're mentioning a valid user~ 🌸"
                ),
                accent_color=discord.Color(config.PASTEL_PEACH),
            )
        elif isinstance(error, commands.NoPrivateMessage):
            container = discord.ui.Container(
                discord.ui.TextDisplay(
                    f"## {cross} Server only\n"
                    "This command can only be used inside a server."
                ),
                accent_color=discord.Color(config.PASTEL_PEACH),
            )
        else:
            import console as _console
            _console.get_logger("cogs.rp").error(
                "Unhandled RP error: cmd=%s error=%s", ctx.command, error
            )
            container = discord.ui.Container(
                discord.ui.TextDisplay(
                    f"## {cross} Something went wrong\n"
                    "An unexpected error occurred. Please try again~ 🌸"
                ),
                accent_color=discord.Color(config.PASTEL_PEACH),
            )

        lv = discord.ui.LayoutView()
        lv.add_item(container)
        try:
            await ctx.send(view=lv, ephemeral=True)
        except discord.HTTPException:
            pass

    # ── hybrid commands ────────────────────────────────────────────────────────

    async def _send_rp(
        self,
        ctx: commands.Context,
        action: str,
        target: discord.User | None = None,
    ) -> None:
        # Defer immediately so Discord doesn't drop the interaction while we
        # fetch the GIF (which can take up to 5 s and would cause a 10062 error).
        await ctx.defer()

        loader = self._loader()
        gif_url = await _fetch_gif(action)
        await database.log_rp(
            str(ctx.author.id),
            action,
            str(target.id) if target else None,
            str(ctx.guild.id) if ctx.guild else None,
        )
        lv = _build_rp_view(action, ctx.author, target, gif_url, loader)
        await ctx.send(view=lv)

    @commands.hybrid_command(name="hug", description="Give someone a warm hug! 🫂")
    @app_commands.describe(target="Who to hug")
    @_INSTALLS
    @_CONTEXTS
    async def hug(self, ctx: commands.Context, target: discord.User | None = None) -> None:
        await self._send_rp(ctx, "hug", target)

    @commands.hybrid_command(name="pat", description="Pat someone on the head~ 🌸")
    @app_commands.describe(target="Who to pat")
    @_INSTALLS
    @_CONTEXTS
    async def pat(self, ctx: commands.Context, target: discord.User | None = None) -> None:
        await self._send_rp(ctx, "pat", target)

    @commands.hybrid_command(name="kiss", description="Give someone a sweet kiss 💋")
    @app_commands.describe(target="Who to kiss")
    @_INSTALLS
    @_CONTEXTS
    async def kiss(self, ctx: commands.Context, target: discord.User | None = None) -> None:
        await self._send_rp(ctx, "kiss", target)

    @commands.hybrid_command(name="bonk", description="Bonk someone on the head! 🔨")
    @app_commands.describe(target="Who to bonk")
    @_INSTALLS
    @_CONTEXTS
    async def bonk(self, ctx: commands.Context, target: discord.User | None = None) -> None:
        await self._send_rp(ctx, "bonk", target)

    @commands.hybrid_command(name="blush", description="Express your blush 😳")
    @_INSTALLS
    @_CONTEXTS
    async def blush(self, ctx: commands.Context) -> None:
        await self._send_rp(ctx, "blush")

    @commands.hybrid_command(name="cuddle", description="Cuddle with someone 🥰")
    @app_commands.describe(target="Who to cuddle with")
    @_INSTALLS
    @_CONTEXTS
    async def cuddle(self, ctx: commands.Context, target: discord.User | None = None) -> None:
        await self._send_rp(ctx, "cuddle", target)

    @commands.hybrid_command(name="poke", description="Poke someone playfully 👉")
    @app_commands.describe(target="Who to poke")
    @_INSTALLS
    @_CONTEXTS
    async def poke(self, ctx: commands.Context, target: discord.User | None = None) -> None:
        await self._send_rp(ctx, "poke", target)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RP(bot))
