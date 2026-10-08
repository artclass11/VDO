from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from vdo.post import (
    EDITOR_CAPABILITIES,
    create_post_package,
    scan_media,
    suggest_edit_plan,
    tool_health,
    write_asc_cdl,
    write_cube_lut,
)

try:
    from mcp.server import MCPServer
except ImportError as exc:
    raise RuntimeError("VDO MCP requires MCP Python SDK v2. Install with: pip install -e '.[post]'") from exc

mcp = MCPServer(
    "vdo-post-production",
    title="VDO Post Production MCP",
    description="Professional documentary and film editorial, interchange, and color-finishing handoff tools.",
    instructions=(
        "Keep the workflow simple: analyze media, create a reviewable edit plan, "
        "choose the target editor, build interchange, then apply and refine the "
        "generated color look. Never claim an automatic picture lock or final grade "
        "without human review. Normalize LOG/RAW footage before display-referred LUTs."
    ),
)

@mcp.tool()
def vdo_health() -> dict:
    """Return local dependency and editor capability health."""
    return tool_health()

@mcp.tool()
def vdo_editors() -> dict:
    """List supported post-production editors and their safe interchange paths."""
    return EDITOR_CAPABILITIES

@mcp.tool()
def vdo_analyze_media(media_dir: str, recursive: bool = True) -> dict:
    """Scan a media folder with ffprobe and return a structured manifest."""
    clips = scan_media(media_dir, recursive=recursive)
    return {"media_dir": str(Path(media_dir).expanduser().resolve()), "count": len(clips), "clips": [asdict(c) for c in clips]}

@mcp.tool()
def vdo_make_edit_plan(
    media_dir: str,
    brief: str,
    duration_seconds: float | None = None,
    editor: str = "resolve",
    fps: float = 24.0,
) -> dict:
    """Create a deterministic, reviewable first-pass documentary edit plan."""
    clips = scan_media(media_dir)
    project = suggest_edit_plan(clips, brief, duration_seconds=duration_seconds)
    project.editor = editor
    project.fps = fps
    return {"project": asdict(project), "clips": [asdict(c) for c in clips], "review_required": True}

@mcp.tool()
def vdo_build_post_package(
    media_dir: str,
    output_dir: str,
    brief: str,
    editor: str = "resolve",
    duration_seconds: float | None = None,
    project_name: str = "VDO Documentary",
    width: int = 1920,
    height: int = 1080,
    fps: float = 24.0,
    color_style: str = "neutral_documentary",
) -> dict:
    """Build a complete editorial + color handoff package for Resolve, Premiere, Final Cut, CapCut, or VN."""
    return create_post_package(
        media_dir=media_dir,
        output_dir=output_dir,
        brief=brief,
        editor=editor,
        duration_seconds=duration_seconds,
        project_name=project_name,
        width=width,
        height=height,
        fps=fps,
        color_style=color_style,
    )

@mcp.tool()
def vdo_make_color_package(
    output_dir: str,
    color_style: str = "neutral_documentary",
    lut_size: int = 33,
) -> dict:
    """Create a display-referred .cube LUT, ASC CDL and machine-readable grade recipe."""
    root = Path(output_dir).expanduser().resolve()
    color = root / "color"
    color.mkdir(parents=True, exist_ok=True)
    safe = color_style.lower().replace(" ", "_")
    lut = write_cube_lut(color_style, color / f"VDO_{safe}.cube", size=lut_size)
    cdl = write_asc_cdl(color_style, color / f"VDO_{safe}.cdl")
    return {
        "lut": str(lut),
        "cdl": str(cdl),
        "style": color_style,
        "lut_size": lut_size,
        "warning": "Normalize LOG/RAW footage first; the VDO look is display-referred, not a camera IDT.",
    }

def main() -> None:
    mcp.run()

if __name__ == "__main__":
    main()
