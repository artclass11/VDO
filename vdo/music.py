from __future__ import annotations

from pathlib import Path

from vdo.utils import run


def generate_ambient_bed(duration: float, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and output.stat().st_size > 1000:
        return

    # A restrained harmonic ambient pad made entirely in FFmpeg.
    # It avoids generic noise while staying royalty-free and deterministic.
    filter_graph = (
        "aevalsrc="
        "0.030*sin(2*PI*110*t)"
        "+0.019*sin(2*PI*164.81*t)"
        "+0.014*sin(2*PI*220*t)"
        "+0.008*sin(2*PI*329.63*t)"
        ":s=stereo,"
        "tremolo=f=0.045:d=0.22,"
        "lowpass=f=1800,"
        "aecho=0.75:0.80:650|1100:0.20|0.14,"
        "highpass=f=55,"
        "volume=0.9"
    )
    run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", filter_graph,
            "-t", f"{max(1.0, duration):.3f}",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            str(output),
        ],
        timeout=300,
    )
