from __future__ import annotations

import hashlib
import json
import math
import platform
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree as ET

VIDEO_EXTS = {".mp4", ".mov", ".mxf", ".mkv", ".webm", ".avi", ".m4v", ".mts", ".m2ts"}
AUDIO_EXTS = {".wav", ".mp3", ".aac", ".m4a", ".flac", ".ogg"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"}
MEDIA_EXTS = VIDEO_EXTS | AUDIO_EXTS | IMAGE_EXTS
COLOR_STYLES = ("neutral_documentary", "warm_documentary", "cool_observational", "night_cinematic", "mono")

EDITOR_CAPABILITIES: dict[str, dict[str, Any]] = {
    "resolve": {"label": "DaVinci Resolve", "timeline": ["fcpxml", "edl", "otio"], "grading": ["cube", "cdl", "resolve_python"]},
    "premiere": {"label": "Adobe Premiere Pro", "timeline": ["fcpxml", "edl", "otio"], "grading": ["cube", "cdl", "premiere_uxp_manifest"]},
    "final_cut": {"label": "Final Cut Pro", "timeline": ["fcpxml", "otio"], "grading": ["cube", "cdl"]},
    "capcut": {"label": "CapCut", "timeline": ["edit_plan"], "grading": ["cube_if_supported", "grade_recipe"]},
    "vn": {"label": "VN Video Editor", "timeline": ["edit_plan"], "grading": ["cube_if_supported", "grade_recipe"]},
}


@dataclass(frozen=True)
class Clip:
    id: str
    path: str
    name: str
    kind: str
    duration: float
    width: int = 0
    height: int = 0
    fps: float = 0.0
    video_codec: str = ""
    audio_codec: str = ""
    channels: int = 0
    sample_rate: int = 0
    timebase: str = ""
    reel: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EditDecision:
    clip_id: str
    timeline_in: float
    timeline_out: float
    source_in: float = 0.0
    source_out: float | None = None
    track: int = 1
    role: str = "picture"
    notes: str = ""


@dataclass
class EditProject:
    name: str
    brief: str
    editor: str = "resolve"
    width: int = 1920
    height: int = 1080
    fps: float = 24.0
    sample_rate: int = 48000
    decisions: list[EditDecision] = field(default_factory=list)
    markers: list[dict[str, Any]] = field(default_factory=list)


def _run(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=timeout)


def _fps(value: Any) -> float:
    if not value:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if "/" in str(value):
        numerator, denominator = str(value).split("/", 1)
        try:
            return float(numerator) / float(denominator)
        except (ValueError, ZeroDivisionError):
            return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def scan_media(root: str | Path, recursive: bool = True) -> list[Clip]:
    if shutil.which("ffprobe") is None:
        raise RuntimeError("ffprobe is required. Install FFmpeg and put ffprobe on PATH.")
    base = Path(root).expanduser().resolve()
    if not base.is_dir():
        raise FileNotFoundError(f"Media directory does not exist: {base}")
    paths = sorted(
        p for p in (base.rglob("*") if recursive else base.glob("*"))
        if p.is_file() and p.suffix.lower() in MEDIA_EXTS
    )
    clips: list[Clip] = []
    for path in paths:
        payload = json.loads(
            _run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]).stdout or "{}"
        )
        streams = payload.get("streams") or []
        fmt = payload.get("format") or {}
        video = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
        raw_duration = fmt.get("duration") or (video or {}).get("duration") or (audio or {}).get("duration") or 0
        duration = float(raw_duration)
        suffix = path.suffix.lower()
        if suffix in IMAGE_EXTS:
            kind = "image"
            duration = max(5.0, duration)
        elif video:
            kind = "video"
        elif audio:
            kind = "audio"
        else:
            kind = "unknown"
        relative = path.relative_to(base).as_posix()
        tags = fmt.get("tags") or {}
        clips.append(
            Clip(
                id=hashlib.sha1(relative.encode("utf-8")).hexdigest()[:12],
                path=str(path), name=path.name, kind=kind, duration=max(0.0, duration),
                width=int((video or {}).get("width") or 0),
                height=int((video or {}).get("height") or 0),
                fps=_fps((video or {}).get("avg_frame_rate") or (video or {}).get("r_frame_rate")),
                video_codec=str((video or {}).get("codec_name") or ""),
                audio_codec=str((audio or {}).get("codec_name") or ""),
                channels=int((audio or {}).get("channels") or 0),
                sample_rate=int((audio or {}).get("sample_rate") or 0),
                timebase=str((video or {}).get("time_base") or (audio or {}).get("time_base") or ""),
                reel=str(tags.get("reel_name") or path.stem),
            )
        )
    return clips


