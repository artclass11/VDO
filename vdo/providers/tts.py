from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import wave
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from vdo.config import SETTINGS
from vdo.utils import run


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


def _postprocess_voice(wav: Path) -> None:
    processed = wav.with_name(wav.stem + ".processed.wav")
    run(
        [
            "ffmpeg", "-y",
            "-i", str(wav),
            "-af",
            "highpass=f=65,lowpass=f=17000,"
            "acompressor=threshold=-19dB:ratio=2.0:attack=6:release=90:makeup=1.5,"
            "loudnorm=I=-16:TP=-1.5:LRA=7",
            "-ar", "48000",
            "-c:a", "pcm_s24le",
            str(processed),
        ],
        timeout=300,
    )
    processed.replace(wav)


def _scene_instruction(scene: dict) -> str:
    role = str(scene.get("story_role", "context"))
    if role == "hook":
        return "Open with quiet confidence and human curiosity. Slightly more urgency, but never sensational."
    if role in {"turning_point", "conflict"}:
        return "Build restrained tension. Start grounded and become more emotionally charged only where the words demand it."
    if role == "human":
        return "Warm, empathetic and observant. Let the listener feel that a real person is telling this story."
    if role in {"reflection", "resolution"}:
        return "Soft, reflective and intimate. Leave small natural pauses between ideas."
    if role == "evidence":
        return "Precise, calm and trustworthy. Emphasize important numbers or facts naturally."
    return SETTINGS.qwen3_instruct


def _qwen3_model_name() -> str:
    if SETTINGS.qwen3_model != "auto":
        return SETTINGS.qwen3_model
    import torch
    if torch.cuda.is_available():
        return "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
    return "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"


def _qwen3_device_and_dtype():
    import torch
    requested = SETTINGS.qwen3_device
    if requested != "auto":
        device = requested
    else:
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
    if str(device).startswith("cuda"):
        return device, torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    return "cpu", torch.float32


@lru_cache(maxsize=1)
def _load_qwen3():
    from qwen_tts import Qwen3TTSModel
    model_name = _qwen3_model_name()
    device, dtype = _qwen3_device_and_dtype()
    kwargs = {"device_map": device, "dtype": dtype}
    if str(device).startswith("cuda") and os.getenv("VDO_QWEN3_FLASH_ATTN", "0") in {"1", "true", "yes"}:
        kwargs["attn_implementation"] = "flash_attention_2"
    return Qwen3TTSModel.from_pretrained(model_name, **kwargs), model_name


def _synthesize_qwen3(scenes: Iterable[dict], out_dir: Path) -> list[Path]:
    import soundfile as sf
    scenes = list(scenes)
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = [out_dir / f"scene_{int(scene['id']):03d}.wav" for scene in scenes]
    pending = [(scene, out) for scene, out in zip(scenes, outputs) if not (out.exists() and out.stat().st_size > 1000)]
    if not pending:
        return outputs

    model, model_name = _load_qwen3()
    texts = [str(scene["narration"]).strip() for scene, _ in pending]
    languages = [SETTINGS.qwen3_lang for _ in pending]
    speakers = [SETTINGS.qwen3_voice for _ in pending]

    if "1.7B" in model_name:
        instructs = [_scene_instruction(scene) for scene, _ in pending]
        wavs, sr = model.generate_custom_voice(
            text=texts, language=languages, speaker=speakers, instruct=instructs
        )
    else:
        wavs, sr = model.generate_custom_voice(
            text=texts, language=languages, speaker=speakers
        )

    for (_, _), out, audio in zip(pending, outputs, wavs):
        sf.write(out, audio, sr, subtype="PCM_24")
        _postprocess_voice(out)
    return outputs


@lru_cache(maxsize=1)
def _load_qwen3_clone():
    import torch
    from qwen_tts import Qwen3TTSModel
    requested = SETTINGS.qwen3_model
    if requested == "auto" or "CustomVoice" in requested:
        requested = "Qwen/Qwen3-TTS-12Hz-1.7B-Base" if torch.cuda.is_available() else "Qwen/Qwen3-TTS-12Hz-0.6B-Base"
    device, dtype = _qwen3_device_and_dtype()
    return Qwen3TTSModel.from_pretrained(requested, device_map=device, dtype=dtype)


