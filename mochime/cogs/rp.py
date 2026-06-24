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

# MediaGallery component type integer (Discord CV2 spec)
_MEDIA_GALLERY_TYPE = 12


def _extract_gif_url(message: discord.Message) -> str | None:
    """Walk a CV2 message's component tree and return the first MediaGallery URL."""

    def _type_val(comp: object) -> int | None:
        t = getattr(comp, "type", None)
        if isinstance(t, int):
            return t
        if hasattr(t, "value"):
            return int(t.value)
        return None

    def _walk(items: list) -> str | None:
        for comp in items:
            if _type_val(comp) == _MEDIA_GALLERY_TYPE:
                for item in getattr(comp, "items", []):
                    media = getattr(item, "media", None)
                    url = getattr(media, "url", None) or getattr(media, "proxy_url", None)
                    if url and str(url).startswith("http"):
                        return str(url)
            for attr in ("children", "components"):
                sub = getattr(comp, attr, None)
                if sub:
                    result = _walk(sub)
                    if result:
                        return result
        return None

    try:
        return _walk(message.components)
    except Exception:
        return None

_NEKOS_ACTION_MAP: dict[str, str] = {
    "hug":      "hug",
    "pat":      "pat",
    "kiss":     "kiss",
    "bonk":     "slap",
    "blush":    "blush",
    "cuddle":   "cuddle",
    "poke":     "poke",
    "wave":     "wave",
    "bite":     "bite",
    "nuzzle":   "nuzzle",
    "nom":      "nom",
    "tickle":   "tickle",
    "dance":    "dance",
    "cry":      "cry",
    "highfive": "highfive",
    "wink":     "wink",
    "pout":     "pout",
    "laugh":    "laugh",
    "sleep":    "sleep",
    "smug":     "smug",
}

_BACK_LABELS: dict[str, tuple[str, str]] = {
    "hug":      ("Hug back",       "hug"),
    "pat":      ("Pat back",       "pat"),
    "kiss":     ("Kiss back",      "kiss"),
    "bonk":     ("Bonk back",      "bonk"),
    "cuddle":   ("Cuddle back",    "cuddle"),
    "poke":     ("Poke back",      "poke"),
    "wave":     ("Wave back",      "wave"),
    "bite":     ("Bite back",      "bite"),
    "nuzzle":   ("Nuzzle back",    "nuzzle"),
    "nom":      ("Nom back",       "nom"),
    "tickle":   ("Tickle back",    "tickle"),
    "dance":    ("Dance back",     "dance"),
    "highfive": ("High five back", "highfive"),
    "wink":     ("Wink back",      "wink"),
}

