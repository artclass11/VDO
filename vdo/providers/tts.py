from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path
from typing import Iterable

from vdo.config import SETTINGS


def _model_paths() -> tuple[Path, Path]:
    root = Path(SETTINGS.piper_data_dir)
    return root / f"{SETTINGS.piper_model}.onnx", root / f"{SETTINGS.piper_model}.onnx.json"


def ensure_voice() -> tuple[Path, Path]:
    model_path, config_path = _model_paths()
    if model_path.exists() and config_path.exists():
        return model_path, config_path
    Path(SETTINGS.piper_data_dir).mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "piper.download_voices",
            SETTINGS.piper_model,
            "--data-dir",
            SETTINGS.piper_data_dir,
        ],
        check=True,
        text=True,
        capture_output=True,
        timeout=600,
    )
    if not model_path.exists() or not config_path.exists():
        raise RuntimeError(f"Piper voice download did not create {model_path}")
    return model_path, config_path


def _synthesize_batch(scenes: Iterable[dict], out_dir: Path) -> list[Path]:
    from piper import PiperVoice
    import wave

    model_path, config_path = ensure_voice()
    voice = PiperVoice.load(model_path=str(model_path), config_path=str(config_path))
    outputs: list[Path] = []
    out_dir.mkdir(parents=True, exist_ok=True)

    for scene in scenes:
        out = out_dir / f"scene_{int(scene['id']):03d}.wav"
        outputs.append(out)
        if out.exists() and out.stat().st_size > 1000:
            continue
        with wave.open(str(out), "wb") as wav_file:
            voice.synthesize(scene["narration"], wav_file)

    return outputs


async def synthesize_scenes(scenes: list[dict], out_dir: Path, workers: int = 1) -> list[Path]:
    # One loaded PiperVoice is intentionally reused for every scene. The standard
    # CLI reloads the voice per process; keeping one model resident is substantially
    # faster for long documentaries.
    return await asyncio.to_thread(_synthesize_batch, scenes, out_dir)
