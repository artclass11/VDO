from __future__ import annotations

import hashlib
import json
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

EDITOR_CAPABILITIES: dict[str, dict[str, Any]] = {
    "resolve": {"label": "DaVinci Resolve", "timeline": ["fcpxml", "edl", "otio"], "grading": ["cube", "cdl", "resolve_python"]},
    "premiere": {"label": "Adobe Premiere Pro", "timeline": ["fcpxml", "edl", "otio"], "grading": ["cube", "cdl", "premiere_uxp_manifest"]},
    "final_cut": {"label": "Final Cut Pro", "timeline": ["fcpxml", "otio"], "grading": ["cube", "cdl"]},
    "capcut": {"label": "CapCut", "timeline": ["fcpxml", "edl", "otio"], "grading": ["cube", "grade_recipe"]},
    "vn": {"label": "VN Video Editor", "timeline": ["edl", "otio"], "grading": ["cube", "grade_recipe"]},
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

def _fps(v: Any) -> float:
    if not v:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if "/" in str(v):
        a, b = str(v).split("/", 1)
        try:
            return float(a) / float(b)
        except (ValueError, ZeroDivisionError):
            return 0.0
    try:
        return float(v)
    except ValueError:
        return 0.0

def scan_media(root: str | Path, recursive: bool = True) -> list[Clip]:
    if shutil.which("ffprobe") is None:
        raise RuntimeError("ffprobe is required. Install FFmpeg and put ffprobe on PATH.")
    base = Path(root).expanduser().resolve()
    if not base.is_dir():
        raise FileNotFoundError(f"Media directory does not exist: {base}")
    files = sorted(p for p in (base.rglob("*") if recursive else base.glob("*")) if p.is_file() and p.suffix.lower() in MEDIA_EXTS)
    result: list[Clip] = []
    for p in files:
        data = json.loads(_run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(p)]).stdout or "{}")
        streams = data.get("streams") or []
        fmt = data.get("format") or {}
        video = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
        duration = float(fmt.get("duration") or (video or {}).get("duration") or (audio or {}).get("duration") or 0)
        rel = p.relative_to(base).as_posix()
        result.append(Clip(
            id=hashlib.sha1(rel.encode()).hexdigest()[:12],
            path=str(p), name=p.name, kind="video" if video else "audio" if audio else "image",
            duration=max(0.0, duration),
            width=int((video or {}).get("width") or 0),
            height=int((video or {}).get("height") or 0),
            fps=_fps((video or {}).get("avg_frame_rate") or (video or {}).get("r_frame_rate")),
            video_codec=str((video or {}).get("codec_name") or ""),
            audio_codec=str((audio or {}).get("codec_name") or ""),
            channels=int((audio or {}).get("channels") or 0),
            sample_rate=int((audio or {}).get("sample_rate") or 0),
            timebase=str((video or {}).get("time_base") or (audio or {}).get("time_base") or ""),
            reel=str((fmt.get("tags") or {}).get("reel_name") or p.stem),
        ))
    return result

def _words(s: str) -> set[str]:
    return set(re.findall(r"[A-Za-z0-9]{3,}", s.lower()))

def suggest_edit_plan(clips: Iterable[Clip], brief: str, duration_seconds: float | None = None) -> EditProject:
    items = list(clips)
    if not items:
        raise ValueError("No media available for an edit plan.")
    target = max(5.0, float(duration_seconds or sum(max(2.0, c.duration) for c in items if c.kind == "video")))
    query = _words(brief)
    ranked = []
    for c in items:
        score = len(query & _words(c.name)) + (3 if c.kind == "video" else 0) + (1 if c.duration >= 3 else 0)
        ranked.append((score, c))
    ranked.sort(key=lambda x: (-x[0], x[1].name.lower()))
    cursor = 0.0
    decisions: list[EditDecision] = []
    for _, c in ranked:
        if c.kind != "video" or cursor >= target:
            continue
        take = min(max(2.0, c.duration), target - cursor)
        decisions.append(EditDecision(c.id, cursor, cursor + take, 0.0, take, notes="Deterministic VDO first pass; review before picture lock."))
        cursor += take
    return EditProject("VDO Documentary", brief.strip() or "Documentary edit", decisions=decisions)

def _rate(fps: float) -> tuple[int, int]:
    from fractions import Fraction
    f = Fraction(fps).limit_denominator(1001)
    return f.numerator, f.denominator

