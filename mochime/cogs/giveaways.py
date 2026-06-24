"""
Giveaway system — CV2 containers, enter/manage buttons,
requirement checks, bonus entries, full persistence across restarts.
"""
from __future__ import annotations

import asyncio
import json
import random
import re
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

import config
import console
import database
from cogs.emoji_loader import EmojiLoader

log = console.get_logger("cogs.giveaways")


# ── tiny helpers ──────────────────────────────────────────────────────────────

def _cv2(*items: discord.ui.Component) -> discord.ui.LayoutView:
    lv = discord.ui.LayoutView(timeout=None)
    for item in items:
        lv.add_item(item)
    return lv


def _e(loader: EmojiLoader | None, key: str, fallback: str) -> str:
    return loader.get(key) if loader else fallback


# ── duration parsing ──────────────────────────────────────────────────────────

_DUR_RE = re.compile(
    r"^\s*"
    r"(?:(\d+)\s*d(?:ays?)?)?\s*"
    r"(?:(\d+)\s*h(?:ours?)?)?\s*"
    r"(?:(\d+)\s*m(?:in(?:utes?)?)?)?\s*"
    r"(?:(\d+)\s*s(?:ec(?:onds?)?)?)?\s*$",
    re.IGNORECASE,
)


def _parse_duration(s: str) -> int | None:
    m = _DUR_RE.match(s.strip())
    if not m or not any(m.groups()):
        return None
    d, h, mi, sec = (int(x or 0) for x in m.groups())
    total = d * 86400 + h * 3600 + mi * 60 + sec
    return total if total > 0 else None


def _fmt_duration(seconds: int) -> str:
    parts: list[str] = []
    for unit, label in ((86400, "d"), (3600, "h"), (60, "m"), (1, "s")):
        if seconds >= unit:
            parts.append(f"{seconds // unit}{label}")
            seconds %= unit
    return " ".join(parts) if parts else "0s"


# ── CV2 view builders ─────────────────────────────────────────────────────────

def _build_active_view(
    row: dict,
    entry_count: int,
    *,
    loader: EmojiLoader | None = None,
) -> discord.ui.LayoutView:
    confetti = _e(loader, "confetti", "🎉")
    trophy   = _e(loader, "trophy",   "🏆")
    sparkle  = _e(loader, "sparkle",  "✨")
    star     = _e(loader, "star",     "⭐")
    moon     = _e(loader, "moon",     "🌙")
    bolt     = _e(loader, "bolt",     "⚡")
    settings = _e(loader, "settings", "⚙️")

    mid         = row["message_id"]
    prize       = row["prize"]
    description = row.get("description") or ""
    w_count     = row["winner_count"]
    ends_ts     = int(datetime.fromisoformat(row["ends_at"]).replace(tzinfo=timezone.utc).timestamp())
    host_id     = row["host_id"]
    req_roles   = json.loads(row.get("required_role_ids") or "[]")
    bonus_roles = json.loads(row.get("bonus_role_ids") or "[]")
    min_acc     = int(row.get("min_account_age") or 0)
    min_srv     = int(row.get("min_server_age") or 0)

    sections: list[str] = []

    # Header
    header = f"## {confetti} Giveaway\n### {prize}"
    if description:
        header += f"\n*{description}*"
    sections.append(header)

    # Core stats
    sections.append(
        f"{trophy} **Winners:** {w_count}\n"
        f"⏰ **Ends:** <t:{ends_ts}:R>\n"
        f"{bolt} **Entries:** {entry_count}"
    )

    # Requirements block
    req_lines: list[str] = []
    for rid in req_roles:
        req_lines.append(f"{moon} Role required: <@&{rid}>")
    if min_acc:
        req_lines.append(f"{moon} Account age: **{min_acc}+** days")
    if min_srv:
        req_lines.append(f"{moon} Server member: **{min_srv}+** days")
    if req_lines:
        sections.append("**Requirements:**\n" + "\n".join(req_lines))

    # Bonus entries block
    bon_lines: list[str] = []
    for br in bonus_roles:
        bon_lines.append(f"{star} <@&{br['role_id']}> → **{br['entries']}×** entries")
    if bon_lines:
        sections.append("**Bonus Entries:**\n" + "\n".join(bon_lines))

    sections.append(f"-# {sparkle} Hosted by <@{host_id}>")

    container = discord.ui.Container(
        discord.ui.TextDisplay("\n\n".join(sections)),
        discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
        discord.ui.ActionRow(
            discord.ui.Button(
                label=f"Enter  ·  {entry_count}",
                emoji=confetti,
                style=discord.ButtonStyle.primary,
                custom_id=f"giveaway_enter:{mid}",
            ),
            discord.ui.Button(
                label="Manage",
                emoji=settings,
                style=discord.ButtonStyle.secondary,
                custom_id=f"giveaway_manage:{mid}",
            ),
        ),
        accent_color=discord.Color(config.PASTEL_PINK),
    )
    return _cv2(container)


