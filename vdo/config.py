from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    root: Path = Path(os.getenv("VDO_OUTPUT_DIR", "./outputs"))
    ollama_url: str = os.getenv("VDO_OLLAMA_URL", "http://127.0.0.1:11434")
    ollama_model: str = os.getenv("VDO_OLLAMA_MODEL", "qwen3:8b")

    tts_provider: str = os.getenv("VDO_TTS_PROVIDER", "auto").lower()
    tts_strict: bool = _env_bool("VDO_TTS_STRICT", False)

    piper_model: str = os.getenv("VDO_PIPER_MODEL", "en_US-lessac-medium")
    piper_data_dir: str = os.getenv("VDO_PIPER_DATA_DIR", "./models")
    kokoro_voice: str = os.getenv("VDO_KOKORO_VOICE", "af_bella")
    kokoro_lang: str = os.getenv("VDO_KOKORO_LANG", "a")
    kokoro_speed: float = float(os.getenv("VDO_KOKORO_SPEED", "0.96"))

    qwen3_model: str = os.getenv("VDO_QWEN3_MODEL", "auto")
    qwen3_voice: str = os.getenv("VDO_QWEN3_VOICE", "Aiden")
    qwen3_lang: str = os.getenv("VDO_QWEN3_LANG", "English")
    qwen3_instruct: str = os.getenv(
        "VDO_QWEN3_INSTRUCT",
        "Natural human documentary narrator. Warm, intimate and understated. "
        "Speak like a thoughtful real person, not an announcer. Keep the same "
        "voice identity and timbre across scenes. Use relaxed conversational "
        "pacing, clear diction, subtle breath and emphasis, natural sentence "
        "endings, and small pauses between ideas. Never sound robotic, overly "
        "polished, dramatic, sales-like or synthetic.",
    )
    qwen3_device: str = os.getenv("VDO_QWEN3_DEVICE", "auto")
    voice_reference: str = os.getenv("VDO_VOICE_REFERENCE", "").strip()
    voice_reference_text: str = os.getenv("VDO_VOICE_REFERENCE_TEXT", "").strip()
    allow_piper_fallback: bool = _env_bool("VDO_ALLOW_PIPER_FALLBACK", False)

    fps: int = int(os.getenv("VDO_FPS", "30"))
    width: int = int(os.getenv("VDO_WIDTH", "1920"))
    height: int = int(os.getenv("VDO_HEIGHT", "1080"))
    workers: int = max(2, int(os.getenv("VDO_WORKERS", "6")))
    media_workers: int = max(2, int(os.getenv("VDO_MEDIA_WORKERS", "8")))
    whisper_model: str = os.getenv("VDO_WHISPER_MODEL", "base")
    request_timeout: float = float(os.getenv("VDO_REQUEST_TIMEOUT", "45"))

    cinematic: bool = _env_bool("VDO_CINEMATIC", True)
    real_footage_first: bool = _env_bool("VDO_REAL_FOOTAGE_FIRST", True)
    show_scene_titles: bool = _env_bool("VDO_SHOW_SCENE_TITLES", False)
    transition_seconds: float = max(0.0, float(os.getenv("VDO_TRANSITION_SECONDS", "0.45")))
    music_level: float = max(0.0, min(0.25, float(os.getenv("VDO_MUSIC_LEVEL", "0.075"))))
    video_crf: int = int(os.getenv("VDO_VIDEO_CRF", "18"))
    x264_preset: str = os.getenv("VDO_X264_PRESET", "medium")
    audio_bitrate: str = os.getenv("VDO_AUDIO_BITRATE", "256k")
    grain: float = max(
        0.0, min(3.0, float(os.getenv("VDO_CINEMATIC_GRAIN", "0.30")))
    )
    image_motion: float = max(
        0.00005, min(0.001, float(os.getenv("VDO_IMAGE_MOTION", "0.00022")))
    )


SETTINGS = Settings()
