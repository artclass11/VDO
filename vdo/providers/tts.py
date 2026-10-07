from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path

from vdo.config import SETTINGS


def _synthesize(text: str, out_wav: Path) -> None:
    model = SETTINGS.piper_model
    if not model:
        raise RuntimeError("Set VDO_PIPER_MODEL to a local Piper .onnx voice model.")
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [SETTINGS.piper_bin, "--model", model, "--output_file", str(out_wav)],
        input=text,
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
