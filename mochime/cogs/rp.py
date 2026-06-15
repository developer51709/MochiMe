from __future__ import annotations

import random

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

import config
import database
from cogs.emoji_loader import EmojiLoader

# nekos.best — free, no-auth anime GIF API (primary)
NEKOS_BEST_BASE = "https://nekos.best/api/v2/{action}"

# waifu.pics — fallback
WAIFU_PICS_BASE = "https://api.waifu.pics/sfw/{action}"

# nekos.best uses different names for some actions
_NEKOS_ACTION_MAP: dict[str, str] = {
    "hug":    "hug",
    "pat":    "pat",
    "kiss":   "kiss",
    "bonk":   "slap",
    "blush":  "blush",
    "cuddle": "cuddle",
    "poke":   "poke",
}

# "Action back" button labels + emoji per action
_BACK_LABELS: dict[str, tuple[str, str]] = {
    "hug":    ("Hug back",    "🫂"),
    "pat":    ("Pat back",    "🌸"),
    "kiss":   ("Kiss back",   "💋"),
    "bonk":   ("Bonk back",   "🔨"),
    "cuddle": ("Cuddle back", "🥰"),
    "poke":   ("Poke back",   "👉"),
}

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

# Decorators for user-installed app + DM support
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
) -> discord.ui.Container:
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

    return discord.ui.Container(*children, accent_color=discord.Color(color))


def _build_rp_view(
    action: str,
    author: discord.Member | discord.User,
    target: discord.Member | discord.User | None,
    container: discord.ui.Container,
) -> discord.ui.LayoutView:
    """Wrap the container in a LayoutView, adding a back-button when there's a target."""
    lv = discord.ui.LayoutView(timeout=None)

    if target is not None and target.id != author.id and action in _BACK_LABELS:
        label, emoji = _BACK_LABELS[action]
        btn = discord.ui.Button(
            label=label,
            emoji=emoji,
            style=discord.ButtonStyle.primary,
            custom_id=f"rp_back:{action}:{author.id}:{target.id}",
        )
        ar = discord.ui.ActionRow(btn)
        container.add_item(ar)

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
        menus = [
            app_commands.ContextMenu(
                name="🫂 Hug",    callback=self._ctx_hug,
                allowed_installs=_installs, allowed_contexts=_contexts,
            ),
            app_commands.ContextMenu(
                name="🌸 Pat",    callback=self._ctx_pat,
                allowed_installs=_installs, allowed_contexts=_contexts,
            ),
            app_commands.ContextMenu(
                name="💋 Kiss",   callback=self._ctx_kiss,
                allowed_installs=_installs, allowed_contexts=_contexts,
            ),
            app_commands.ContextMenu(
                name="🔨 Bonk",   callback=self._ctx_bonk,
                allowed_installs=_installs, allowed_contexts=_contexts,
            ),
            app_commands.ContextMenu(
                name="🥰 Cuddle", callback=self._ctx_cuddle,
                allowed_installs=_installs, allowed_contexts=_contexts,
            ),
            app_commands.ContextMenu(
                name="👉 Poke",   callback=self._ctx_poke,
                allowed_installs=_installs, allowed_contexts=_contexts,
            ),
        ]
        for menu in menus:
            self.bot.tree.add_command(menu)
            self._ctx_menus.append(menu)

    async def cog_unload(self) -> None:
        for menu in self._ctx_menus:
            self.bot.tree.remove_command(menu.name, type=menu.type)

    # ── persistent button handler ──────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction) -> None:
        if interaction.type != discord.InteractionType.component:
            return
        data = interaction.data or {}
        custom_id: str = data.get("custom_id", "")
        if not custom_id.startswith("rp_back:"):
            return

        parts = custom_id.split(":")
        if len(parts) != 4:
            return
        _, action, author_id_str, target_id_str = parts

        # Only the original target can press this button
        if str(interaction.user.id) != target_id_str:
            await interaction.response.send_message(
                "This button is only for the person who was hugged~ 🌸",
                ephemeral=True,
            )
            return

        # Fetch the original author to use as the new target
        try:
            new_target = await self.bot.fetch_user(int(author_id_str))
        except Exception:
            new_target = None

        loader = self._loader()
        gif_url = await _fetch_gif(action)
        container = _build_rp_container(action, interaction.user, new_target, loader, gif_url)
        await database.log_rp(
            str(interaction.user.id),
            action,
            author_id_str,
            str(interaction.guild_id) if interaction.guild_id else None,
        )
        lv = _build_rp_view(action, interaction.user, new_target, container)
        await interaction.response.send_message(view=lv)

    # ── context menus ──────────────────────────────────────────────────────────

    async def _send_rp_ctx(
        self,
        interaction: discord.Interaction,
        action: str,
        target: discord.Member | discord.User,
    ) -> None:
        loader = self._loader()
        gif_url = await _fetch_gif(action)
        container = _build_rp_container(action, interaction.user, target, loader, gif_url)
        await database.log_rp(
            str(interaction.user.id),
            action,
            str(target.id),
            str(interaction.guild_id) if interaction.guild_id else None,
        )
        lv = _build_rp_view(action, interaction.user, target, container)
        await interaction.response.send_message(view=lv)

    async def _ctx_hug(self, interaction: discord.Interaction, member: discord.User) -> None:
        await self._send_rp_ctx(interaction, "hug", member)

    async def _ctx_pat(self, interaction: discord.Interaction, member: discord.User) -> None:
        await self._send_rp_ctx(interaction, "pat", member)

    async def _ctx_kiss(self, interaction: discord.Interaction, member: discord.User) -> None:
        await self._send_rp_ctx(interaction, "kiss", member)

    async def _ctx_bonk(self, interaction: discord.Interaction, member: discord.User) -> None:
        await self._send_rp_ctx(interaction, "bonk", member)

    async def _ctx_cuddle(self, interaction: discord.Interaction, member: discord.User) -> None:
        await self._send_rp_ctx(interaction, "cuddle", member)

    async def _ctx_poke(self, interaction: discord.Interaction, member: discord.User) -> None:
        await self._send_rp_ctx(interaction, "poke", member)

    # ── hybrid commands ────────────────────────────────────────────────────────

    async def _send_rp(
        self,
        ctx: commands.Context,
        action: str,
        target: discord.User | None = None,
    ) -> None:
        loader = self._loader()
        gif_url = await _fetch_gif(action)
        container = _build_rp_container(action, ctx.author, target, loader, gif_url)
        await database.log_rp(
            str(ctx.author.id),
            action,
            str(target.id) if target else None,
            str(ctx.guild.id) if ctx.guild else None,
        )
        lv = _build_rp_view(action, ctx.author, target, container)
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
