from __future__ import annotations

import shutil
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


def _grade_filters() -> str:
    if not SETTINGS.cinematic:
        return ""
    return (
        ",eq=contrast=1.028:brightness=-0.008:saturation=0.985,"
        "unsharp=luma_msize_x=5:luma_msize_y=5:luma_amount=0.12,"
        f"noise=alls={SETTINGS.grain:.2f}:allf=t+u,vignette=PI/9"
    )


def _cinematic_bars() -> str:
    return (
        ",drawbox=x=0:y=0:w=iw:h=30:color=black@0.72:t=fill"
        ",drawbox=x=0:y=ih-30:w=iw:h=30:color=black@0.72:t=fill"
    )


def _title_overlay(title: str, opening: bool) -> str:
    if not title or (not SETTINGS.show_scene_titles and not opening):
        return ""
    safe = _escape_drawtext(title[:90])
    enable = ":enable='between(t,0,4)'" if opening else ""
    return (
        f",drawtext=text='{safe}':fontcolor=white:fontsize=52:"
        "box=1:boxcolor=black@0.32:boxborderw=18:"
        "x=76:y=h-165"
        + enable
    )


def _evidence_overlay(text: str, story_role: str) -> str:
    if not text:
        return ""
    if story_role not in {"evidence", "turning_point", "human", "resolution"}:
        return ""
    safe = _escape_drawtext(text[:110])
    return (
        f",drawtext=text='{safe}':fontcolor=white:fontsize=30:"
        "box=1:boxcolor=black@0.60:boxborderw=14:"
        "x=78:y=98:"
        "alpha='if(lt(t,0.4),t/0.4,if(gt(t,5),1,1))'"
    )


def render_scene(
    asset: str | None,
    wav: Path,
    title: str,
    out_mp4: Path,
    *,
    opening: bool = False,
    on_screen: str = "",
    story_role: str = "context",
) -> None:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    suffix = Path(asset).suffix.lower() if asset else ""
    common = (
        _grade_filters()
        + _cinematic_bars()
        + _title_overlay(title, opening)
        + _evidence_overlay(on_screen, story_role)
    )

    if asset and suffix in {".mp4", ".webm", ".ogg"}:
        vf = (
            f"scale={SETTINGS.width}:{SETTINGS.height}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={SETTINGS.width}:{SETTINGS.height}:(in_w-out_w)/2:(in_h-out_h)/2,"
            f"fps={SETTINGS.fps},setsar=1,"
            "setpts=PTS-STARTPTS"
            + common
        )
        inputs = ["-stream_loop", "-1", "-i", asset]
    elif asset:
        vf = (
            f"scale={SETTINGS.width}:{SETTINGS.height}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={SETTINGS.width}:{SETTINGS.height}:(in_w-out_w)/2:(in_h-out_h)/2,"
            f"zoompan=z='min(max(zoom,1)+0.00022,1.055)':d=1:"
            f"s={SETTINGS.width}x{SETTINGS.height}:fps={SETTINGS.fps},"
            "setpts=PTS-STARTPTS"
            + common
        )
        inputs = ["-loop", "1", "-i", asset]
    else:
        vf = (
            f"color=c=0x0b0d10:s={SETTINGS.width}x{SETTINGS.height}:r={SETTINGS.fps},"
            "setpts=PTS-STARTPTS"
            + common
        )
        inputs = ["-f", "lavfi", "-i", vf]
        vf = "format=yuv420p"

    run(
        [
            "ffmpeg", "-y",
            *inputs,
            "-i", str(wav),
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            "-vf", vf,
            "-r", str(SETTINGS.fps),
            "-c:v", "libx264", "-preset", SETTINGS.x264_preset, "-crf", str(SETTINGS.video_crf),
            "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1",
            "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
            "-af",
            "aresample=48000:async=1:first_pts=0,highpass=f=55,lowpass=f=18000,"
            "acompressor=threshold=-20dB:ratio=1.55:attack=18:release=180:knee=2dB:makeup=1.0,"
            "loudnorm=I=-16:TP=-1.5:LRA=7",
            "-c:a", "aac", "-b:a", SETTINGS.audio_bitrate,
            "-movflags", "+faststart",
            str(out_mp4),
        ],
        timeout=900,
    )


