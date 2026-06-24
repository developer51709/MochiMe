import os

BOT_TOKEN: str = os.environ.get("BOT_TOKEN", "")
PREFIX: str = "mochi "
DB_PATH: str = "mochime.db"
PHOSPHOR_DIR: str = "assets/phosphor"

PASTEL_PINK = 0xFFB3C6
PASTEL_PURPLE = 0xC9B1FF
PASTEL_BLUE = 0xB3D9FF
PASTEL_GREEN = 0xB3FFD9
PASTEL_YELLOW = 0xFFF5B3
PASTEL_PEACH = 0xFFCDB3

PASTEL_LAVENDER = 0xDDB3FF

FALLBACK_EMOJIS: dict[str, str] = {
    "heart": "🩷",
    "star": "⭐",
    "shield": "🛡️",
    "info": "ℹ️",
    "warning": "⚠️",
    "user": "👤",
    "smiley": "😊",
    "hand_heart": "🤲",
    "check": "✅",
    "cross": "❌",
    "chat": "💬",
    "sparkle": "✨",
    "hug": "🫂",
    "pat": "🫶",
    "kiss": "💋",
    "bonk": "🔨",
    "blush": "😳",
    "cuddle": "🥰",
    "poke": "👉",
    "ban": "🔨",
    "kick": "👢",
    "mute": "🔇",
    "warn": "⚠️",
    "crown": "👑",
    "bow": "🙇",
    "wave": "👋",
    "moon": "🌙",
    "flower": "🌸",
    "ribbon": "🎀",
    "cake": "🎂",
    "music": "🎵",
    "pencil": "✏️",
    "settings": "⚙️",
    "lock": "🔒",
    "unlock": "🔓",
    "pin": "📌",
    "trophy": "🏆",
    "crystal_ball": "🔮",
    "dice": "🎲",
    "chart": "📊",
    "bolt": "⚡",
    "coin": "🪙",
    "level_up": "🌟",
    "rank": "🌸",
    "confetti": "🎉",
    "wand":     "🪄",
    "eye":      "👁️",
    "add":      "➕",
    "remove":   "➖",
    "trash":    "🗑️",
    "bell":     "🔔",
    "book":     "📖",
}

BOOT_BANNER = """
╔═══════════════════════════════════════╗
║         🌸  M o c h i M e  🌸         ║
║      cute · pastel · discord bot      ║
╚═══════════════════════════════════════╝
"""
