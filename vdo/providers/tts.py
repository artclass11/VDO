from __future__ import annotations

import asyncio
import subprocess
import sys
import wave
from pathlib import Path
from typing import Iterable

from vdo.config import SETTINGS


def _piper_model_paths() -> tuple[Path, Path]:
    root = Path(SETTINGS.piper_data_dir)
    return root / f"{SETTINGS.piper_model}.onnx", root / f"{SETTINGS.piper_model}.onnx.json"


def ensure_voice() -> tuple[Path, Path]:
    model_path, config_path = _piper_model_paths()
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


def _synthesize_piper(scenes: Iterable[dict], out_dir: Path) -> list[Path]:
    from piper import PiperVoice

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


def _synthesize_kokoro(scenes: Iterable[dict], out_dir: Path) -> list[Path]:
    import numpy as np
    import soundfile as sf
    from kokoro import KPipeline

    pipeline = KPipeline(lang_code=SETTINGS.kokoro_lang)
    outputs: list[Path] = []
    out_dir.mkdir(parents=True, exist_ok=True)

    for scene in scenes:
        out = out_dir / f"scene_{int(scene['id']):03d}.wav"
        outputs.append(out)
        if out.exists() and out.stat().st_size > 1000:
            continue

        chunks = []
        for _, _, audio in pipeline(
            scene["narration"],
            voice=SETTINGS.kokoro_voice,
            speed=0.96,
        ):
            chunks.append(audio)

        if not chunks:
            raise RuntimeError(f"Kokoro produced no audio for scene {scene['id']}")
        audio = np.concatenate(chunks)
        sf.write(out, audio, 24000, subtype="PCM_16")

    return outputs


def _synthesize_batch(scenes: Iterable[dict], out_dir: Path) -> list[Path]:
    scenes = list(scenes)
    provider = SETTINGS.tts_provider
    if provider == "kokoro":
        try:
            return _synthesize_kokoro(scenes, out_dir)
        except ImportError as exc:
            if "kokoro" not in str(exc).lower():
                raise
            # Optional dependency: keep the base installation usable.
            return _synthesize_piper(scenes, out_dir)
        except Exception:
            # If a local Kokoro install is broken, fail over cleanly to Piper.
            return _synthesize_piper(scenes, out_dir)
    return _synthesize_piper(scenes, out_dir)


async def synthesize_scenes(scenes: list[dict], out_dir: Path, workers: int = 1) -> list[Path]:
    # Load one TTS model per job and reuse it across scenes.
    return await asyncio.to_thread(_synthesize_batch, scenes, out_dir)
