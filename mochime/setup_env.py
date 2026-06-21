"""
MochiMe setup helper — invoked via `python -m mochime --setup`

Detects the current platform (Termux/Android, Windows, Linux, macOS),
finds the best pip executable, installs every required package, and
validates that the environment is ready to run MochiMe.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

REQUIRED_PACKAGES = [
    "discord.py>=2.4.0",
    "aiosqlite>=0.20.0",
    "aiohttp>=3.9.0",
    "Pillow>=10.0.0",
]

# cairosvg gives perfect SVG→PNG fidelity but needs libcairo on the system.
# We attempt it as an optional install and skip silently if it fails.
OPTIONAL_PACKAGES = [
    "cairosvg>=2.7.0",
]

MIN_PYTHON = (3, 10)

BANNER = """
╔═══════════════════════════════════════════╗
║   🌸  MochiMe  ·  Environment Setup  🌸   ║
╚═══════════════════════════════════════════╝
"""


# ──────────────────────────────────────────
# Platform detection
# ──────────────────────────────────────────

class Env(NamedTuple):
    name: str          # human-readable label
    is_termux: bool
    is_windows: bool
    is_linux: bool
    is_macos: bool


def detect_env() -> Env:
    is_termux = (
        "TERMUX_VERSION" in os.environ
        or os.path.isdir("/data/data/com.termux")
        or "com.termux" in os.environ.get("PREFIX", "")
    )
    is_windows = sys.platform == "win32"
    is_macos = sys.platform == "darwin"
    is_linux = sys.platform.startswith("linux") and not is_termux

    if is_termux:
        name = "Android (Termux)"
    elif is_windows:
        name = f"Windows {platform.version()}"
    elif is_macos:
        name = f"macOS {platform.mac_ver()[0]}"
    else:
        name = f"Linux ({platform.freedesktop_os_release().get('NAME', 'unknown') if hasattr(platform, 'freedesktop_os_release') else platform.system()})"

    return Env(
        name=name,
        is_termux=is_termux,
        is_windows=is_windows,
        is_linux=is_linux,
        is_macos=is_macos,
    )


# ──────────────────────────────────────────
# pip discovery
# ──────────────────────────────────────────

def find_pip(env: Env) -> list[str]:
    """Return a pip command as a list of strings, or raise RuntimeError."""
    candidates: list[list[str]] = []

    if env.is_windows:
        candidates = [
            [sys.executable, "-m", "pip"],
            ["pip"],
            ["pip3"],
            ["py", "-m", "pip"],
        ]
    else:
        candidates = [
            [sys.executable, "-m", "pip"],
            ["pip3"],
            ["pip"],
        ]

    for cmd in candidates:
        try:
            result = subprocess.run(
                cmd + ["--version"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return cmd
        except FileNotFoundError:
            continue

    raise RuntimeError(
        "Could not find pip. Please install pip manually:\n"
        "  • Termux:  pkg install python (includes pip)\n"
        "  • Linux:   sudo apt install python3-pip\n"
        "  • Windows: python -m ensurepip --upgrade\n"
    )


# ──────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────

def _ok(msg: str) -> None:
    print(f"  ✓  {msg}")


def _info(msg: str) -> None:
    print(f"  ·  {msg}")


def _warn(msg: str) -> None:
    print(f"  ⚠  {msg}")


def _fail(msg: str) -> None:
    print(f"  ✗  {msg}")


def _section(title: str) -> None:
    print(f"\n  ── {title} ──")


# ──────────────────────────────────────────
# Step: check Python version
# ──────────────────────────────────────────

def check_python() -> bool:
    ver = sys.version_info
    if ver >= MIN_PYTHON:
        _ok(f"Python {ver.major}.{ver.minor}.{ver.micro}")
        return True
    _fail(
        f"Python {ver.major}.{ver.minor} is too old. "
        f"MochiMe requires Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+."
    )
    if "TERMUX_VERSION" in os.environ or os.path.isdir("/data/data/com.termux"):
        print("  → On Termux: pkg install python")
    else:
        print("  → Download from https://www.python.org/downloads/")
    return False


# ──────────────────────────────────────────
# Step: install packages
# ──────────────────────────────────────────

def install_packages(pip_cmd: list[str], env: Env) -> bool:
    extra_args: list[str] = []

    if env.is_termux:
        # Termux doesn't support --user flag; packages install globally in its prefix
        extra_args = []
    elif env.is_windows:
        extra_args = []
    else:
        # On Linux/macOS without a venv, --user avoids needing sudo
        in_venv = sys.prefix != sys.base_prefix
        if not in_venv:
            extra_args = ["--user"]

    cmd = pip_cmd + ["install", "--upgrade"] + extra_args + REQUIRED_PACKAGES
    _info(f"Running: {' '.join(cmd)}")
    print()

    result = subprocess.run(cmd)
    if result.returncode != 0:
        _fail("pip install failed — see output above for details")
        return False

    _ok("Required packages installed successfully")

    # Optional: cairosvg for perfect SVG→PNG emoji conversion.
    # Needs libcairo on the system; skip silently if it fails.
    _info("Attempting optional install: cairosvg (better emoji quality)…")
    if env.is_termux:
        _info("  Termux tip: run  pkg install cairo  first for cairosvg support")

    opt_cmd = pip_cmd + ["install", "--upgrade"] + extra_args + OPTIONAL_PACKAGES
    opt_result = subprocess.run(opt_cmd, capture_output=True, text=True)
    if opt_result.returncode == 0:
        _ok("cairosvg installed — emojis will use real Phosphor vectors")
    else:
        _warn("cairosvg skipped — Pillow pastel-circle fallback will be used instead")

    return True


# ──────────────────────────────────────────
# Step: verify imports
# ──────────────────────────────────────────

def verify_imports() -> bool:
    required = [
        ("discord",    "discord.py"),
        ("aiosqlite",  "aiosqlite"),
        ("aiohttp",    "aiohttp"),
        ("PIL",        "Pillow"),
    ]
    optional = [
        ("cairosvg",   "cairosvg (SVG→PNG, optional)"),
    ]
    all_ok = True
    for module, label in required:
        try:
            mod = __import__(module)
            ver = getattr(mod, "__version__", "?")
            _ok(f"{label} {ver}")
        except ImportError:
            _fail(f"{label} — import failed even after install")
            all_ok = False
    for module, label in optional:
        try:
            mod = __import__(module)
            ver = getattr(mod, "__version__", "?")
            _ok(f"{label} {ver}")
        except ImportError:
            _info(f"{label} — not installed (Pillow fallback active)")
    return all_ok


# ──────────────────────────────────────────
# Step: check BOT_TOKEN
# ──────────────────────────────────────────

def check_bot_token(env: Env) -> None:
    token = os.environ.get("BOT_TOKEN", "").strip()
    if token:
        _ok("BOT_TOKEN is set")
        return

    _warn("BOT_TOKEN is not set")
    print()
    if env.is_termux:
        print("  To set it on Termux (survives reboots):")
        print("    echo 'export BOT_TOKEN=your_token_here' >> ~/.bashrc")
        print("    source ~/.bashrc")
    elif env.is_windows:
        print("  To set it on Windows (PowerShell):")
        print("    $env:BOT_TOKEN = 'your_token_here'")
        print("  Or permanently via System Properties → Environment Variables")
    else:
        print("  To set it on Linux/macOS:")
        print("    export BOT_TOKEN=your_token_here")
        print("  Or add it to ~/.bashrc / ~/.zshrc for persistence")

    print()
    token_input = input("  Paste your BOT_TOKEN now (or press Enter to skip): ").strip()
    if token_input:
        _write_dotenv(token_input, env)


def _write_dotenv(token: str, env: Env) -> None:
    dotenv_path = Path(__file__).parent / ".env"
    dotenv_path.write_text(f"BOT_TOKEN={token}\n", encoding="utf-8")
    _ok(f"Token saved to {dotenv_path}")

    # Patch config.py to try loading .env automatically
    _patch_config_for_dotenv()

    if env.is_termux or env.is_linux or env.is_macos:
        print()
        print("  To load it automatically in your shell add this to ~/.bashrc:")
        print(f"    export $(grep -v '^#' {dotenv_path} | xargs)")


def _patch_config_for_dotenv() -> None:
    """Add .env loading to config.py if it isn't there already."""
    config_path = Path(__file__).parent / "config.py"
    content = config_path.read_text(encoding="utf-8")
    if "dotenv" in content or ".env" in content:
        return

    patch = (
        "# Auto-load .env file if present (added by --setup)\n"
        "import pathlib as _pl\n"
        "_env_file = _pl.Path(__file__).parent / '.env'\n"
        "if _env_file.exists():\n"
        "    for _line in _env_file.read_text().splitlines():\n"
        "        if _line.strip() and not _line.startswith('#') and '=' in _line:\n"
        "            _k, _, _v = _line.partition('=')\n"
        "            os.environ.setdefault(_k.strip(), _v.strip())\n\n"
    )
    config_path.write_text(patch + content, encoding="utf-8")
    _ok("config.py patched to auto-load .env")


