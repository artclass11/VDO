from __future__ import annotations

import os
from pathlib import Path

from faster_whisper import WhisperModel


def make_srt(audio: Path, output: Path, model_size: str = "small") -> None:
    device = os.getenv("VDO_WHISPER_DEVICE", "cpu")
    compute_type = os.getenv("VDO_WHISPER_COMPUTE_TYPE", "int8")
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    segments, _ = model.transcribe(
        str(audio),
        vad_filter=True,
        beam_size=1,
        word_timestamps=False,
    )
    lines: list[str] = []
    for i, seg in enumerate(segments, 1):
        text = seg.text.strip()
        if not text:
            continue
        lines.extend([str(i), f"{_ts(seg.start)} --> {_ts(seg.end)}", text, ""])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")


def _ts(sec: float) -> str:
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
