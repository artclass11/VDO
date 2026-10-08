# VDO Post-Production MCP

VDO now includes a post-production MCP that turns one natural-language brief into a reviewable documentary/film editing handoff.

## One simple workflow

1. Analyze the media folder.
2. Describe the story in one prompt.
3. Choose the editing system.
4. Generate the edit plan and interchange.
5. Review picture lock.
6. Apply the generated color look.
7. Finish shot matching, dialogue, ambience, music and delivery in the target NLE.

Example MCP intent:

    Make a 6-minute investigative documentary from ./media about the rise of illegal sand mining. Use DaVinci Resolve, 24 fps, natural documentary pacing, restrained lower thirds, and a neutral cinematic grade.

## Supported editors

| Editor | Primary handoff | Color handoff | Automation |
|---|---|---|---|
| DaVinci Resolve | FCPXML / EDL / OTIO | .cube + ASC CDL + Resolve Python helper | Local Resolve scripting |
| Premiere Pro | FCPXML / EDL / OTIO | .cube + ASC CDL | UXP-ready handoff |
| Final Cut Pro | FCPXML / OTIO | .cube + ASC CDL | Native FCPXML interchange |
| CapCut | Open interchange + edit plan | .cube + grade recipe | Guided handoff |
| VN | Edit plan + open interchange | .cube + grade recipe | Guided handoff |

VDO deliberately avoids undocumented private CapCut/VN project formats. The project remains portable and auditable through open interchange artifacts.

## Generated package

- media_manifest.json — ffprobe-derived source inventory
- EDIT_PLAN.json — human-reviewable edit decisions
- interchange/*.fcpxml — FCPXML sequence handoff
- interchange/*.edl — CMX-style edit decision list
- interchange/*.otio — OpenTimelineIO when installed
- color/*.cube — 33-point display-referred finishing look by default
- color/*.cdl — ASC CDL representation
- color/*.json — machine-readable grade recipe
- resolve/apply_vdo_grade.py — trusted local Resolve scripting helper
- per-editor IMPORT_GUIDE.md — minimal handoff instructions

## Professional color policy

VDO does not pretend a LUT can replace color management.

For LOG/RAW camera sources:

    camera RAW/LOG
        -> camera IDT / correct input transform
        -> exposure + white balance
        -> shot matching
        -> VDO display-referred look
        -> creative shot work
        -> output transform
        -> delivery

The generated VDO LUT is a finishing/look asset, not an IDT.

## MCP installation

From the repository root:

    pip install -e ".[post]"

Run the server:

    python mcp_server.py

For a local MCP-capable client, configure the command as:

    python /absolute/path/to/VDO/mcp_server.py

The MCP exposes:

- vdo_health
- vdo_editors
- vdo_analyze_media
- vdo_make_edit_plan
- vdo_build_post_package
- vdo_make_color_package

## Production notes

- The MCP is local-first: media paths remain on the workstation.
- Generated edit decisions are deterministic and reviewable instead of silently destructive.
- OpenTimelineIO is optional; when installed, VDO emits OTIO alongside FCPXML and EDL.
- Resolve automation is opt-in and requires a trusted local Resolve scripting environment.
- Human review remains mandatory for factual claims, shot selection, skin tones, legal/licensing checks, picture lock and final delivery.
