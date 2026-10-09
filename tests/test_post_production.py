import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from vdo.post import core


def _clips():
    return {
        "a": core.Clip(id="a", path="/tmp/interview.mp4", name="interview.mp4", kind="video", duration=12, width=1920, height=1080, fps=24, reel="INTERVIEW"),
        "b": core.Clip(id="b", path="/tmp/broll.mp4", name="broll.mp4", kind="video", duration=8, width=1920, height=1080, fps=24, reel="BROLL"),
    }


def test_fcpxml_is_well_formed_and_all_refs_resolve(tmp_path: Path):
    clips = _clips()
    project = core.EditProject(
        name="Test Documentary",
        brief="Interview led documentary",
        fps=24,
        decisions=[
            core.EditDecision("a", 0, 6, 0, 6),
            core.EditDecision("b", 6, 10, 1, 5),
        ],
    )
    path = core.write_fcpxml(project, clips, tmp_path / "timeline.fcpxml")
    root = ET.parse(path).getroot()
    assert root.attrib["version"] == "1.10"
    ids = {node.attrib["id"] for node in root.findall(".//asset")}
    refs = {node.attrib["ref"] for node in root.findall(".//asset-clip")}
    assert refs <= ids
    assert len(refs) == 2


def test_edl_timecode_and_events(tmp_path: Path):
    clips = _clips()
    project = core.EditProject(
        name="Test Documentary",
        brief="Interview led documentary",
        fps=23.976,
        decisions=[core.EditDecision("a", 0, 6, 0, 6)],
    )
    path = core.write_edl(project, clips, tmp_path / "timeline.edl")
    text = path.read_text(encoding="utf-8")
    assert "FCM: NON-DROP FRAME" in text
    assert "001" in text and "* FROM CLIP NAME: interview.mp4" in text
    assert "00:00:06:00" in text


def test_lut_has_correct_cube_size_order_and_clamped_values(tmp_path: Path):
    lut = core.write_cube_lut("warm_documentary", tmp_path / "warm.cube", size=17)
    lines = [line for line in lut.read_text(encoding="utf-8").splitlines() if line and not line.startswith(("TITLE", "LUT_", "DOMAIN_"))]
    assert len(lines) == 17**3
    vals = [[float(v) for v in row.split()] for row in lines]
    assert all(len(row) == 3 and all(0 <= value <= 1 for value in row) for row in vals)
    assert vals[0] == pytest.approx(list(core._grade(0, 0, 0, core._look("warm_documentary"))))
    assert vals[1] == pytest.approx(list(core._grade(1/16, 0, 0, core._look("warm_documentary"))))


def test_cdl_is_well_formed_and_color_presets_are_explicit(tmp_path: Path):
    cdl = core.write_asc_cdl("warm_documentary", tmp_path / "warm.cdl")
    root = ET.parse(cdl).getroot()
    assert root.tag.endswith("ColorDecisionList")
    assert any(child.tag.endswith("SatNode") for child in root.iter())
    with pytest.raises(ValueError):
        core.write_cube_lut("invented_look", tmp_path / "bad.cube", size=17)


def test_edit_plan_never_selects_audio_and_does_not_overrun_clip():
    clips = [
        core.Clip(id="audio", path="/tmp/music.wav", name="music.wav", kind="audio", duration=100),
        core.Clip(id="tiny", path="/tmp/tiny.mp4", name="tiny.mp4", kind="video", duration=1.25),
        core.Clip(id="long", path="/tmp/long.mp4", name="long.mp4", kind="video", duration=20),
    ]
    plan = core.suggest_edit_plan(clips, "tiny b roll documentary", duration_seconds=2)
    assert len(plan.decisions) == 1
    assert plan.decisions[0].clip_id == "tiny"
    assert plan.decisions[0].source_out <= 1.25
    assert plan.decisions[0].timeline_out <= 1.25


def test_media_scanner_classifies_stills_as_images(monkeypatch, tmp_path: Path):
    photo = tmp_path / "portrait.jpg"
    photo.write_bytes(b"fake")
    payload = {
        "streams": [{"codec_type": "video", "codec_name": "mjpeg", "width": 640, "height": 480, "avg_frame_rate": "25/1"}],
        "format": {"duration": "0.04", "tags": {}},
    }
    monkeypatch.setattr(core.shutil, "which", lambda name: "/usr/bin/ffprobe")
    monkeypatch.setattr(core, "_run", lambda cmd, timeout=120: subprocess.CompletedProcess(cmd, 0, json.dumps(payload), ""))
    clip = core.scan_media(tmp_path)[0]
    assert clip.kind == "image"
    assert clip.duration >= 2


def test_unsupported_fps_and_bad_edit_decisions_are_rejected(tmp_path: Path):
    clips = _clips()
    with pytest.raises(ValueError):
        core.write_fcpxml(core.EditProject("bad", "bad", fps=0, decisions=[core.EditDecision("a", 0, 1, 0, 1)]), clips, tmp_path / "bad.fcpxml")
    with pytest.raises(ValueError):
        core.write_fcpxml(core.EditProject("bad", "bad", fps=24, decisions=[core.EditDecision("missing", 0, 1, 0, 1)]), clips, tmp_path / "bad.fcpxml")


def test_editor_package_support_surface():
    assert {"resolve", "premiere", "final_cut", "capcut", "vn"} <= set(core.EDITOR_CAPABILITIES)