def _tc(seconds: float, fps: float) -> str:
    rate = max(1, int(round(fps)))
    frames = max(0, int(round(seconds * rate)))
    h, rem = divmod(frames, rate * 3600)
    m, rem = divmod(rem, rate * 60)
    s, f = divmod(rem, rate)
    return f"{h:02d}:{m:02d}:{s:02d}:{f:02d}"

def write_edl(project: EditProject, clips: dict[str, Clip], path: str | Path) -> Path:
    out = Path(path); out.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"TITLE: {project.name}", "FCM: NON-DROP FRAME", ""]
    for i, d in enumerate(project.decisions, 1):
        c = clips[d.clip_id]
        source_out = d.source_out if d.source_out is not None else c.duration
        lines.append(f"{i:03d}  {c.reel[:8]:8s} V     C        {_tc(d.source_in, project.fps)} {_tc(source_out, project.fps)} {_tc(d.timeline_in, project.fps)} {_tc(d.timeline_out, project.fps)}")
        lines.append(f"* FROM CLIP NAME: {c.name}")
        if d.notes:
            lines.append(f"* NOTE: {d.notes}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out

def write_fcpxml(project: EditProject, clips: dict[str, Clip], path: str | Path) -> Path:
    out = Path(path); out.parent.mkdir(parents=True, exist_ok=True)
    n, d = _rate(project.fps)
    root = ET.Element("fcpxml", {"version": "1.10"})
    resources = ET.SubElement(root, "resources")
    ET.SubElement(resources, "format", {"id": "r1", "name": f"{project.width}x{project.height}", "frameDuration": f"{n}/{d}s", "width": str(project.width), "height": str(project.height)})
    refs: dict[str, str] = {}
    for i, c in enumerate(clips.values(), 10):
        rid = f"r{i}"; refs[c.id] = rid
        attrs = {"id": rid, "name": c.name, "src": Path(c.path).resolve().as_uri(), "start": "0s", "duration": f"{max(c.duration, 0.001):.6f}s"}
        if c.kind == "video":
            attrs["format"] = "r1"
        ET.SubElement(resources, "asset", attrs)
    library = ET.SubElement(root, "library")
    event = ET.SubElement(library, "event", {"name": project.name})
    proj = ET.SubElement(event, "project", {"name": project.name})
    seq = ET.SubElement(proj, "sequence", {"format": "r1", "duration": f"{max((x.timeline_out for x in project.decisions), default=0):.6f}s", "tcStart": "0s", "tcFormat": "NDF"})
    spine = ET.SubElement(seq, "spine")
    for x in project.decisions:
        if x.clip_id not in refs:
            continue
        c = clips[x.clip_id]
        ET.SubElement(spine, "asset-clip", {
            "name": c.name, "ref": refs[c.id], "offset": f"{x.timeline_in:.6f}s",
            "start": f"{x.source_in:.6f}s", "duration": f"{max(0.001, x.timeline_out-x.timeline_in):.6f}s",
        })
    tree = ET.ElementTree(root)
    ET.indent(tree, "  ")
    tree.write(out, encoding="utf-8", xml_declaration=True)
    return out

def write_otio(project: EditProject, clips: dict[str, Clip], path: str | Path) -> Path:
    try:
        import opentimelineio as otio
    except ImportError as exc:
        raise RuntimeError("OpenTimelineIO is not installed. Install the VDO post extra.") from exc
    out = Path(path); out.parent.mkdir(parents=True, exist_ok=True)
    timeline = otio.schema.Timeline(name=project.name)
    track = otio.schema.Track(name="Picture", kind="Video")
    timeline.tracks.append(track)
    for d in project.decisions:
        c = clips[d.clip_id]
        source_out = d.source_out if d.source_out is not None else c.duration
        ref = otio.schema.ExternalReference(target_url=Path(c.path).resolve().as_uri())
        item = otio.schema.Clip(name=c.name, media_reference=ref)
        item.source_range = otio.opentime.TimeRange(
            otio.opentime.RationalTime(d.source_in * project.fps, project.fps),
            otio.opentime.RationalTime((source_out-d.source_in) * project.fps, project.fps),
        )
        item.metadata["vdo"] = {"clip_id": c.id, "notes": d.notes}
        track.append(item)
    otio.adapters.write_to_file(timeline, str(out), adapter_name="otio_json")
    return out

def _look(style: str) -> dict[str, float]:
    presets = {
        "neutral_documentary": (1.025, 0.98, 0.0, 0.0, 0.0, 1.0),
        "warm_documentary": (1.04, 1.02, 0.012, -0.002, 0.006, 0.995),
        "cool_observational": (1.035, 0.98, -0.010, 0.008, 0.004, 1.002),
        "night_cinematic": (1.06, 0.93, -0.014, 0.014, 0.0, 1.01),
        "mono": (1.06, 0.0, 0.0, 0.0, 0.004, 1.0),
    }
    c, s, w, t, f, g = presets.get(style.lower().replace(" ", "_"), presets["neutral_documentary"])
    return {"contrast": c, "saturation": s, "warm": w, "teal": t, "fade": f, "gamma": g}

def _grade(r: float, g: float, b: float, p: dict[str, float]) -> tuple[float, float, float]:
    rgb = [max(0, min(1, ((x-.5)*p["contrast"])+.5)) for x in (r,g,b)]
    lum = 0.2126*rgb[0]+0.7152*rgb[1]+0.0722*rgb[2]
    rgb = [lum+(x-lum)*p["saturation"] for x in rgb]
    rgb[0] += p["warm"]; rgb[2] -= p["warm"]; rgb[2] += p["teal"]; rgb[1] += p["teal"]*.35
    rgb = [x*(1-p["fade"])+p["fade"]*.035 for x in rgb]
    rgb = [max(0, min(1, x**p["gamma"])) for x in rgb]
    return tuple(rgb)

def write_cube_lut(style: str, path: str | Path, size: int = 33) -> Path:
    if size not in (17, 33, 65):
        raise ValueError("LUT size must be 17, 33 or 65.")
    out = Path(path); out.parent.mkdir(parents=True, exist_ok=True)
    p = _look(style)
    lines = [f'TITLE "VDO {style.replace(chr(34), "")}"', f"LUT_3D_SIZE {size}", "DOMAIN_MIN 0 0 0", "DOMAIN_MAX 1 1 1"]
    for ri in range(size):
        for gi in range(size):
            for bi in range(size):
                lines.append(" ".join(f"{v:.6f}" for v in _grade(ri/(size-1), gi/(size-1), bi/(size-1), p)))
    out.write_text("\n".join(lines)+"\n", encoding="utf-8")
    return out

def write_asc_cdl(style: str, path: str | Path) -> Path:
    out = Path(path); out.parent.mkdir(parents=True, exist_ok=True)
    p = _look(style)
    safe = re.sub(r"[^A-Za-z0-9]+", "-", style).strip("-") or "look"
    slope = p["contrast"]; warm = p["warm"]; sat = p["saturation"]
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<ColorDecisionList xmlns="urn:ASC:CDL:v1.01">
  <ColorDecision><ColorCorrection id="VDO-{safe}">
    <SOPNode>
      <Slope>{slope:.6f} {slope:.6f} {max(0.0, slope-warm):.6f}</Slope>
      <Offset>{warm:.6f} {warm*0.35:.6f} {-warm:.6f}</Offset>
      <Power>1 1 1</Power>
    </SOPNode>
    <SatNode>{sat:.6f}</SatNode>
  </ColorCorrection></ColorDecision>
</ColorDecisionList>
'''
    out.write_text(xml, encoding="utf-8")
    return out

def write_resolve_script(lut: Path, output: str | Path) -> Path:
    out = Path(output); out.parent.mkdir(parents=True, exist_ok=True)
    escaped = str(lut.resolve()).replace("\\", "\\\\")
    text = f'''from pathlib import Path

LUT_PATH = r"{escaped}"

def get_resolve():
    import DaVinciResolveScript as dvr_script
    return dvr_script.scriptapp("Resolve")

def apply_grade():
    resolve = get_resolve()
    project = resolve.GetProjectManager().GetCurrentProject()
    if not project:
        raise RuntimeError("No current Resolve project.")
    timeline = project.GetCurrentTimeline()
    if not timeline:
        raise RuntimeError("No current Resolve timeline.")
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
    out.write_text(text, encoding="utf-8")
    return out

def write_grade_recipe(style: str, path: str | Path) -> Path:
    out = Path(path); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"style": style, "type": "display-referred-look", "warning": "Normalize LOG/RAW input first.", "parameters": _look(style)}, indent=2)+"\n", encoding="utf-8")
    return out