# ──────────────────────────────────────────
# Step: platform-specific guidance
# ──────────────────────────────────────────

def print_platform_notes(env: Env) -> None:
    if env.is_termux:
        print()
        print("  📱  Termux tips:")
        print("    • Keep screen on while bot runs: termux-wake-lock")
        print("    • Run in background:             nohup python -m mochime &")
        print("    • Auto-start on boot:            use Termux:Boot add-on")
    elif env.is_windows:
        print()
        print("  🖥   Windows tips:")
        print("    • Run in background:  pythonw -m mochime  (no console window)")
        print("    • Always-on:          add to Windows Task Scheduler")
    else:
        print()
        print("  🐧  Linux tips:")
        print("    • Run in background:  nohup python3 -m mochime &")
        print("    • Always-on:          use systemd service or screen/tmux")


# ──────────────────────────────────────────
# Main entry
# ──────────────────────────────────────────

def run_setup() -> None:
    print(BANNER)

    env = detect_env()
    _section("Environment")
    _info(f"Platform : {env.name}")
    _info(f"Python   : {sys.executable}")
    _info(f"Version  : {sys.version.split()[0]}")

    _section("Python version check")
    if not check_python():
        sys.exit(1)

    _section("Finding pip")
    try:
        pip_cmd = find_pip(env)
        _ok(f"pip found: {' '.join(pip_cmd)}")
    except RuntimeError as exc:
        _fail(str(exc))
        sys.exit(1)

    _section("Installing / upgrading packages")
    if not install_packages(pip_cmd, env):
        sys.exit(1)

    _section("Verifying imports")

    # Reload site-packages in case we just installed into --user
    import importlib
    import site
    if hasattr(site, "getusersitepackages"):
        user_site = site.getusersitepackages()
        if user_site not in sys.path:
            sys.path.append(user_site)

    if not verify_imports():
        _warn("Some imports failed. Try restarting your terminal and re-running.")

    _section("Discord bot token")
    check_bot_token(env)

    print_platform_notes(env)

    print()
    print("  ══════════════════════════════════════")
    print("  🌸  Setup complete! Run the bot with:")
    print("      python -m mochime")
    print("  ══════════════════════════════════════")
    print()
