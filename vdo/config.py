from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    root: Path = Path(os.getenv("VDO_OUTPUT_DIR", "./outputs"))
    ollama_url: str = os.getenv("VDO_OLLAMA_URL", "http://127.0.0.1:11434")
    ollama_model: str = os.getenv("VDO_OLLAMA_MODEL", "qwen3:8b")
    piper_bin: str = os.getenv("VDO_PIPER_BIN", "piper")
    piper_model: str = os.getenv("VDO_PIPER_MODEL", "")
    fps: int = int(os.getenv("VDO_FPS", "30"))
    width: int = int(os.getenv("VDO_WIDTH", "1920"))
    height: int = int(os.getenv("VDO_HEIGHT", "1080"))
    workers: int = max(2, int(os.getenv("VDO_WORKERS", "6")))
    media_workers: int = max(2, int(os.getenv("VDO_MEDIA_WORKERS", "8")))
    whisper_model: str = os.getenv("VDO_WHISPER_MODEL", "small")
    request_timeout: float = float(os.getenv("VDO_REQUEST_TIMEOUT", "45"))


SETTINGS = Settings()
