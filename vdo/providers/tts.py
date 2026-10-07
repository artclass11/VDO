from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

from vdo.config import SETTINGS


def _synthesize(text: str, out_wav: Path) -> None:
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "piper",
            "-m",
            SETTINGS.piper_model,
            "--data-dir",
            SETTINGS.piper_data_dir,
            "-f",
            str(out_wav),
            "--",
            text,
        ],
        text=True,
        capture_output=True,
        timeout=300,
    )
    if proc.returncode:
        raise RuntimeError(proc.stderr[-2000:] or "Piper TTS failed")


async def synthesize_scenes(scenes: list[dict], out_dir: Path, workers: int = 3) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(workers)

    async def one(scene: dict) -> Path:
        out = out_dir / f"scene_{int(scene['id']):03d}.wav"
        if out.exists() and out.stat().st_size > 1000:
            return out
        async with sem:
            await asyncio.to_thread(_synthesize, scene["narration"], out)
        return out

    return await asyncio.gather(*[one(scene) for scene in scenes])