def _words(value: str) -> set[str]:
    return set(re.findall(r"[A-Za-z0-9]{3,}", value.lower()))


def suggest_edit_plan(clips: Iterable[Clip], brief: str, duration_seconds: float | None = None) -> EditProject:
    items = list(clips)
    candidates = [clip for clip in items if clip.kind in {"video", "image"} and clip.duration > 0]
    if not candidates:
        raise ValueError("No usable video clips or still images were found in the media folder.")
    if duration_seconds is not None:
        if not math.isfinite(duration_seconds) or duration_seconds <= 0:
            raise ValueError("duration_seconds must be a finite number greater than zero.")
        target = float(duration_seconds)
    else:
        target = sum(clip.duration for clip in candidates)
    query = _words(brief)
    ranked: list[tuple[int, Clip]] = []
    for clip in candidates:
        score = len(query & _words(f"{clip.name} {' '.join(clip.tags)}"))
        score += 3 if clip.kind == "video" else 1
        score += 1 if clip.duration >= 3 else 0
        ranked.append((score, clip))
    ranked.sort(key=lambda item: (-item[0], item[1].name.lower(), item[1].id))
    cursor = 0.0
    decisions: list[EditDecision] = []
    for _, clip in ranked:
        if cursor >= target:
            break
        take = min(clip.duration, target - cursor)
        if not math.isfinite(take) or take <= 0:
            continue
        decisions.append(EditDecision(
            clip_id=clip.id,
            timeline_in=cursor,
            timeline_out=cursor + take,
            source_in=0.0,
            source_out=take,
            notes="Deterministic VDO first pass; review and refine before picture lock.",
        ))
        cursor += take
    if not decisions:
        raise ValueError("The media folder did not contain any usable timeline duration.")
    return EditProject("VDO Documentary", brief.strip() or "Documentary edit", decisions=decisions)


def _rate(fps: float) -> tuple[int, int]:
    from fractions import Fraction
    if not math.isfinite(fps) or fps <= 0 or fps > 240:
        raise ValueError("fps must be finite and between 0 and 240.")
    fraction = Fraction(fps).limit_denominator(1001)
    return fraction.numerator, fraction.denominator


def _project_duration(project: EditProject) -> float:
    return max((decision.timeline_out for decision in project.decisions), default=0.0)


def _validate_project(project: EditProject, clips: dict[str, Clip]) -> None:
    _rate(project.fps)
    if project.width <= 0 or project.height <= 0:
        raise ValueError("Timeline width and height must be positive integers.")
    if not project.decisions:
        raise ValueError("Cannot export an empty timeline.")
    previous_end = 0.0
    for index, decision in enumerate(project.decisions, 1):
        if decision.clip_id not in clips:
            raise ValueError(f"Edit decision {index} references unknown clip id: {decision.clip_id}")
        clip = clips[decision.clip_id]
        values = (decision.timeline_in, decision.timeline_out, decision.source_in)
        if not all(math.isfinite(value) for value in values):
            raise ValueError(f"Edit decision {index} contains non-finite time values.")
        source_out = decision.source_out
        if source_out is None:
            source_out = decision.source_in + (decision.timeline_out - decision.timeline_in)
        if not math.isfinite(source_out):
            raise ValueError(f"Edit decision {index} has a non-finite source out.")
        timeline_duration = decision.timeline_out - decision.timeline_in
        source_duration = source_out - decision.source_in
        if decision.timeline_in < 0 or timeline_duration <= 0:
            raise ValueError(f"Edit decision {index} must have a non-negative in-point and positive duration.")
        if decision.source_in < 0 or source_duration <= 0:
            raise ValueError(f"Edit decision {index} must have a non-negative source in-point and positive source duration.")
        if decision.timeline_in < previous_end - 1e-6:
            raise ValueError(f"Edit decision {index} overlaps the previous timeline edit.")
        if abs(timeline_duration - source_duration) > max(1.0 / project.fps, 1e-3):
            raise ValueError(f"Edit decision {index} changes playback speed; retiming is not supported by this exporter.")
        if clip.duration > 0 and source_out > clip.duration + max(1.0 / project.fps, 1e-3):
            raise ValueError(f"Edit decision {index} runs past source media duration for {clip.name}.")
        previous_end = decision.timeline_out


