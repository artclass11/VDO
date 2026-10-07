from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from vdo.pipeline import generate


def cli() -> None:
    parser = argparse.ArgumentParser(description="VDO open-source documentary maker")
    parser.add_argument("topic", help="One-line documentary topic")
    parser.add_argument("--minutes", type=int, default=10)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    result = asyncio.run(generate(args.topic, args.minutes, args.output))
    print(f"DOCUMENTARY_READY={result}")


if __name__ == "__main__":
    cli()