def _build_ended_view(
    row: dict,
    entry_count: int,
    winners: list[str],
    *,
    loader: EmojiLoader | None = None,
) -> discord.ui.LayoutView:
    ribbon  = _e(loader, "ribbon",  "🎀")
    trophy  = _e(loader, "trophy",  "🏆")
    sparkle = _e(loader, "sparkle", "✨")
    wand    = _e(loader, "wand",    "🪄")

    mid      = row["message_id"]
    prize    = row["prize"]
    host_id  = row["host_id"]
    ends_ts  = int(datetime.fromisoformat(row["ends_at"]).replace(tzinfo=timezone.utc).timestamp())
    w_label  = "Winners" if len(winners) != 1 else "Winner"

    winner_block = (
        "\n".join(f"• <@{uid}>" for uid in winners)
        if winners else "• *No eligible entries*"
    )

    body = (
        f"## {ribbon} Giveaway Ended\n### {prize}\n\n"
        f"{trophy} **{w_label}:**\n{winner_block}\n\n"
        f"🎫 **Total entries:** {entry_count}\n"
        f"📅 **Ended:** <t:{ends_ts}:R>\n\n"
        f"-# {sparkle} Hosted by <@{host_id}>"
    )

    container = discord.ui.Container(
        discord.ui.TextDisplay(body),
        discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
        discord.ui.ActionRow(
            discord.ui.Button(
                label="Giveaway Ended",
                emoji=ribbon,
                style=discord.ButtonStyle.secondary,
                custom_id=f"giveaway_ended:{mid}",
                disabled=True,
            ),
            discord.ui.Button(
                label="Reroll",
                emoji=wand,
                style=discord.ButtonStyle.primary,
                custom_id=f"giveaway_reroll:{mid}",
            ),
        ),
        accent_color=discord.Color(config.PASTEL_PURPLE),
    )
    return _cv2(container)


def _build_cancelled_view(
    row: dict,
    *,
    loader: EmojiLoader | None = None,
) -> discord.ui.LayoutView:
    cross   = _e(loader, "cross",   "❌")
    sparkle = _e(loader, "sparkle", "✨")
    ribbon  = _e(loader, "ribbon",  "🎀")

    mid     = row["message_id"]
    prize   = row["prize"]
    host_id = row["host_id"]

    container = discord.ui.Container(
        discord.ui.TextDisplay(
            f"## {ribbon} Giveaway Cancelled\n### {prize}\n\n"
            f"This giveaway was cancelled by a staff member.\n\n"
            f"-# {sparkle} Hosted by <@{host_id}>"
        ),
        discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
        discord.ui.ActionRow(
            discord.ui.Button(
                label="Cancelled",
                emoji=cross,
                style=discord.ButtonStyle.secondary,
                custom_id=f"giveaway_ended:{mid}",
                disabled=True,
            ),
        ),
        accent_color=discord.Color(config.PASTEL_PEACH),
    )
    return _cv2(container)


