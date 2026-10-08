from dataclasses import asdict
from pathlib import Path

from vdo.post.core import Clip, EditDecision, EditProject, write_asc_cdl, write_cube_lut, write_edl, write_fcpxml


def _clips():
    return {
        "a": Clip(id="a", path="/tmp/interview.mp4", name="interview.mp4", kind="video", duration=12, width=1920, height=1080, fps=24, reel="INTERVIEW"),
        "b": Clip(id="b", path="/tmp/broll.mp4", name="broll.mp4", kind="video", duration=8, width=1920, height=1080, fps=24, reel="BROLL"),
    }


def test_fcpxml_and_edl_are_created(tmp_path: Path):
    clips = _clips()
    project = EditProject(
        name="Test Documentary",
        brief="Interview led documentary",
        fps=24,
        decisions=[
            EditDecision("a", 0, 6, 0, 6),
            EditDecision("b", 6, 10, 1, 5),
        ],
    )
    fcpxml = write_fcpxml(project, clips, tmp_path / "timeline.fcpxml")
    edl = write_edl(project, clips, tmp_path / "timeline.edl")
    assert fcpxml.exists()
    assert "<fcpxml version=\\"1.10\\"" in fcpxml.read_text(encoding="utf-8")
    assert "001" in edl.read_text(encoding="utf-8")
    assert asdict(project)["decisions"][0]["clip_id"] == "a"


def test_lut_and_cdl_have_valid_headers(tmp_path: Path):
    lut = write_cube_lut("warm_documentary", tmp_path / "warm.cube", size=17)
    cdl = write_asc_cdl("warm_documentary", tmp_path / "warm.cdl")
    lut_text = lut.read_text(encoding="utf-8")
    cdl_text = cdl.read_text(encoding="utf-8")
    assert "LUT_3D_SIZE 17" in lut_text
    assert "DOMAIN_MIN 0 0 0" in lut_text
    assert "<ColorDecisionList" in cdl_text
    assert "<SatNode>" in cdl_text


def test_editor_package_surface():
    from vdo.post.core import EDITOR_CAPABILITIES
    assert {"resolve", "premiere", "final_cut", "capcut", "vn"} <= set(EDITOR_CAPABILITIES)