def _tc(seconds: float, fps: float) -> str:
    nominal_rate = max(1, int(round(fps)))
    total_frames = max(0, int(round(seconds * fps)))
    hours, remainder = divmod(total_frames, nominal_rate * 3600)
    minutes, remainder = divmod(remainder, nominal_rate * 60)
    secs, frames = divmod(remainder, nominal_rate)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}:{frames:02d}"


def write_edl(project: EditProject, clips: dict[str, Clip], path: str | Path) -> Path:
    _validate_project(project, clips)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"TITLE: {project.name}", "FCM: NON-DROP FRAME", ""]
    for event, decision in enumerate(project.decisions, 1):
        clip = clips[decision.clip_id]
        source_out = decision.source_out
        if source_out is None:
            source_out = decision.source_in + decision.timeline_out - decision.timeline_in
        reel = re.sub(r"[^A-Za-z0-9_]", "_", clip.reel or Path(clip.name).stem)[:8].upper()
        lines.append(
            f"{event:03d}  {reel:8s} V     C        "
            f"{_tc(decision.source_in, project.fps)} {_tc(source_out, project.fps)} "
            f"{_tc(decision.timeline_in, project.fps)} {_tc(decision.timeline_out, project.fps)}"
        )
        lines.append(f"* FROM CLIP NAME: {clip.name}")
        if decision.notes:
            lines.append(f"* NOTE: {decision.notes}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def write_fcpxml(project: EditProject, clips: dict[str, Clip], path: str | Path) -> Path:
    _validate_project(project, clips)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    numerator, denominator = _rate(project.fps)
    root = ET.Element("fcpxml", {"version": "1.10"})
    resources = ET.SubElement(root, "resources")
    ET.SubElement(resources, "format", {
        "id": "r1", "name": f"{project.width}x{project.height}",
        "frameDuration": f"{denominator}/{numerator}s",
        "width": str(project.width), "height": str(project.height),
    })
    references: dict[str, str] = {}
    for index, clip in enumerate(clips.values(), start=10):
        resource_id = f"r{index}"
        references[clip.id] = resource_id
        attrs = {
            "id": resource_id,
            "name": clip.name,
            "src": Path(clip.path).resolve().as_uri(),
            "start": "0s",
            "duration": f"{max(clip.duration, 0.001):.6f}s",
        }
        if clip.kind in {"video", "image"}:
            attrs["format"] = "r1"
        ET.SubElement(resources, "asset", attrs)
    library = ET.SubElement(root, "library")
    event = ET.SubElement(library, "event", {"name": project.name})
    project_node = ET.SubElement(event, "project", {"name": project.name})
    sequence = ET.SubElement(project_node, "sequence", {
        "format": "r1", "duration": f"{_project_duration(project):.6f}s",
        "tcStart": "0s", "tcFormat": "NDF",
    })
    spine = ET.SubElement(sequence, "spine")
    for decision in project.decisions:
        clip = clips[decision.clip_id]
        source_out = decision.source_out
        if source_out is None:
            source_out = decision.source_in + decision.timeline_out - decision.timeline_in
        ET.SubElement(spine, "asset-clip", {
            "name": clip.name,
            "ref": references[clip.id],
            "offset": f"{decision.timeline_in:.6f}s",
            "start": f"{decision.source_in:.6f}s",
            "duration": f"{max(0.001, source_out - decision.source_in):.6f}s",
        })
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(out, encoding="utf-8", xml_declaration=True)
    return out


def write_otio(project: EditProject, clips: dict[str, Clip], path: str | Path) -> Path:
    _validate_project(project, clips)
    try:
        import opentimelineio as otio
    except ImportError as exc:
        raise RuntimeError("OpenTimelineIO is not installed. Install the VDO post extra.") from exc
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    timeline = otio.schema.Timeline(name=project.name)
    track = otio.schema.Track(name="Picture", kind="Video")
    timeline.tracks.append(track)
    for decision in project.decisions:
        clip = clips[decision.clip_id]
        source_out = decision.source_out
        if source_out is None:
            source_out = decision.source_in + decision.timeline_out - decision.timeline_in
        reference = otio.schema.ExternalReference(target_url=Path(clip.path).resolve().as_uri())
        item = otio.schema.Clip(name=clip.name, media_reference=reference)
        item.source_range = otio.opentime.TimeRange(
            start_time=otio.opentime.RationalTime(decision.source_in * project.fps, project.fps),
            duration=otio.opentime.RationalTime((source_out - decision.source_in) * project.fps, project.fps),
        )
        item.metadata["vdo"] = {"clip_id": clip.id, "notes": decision.notes}
        track.append(item)
    otio.adapters.write_to_file(timeline, str(out), adapter_name="otio_json")
    return out


def _look(style: str) -> dict[str, float]:
    key = style.strip().lower().replace(" ", "_")
    presets = {
        "neutral_documentary": (1.025, 0.98, 0.0, 0.0, 0.0, 1.0),
        "warm_documentary": (1.04, 1.02, 0.012, -0.002, 0.006, 0.995),
        "cool_observational": (1.035, 0.98, -0.010, 0.008, 0.004, 1.002),
        "night_cinematic": (1.06, 0.93, -0.014, 0.014, 0.0, 1.01),
        "mono": (1.06, 0.0, 0.0, 0.0, 0.004, 1.0),
    }
    if key not in presets:
        raise ValueError(f"Unknown color style '{style}'. Choose one of: {', '.join(COLOR_STYLES)}")
    contrast, saturation, warm, teal, fade, gamma = presets[key]
    return {"contrast": contrast, "saturation": saturation, "warm": warm, "teal": teal, "fade": fade, "gamma": gamma}


def _grade(red: float, green: float, blue: float, params: dict[str, float]) -> tuple[float, float, float]:
    rgb = [max(0.0, min(1.0, ((channel - 0.5) * params["contrast"]) + 0.5)) for channel in (red, green, blue)]
    luminance = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
    rgb = [luminance + (channel - luminance) * params["saturation"] for channel in rgb]
    rgb[0] += params["warm"]
    rgb[2] -= params["warm"]
    rgb[2] += params["teal"]
    rgb[1] += params["teal"] * 0.35
    rgb = [channel * (1.0 - params["fade"]) + params["fade"] * 0.035 for channel in rgb]
    rgb = [max(0.0, min(1.0, channel ** params["gamma"])) for channel in rgb]
    return (rgb[0], rgb[1], rgb[2])


def write_cube_lut(style: str, path: str | Path, size: int = 33) -> Path:
    if size not in (17, 33, 65):
        raise ValueError("LUT size must be 17, 33 or 65.")
    params = _look(style)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    safe_title = re.sub(r'["\r\n]', "", style)
    lines = [f'TITLE "VDO {safe_title}"', f"LUT_3D_SIZE {size}", "DOMAIN_MIN 0 0 0", "DOMAIN_MAX 1 1 1"]
    # .cube ordering: red varies fastest, then green, then blue.
    for blue_i in range(size):
        blue = blue_i / (size - 1)
        for green_i in range(size):
            green = green_i / (size - 1)
            for red_i in range(size):
                red = red_i / (size - 1)
                lines.append(" ".join(f"{channel:.6f}" for channel in _grade(red, green, blue, params)))
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def write_asc_cdl(style: str, path: str | Path) -> Path:
    params = _look(style)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    safe_id = re.sub(r"[^A-Za-z0-9]+", "-", style).strip("-") or "look"
    contrast, warm, saturation = params["contrast"], params["warm"], params["saturation"]
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<ColorDecisionList xmlns="urn:ASC:CDL:v1.01">
  <ColorDecision>
    <ColorCorrection id="VDO-{safe_id}">
      <SOPNode>
        <Slope>{contrast:.6f} {contrast:.6f} {max(0.0, contrast - warm):.6f}</Slope>
        <Offset>{warm:.6f} {warm * 0.35:.6f} {-warm:.6f}</Offset>
        <Power>1.000000 1.000000 1.000000</Power>
      </SOPNode>
      <SatNode>{saturation:.6f}</SatNode>
    </ColorCorrection>
  </ColorDecision>
</ColorDecisionList>
'''
    out.write_text(xml, encoding="utf-8")
    return out


def write_resolve_script(lut: Path, output: str | Path) -> Path:
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    escaped = str(lut.resolve()).replace("\\", "\\\\")
    script = f'''LUT_PATH = r"{escaped}"

def get_resolve():
    import DaVinciResolveScript as dvr_script
    return dvr_script.scriptapp("Resolve")

def apply_grade():
    resolve = get_resolve()
    manager = resolve.GetProjectManager()
    project = manager.GetCurrentProject() if manager else None
    if not project:
        raise RuntimeError("Open a Resolve project before running this helper.")
    timeline = project.GetCurrentTimeline()
    if not timeline:
        raise RuntimeError("Select a timeline before running this helper.")
    project.RefreshLUTList()
    items = timeline.GetItemListInTrack("video", 1) or []
    applied = 0
    for item in items:
        if item.GetNumNodes() >= 1 and item.SetLUT(1, LUT_PATH):
            applied += 1
    return {{"timeline": timeline.GetName(), "applied": applied, "lut": LUT_PATH}}

if __name__ == "__main__":
    print(apply_grade())
'''
    out.write_text(script, encoding="utf-8")
    return out


def write_grade_recipe(style: str, path: str | Path) -> Path:
    recipe = {
        "style": style,
        "type": "display-referred-look",
        "warning": "Normalize LOG/RAW input first. ASC CDL is an approximation; the .cube is the preferred look interchange.",
        "parameters": _look(style),
    }
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(recipe, indent=2) + "\n", encoding="utf-8")
    return out


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value.lower()).strip("-")
    return slug or "vdo-project"


def _write_uxp_handoff(output: Path, package_dir: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "name": "VDO Post Production",
        "description": "Editorial/color handoff guide; not an installed UXP plugin.",
        "package_dir": str(package_dir),
        "steps": [
            "Import the open interchange timeline and verify media links.",
            "Review edit decisions before picture lock.",
            "Normalize camera LOG/RAW correctly before applying the display-referred LUT.",
            "Finish shot matching and audio in the NLE.",
        ],
    }
    output.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


def create_post_package(
    media_dir: str | Path,
    output_dir: str | Path,
    *,
    brief: str,
    editor: str = "resolve",
    duration_seconds: float | None = None,
    project_name: str = "VDO Documentary",
    width: int = 1920,
    height: int = 1080,
    fps: float = 24.0,
    color_style: str = "neutral_documentary",
) -> dict[str, Any]:
    editor_key = editor.strip().lower().replace(" ", "_")
    editor_key = {
        "davinci": "resolve",
        "davinci_resolve": "resolve",
        "premiere_pro": "premiere",
        "final_cut_pro": "final_cut",
        "finalcut": "final_cut",
    }.get(editor_key, editor_key)
    if editor_key not in EDITOR_CAPABILITIES:
        raise ValueError(f"Unsupported editor '{editor}'. Choose: {', '.join(EDITOR_CAPABILITIES)}")
    if not project_name.strip():
        raise ValueError("project_name cannot be empty.")
    if not brief.strip():
        raise ValueError("brief cannot be empty.")
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive integers.")
    _rate(fps)
    _look(color_style)

    media_root = Path(media_dir).expanduser().resolve()
    output_root = Path(output_dir).expanduser().resolve()
    if not media_root.is_dir():
        raise FileNotFoundError(f"Media directory does not exist: {media_root}")
    if output_root == media_root or media_root in output_root.parents:
        raise ValueError("Choose an output directory outside the media folder to avoid re-scanning generated exports.")

    clips = scan_media(media_root)
    clip_map = {clip.id: clip for clip in clips}
    project = suggest_edit_plan(clips, brief, duration_seconds)
    project.name = project_name
    project.editor = editor_key
    project.width = width
    project.height = height
    project.fps = fps
    _validate_project(project, clip_map)

    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "media_manifest.json").write_text(json.dumps([asdict(clip) for clip in clips], indent=2) + "\n", encoding="utf-8")
    (output_root / "EDIT_PLAN.json").write_text(json.dumps({"project": asdict(project), "clips": [asdict(clip) for clip in clips]}, indent=2) + "\n", encoding="utf-8")

    interchange = output_root / "interchange"
    interchange.mkdir(parents=True, exist_ok=True)
    slug = _slug(project.name)
    write_fcpxml(project, clip_map, interchange / f"{slug}.fcpxml")
    write_edl(project, clip_map, interchange / f"{slug}.edl")
    otio_status = "not installed"
    try:
        write_otio(project, clip_map, interchange / f"{slug}.otio")
        otio_status = "generated"
    except RuntimeError as exc:
        if "not installed" not in str(exc):
            raise

    color_dir = output_root / "color"
    color_dir.mkdir(parents=True, exist_ok=True)
    safe_style = _slug(color_style)
    lut = write_cube_lut(color_style, color_dir / f"VDO_{safe_style}.cube", size=33)
    cdl = write_asc_cdl(color_style, color_dir / f"VDO_{safe_style}.cdl")
    write_grade_recipe(color_style, color_dir / f"VDO_{safe_style}.json")
    write_resolve_script(lut, output_root / "resolve" / "apply_vdo_grade.py")
    _write_uxp_handoff(output_root / "premiere" / "vdo_handoff.json", output_root)

    guides = {
        "resolve": "Import the FCPXML and verify media/frame rate. Review the timeline, then run apply_vdo_grade.py from a trusted Resolve scripting environment. Use the Color page to normalize inputs and shot-match.",
        "premiere": "Import a supported interchange timeline and verify links. Apply the generated .cube through Lumetri after correct input normalization; then refine shot matching and audio.",
        "final_cut": "Import FCPXML, verify links and frame rate, refine the edit, then apply the generated look and finish audio.",
        "capcut": "Use EDIT_PLAN.json as the shot-order blueprint. Import media manually if FCPXML/EDL import is unavailable in your build. VDO does not depend on private project internals.",
        "vn": "Use EDIT_PLAN.json as the shot-order blueprint and apply the LUT/recipe if supported by your VN build. VDO does not reverse-engineer private project internals.",
    }
    for target, instructions in guides.items():
        guide = output_root / target / "IMPORT_GUIDE.md"
        guide.parent.mkdir(parents=True, exist_ok=True)
        guide.write_text("# VDO handoff\n\n" + instructions + "\n", encoding="utf-8")

    readme = (
        f"# {project.name}\n\n{project.brief}\n\n"
        f"Target editor: {EDITOR_CAPABILITIES[editor_key]['label']}\n\n"
        f"Actual first-pass duration: {_project_duration(project):.2f} seconds\n\n"
        "Timeline handoff: interchange/\n\nColor handoff: color/\n\n"
        "The generated look is display-referred; normalize LOG/RAW input first. "
        "Review shot choices and media licensing before delivery.\n"
    )
    (output_root / "README.md").write_text(readme, encoding="utf-8")
    return {
        "project": asdict(project),
        "media_count": len(clips),
        "decision_count": len(project.decisions),
        "requested_duration_seconds": duration_seconds,
        "actual_duration_seconds": round(_project_duration(project), 3),
        "editor": EDITOR_CAPABILITIES[editor_key],
        "output_dir": str(output_root),
        "otio": otio_status,
        "lut": str(lut),
        "cdl": str(cdl),
        "artifacts": sorted(str(path.relative_to(output_root)) for path in output_root.rglob("*") if path.is_file()),
        "review_required": True,
    }


def tool_health() -> dict[str, Any]:
    try:
        import opentimelineio
        otio_installed = True
    except Exception:
        otio_installed = False
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "ffprobe": shutil.which("ffprobe") is not None,
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "open_timeline_io": otio_installed,
        "supported_color_styles": list(COLOR_STYLES),
        "editors": EDITOR_CAPABILITIES,
    }