def _build_manage_panel(
    message_id: str,
    *,
    loader: EmojiLoader | None = None,
) -> discord.ui.LayoutView:
    settings = _e(loader, "settings", "⚙️")
    trophy   = _e(loader, "trophy",   "🏆")
    wand     = _e(loader, "wand",     "🪄")
    eye      = _e(loader, "eye",      "👁️")
    cross    = _e(loader, "cross",    "❌")

    container = discord.ui.Container(
        discord.ui.TextDisplay(
            f"## {settings} Giveaway Management\nChoose an action below~"
        ),
        discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
        discord.ui.ActionRow(
            discord.ui.Button(
                label="End Now",
                emoji=trophy,
                style=discord.ButtonStyle.success,
                custom_id=f"giveaway_mgmt_end:{message_id}",
            ),
            discord.ui.Button(
                label="Reroll",
                emoji=wand,
                style=discord.ButtonStyle.primary,
                custom_id=f"giveaway_mgmt_reroll:{message_id}",
            ),
            discord.ui.Button(
                label="View Entries",
                emoji=eye,
                style=discord.ButtonStyle.secondary,
                custom_id=f"giveaway_mgmt_entries:{message_id}",
            ),
            discord.ui.Button(
                label="Cancel",
                emoji=cross,
                style=discord.ButtonStyle.danger,
                custom_id=f"giveaway_mgmt_cancel:{message_id}",
            ),
        ),
        accent_color=discord.Color(config.PASTEL_LAVENDER),
    )
    return _cv2(container)


# ── winner selection helper ───────────────────────────────────────────────────

def _pick_winners(entries: list, count: int) -> list[str]:
    """Weighted random draw without replacement (bonus entries = extra tickets)."""
    pool: list[str] = []
    for e in entries:
        pool.extend([e["user_id"]] * int(e["entries"]))

    winners: list[str] = []
    remaining = list(pool)
    while len(winners) < count and remaining:
        chosen = random.choice(remaining)
        winners.append(chosen)
        remaining = [t for t in remaining if t != chosen]
    return winners


# ── Cog ───────────────────────────────────────────────────────────────────────

