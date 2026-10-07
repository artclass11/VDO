from __future__ import annotations

from pathlib import Path

from vdo.utils import run


def generate_ambient_bed(duration: float, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and output.stat().st_size > 1000:
        return

    # Procedural, royalty-free ambient bed produced entirely by FFmpeg.
    filter_graph = (
        "anoisesrc=color=pink:amplitude=0.08,"
        "lowpass=f=1100,"
        "highpass=f=70,"
        "aecho=0.8:0.88:900|1400:0.25|0.18,"
        "volume=0.28"
    )
    run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", filter_graph,
            "-t", f"{max(1.0, duration):.3f}",
            "-c:a", "aac", "-b:a", "96k",
            str(output),
        ],
        timeout=300,
    )
