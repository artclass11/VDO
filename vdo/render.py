from __future__ import annotations

from pathlib import Path

from vdo.config import SETTINGS
from vdo.utils import run


def _escape_drawtext(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace("%", "\\%")
    )


def render_scene(
    image: str | None,
    duration: float,
    wav: Path,
    title: str,
    out_mp4: Path,
) -> None:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    safe_title = _escape_drawtext(title[:90])

    if image:
        vf = (
            f"scale={SETTINGS.width}:{SETTINGS.height}:force_original_aspect_ratio=increase,"
            f"crop={SETTINGS.width}:{SETTINGS.height},"
            f"zoompan=z='min(zoom+0.0007,1.06)':d=1:"
            f"s={SETTINGS.width}x{SETTINGS.height}:fps={SETTINGS.fps},"
            f"fade=t=in:st=0:d=0.35,"
            f"fade=t=out:st={max(duration - 0.55, 0.4):.2f}:d=0.5,"
            f"drawtext=text='{safe_title}':fontcolor=white:fontsize=44:"
            "box=1:boxcolor=black@0.42:boxborderw=18:x=70:y=h-150"
        )
        inputs = ["-loop", "1", "-i", image]
    else:
        vf = (
            f"drawtext=text='{safe_title}':fontcolor=white:fontsize=54:"
            "box=1:boxcolor=black@0.55:boxborderw=22:x=90:y=h-170"
        )
        inputs = [
            "-f", "lavfi",
            "-i", f"color=c=0x101010:s={SETTINGS.width}x{SETTINGS.height}:r={SETTINGS.fps}",
        ]

    run(
        [
            "ffmpeg", "-y",
            *inputs,
            "-i", str(wav),
            "-t", f"{duration:.3f}",
            "-vf", vf,
            "-r", str(SETTINGS.fps),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k",
            "-shortest",
            str(out_mp4),
        ],
        timeout=900,
    )


def concatenate(scene_files: list[Path], out_mp4: Path) -> None:
    concat_file = out_mp4.with_suffix(".concat.txt")
    concat_file.write_text(
        "\n".join(f"file '{p.resolve()}'" for p in scene_files) + "\n",
        encoding="utf-8",
    )
    run(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            str(out_mp4),
        ],
        timeout=1800,
    )


def burn_subtitles(video: Path, srt: Path, out_mp4: Path) -> None:
    style = (
        "FontName=DejaVu Sans,FontSize=22,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H80000000,BorderStyle=1,Outline=2,Shadow=1,"
        "Alignment=2,MarginV=34"
    )
    run(
        [
            "ffmpeg", "-y",
            "-i", str(video),
            "-vf", f"subtitles={srt}:force_style='{style}'",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "copy",
            str(out_mp4),
        ],
        timeout=1800,
    )