def _duration(path: Path) -> float:
    result = run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        timeout=60,
    )
    return float(result.stdout.strip())


def concatenate(scene_files: list[Path], out_mp4: Path) -> None:
    if not scene_files:
        raise ValueError("No scene files to concatenate")
    if len(scene_files) == 1 or SETTINGS.transition_seconds <= 0:
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
                "-movflags", "+faststart",
                str(out_mp4),
            ],
            timeout=1800,
        )
        return

    transition = min(SETTINGS.transition_seconds, 0.75)
    durations = [_duration(p) for p in scene_files]
    if any(d <= transition * 1.5 for d in durations):
        transition = 0.0

    if transition <= 0:
        return concatenate(scene_files, out_mp4)

    filters: list[str] = []
    video_label = "0:v"
    audio_label = "0:a"
    cumulative = durations[0]

    for i in range(1, len(scene_files)):
        v_out = f"v{i}"
        a_out = f"a{i}"
        offset = cumulative - transition
        filters.append(
            f"[{video_label}][{i}:v]xfade=transition=fade:duration={transition}:offset={offset:.3f}[{v_out}]"
        )
        filters.append(
            f"[{audio_label}][{i}:a]acrossfade=d={transition}:c1=tri:c2=tri[{a_out}]"
        )
        video_label = v_out
        audio_label = a_out
        cumulative += durations[i] - transition

    inputs: list[str] = []
    for p in scene_files:
        inputs += ["-i", str(p)]

    run(
        [
            "ffmpeg", "-y",
            *inputs,
            "-filter_complex", ";".join(filters),
            "-map", f"[{video_label}]",
            "-map", f"[{audio_label}]",
            "-c:v", "libx264", "-preset", SETTINGS.x264_preset, "-crf", str(SETTINGS.video_crf),
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", SETTINGS.audio_bitrate,
            "-movflags", "+faststart",
            str(out_mp4),
        ],
        timeout=1800,
    )


def mix_music(video: Path, music: Path, out_mp4: Path) -> None:
    level = SETTINGS.music_level
    filter_complex = (
        "[0:a]loudnorm=I=-16:TP=-1.5:LRA=7[voice];"
        f"[1:a]volume={level:.3f}[music];"
        "[music][voice]sidechaincompress=threshold=0.035:ratio=8:attack=25:release=500[ducked];"
        "[voice][ducked]amix=inputs=2:duration=first:dropout_transition=3,"
        "alimiter=limit=0.95[a]"
    )
    run(
        [
            "ffmpeg", "-y",
            "-i", str(video),
            "-i", str(music),
            "-filter_complex", filter_complex,
            "-map", "0:v:0",
            "-map", "[a]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", SETTINGS.audio_bitrate,
            "-movflags", "+faststart",
            str(out_mp4),
        ],
        timeout=1800,
    )


def burn_subtitles(video: Path, srt: Path, out_mp4: Path) -> None:
    style = (
        "FontName=DejaVu Sans,FontSize=26,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H70000000,BackColour=&H90000000,"
        "BorderStyle=3,Outline=0,Shadow=0,Alignment=2,"
        "MarginV=82,WrapStyle=2,Spacing=0"
    )
    try:
        run(
            [
                "ffmpeg", "-y",
                "-i", str(video),
                "-vf", f"subtitles={srt}:force_style='{style}'",
                "-c:v", "libx264", "-preset", "faster", "-crf", "19",
                "-pix_fmt", "yuv420p",
                "-c:a", "copy",
                "-movflags", "+faststart",
                str(out_mp4),
            ],
            timeout=1800,
        )
    except Exception:
        shutil.copy2(video, out_mp4)
