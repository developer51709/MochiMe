"""
console.py — Pastel-coloured terminal output and logging for MochiMe.
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime


# ─────────────────────────────────────────────────────────
# Colour palette  (256-colour pastel theme, ANSI escapes)
# ─────────────────────────────────────────────────────────

class C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    # Pastel 256-colour swatches
    PINK   = "\033[38;5;218m"
    PURPLE = "\033[38;5;183m"
    BLUE   = "\033[38;5;153m"
    GREEN  = "\033[38;5;157m"
    YELLOW = "\033[38;5;222m"
    PEACH  = "\033[38;5;216m"
    RED    = "\033[38;5;210m"
    GRAY   = "\033[38;5;245m"
    WHITE  = "\033[38;5;255m"
    CYAN   = "\033[38;5;159m"
    MUTED  = "\033[38;5;239m"
    ROSE   = "\033[38;5;204m"


def _supports_color() -> bool:
    if os.environ.get("NO_COLOR") or os.environ.get("TERM") == "dumb":
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    if sys.platform == "win32":
        try:
            import ctypes
            k = ctypes.windll.kernel32  # type: ignore[attr-defined]
            k.SetConsoleMode(k.GetStdHandle(-11), 7)
            return True
        except Exception:
            return False
    return getattr(sys.stdout, "isatty", lambda: False)()


USE_COLOR: bool = _supports_color()


def _paint(code: str, text: str) -> str:
    return f"{code}{text}{C.RESET}" if USE_COLOR else text


# ─────────────────────────────────────────────────────────
# ASCII banner
# ─────────────────────────────────────────────────────────

_LOGO_LINES = [
    r"  ___  ___         _     _  __  __      ",
    r" |  \/  |         | |   (_)|  \/  |     ",
    r" | .  . | ___  ___| |__  _ | .  . | ___ ",
    r" | |\/| |/ _ \/ __| '_ \| || |\/| |/ _ \\",
    r" | |  | | (_) \__ \ | | | || |  | |  __/",
    r" \_|  |_/\___/|___/_| |_|_|\_|  |_/\___|",
]


def print_banner(version: str = "1.0.0", prefix: str = "mochi ") -> None:
    import discord as _discord

    border   = _paint(C.DIM   + C.PURPLE, "─" * 46)
    tl, tr   = _paint(C.DIM + C.PURPLE, "╭"), _paint(C.DIM + C.PURPLE, "╮")
    bl, br   = _paint(C.DIM + C.PURPLE, "╰"), _paint(C.DIM + C.PURPLE, "╯")
    vbar     = _paint(C.DIM + C.PURPLE, "│")

    print()
    print(f"  {tl}{border}{tr}")

    for i, line in enumerate(_LOGO_LINES):
        col = C.PINK if i % 2 == 0 else C.PURPLE
        print(f"  {vbar}  {_paint(C.BOLD + col, line.ljust(44))}  {vbar}")

    sub = _paint(C.DIM + C.PINK, "cute  ·  pastel  ·  discord bot")
    print(f"  {vbar}      {'':>2}{sub:<52}     {vbar}")
    print(f"  {bl}{border}{br}")
    print()

    def kv(key: str, val: str) -> None:
        k = _paint(C.GRAY,   f"  {'':>2}{'✦':1}  {key:<12}")
        v = _paint(C.WHITE,  val)
        print(k + v)

    kv("prefix",  f"{prefix!r}  (or  /slash commands)")
    kv("version",  version)
    kv("python",   sys.version.split()[0])
    kv("discord",  _discord.__version__)
    print()


# ─────────────────────────────────────────────────────────
# Log-level metadata
# ─────────────────────────────────────────────────────────

_LEVEL_META: dict[int, tuple[str, str]] = {
    logging.DEBUG:    (C.MUTED,  "·"),
    logging.INFO:     (C.CYAN,   "·"),
    logging.WARNING:  (C.YELLOW, "⚠"),
    logging.ERROR:    (C.RED,    "✗"),
    logging.CRITICAL: (C.ROSE,   "✗"),
}

# Map logger names to pastel accent colours
_SOURCE_COLORS: dict[str, str] = {
    "discord":        C.BLUE,
    "discord.client": C.BLUE,
    "discord.http":   C.MUTED,
    "discord.gateway":C.MUTED,
    "cogs.emoji":     C.PINK,
    "cogs.help":      C.PURPLE,
    "cogs.rp":        C.PINK,
    "cogs.mod":       C.PEACH,
    "cogs.app":       C.CYAN,
    "cogs.server":    C.BLUE,
    "mochime":        C.PINK,
    "database":       C.GREEN,
    "setup":          C.YELLOW,
}

# Labels shown in brackets beside the timestamp
_SOURCE_LABELS: dict[str, str] = {
    "discord":         "discord",
    "discord.client":  "discord",
    "discord.http":    "http   ",
    "discord.gateway": "gateway",
    "discord.ext.commands": "commands",
    "cogs.emoji_loader": "emojis ",
    "cogs.help":       "help   ",
    "cogs.rp":         "rp     ",
    "cogs.moderation": "mod    ",
    "cogs.application":"app    ",
    "cogs.server_features": "server ",
    "mochime":         "bot    ",
    "database":        "db     ",
    "setup":           "setup  ",
}


class _MochiFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        now   = datetime.now().strftime("%H:%M:%S")
        color, icon = _LEVEL_META.get(record.levelno, (C.GRAY, "·"))
        name  = record.name.lower()

        src_color = next(
            (v for k, v in _SOURCE_COLORS.items() if name.startswith(k)),
            C.GRAY,
        )
        src_label = next(
            (v for k, v in _SOURCE_LABELS.items() if name.startswith(k)),
            name[:7].ljust(7),
        )

        ts   = _paint(C.MUTED,  f"  {now}")
        ic   = _paint(color,    f"  {icon}")
        lbl  = _paint(src_color + C.DIM, f"[{src_label}]")
        msg  = _paint(C.WHITE if record.levelno < logging.WARNING else color,
                      record.getMessage())

        line = f"{ts}{ic}  {lbl}  {msg}"

        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


class _MochiHandler(logging.StreamHandler):
    def __init__(self) -> None:
        super().__init__(sys.stdout)
        self.setFormatter(_MochiFormatter())


# ─────────────────────────────────────────────────────────
# Public log helpers  (used inside bot & cogs)
# ─────────────────────────────────────────────────────────

_root = logging.getLogger("mochime")


def setup_logging(level: int = logging.INFO) -> None:
    """Attach the MochiMe handler to the root and discord loggers."""
    handler = _MochiHandler()

    # Our bot logger
    _root.setLevel(level)
    _root.handlers.clear()
    _root.addHandler(handler)
    _root.propagate = False

    # discord.py logger — show INFO+, silence noisy gateway debug
    discord_log = logging.getLogger("discord")
    discord_log.setLevel(logging.INFO)
    discord_log.handlers.clear()
    discord_log.addHandler(handler)
    discord_log.propagate = False

    logging.getLogger("discord.http").setLevel(logging.WARNING)
    logging.getLogger("discord.gateway").setLevel(logging.WARNING)


def get_logger(name: str = "mochime") -> logging.Logger:
    log = logging.getLogger(name)
    if not log.handlers:
        log.setLevel(logging.DEBUG)
        log.addHandler(_MochiHandler())
        log.propagate = False
    return log


# ─────────────────────────────────────────────────────────
# Shorthand coloured printers  (for startup steps)
# ─────────────────────────────────────────────────────────

def ok(msg: str)    -> None: print(_paint(C.GREEN,  f"  ✓  {msg}"))
def info(msg: str)  -> None: print(_paint(C.CYAN,   f"  ·  {msg}"))
def warn(msg: str)  -> None: print(_paint(C.YELLOW, f"  ⚠  {msg}"))
def fail(msg: str)  -> None: print(_paint(C.RED,    f"  ✗  {msg}"))
def step(msg: str)  -> None: print(_paint(C.PURPLE, f"\n  ── {msg} ──"))
def dim(msg: str)   -> None: print(_paint(C.MUTED,  f"  {msg}"))
