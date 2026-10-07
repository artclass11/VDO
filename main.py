from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from vdo.pipeline import generate
from vdo.intro import generate_intro


def cli() -> None:
    parser = argparse.ArgumentParser(description="VDO open-source documentary maker")
    parser.add_argument("topic", nargs="?", help="One-line documentary topic")
    parser.add_argument("--minutes", type=int, default=10)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--intro",
        action="store_true",
        help="Render the deterministic VDO product intro using only local/open components.",
    )
    parser.add_argument(
        "--intro-seconds",
        type=int,
        default=40,
        choices=range(20, 61),
        metavar="SECONDS",
        help="Intro target duration (20-60 seconds).",
    )
    args = parser.parse_args()

    if args.intro:
        result = asyncio.run(generate_intro(args.intro_seconds, args.output))
        print(f"INTRO_READY={result}")
        return

    if not args.topic:
        parser.error("topic is required unless --intro is used")

    result = asyncio.run(generate(args.topic, args.minutes, args.output))
    print(f"DOCUMENTARY_READY={result}")


if __name__ == "__main__":
    cli()
