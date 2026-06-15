# 🎨 MochiMe — Components v2 UI Guide

Discord Components v2 (CV2) is a newer message format that replaces legacy
embeds with a fully composable component tree. MochiMe uses CV2 **exclusively**.

---

## Component Types Used

### `Container`
The outermost wrapper for every MochiMe response. Supports an `accent_color`
(the coloured left border strip). Holds any number of child components.

```python
container = discord.ui.Container(
    discord.ui.TextDisplay("Hello!"),
    discord.ui.Separator(divider=True),
    discord.ui.ActionRow(
        discord.ui.Button(label="Click me", style=discord.ButtonStyle.primary)
    ),
    accent_color=discord.Color(0xFFB3C6),  # pastel pink
)
```

### `TextDisplay`
Renders a string of Markdown inside a container. Supports headings, bold,
italic, inline code, and mentions.

```python
discord.ui.TextDisplay("## Title\n**Bold** and *italic* and `code`")
```

### `Separator`
A visual divider. Set `divider=True` to show a horizontal rule.

```python
discord.ui.Separator(
    spacing=discord.SeparatorSpacing.small,  # or .large
    divider=True,
)
```

### `MediaGallery` + `MediaGalleryItem`
Renders one or more images/GIFs inline inside the container.

```python
discord.ui.MediaGallery(
    discord.MediaGalleryItem(
        media=discord.UnfurledMediaItem(url="https://example.com/image.gif")
    )
)
```

### `ActionRow`
A horizontal row of interactive components (buttons, select menus).

```python
discord.ui.ActionRow(
    discord.ui.Button(label="Confirm", style=discord.ButtonStyle.danger, custom_id="confirm"),
    discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary, custom_id="cancel"),
)
```

### `Section`
Groups a block of text with an optional accessory (e.g. a thumbnail image)
floated to the right.

```python
discord.ui.Section(
    discord.ui.TextDisplay("Some content here"),
    accessory=discord.ui.Thumbnail(media=discord.UnfurledMediaItem(url="...")),
)
```

---

## Sending CV2 Messages

All CV2 messages require the `is_components_v2` flag:

```python
# Slash command / interaction
await interaction.response.send_message(
    components=[container],
    flags=discord.MessageFlags(is_components_v2=True),
)

# Prefix command
await ctx.send(
    components=[container],
    flags=discord.MessageFlags(is_components_v2=True),
)

# Editing an existing CV2 message
await interaction.response.edit_message(
    components=[new_container],
)
```

> **Note:** You cannot mix CV2 components with a `content=` string or `embed=`
> in the same message. CV2 is an all-or-nothing format.

---

## MochiMe Colour Palette

| Name | Hex | Used for |
|---|---|---|
| Pastel Pink | `#FFB3C6` | RP · love · welcome |
| Pastel Purple | `#C9B1FF` | Profiles · help |
| Pastel Blue | `#B3D9FF` | Info · utility |
| Pastel Green | `#B3FFD9` | Success · confirmations |
| Pastel Yellow | `#FFF5B3` | Warnings |
| Pastel Peach | `#FFCDB3` | Errors · moderation |

```python
# In config.py
PASTEL_PINK   = 0xFFB3C6
PASTEL_PURPLE = 0xC9B1FF
PASTEL_BLUE   = 0xB3D9FF
PASTEL_GREEN  = 0xB3FFD9
PASTEL_YELLOW = 0xFFF5B3
PASTEL_PEACH  = 0xFFCDB3
```

---

## Adding a New CV2 Command

```python
from discord.ext import commands
import discord
import config
from cogs.emoji_loader import EmojiLoader

class MyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="greet", description="Say hello!")
    async def greet(self, ctx: commands.Context) -> None:
        loader: EmojiLoader = self.bot.get_cog("EmojiLoader")
        sparkle = loader.get("sparkle")   # application emoji or Unicode fallback

        container = discord.ui.Container(
            discord.ui.TextDisplay(
                f"## {sparkle} Hello, {ctx.author.mention}!\n"
                "Welcome to MochiMe 🌸"
            ),
            accent_color=discord.Color(config.PASTEL_PINK),
        )
        await ctx.send(
            components=[container],
            flags=discord.MessageFlags(is_components_v2=True),
        )
```

---

## Interactive Panels (Confirmation Views)

MochiMe's moderation commands use a `discord.ui.View` whose buttons update
the message in-place via `interaction.response.edit_message(components=[...])`.

```python
class MyView(discord.ui.View):
    @discord.ui.button(label="Yes", style=discord.ButtonStyle.primary, custom_id="yes")
    async def on_yes(self, interaction: discord.Interaction, button):
        result = discord.ui.Container(
            discord.ui.TextDisplay("✅ Confirmed!"),
            accent_color=discord.Color(config.PASTEL_GREEN),
        )
        await interaction.response.edit_message(components=[result])
        self.stop()
```
