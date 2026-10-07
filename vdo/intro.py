from __future__ import annotations

import asyncio
from pathlib import Path

from vdo.config import SETTINGS
from vdo.music import generate_ambient_bed
from vdo.providers.media import download_assets, save_manifest
from vdo.providers.tts import synthesize_scenes
from vdo.render import burn_subtitles, concatenate, mix_music, render_scene
from vdo.subtitles import make_srt
from vdo.utils import write_json


INTRO_PIPELINE_VERSION = "1.0-production-intro"


def _plan(seconds: int) -> list[dict]:
    if seconds <= 30:
        return [
            {
                "id": 1,
                "title": "ONE IDEA",
                "narration": "Start with one idea.",
                "visual_query": "",
                "on_screen": "ONE IDEA",
                "story_role": "hook",
                "shot_type": "detail",
            },
            {
                "id": 2,
                "title": "RESEARCH",
                "narration": "VDO researches the subject, finds the evidence, and shapes a real story.",
                "visual_query": "researcher desk archival documents books notes documentary footage",
                "on_screen": "RESEARCH • STORY",
                "story_role": "context",
                "shot_type": "process",
            },
            {
                "id": 3,
                "title": "NATURAL NARRATION",
                "narration": "Natural narration is generated locally, while real people and real places keep the film grounded.",
                "visual_query": "person recording narration microphone studio documentary behind the scenes",
                "on_screen": "NATURAL VOICE • REAL WORLD",
                "story_role": "human",
                "shot_type": "human",
            },
            {
                "id": 4,
                "title": "THE EDIT",
                "narration": "Then the edit comes together with motion, music, and subtitles.",
                "visual_query": "film editor video editing timeline workstation documentary editing room",
                "on_screen": "EDIT • MIX • SUBTITLES",
                "story_role": "turning_point",
                "shot_type": "process",
            },
            {
                "id": 5,
                "title": "VDO",
                "narration": "VDO. Open Documentary Maker.",
                "visual_query": "",
                "on_screen": "VDO\nOPEN DOCUMENTARY MAKER",
                "story_role": "resolution",
                "shot_type": "detail",
            },
        ]
    return [
        {
            "id": 1,
            "title": "ONE IDEA",
            "narration": "Start with one idea. The rest should feel like filmmaking, not assembly.",
            "visual_query": "",
            "on_screen": "ONE IDEA",
            "story_role": "hook",
            "shot_type": "detail",
        },
        {
            "id": 2,
            "title": "RESEARCH",
            "narration": "VDO researches the subject, checks the evidence, and builds a story with a beginning, a turn, and a reason to care.",
            "visual_query": "researcher desk archival photographs documents books notes documentary footage",
            "on_screen": "RESEARCH • STORY",
            "story_role": "context",
            "shot_type": "process",
        },
        {
            "id": 3,
            "title": "REAL WORLD",
            "narration": "It looks for real moving footage, human details, archive material, and the moments that make the subject feel alive.",
            "visual_query": "real people working observational documentary street human detail archival footage",
            "on_screen": "REAL PEOPLE • REAL PLACES",
            "story_role": "human",
            "shot_type": "human",
        },
        {
            "id": 4,
            "title": "NATURAL NARRATION",
            "narration": "Natural narration is generated locally, with one consistent voice, clean mastering, and space for the story to breathe.",
            "visual_query": "person recording documentary narration microphone quiet recording studio close up",
            "on_screen": "NATURAL VOICE",
            "story_role": "evidence",
            "shot_type": "human",
        },
        {
            "id": 5,
            "title": "THE EDIT",
            "narration": "Then the film is assembled, mixed, captioned, and rendered as a finished 1080p documentary.",
            "visual_query": "professional film editor video timeline color grading workstation documentary post production",
            "on_screen": "EDIT • MIX • CAPTION • RENDER",
            "story_role": "turning_point",
            "shot_type": "process",
        },
        {
            "id": 6,
            "title": "LOCAL • RESUMABLE • OPEN",
            "narration": "It stays local-first, resumable, and open source, so the workflow can keep moving even when a hosted service is unavailable.",
            "visual_query": "developer terminal open source code laptop late night workstation documentary",
            "on_screen": "LOCAL • RESUMABLE • OPEN SOURCE",
            "story_role": "reflection",
            "shot_type": "detail",
        },
        {
            "id": 7,
            "title": "VDO",
            "narration": "VDO. Open Documentary Maker.",
            "visual_query": "",
            "on_screen": "VDO  •  OPEN DOCUMENTARY MAKER  •  github.com/artclass11/VDO",
            "story_role": "resolution",
            "shot_type": "detail",
        },
    ]


async def generate_intro(seconds: int = 40, output_dir: Path | None = None) -> Path:
    seconds = max(20, min(60, int(seconds)))
    root = output_dir or SETTINGS.root / "vdo-intro"
    root.mkdir(parents=True, exist_ok=True)

    plan = _plan(seconds)
    media_dir = root / "media"
    audio_dir = root / "audio"
    scenes_dir = root / "scenes"
    final_dir = root / "final"
    final_dir.mkdir(parents=True, exist_ok=True)

    assets = await download_assets(
        plan,
        media_dir,
        workers=SETTINGS.media_workers,
        real_footage_first=True,
    )
    save_manifest(media_dir / "manifest.json", assets)

    audio_files = await synthesize_scenes(plan, audio_dir, workers=1)

    scene_files: list[Path] = []
    for index, (scene, audio) in enumerate(zip(plan, audio_files)):
        out = scenes_dir / f"scene_{int(scene['id']):03d}.mp4"
        asset = next((x for x in assets if int(x["scene_id"]) == int(scene["id"])), {})
        render_scene(
            asset.get("path"),
            audio,
            scene["title"],
            out,
            opening=index == 0,
            on_screen=scene.get("on_screen", ""),
            story_role=scene.get("story_role", "context"),
        )
        scene_files.append(out)

    assembled = final_dir / "vdo_intro_clean.mp4"
    concatenate(scene_files, assembled)

    narration = root / "narration.wav"
    concat_audio = root / "audio_concat.txt"
    concat_audio.write_text(
        "\n".join(f"file '{p.resolve()}'" for p in audio_files) + "\n",
        encoding="utf-8",
    )
    from vdo.utils import run
    run(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_audio),
            "-c:a", "pcm_s16le",
            str(narration),
        ],
        timeout=900,
    )

    srt = root / "captions.srt"
    make_srt(narration, srt, SETTINGS.whisper_model)

    scored = final_dir / "vdo_intro_scored.mp4"
    duration = float(
        run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(assembled),
            ],
            timeout=60,
        ).stdout.strip()
    )
    music = root / "ambient_music.m4a"
    generate_ambient_bed(duration, music)
    mix_music(assembled, music, scored)

    final = final_dir / "vdo_intro.mp4"
    burn_subtitles(scored, srt, final)

    write_json(
        root / "intro.json",
        {
            "pipeline_version": INTRO_PIPELINE_VERSION,
            "target_seconds": seconds,
            "output": str(final.resolve()),
            "tts_provider": SETTINGS.tts_provider,
            "voice": SETTINGS.kokoro_voice if SETTINGS.tts_provider in {"auto", "kokoro"} else SETTINGS.qwen3_voice,
            "resolution": f"{SETTINGS.width}x{SETTINGS.height}",
            "fps": SETTINGS.fps,
            "open_source_visual_source": "Wikimedia Commons",
            "scenes": len(plan),
            "license_note": "Verify each retrieved Commons asset's individual license and attribution requirements before publication.",
        },
    )
    return final
