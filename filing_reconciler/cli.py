"""Cross-platform console entrypoint (Windows has no `make`).

Subcommands are wired up in later steps; this is the stub.
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="filing-reconciler")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("run", help="Run a full analysis over sample data")
    sub.add_parser("eval", help="Run the offline evaluation harness")

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    print(f"command '{args.command}' is not implemented yet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
