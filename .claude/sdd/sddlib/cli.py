"""`bash .claude/sdd/sdd.sh <command>` -- the method's tooling, one entry point."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from . import OPENSPEC_VERSION, VERSION


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="sdd", description="SDD method tooling")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="project root (default: cwd)")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="requirement <-> test traceability; exit 1 on error")
    check.add_argument("--config", type=Path, help="adapter file (default: <root>/sdd.toml)")
    check.add_argument("--json", action="store_true", help="the diagnostic envelope, for machines")
    check.add_argument("--today", type=date.fromisoformat, help=argparse.SUPPRESS)

    status = sub.add_parser("status", help="where each in-flight change stands")
    status.add_argument("--brief", action="store_true", help="one line per change, or nothing")

    sub.add_parser("version", help="method and pinned OpenSpec versions")

    # Distribution and health live in their own modules and register themselves.
    from . import distribute, stats

    distribute.register(sub)
    stats.register(sub)

    args = parser.parse_args(argv)
    root = args.root.resolve()

    if args.command == "check":
        from .check import run
        from .report import render_json, render_text

        result = run(root, args.config and (root / args.config), args.today)
        print(render_json(result) if args.json else render_text(result))
        return 0 if result.ok else 1

    if args.command == "status":
        from .status import read

        changes = read(root)
        if args.brief:
            if changes:
                print("SDD changes in flight (resume at the earliest incomplete stage):")
                for change in changes:
                    print(f"  {change.line()}")
            return 0
        if not changes:
            print("no changes in flight -- start one with /intake")
        for change in changes:
            print(change.line())
        return 0

    if args.command == "version":
        print(f"sdd {VERSION} (OpenSpec {OPENSPEC_VERSION}, Python {sys.version.split()[0]})")
        return 0

    return args.handler(root, args)
