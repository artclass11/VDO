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
        "+0.007*sin(2*PI*329.63*t)"
        "|0.024*sin(2*PI*110*t+0.18)"
        "+0.015*sin(2*PI*164.81*t+0.09)"
        "+0.010*sin(2*PI*220*t+0.14)"
        "+0.006*sin(2*PI*329.63*t+0.06)"
        ":s=48000:channel_layout=stereo,"
        "tremolo=f=0.10:d=0.18,"
        "aecho=0.72:0.78:540|980:0.16|0.10,"
        "highpass=f=48,"
        "lowpass=f=2400,"
        "volume=0.82"
    )
    run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", filter_graph,
            "-t", f"{max(1.0, duration):.3f}",
            "-c:a", "aac", "-b:a", "160k",
            "-movflags", "+faststart",
            str(output),
        ],
        timeout=300,
    )