def _synthesize_qwen3_clone(scenes: Iterable[dict], out_dir: Path) -> list[Path]:
    import soundfile as sf
    if not SETTINGS.voice_reference:
        raise RuntimeError("VDO_VOICE_REFERENCE is not set")
    reference = Path(SETTINGS.voice_reference)
    if not reference.exists():
        raise FileNotFoundError(f"Voice reference not found: {reference}")

    scenes = list(scenes)
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = [out_dir / f"scene_{int(scene['id']):03d}.wav" for scene in scenes]
    pending = [(scene, out) for scene, out in zip(scenes, outputs) if not (out.exists() and out.stat().st_size > 1000)]
    if not pending:
        return outputs

    model = _load_qwen3_clone()
    prompt = model.create_voice_clone_prompt(
        ref_audio=str(reference),
        ref_text=SETTINGS.voice_reference_text or None,
        x_vector_only_mode=not bool(SETTINGS.voice_reference_text),
    )
    texts = [str(scene["narration"]).strip() for scene, _ in pending]
    languages = [SETTINGS.qwen3_lang for _ in pending]
    wavs, sr = model.generate_voice_clone(
        text=texts, language=languages, voice_clone_prompt=prompt
    )

    for (_, _), out, audio in zip(pending, outputs, wavs):
        sf.write(out, audio, sr, subtype="PCM_24")
        _postprocess_voice(out)
    return outputs


def _synthesize_kokoro(scenes: Iterable[dict], out_dir: Path) -> list[Path]:
    import numpy as np
    import soundfile as sf
    from kokoro import KPipeline
    pipeline = KPipeline(lang_code=SETTINGS.kokoro_lang)
    outputs = []
    out_dir.mkdir(parents=True, exist_ok=True)

    for scene in scenes:
        out = out_dir / f"scene_{int(scene['id']):03d}.wav"
        outputs.append(out)
        if out.exists() and out.stat().st_size > 1000:
            continue
        chunks = []
        for _, _, audio in pipeline(scene["narration"], voice=SETTINGS.kokoro_voice, speed=0.96):
            chunks.append(audio)
        if not chunks:
            raise RuntimeError(f"Kokoro produced no audio for scene {scene['id']}")
        sf.write(out, np.concatenate(chunks), 24000, subtype="PCM_16")
        _postprocess_voice(out)
    return outputs


def _synthesize_piper(scenes: Iterable[dict], out_dir: Path) -> list[Path]:
    from piper import PiperVoice
    model_path, config_path = ensure_voice()
    voice = PiperVoice.load(model_path=str(model_path), config_path=str(config_path))
    outputs = []
    out_dir.mkdir(parents=True, exist_ok=True)
    for scene in scenes:
        out = out_dir / f"scene_{int(scene['id']):03d}.wav"
        outputs.append(out)
        if out.exists() and out.stat().st_size > 1000:
            continue
        with wave.open(str(out), "wb") as wav_file:
            voice.synthesize(scene["narration"], wav_file)
        _postprocess_voice(out)
    return outputs


def _synthesize_batch(scenes: Iterable[dict], out_dir: Path) -> list[Path]:
    scenes = list(scenes)
    provider = SETTINGS.tts_provider

    if provider == "qwen3-clone":
        return _synthesize_qwen3_clone(scenes, out_dir)

    if provider == "qwen3":
        try:
            return _synthesize_qwen3(scenes, out_dir)
        except ImportError as exc:
            if "qwen_tts" not in str(exc).lower():
                raise

    if provider in {"qwen3", "kokoro"}:
        try:
            return _synthesize_kokoro(scenes, out_dir)
        except ImportError as exc:
            if "kokoro" not in str(exc).lower():
                raise

    if provider == "piper" or SETTINGS.allow_piper_fallback:
        return _synthesize_piper(scenes, out_dir)

    raise RuntimeError(
        "No high-quality TTS backend is available. Install qwen-tts or kokoro, "
        "or explicitly set VDO_ALLOW_PIPER_FALLBACK=1 for the legacy Piper voice."
    )


async def synthesize_scenes(scenes: list[dict], out_dir: Path, workers: int = 1) -> list[Path]:
    return await asyncio.to_thread(_synthesize_batch, scenes, out_dir)