class Giveaways(commands.Cog):
    """Host cute pastel giveaways with requirements and bonus entries~ 🎉"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._tasks: dict[str, asyncio.Task] = {}

    async def cog_load(self) -> None:
        rows = await database.get_active_giveaways()
        now  = datetime.now(timezone.utc)
        for row in rows:
            ends_at = datetime.fromisoformat(row["ends_at"]).replace(tzinfo=timezone.utc)
            delay   = max(0.0, (ends_at - now).total_seconds())
            self._schedule_end(row["message_id"], delay, dict(row))
            log.info("Resumed giveaway %s (ends in %.0fs)", row["message_id"], delay)

    def _loader(self) -> EmojiLoader | None:
        return self.bot.get_cog("EmojiLoader")  # type: ignore[return-value]

    # ── scheduling ────────────────────────────────────────────────────────────

    def _schedule_end(self, message_id: str, delay: float, row: dict) -> None:
        if message_id in self._tasks:
            self._tasks[message_id].cancel()
        task = asyncio.create_task(self._end_after(message_id, delay, row))
        self._tasks[message_id] = task

    async def _end_after(self, message_id: str, delay: float, row: dict) -> None:
        try:
            await asyncio.sleep(delay)
            await self._conclude(message_id, row)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            log.error("Error ending giveaway %s: %s", message_id, exc)
        finally:
            self._tasks.pop(message_id, None)

    # ── conclusion logic ──────────────────────────────────────────────────────

    async def _conclude(self, message_id: str, row_hint: dict | None = None) -> list[str]:
        """Pick winners, persist, update message, announce. Returns winner IDs."""
        row = await database.get_giveaway(message_id)
        if not row or row["ended"]:
            return []

        loader  = self._loader()
        entries = await database.get_giveaway_entries(message_id)
        winners = _pick_winners(entries, row["winner_count"])

        await database.end_giveaway(message_id, json.dumps(winners))

        entry_count = len(entries)
        row_dict    = dict(row)
        row_dict["message_id"] = message_id

        try:
            channel = self.bot.get_channel(int(row["channel_id"]))
            if channel is None:
                channel = await self.bot.fetch_channel(int(row["channel_id"]))
            if isinstance(channel, discord.TextChannel):
                msg = await channel.fetch_message(int(message_id))
                await msg.edit(view=_build_ended_view(row_dict, entry_count, winners, loader=loader))

                confetti = _e(loader, "confetti", "🎉")
                trophy   = _e(loader, "trophy",   "🏆")
                sparkle  = _e(loader, "sparkle",  "✨")
                prize    = row["prize"]
                guild_id = row["guild_id"]
                ch_id    = row["channel_id"]
                jump     = f"https://discord.com/channels/{guild_id}/{ch_id}/{message_id}"

                if winners:
                    mentions  = " ".join(f"<@{uid}>" for uid in winners)
                    w_label   = "Winners" if len(winners) != 1 else "Winner"
                    ann_body  = (
                        f"## {confetti} Giveaway {w_label}!\n\n"
                        f"{trophy} Congratulations to {mentions}!\n"
                        f"You won **{prize}**! Please contact <@{row['host_id']}> to claim your prize~\n\n"
                        f"-# {sparkle} [Jump to giveaway]({jump})"
                    )
                else:
                    ann_body = (
                        f"## {confetti} Giveaway Ended\n\n"
                        f"*No eligible entries for **{prize}***~ Better luck next time!\n\n"
                        f"-# {sparkle} [Jump to giveaway]({jump})"
                    )

                ann = discord.ui.Container(
                    discord.ui.TextDisplay(ann_body),
                    accent_color=discord.Color(config.PASTEL_YELLOW),
                )
                await channel.send(view=_cv2(ann))
        except Exception as exc:
            log.error("Failed to finalise giveaway %s: %s", message_id, exc)

        return winners

    # ── requirement checks ────────────────────────────────────────────────────

    async def _check_requirements(
        self,
        interaction: discord.Interaction,
        row: dict,
    ) -> bool:
        loader = self._loader()
        cross  = _e(loader, "cross", "❌")
        moon   = _e(loader, "moon",  "🌙")

        member: discord.Member | None = None
        if interaction.guild:
            member = interaction.guild.get_member(interaction.user.id)
            if not member:
                try:
                    member = await interaction.guild.fetch_member(interaction.user.id)
                except Exception:
                    pass

        req_roles = json.loads(row.get("required_role_ids") or "[]")
        if req_roles and member:
            have    = {str(r.id) for r in member.roles}
            missing = [rid for rid in req_roles if rid not in have]
            if missing:
                mentions = ", ".join(f"<@&{rid}>" for rid in missing)
                c = discord.ui.Container(
                    discord.ui.TextDisplay(
                        f"## {cross} Requirements not met\n"
                        f"{moon} You need the {mentions} role{'s' if len(missing) > 1 else ''} to enter~ 🌸"
                    ),
                    accent_color=discord.Color(config.PASTEL_PEACH),
                )
                await interaction.response.send_message(view=_cv2(c), ephemeral=True)
                return False

        min_acc = int(row.get("min_account_age") or 0)
        if min_acc:
            age = (datetime.now(timezone.utc) - interaction.user.created_at).days
            if age < min_acc:
                c = discord.ui.Container(
                    discord.ui.TextDisplay(
                        f"## {cross} Requirements not met\n"
                        f"{moon} Your account must be at least **{min_acc} days** old~\n"
                        f"Your account is `{age}` day{'s' if age != 1 else ''} old. 🌸"
                    ),
                    accent_color=discord.Color(config.PASTEL_PEACH),
                )
                await interaction.response.send_message(view=_cv2(c), ephemeral=True)
                return False

        min_srv = int(row.get("min_server_age") or 0)
        if min_srv and member and member.joined_at:
            joined = member.joined_at.replace(tzinfo=timezone.utc)
            srv_age = (datetime.now(timezone.utc) - joined).days
            if srv_age < min_srv:
                c = discord.ui.Container(
                    discord.ui.TextDisplay(
                        f"## {cross} Requirements not met\n"
                        f"{moon} You must have been in the server for **{min_srv} days**~\n"
                        f"You've been here `{srv_age}` day{'s' if srv_age != 1 else ''}. 🌸"
                    ),
                    accent_color=discord.Color(config.PASTEL_PEACH),
                )
                await interaction.response.send_message(view=_cv2(c), ephemeral=True)
                return False

        return True

    def _count_bonus_entries(self, member: discord.Member | None, bonus_json: str) -> int:
        bonus_roles: list = json.loads(bonus_json or "[]")
        if not bonus_roles or not member:
            return 1
        have  = {str(r.id) for r in member.roles}
        total = 1
        for br in bonus_roles:
            if br["role_id"] in have:
                total += int(br["entries"]) - 1
        return max(1, total)

    def _is_staff(self, interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            return False
        m = interaction.guild.get_member(interaction.user.id)
        if not m:
            return False
        return m.guild_permissions.manage_guild or m.guild_permissions.administrator

    # ── /giveaway command ─────────────────────────────────────────────────────

    @commands.hybrid_command(name="giveaway", description="Start a giveaway~ 🎉")
    @app_commands.describe(
        prize="What are you giving away?",
        duration="Duration — e.g. 1d, 2h 30m, 1d 12h",
        winners="Number of winners (default: 1)",
        description="Optional extra details shown on the giveaway card",
        required_role="Role members must have to enter",
        bonus_role="Role that earns bonus entries",
        bonus_entries="Entries the bonus role receives (default: 2)",
        min_account_age="Minimum Discord account age in days",
        min_server_age="Minimum days the user must have been in this server",
        channel="Channel to post in (default: current channel)",
    )
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def giveaway(
        self,
        ctx: commands.Context,
        prize: str,
        duration: str,
        winners: int = 1,
        description: str | None = None,
        required_role: discord.Role | None = None,
        bonus_role: discord.Role | None = None,
        bonus_entries: int = 2,
        min_account_age: int | None = None,
        min_server_age: int | None = None,
        channel: discord.TextChannel | None = None,
    ) -> None:
        await ctx.defer(ephemeral=True)

        loader   = self._loader()
        cross    = _e(loader, "cross",    "❌")
        check    = _e(loader, "check",    "✅")
        confetti = _e(loader, "confetti", "🎉")

        assert ctx.guild is not None

        seconds = _parse_duration(duration)
        if not seconds:
            c = discord.ui.Container(
                discord.ui.TextDisplay(
                    f"## {cross} Invalid duration\n"
                    "Use formats like `1d`, `2h`, `30m`, `1d 12h 30m`~ 🌸"
                ),
                accent_color=discord.Color(config.PASTEL_PEACH),
            )
            await ctx.send(view=_cv2(c), ephemeral=True)
            return

        if not 1 <= winners <= 20:
            c = discord.ui.Container(
                discord.ui.TextDisplay(
                    f"## {cross} Invalid winner count\n"
                    "Winners must be between **1** and **20**~ 🌸"
                ),
                accent_color=discord.Color(config.PASTEL_PEACH),
            )
            await ctx.send(view=_cv2(c), ephemeral=True)
            return

        target = channel or (
            ctx.channel if isinstance(ctx.channel, discord.TextChannel) else None
        )
        if target is None:
            c = discord.ui.Container(
                discord.ui.TextDisplay(
                    f"## {cross} Invalid channel\nPlease specify a valid text channel~ 🌸"
                ),
                accent_color=discord.Color(config.PASTEL_PEACH),
            )
            await ctx.send(view=_cv2(c), ephemeral=True)
            return

        ends_at     = datetime.now(timezone.utc) + timedelta(seconds=seconds)
        ends_at_str = ends_at.isoformat()

        req_json   = json.dumps([str(required_role.id)] if required_role else [])
        bonus_json = json.dumps(
            [{"role_id": str(bonus_role.id), "entries": bonus_entries}]
            if bonus_role else []
        )

        row_hint: dict = {
            "message_id":       "pending",
            "prize":            prize,
            "description":      description,
            "winner_count":     winners,
            "ends_at":          ends_at_str,
            "host_id":          str(ctx.author.id),
            "required_role_ids": req_json,
            "bonus_role_ids":   bonus_json,
            "min_account_age":  min_account_age or 0,
            "min_server_age":   min_server_age or 0,
        }

        # Post with placeholder ID then edit with real ID
        msg = await target.send(view=_build_active_view(row_hint, 0, loader=loader))
        real_id              = str(msg.id)
        row_hint["message_id"] = real_id
        await msg.edit(view=_build_active_view(row_hint, 0, loader=loader))

        await database.create_giveaway(
            message_id=real_id,
            channel_id=str(target.id),
            guild_id=str(ctx.guild.id),
            host_id=str(ctx.author.id),
            prize=prize,
            description=description,
            winner_count=winners,
            ends_at=ends_at_str,
            required_role_ids=req_json,
            bonus_role_ids=bonus_json,
            min_account_age=min_account_age or 0,
            min_server_age=min_server_age or 0,
        )

        self._schedule_end(real_id, float(seconds), row_hint)

        c = discord.ui.Container(
            discord.ui.TextDisplay(
                f"## {check} Giveaway started!\n"
                f"{confetti} **{prize}** is live in {target.mention}~\n"
                f"Ends in **{_fmt_duration(seconds)}** · **{winners}** winner{'s' if winners != 1 else ''}."
            ),
            accent_color=discord.Color(config.PASTEL_GREEN),
        )
        await ctx.send(view=_cv2(c), ephemeral=True)

    # ── interaction dispatcher ────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction) -> None:
        if interaction.type != discord.InteractionType.component:
            return
        cid: str = (interaction.data or {}).get("custom_id", "")

        if cid.startswith("giveaway_enter:"):
            await self._on_enter(interaction, cid.split(":", 1)[1])
        elif cid.startswith("giveaway_manage:"):
            await self._on_manage_open(interaction, cid.split(":", 1)[1])
        elif cid.startswith("giveaway_mgmt_end:"):
            await self._on_mgmt_end(interaction, cid.split(":", 1)[1])
        elif cid.startswith(("giveaway_reroll:", "giveaway_mgmt_reroll:")):
            await self._on_reroll(interaction, cid.split(":", 1)[1])
        elif cid.startswith("giveaway_mgmt_cancel:"):
            await self._on_cancel(interaction, cid.split(":", 1)[1])
        elif cid.startswith("giveaway_mgmt_entries:"):
            await self._on_view_entries(interaction, cid.split(":", 1)[1])
        elif cid.startswith("giveaway_ended:"):
            await interaction.response.send_message(
                "This giveaway has already ended~ 🌸", ephemeral=True
            )

    # ── enter ─────────────────────────────────────────────────────────────────

    async def _on_enter(self, interaction: discord.Interaction, message_id: str) -> None:
        loader   = self._loader()
        cross    = _e(loader, "cross",    "❌")
        confetti = _e(loader, "confetti", "🎉")
        sparkle  = _e(loader, "sparkle",  "✨")
        check    = _e(loader, "check",    "✅")

        row = await database.get_giveaway(message_id)
        if not row or row["ended"]:
            await interaction.response.send_message(
                f"{cross} This giveaway has ended~ 🌸", ephemeral=True
            )
            return

        if not await self._check_requirements(interaction, dict(row)):
            return

        member = interaction.guild.get_member(interaction.user.id) if interaction.guild else None
        entries_to_add = self._count_bonus_entries(member, row["bonus_role_ids"] or "[]")

        existing = await database.get_giveaway_entry(message_id, str(interaction.user.id))
        if existing:
            e = int(existing["entries"])
            c = discord.ui.Container(
                discord.ui.TextDisplay(
                    f"## {confetti} Already entered!\n"
                    f"You're in with **{e}** {'entry' if e == 1 else 'entries'}~ {sparkle}"
                ),
                accent_color=discord.Color(config.PASTEL_BLUE),
            )
            await interaction.response.send_message(view=_cv2(c), ephemeral=True)
            return

        await database.add_giveaway_entry(message_id, str(interaction.user.id), entries_to_add)
        entry_count = await database.count_giveaway_entries(message_id)

        bonus_note = f" *(+{entries_to_add - 1} bonus!)*" if entries_to_add > 1 else ""
        c = discord.ui.Container(
            discord.ui.TextDisplay(
                f"## {check} You're entered!\n"
                f"You have **{entries_to_add}** {'entry' if entries_to_add == 1 else 'entries'}{bonus_note}~ {sparkle}\n"
                f"Good luck! 🌸"
            ),
            accent_color=discord.Color(config.PASTEL_GREEN),
        )
        await interaction.response.send_message(view=_cv2(c), ephemeral=True)

        try:
            row_dict = dict(row)
            row_dict["message_id"] = message_id
            if interaction.message:
                await interaction.message.edit(
                    view=_build_active_view(row_dict, entry_count, loader=loader)
                )
        except Exception:
            pass

    # ── manage panel ──────────────────────────────────────────────────────────

    async def _on_manage_open(self, interaction: discord.Interaction, message_id: str) -> None:
        if not self._is_staff(interaction):
            loader = self._loader()
            cross  = _e(loader, "cross", "❌")
            await interaction.response.send_message(
                f"{cross} You need **Manage Server** permission to manage giveaways~ 🌸",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            view=_build_manage_panel(message_id, loader=self._loader()),
            ephemeral=True,
        )

    # ── end now ───────────────────────────────────────────────────────────────

    async def _on_mgmt_end(self, interaction: discord.Interaction, message_id: str) -> None:
        if not self._is_staff(interaction):
            await interaction.response.send_message("No permission~ 🌸", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)

        if message_id in self._tasks:
            self._tasks[message_id].cancel()

        winners = await self._conclude(message_id)
        loader  = self._loader()
        check   = _e(loader, "check",  "✅")
        trophy  = _e(loader, "trophy", "🏆")

        w_text = " ".join(f"<@{uid}>" for uid in winners) if winners else "*No eligible entries*"
        c = discord.ui.Container(
            discord.ui.TextDisplay(
                f"## {check} Giveaway ended!\n"
                f"{trophy} **Winner{'s' if len(winners) != 1 else ''}:** {w_text}"
            ),
            accent_color=discord.Color(config.PASTEL_GREEN),
        )
        await interaction.followup.send(view=_cv2(c), ephemeral=True)

    # ── reroll ────────────────────────────────────────────────────────────────

    async def _on_reroll(self, interaction: discord.Interaction, message_id: str) -> None:
        if not self._is_staff(interaction):
            await interaction.response.send_message("No permission~ 🌸", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)

        loader  = self._loader()
        wand    = _e(loader, "wand",    "🪄")
        trophy  = _e(loader, "trophy",  "🏆")
        sparkle = _e(loader, "sparkle", "✨")
        cross   = _e(loader, "cross",   "❌")

        row = await database.get_giveaway(message_id)
        if not row:
            await interaction.followup.send(f"{cross} Giveaway not found~ 🌸", ephemeral=True)
            return

        entries = await database.get_giveaway_entries(message_id)
        winners = _pick_winners(entries, row["winner_count"])
        await database.end_giveaway(message_id, json.dumps(winners))

        row_dict               = dict(row)
        row_dict["message_id"] = message_id

        try:
            channel = self.bot.get_channel(int(row["channel_id"]))
            if channel is None:
                channel = await self.bot.fetch_channel(int(row["channel_id"]))
            if isinstance(channel, discord.TextChannel):
                msg = await channel.fetch_message(int(message_id))
                await msg.edit(
                    view=_build_ended_view(row_dict, len(entries), winners, loader=loader)
                )
                if winners:
                    mentions = " ".join(f"<@{uid}>" for uid in winners)
                    w_label  = "Winners" if len(winners) != 1 else "Winner"
                    jump     = (
                        f"https://discord.com/channels/{row['guild_id']}"
                        f"/{row['channel_id']}/{message_id}"
                    )
                    ann = discord.ui.Container(
                        discord.ui.TextDisplay(
                            f"## {wand} Rerolled!\n\n"
                            f"{trophy} New {w_label}: {mentions}!\n"
                            f"You won **{row['prize']}**~ Congratulations! {sparkle}\n\n"
                            f"-# [Jump to giveaway]({jump})"
                        ),
                        accent_color=discord.Color(config.PASTEL_YELLOW),
                    )
                    await channel.send(view=_cv2(ann))
        except Exception as exc:
            log.error("Reroll failed for %s: %s", message_id, exc)

        w_text = " ".join(f"<@{uid}>" for uid in winners) if winners else "*No eligible entries*"
        c = discord.ui.Container(
            discord.ui.TextDisplay(
                f"## {wand} Rerolled!\n"
                f"{trophy} New winner{'s' if len(winners) != 1 else ''}: {w_text}"
            ),
            accent_color=discord.Color(config.PASTEL_GREEN),
        )
        await interaction.followup.send(view=_cv2(c), ephemeral=True)

    # ── cancel ────────────────────────────────────────────────────────────────

    async def _on_cancel(self, interaction: discord.Interaction, message_id: str) -> None:
        if not self._is_staff(interaction):
            await interaction.response.send_message("No permission~ 🌸", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)

        loader = self._loader()
        check  = _e(loader, "check", "✅")
        cross  = _e(loader, "cross", "❌")

        row = await database.get_giveaway(message_id)
        if not row or row["ended"]:
            await interaction.followup.send(
                f"{cross} Giveaway not found or already ended~ 🌸", ephemeral=True
            )
            return

        if message_id in self._tasks:
            self._tasks[message_id].cancel()

        await database.cancel_giveaway(message_id)

        try:
            channel = self.bot.get_channel(int(row["channel_id"]))
            if isinstance(channel, discord.TextChannel):
                msg = await channel.fetch_message(int(message_id))
                row_dict               = dict(row)
                row_dict["message_id"] = message_id
                await msg.edit(view=_build_cancelled_view(row_dict, loader=loader))
        except Exception:
            pass

        c = discord.ui.Container(
            discord.ui.TextDisplay(
                f"## {check} Cancelled\nThe giveaway has been cancelled~ 🌸"
            ),
            accent_color=discord.Color(config.PASTEL_GREEN),
        )
        await interaction.followup.send(view=_cv2(c), ephemeral=True)

    # ── view entries ──────────────────────────────────────────────────────────

    async def _on_view_entries(
        self, interaction: discord.Interaction, message_id: str
    ) -> None:
        if not self._is_staff(interaction):
            await interaction.response.send_message("No permission~ 🌸", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)

        loader  = self._loader()
        eye     = _e(loader, "eye",     "👁️")
        bolt    = _e(loader, "bolt",    "⚡")
        sparkle = _e(loader, "sparkle", "✨")

        entries     = await database.get_giveaway_entries(message_id)
        total_tix   = sum(int(e["entries"]) for e in entries)
        shown       = entries[:20]

        if not entries:
            c = discord.ui.Container(
                discord.ui.TextDisplay(f"## {eye} Entries\nNo entries yet~ 🌸"),
                accent_color=discord.Color(config.PASTEL_LAVENDER),
            )
        else:
            lines = "\n".join(
                f"{bolt} <@{e['user_id']}> — "
                f"**{e['entries']}×** {'entry' if int(e['entries']) == 1 else 'entries'}"
                for e in shown
            )
            more = f"\n*…and {len(entries) - 20} more*" if len(entries) > 20 else ""
            c = discord.ui.Container(
                discord.ui.TextDisplay(
                    f"## {eye} Giveaway Entries\n"
                    f"**{len(entries)}** unique entrant{'s' if len(entries) != 1 else ''} · "
                    f"**{total_tix}** total ticket{'s' if total_tix != 1 else ''}\n\n"
                    f"{lines}{more}\n\n"
                    f"-# {sparkle} Bonus entries show as extra tickets"
                ),
                accent_color=discord.Color(config.PASTEL_LAVENDER),
            )
        await interaction.followup.send(view=_cv2(c), ephemeral=True)

    # ── error handler ─────────────────────────────────────────────────────────

    async def cog_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        loader = self._loader()
        cross  = _e(loader, "cross", "❌")

        if isinstance(error, commands.MissingPermissions):
            c = discord.ui.Container(
                discord.ui.TextDisplay(
                    f"## {cross} No permission\n"
                    "You need **Manage Server** permission to start giveaways~ 🌸"
                ),
                accent_color=discord.Color(config.PASTEL_PEACH),
            )
            try:
                await ctx.send(view=_cv2(c), ephemeral=True)
            except discord.HTTPException:
                pass
        elif isinstance(error, commands.NoPrivateMessage):
            try:
                await ctx.send(
                    f"{cross} Giveaways can only be used in a server~ 🌸", ephemeral=True
                )
            except discord.HTTPException:
                pass
        else:
            original: BaseException = error
            while hasattr(original, "original"):
                original = original.original  # type: ignore[union-attr]
            log.error("Giveaway command error: %s", original)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Giveaways(bot))