def _slug(v: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", v.lower()).strip("-")
    return s or "vdo-project"

def create_post_package(media_dir: str | Path, output_dir: str | Path, *, brief: str, editor: str = "resolve", duration_seconds: float | None = None, project_name: str = "VDO Documentary", width: int = 1920, height: int = 1080, fps: float = 24.0, color_style: str = "neutral_documentary") -> dict[str, Any]:
    key = editor.lower().replace(" ", "_")
    key = {"davinci": "resolve", "premiere_pro": "premiere", "final_cut_pro": "final_cut"}.get(key, key)
    if key not in EDITOR_CAPABILITIES:
        raise ValueError(f"Unsupported editor: {editor}")
    root = Path(output_dir).expanduser().resolve(); root.mkdir(parents=True, exist_ok=True)
    clips = scan_media(media_dir)
    cmap = {c.id: c for c in clips}
    project = suggest_edit_plan(clips, brief, duration_seconds)
    project.name = project_name; project.editor = key; project.width = width; project.height = height; project.fps = fps
    (root/"media_manifest.json").write_text(json.dumps([asdict(c) for c in clips], indent=2)+"\n", encoding="utf-8")
    (root/"EDIT_PLAN.json").write_text(json.dumps({"project": asdict(project), "clips": [asdict(c) for c in clips]}, indent=2)+"\n", encoding="utf-8")
    it = root/"interchange"; it.mkdir(parents=True, exist_ok=True)
    write_fcpxml(project, cmap, it/f"{_slug(project.name)}.fcpxml")
    write_edl(project, cmap, it/f"{_slug(project.name)}.edl")
    otio_status = "not installed"
    try:
        write_otio(project, cmap, it/f"{_slug(project.name)}.otio"); otio_status = "generated"
    except RuntimeError:
        pass
    color = root/"color"; color.mkdir(parents=True, exist_ok=True)
    lut = write_cube_lut(color_style, color/f"VDO_{_slug(color_style)}.cube")
    cdl = write_asc_cdl(color_style, color/f"VDO_{_slug(color_style)}.cdl")
    recipe = write_grade_recipe(color_style, color/f"VDO_{_slug(color_style)}.json")
    write_resolve_script(lut, root/"resolve"/"apply_vdo_grade.py")
    guides = {
        "resolve": "Import the FCPXML, verify media, review picture lock, then run apply_vdo_grade.py from a trusted Resolve scripting environment. Use Color page for shot matching.",
        "premiere": "Import the interchange timeline, verify links, apply the generated cube look through Lumetri, then refine shot matching and audio.",
        "final_cut": "Import the FCPXML, verify media and frame rate, refine the cut, then apply the cube look and finish audio.",
        "capcut": "Import source media and use the EDL/edit plan where the local build supports the interchange. Apply the cube look only after input normalization. VDO does not use private project internals.",
        "vn": "Import source media and follow EDIT_PLAN.json. Use the cube/grade recipe when supported. VDO does not reverse-engineer private project internals.",
    }
    for name, text in guides.items():
        p = root/name/"IMPORT_GUIDE.md"; p.parent.mkdir(parents=True, exist_ok=True); p.write_text("# VDO handoff\n\n"+text+"\n", encoding="utf-8")
    (root/"README.md").write_text(f"# {project.name}\n\n{project.brief}\n\nTarget editor: {EDITOR_CAPABILITIES[key]['label']}\n\nTimeline handoff: interchange\nColor handoff: color\nResolve helper: resolve/apply_vdo_grade.py\n\nThe generated color look is display-referred; normalize LOG/RAW input first.\n", encoding="utf-8")
    return {"project": asdict(project), "media_count": len(clips), "decision_count": len(project.decisions), "editor": EDITOR_CAPABILITIES[key], "output_dir": str(root), "otio": otio_status, "artifacts": sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())}

def tool_health() -> dict[str, Any]:
    try:
        import opentimelineio
        otio = True
    except Exception:
        otio = False
    return {"platform": platform.platform(), "python": platform.python_version(), "ffprobe": shutil.which("ffprobe") is not None, "ffmpeg": shutil.which("ffmpeg") is not None, "open_timeline_io": otio, "editors": EDITOR_CAPABILITIES}