# Actions available in the context-menu select
_SELECT_ACTIONS: list[tuple[str, str, str]] = [
    ("hug",      "Hug",       "hug"),
    ("pat",      "Pat",       "pat"),
    ("kiss",     "Kiss",      "kiss"),
    ("bonk",     "Bonk",      "bonk"),
    ("cuddle",   "Cuddle",    "cuddle"),
    ("poke",     "Poke",      "poke"),
    ("wave",     "Wave",      "wave"),
    ("bite",     "Bite",      "bite"),
    ("nuzzle",   "Nuzzle",    "nuzzle"),
    ("nom",      "Nom",       "nom"),
    ("tickle",   "Tickle",    "tickle"),
    ("dance",    "Dance",     "dance"),
    ("highfive", "High Five", "highfive"),
    ("wink",     "Wink",      "wink"),
    ("pout",     "Pout",      "pout"),
    ("laugh",    "Laugh",     "laugh"),
    ("smug",     "Smug",      "smug"),
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
    "wave": [
        "{author} waves cheerfully at {target}~ 👋",
        "Hey! {author} gives {target} the friendliest wave~ 🌸",
        "{author} catches {target}'s eye and waves with a big smile! 💕",
        "*wave wave* — {author} waves at {target} with both hands~ ✨",
    ],
    "bite": [
        "{author} playfully nibbles on {target}'s arm! 😤",
        "Nom! {author} gives {target} a cheeky little bite~ 🌸",
        "{author} gently chomps {target}~ it's oddly adorable!",
        "*chomp!* — {author} bites {target} playfully! 💕",
    ],
    "nuzzle": [
        "{author} nuzzles up against {target} softly~ 🥰",
        "So warm! {author} nuzzles into {target}'s shoulder~ 💕",
        "{author} curls up and nuzzles {target} gently~ 🌸",
        "*nuzzle nuzzle* — {author} buries their face against {target}~ ✨",
    ],
    "nom": [
        "{author} noms on {target}~ you're too cute not to! 😋",
        "Nom nom nom! {author} can't stop eating {target}! 🌸",
        "{author} takes a gentle nibble of {target}~ strangely adorable!",
        "*om nom nom* — {author} declares {target} delicious~ ✨",
    ],
    "tickle": [
        "{author} tickles {target} mercilessly~ stop laughing! 🤭",
        "Ha ha ha! {author} finds all of {target}'s ticklish spots~ 🌸",
        "{author} sneaks up and tickles {target}~ gotcha! 💕",
        "{target} didn't see it coming — {author} launches a tickle attack~ ✨",
    ],
    "dance": [
        "{author} grabs {target}'s hand and twirls them~ let's dance! 💃",
        "*spins* — {author} dances with {target} under the stars~ ✨",
        "{author} challenges {target} to a dance-off! 🌸",
        "The music starts and {author} sweeps {target} into a waltz~ 💕",
    ],
    "cry": [
        "{author} starts crying into {target}'s shoulder~ 😢",
        "*sob sob* — {author} tears up and clings to {target}~ 🌸",
        "{author} wells up with tears and hugs {target} for comfort~ 💕",
        "The waterworks are on! {author} cries dramatically at {target}~ ✨",
    ],
    "highfive": [
        "{author} goes for a high five with {target}~ nice! 🙌",
        "SLAP! {author} lands a perfect high five on {target}~ 🌸",
        "{author} holds up a hand for {target}~ don't leave them hanging! 💕",
        "Team effort! {author} and {target} share a satisfying high five~ ✨",
    ],
    "wink": [
        "{author} throws a cheeky wink at {target}~ 😉",
        "Heyyy~ {author} winks playfully at {target}! 🌸",
        "{author} catches {target}'s eye and gives a little wink~ 💕",
        "*wink* — {author} grins at {target}~ so mysterious~ ✨",
    ],
    "pout": [
        "{author} pouts and stares at {target} with big puppy eyes~ 😮",
        "That's not fair! {author} pouts dramatically at {target}~ 🌸",
        "{author} crosses their arms and gives {target} the full pout treatment~ 💕",
        "{target} made {author} pout! Look what you did~ ✨",
    ],
    "laugh": [
        "{author} bursts out laughing at {target}~ they can't help it! 😂",
        "Ha ha ha! {author} doubles over because of {target}~ 🌸",
        "{author} points at {target} and cackles~ too funny! 💕",
        "{target} has {author} in absolute stitches~ ✨",
    ],
    "sleep": [
        "{author} curls up next to {target} and immediately falls asleep~ 😴",
        "zzzz... {author} dozes off on {target}'s shoulder~ 🌸",
        "{author} falls fast asleep, using {target} as a pillow~ 💕",
        "Five more minutes... {author} passes out against {target}~ ✨",
    ],
    "smug": [
        "{author} gives {target} the smuggest look ever~ 😏",
        "{author} crosses their arms and smirks at {target}~ I told you so!",
        "Look at that face! {author} is absolutely smug at {target}~ 🌸",
        "{target} can't handle how smug {author} is right now~ ✨",
    ],
}

RP_COLORS: dict[str, int] = {
    "hug":      config.PASTEL_PINK,
    "pat":      config.PASTEL_PURPLE,
    "kiss":     config.PASTEL_PINK,
    "bonk":     config.PASTEL_PEACH,
    "blush":    config.PASTEL_PINK,
    "cuddle":   config.PASTEL_PURPLE,
    "poke":     config.PASTEL_BLUE,
    "wave":     config.PASTEL_BLUE,
    "bite":     config.PASTEL_PEACH,
    "nuzzle":   config.PASTEL_PINK,
    "nom":      config.PASTEL_YELLOW,
    "tickle":   config.PASTEL_GREEN,
    "dance":    config.PASTEL_PURPLE,
    "cry":      config.PASTEL_BLUE,
    "highfive": config.PASTEL_YELLOW,
    "wink":     config.PASTEL_PINK,
    "pout":     config.PASTEL_PEACH,
    "laugh":    config.PASTEL_YELLOW,
    "sleep":    config.PASTEL_LAVENDER,
    "smug":     config.PASTEL_PURPLE,
}

