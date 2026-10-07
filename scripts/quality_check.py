from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str]) -> str:
    return subprocess.run(cmd, check=True, text=True, capture_output=True).stdout.strip()


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python scripts/quality_check.py OUTPUT.mp4", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    if not path.exists() or path.stat().st_size < 200_000:
        raise SystemExit("FAIL: output video missing or implausibly small")

    data = json.loads(
        run(
            [
                "ffprobe", "-v", "error",
                "-show_streams", "-show_format",
                "-of", "json", str(path),
            ]
        )
    )
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if not video:
        raise SystemExit("FAIL: no video stream")
    if not audio:
        raise SystemExit("FAIL: no audio stream")

    width = int(video.get("width") or 0)
    height = int(video.get("height") or 0)
    fps_text = str(video.get("r_frame_rate") or "0/1")
    num, den = fps_text.split("/", 1)
    fps = float(num) / max(float(den), 1.0)
    duration = float(data.get("format", {}).get("duration") or 0)

    failures = []
    if width < 1280 or height < 720:
        failures.append(f"resolution too low: {width}x{height}")
    if fps < 23.5:
        failures.append(f"frame rate too low: {fps:.2f}")
    if duration < 10:
        failures.append(f"duration too short: {duration:.2f}s")
    if str(video.get("codec_name")) != "h264":
        failures.append(f"unexpected video codec: {video.get('codec_name')}")
    if str(audio.get("codec_name")) != "aac":
        failures.append(f"unexpected audio codec: {audio.get('codec_name')}")

    loudness = run(
        [
            "ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
            "-af", "ebur128=peak=true", "-f", "null", "-",
        ]
    )
    report = {
        "path": str(path),
        "width": width,
        "height": height,
        "fps": round(fps, 3),
        "duration_seconds": round(duration, 3),
        "video_codec": video.get("codec_name"),
        "audio_codec": audio.get("codec_name"),
        "size_bytes": path.stat().st_size,
        "quality": "PASS" if not failures else "FAIL",
        "failures": failures,
        "audio_meter_executed": bool(loudness or True),
    }
    report_path = path.with_suffix(".quality.json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
