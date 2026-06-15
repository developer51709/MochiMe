#!/usr/bin/env python3
"""
MochiMe — entry point for `python -m mochime`

Usage:
  python -m mochime            Start the bot
  python -m mochime --setup    Install/verify all dependencies
  python -m mochime --help     Show this help message
"""
from __future__ import annotations

import os
import sys

# Ensure the package directory is on sys.path so all bare imports inside
# bot.py, config.py, database.py, and the cogs/ folder resolve correctly
# regardless of where the user calls `python -m mochime` from.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)


def _print_help() -> None:
    print(__doc__)


def main() -> None:
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        _print_help()
        sys.exit(0)

    if "--setup" in args:
        from setup_env import run_setup
        run_setup()
        sys.exit(0)

    # Default: start the bot
    try:
        import asyncio
        from bot import main as run_bot
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        print("\n\n  👋  MochiMe stopped. Bye bye~\n")
    except ImportError as exc:
        print(f"\n  ✗  Missing dependency: {exc}")
        print("  → Run  python -m mochime --setup  to install everything.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