RP_EMOJI_KEYS: dict[str, str] = {
    "hug":      "hug",
    "pat":      "pat",
    "kiss":     "kiss",
    "bonk":     "bonk",
    "blush":    "blush",
    "cuddle":   "cuddle",
    "poke":     "poke",
    "wave":     "wave",
    "bite":     "bite",
    "nuzzle":   "nuzzle",
    "nom":      "nom",
    "tickle":   "tickle",
    "dance":    "dance",
    "cry":      "cry",
    "highfive": "highfive",
    "wink":     "wink",
    "pout":     "pout",
    "laugh":    "laugh",
    "sleep":    "sleep",
    "smug":     "smug",
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
        label, emoji_key = _BACK_LABELS[action]
        back_button = discord.ui.Button(
            label=label,
            emoji=emoji_loader.get(emoji_key),
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
            discord.SelectOption(label=label, value=action, emoji=emoji_loader.get(emoji_key))
            for action, label, emoji_key in _SELECT_ACTIONS
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

        # Defer immediately — gif fetch can take up to 5 s and would cause
        # a 10062 "Unknown interaction" error if we respond too late.
        await interaction.response.defer()

        loader = self._loader()

        # Disable the button on the original message, keeping the gif intact
        if interaction.message is not None:
            # Extract the gif URL already displayed so we don't lose it
            existing_gif = _extract_gif_url(interaction.message)

            try:
                orig_author = await self.bot.fetch_user(int(author_id_str))
            except Exception:
                orig_author = interaction.user

            disabled_btn = discord.ui.Button(
                label=_BACK_LABELS[action][0],
                emoji=loader.get(_BACK_LABELS[action][1]),
                style=discord.ButtonStyle.secondary,
                custom_id=custom_id,
                disabled=True,
            )
            orig_container = _build_rp_container(
                action, orig_author, interaction.user, loader,
                gif_url=existing_gif,      # preserve the original gif
                back_button=disabled_btn,
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
        # Reply without back-button to stop the chain; use followup after defer
        lv = _build_rp_view(
            action, interaction.user, new_target, gif_url, loader, include_back=False
        )
        await interaction.followup.send(view=lv)

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

    # ── helpers ────────────────────────────────────────────────────────────────

    async def _send_rp(
        self,
        ctx: commands.Context,
        action: str,
        target: discord.User | None = None,
    ) -> None:
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

    # ── /rp group ──────────────────────────────────────────────────────────────

    @commands.hybrid_group(
        name="rp",
        description="Cute anime roleplay actions~ 🎀",
        invoke_without_command=True,
    )
    @_INSTALLS
    @_CONTEXTS
    async def rp(self, ctx: commands.Context) -> None:
        if ctx.invoked_subcommand is None:
            loader = self._loader()
            flower = loader.get("flower")
            ribbon = loader.get("ribbon")
            container = discord.ui.Container(
                discord.ui.TextDisplay(
                    f"## {flower} Roleplay Commands\n\n"
                    f"{ribbon} Use `/rp <action> [@user]` to send a cute anime GIF!\n\n"
                    "**Actions:** `hug` `pat` `kiss` `bonk` `blush` `cuddle` `poke` "
                    "`wave` `bite` `nuzzle` `nom` `tickle` `dance` `cry` `highfive` "
                    "`wink` `pout` `laugh` `sleep` `smug`"
                ),
                accent_color=discord.Color(config.PASTEL_PINK),
            )
            lv = discord.ui.LayoutView()
            lv.add_item(container)
            await ctx.send(view=lv, ephemeral=True)

    @rp.command(name="hug", description="Give someone a warm hug! 🫂")
    @app_commands.describe(target="Who to hug")
    async def rp_hug(self, ctx: commands.Context, target: discord.User | None = None) -> None:
        await self._send_rp(ctx, "hug", target)

    @rp.command(name="pat", description="Pat someone on the head~ 🌸")
    @app_commands.describe(target="Who to pat")
    async def rp_pat(self, ctx: commands.Context, target: discord.User | None = None) -> None:
        await self._send_rp(ctx, "pat", target)

    @rp.command(name="kiss", description="Give someone a sweet kiss 💋")
    @app_commands.describe(target="Who to kiss")
    async def rp_kiss(self, ctx: commands.Context, target: discord.User | None = None) -> None:
        await self._send_rp(ctx, "kiss", target)

    @rp.command(name="bonk", description="Bonk someone on the head! 🔨")
    @app_commands.describe(target="Who to bonk")
    async def rp_bonk(self, ctx: commands.Context, target: discord.User | None = None) -> None:
        await self._send_rp(ctx, "bonk", target)

    @rp.command(name="blush", description="Express your blush 😳")
    async def rp_blush(self, ctx: commands.Context) -> None:
        await self._send_rp(ctx, "blush")

    @rp.command(name="cuddle", description="Cuddle with someone 🥰")
    @app_commands.describe(target="Who to cuddle with")
    async def rp_cuddle(self, ctx: commands.Context, target: discord.User | None = None) -> None:
        await self._send_rp(ctx, "cuddle", target)

    @rp.command(name="poke", description="Poke someone playfully 👉")
    @app_commands.describe(target="Who to poke")
    async def rp_poke(self, ctx: commands.Context, target: discord.User | None = None) -> None:
        await self._send_rp(ctx, "poke", target)

    @rp.command(name="wave", description="Wave at someone~ 👋")
    @app_commands.describe(target="Who to wave at")
    async def rp_wave(self, ctx: commands.Context, target: discord.User | None = None) -> None:
        await self._send_rp(ctx, "wave", target)

    @rp.command(name="bite", description="Give someone a playful bite! 😤")
    @app_commands.describe(target="Who to bite")
    async def rp_bite(self, ctx: commands.Context, target: discord.User | None = None) -> None:
        await self._send_rp(ctx, "bite", target)

    @rp.command(name="nuzzle", description="Nuzzle up to someone~ 🥰")
    @app_commands.describe(target="Who to nuzzle")
    async def rp_nuzzle(self, ctx: commands.Context, target: discord.User | None = None) -> None:
        await self._send_rp(ctx, "nuzzle", target)

    @rp.command(name="nom", description="Nom on someone~ 😋")
    @app_commands.describe(target="Who to nom on")
    async def rp_nom(self, ctx: commands.Context, target: discord.User | None = None) -> None:
        await self._send_rp(ctx, "nom", target)

    @rp.command(name="tickle", description="Tickle someone mercilessly! 🤭")
    @app_commands.describe(target="Who to tickle")
    async def rp_tickle(self, ctx: commands.Context, target: discord.User | None = None) -> None:
        await self._send_rp(ctx, "tickle", target)

    @rp.command(name="dance", description="Dance with someone~ 💃")
    @app_commands.describe(target="Who to dance with")
    async def rp_dance(self, ctx: commands.Context, target: discord.User | None = None) -> None:
        await self._send_rp(ctx, "dance", target)

    @rp.command(name="cry", description="Have a good cry~ 😢")
    @app_commands.describe(target="Cry on someone's shoulder (optional)")
    async def rp_cry(self, ctx: commands.Context, target: discord.User | None = None) -> None:
        await self._send_rp(ctx, "cry", target)

    @rp.command(name="highfive", description="High five someone! 🙌")
    @app_commands.describe(target="Who to high five")
    async def rp_highfive(self, ctx: commands.Context, target: discord.User | None = None) -> None:
        await self._send_rp(ctx, "highfive", target)

    @rp.command(name="wink", description="Throw a cheeky wink~ 😉")
    @app_commands.describe(target="Who to wink at")
    async def rp_wink(self, ctx: commands.Context, target: discord.User | None = None) -> None:
        await self._send_rp(ctx, "wink", target)

    @rp.command(name="pout", description="Show off your best pout~ 😮")
    @app_commands.describe(target="Who to pout at")
    async def rp_pout(self, ctx: commands.Context, target: discord.User | None = None) -> None:
        await self._send_rp(ctx, "pout", target)

    @rp.command(name="laugh", description="Burst out laughing! 😂")
    @app_commands.describe(target="Who or what you're laughing at")
    async def rp_laugh(self, ctx: commands.Context, target: discord.User | None = None) -> None:
        await self._send_rp(ctx, "laugh", target)

    @rp.command(name="sleep", description="Fall fast asleep~ 😴")
    @app_commands.describe(target="Fall asleep on someone (optional)")
    async def rp_sleep(self, ctx: commands.Context, target: discord.User | None = None) -> None:
        await self._send_rp(ctx, "sleep", target)

    @rp.command(name="smug", description="Give someone your smuggest look~ 😏")
    @app_commands.describe(target="Who to be smug at")
    async def rp_smug(self, ctx: commands.Context, target: discord.User | None = None) -> None:
        await self._send_rp(ctx, "smug", target)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RP(bot))
