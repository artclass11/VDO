from __future__ import annotations

import asyncio
import json
from pathlib import Path

from vdo.config import SETTINGS
from vdo.providers.llm import generate_documentary
from vdo.providers.media import download_assets, save_manifest
from vdo.providers.research import research_topic
from vdo.providers.tts import synthesize_scenes
from vdo.render import burn_subtitles, concatenate, render_scene
from vdo.schemas import Documentary
from vdo.subtitles import make_srt
from vdo.utils import run, write_json


def _job_dir(topic: str, root: Path) -> Path:
    import hashlib
    slug = hashlib.sha1(topic.strip().lower().encode()).hexdigest()[:16]
    return root / slug


class DocumentaryPipeline:
    def __init__(self, topic: str, minutes: int = 10, output_dir: Path | None = None) -> None:
        self.topic = topic.strip()
        if not self.topic:
            raise ValueError("Topic cannot be empty")
        self.minutes = max(1, min(180, minutes))
        self.job_dir = _job_dir(self.topic, output_dir or SETTINGS.root)
        self.job_dir.mkdir(parents=True, exist_ok=True)

    async def run(self) -> Path:
        plan_path = self.job_dir / "documentary.json"
        research_path = self.job_dir / "research.json"
        media_dir = self.job_dir / "media"
        audio_dir = self.job_dir / "audio"
        scenes_dir = self.job_dir / "scenes"
        final_dir = self.job_dir / "final"
        final_dir.mkdir(parents=True, exist_ok=True)

        if plan_path.exists():
            doc = Documentary.model_validate_json(plan_path.read_text(encoding="utf-8"))
        else:
            research = await research_topic(self.topic)
            write_json(research_path, research)
            doc = await generate_documentary(self.topic, research, self.minutes)
            write_json(plan_path, doc.model_dump())

        scenes = [s.model_dump() for s in doc.scenes]

        manifest_path = media_dir / "manifest.json"
        if manifest_path.exists():
            assets = json.loads(manifest_path.read_text(encoding="utf-8"))
        else:
            assets = await download_assets(scenes, media_dir, SETTINGS.media_workers)
            save_manifest(manifest_path, assets)

        audio_files = await synthesize_scenes(
            scenes,
            audio_dir,
            workers=min(3, SETTINGS.workers),
        )

        scene_files: list[Path] = []
        for scene, audio in zip(scenes, audio_files):
            out = scenes_dir / f"scene_{int(scene['id']):03d}.mp4"
            if not out.exists():
                asset = next(
                    (x for x in assets if int(x["scene_id"]) == int(scene["id"])),
                    {},
                )
                await asyncio.to_thread(
                    render_scene,
                    asset.get("path"),
                    float(scene["seconds"]),
                    audio,
                    scene["title"],
                    out,
                )
            scene_files.append(out)

        assembled = final_dir / "documentary_clean.mp4"
        if not assembled.exists():
            await asyncio.to_thread(concatenate, scene_files, assembled)

        narration = self.job_dir / "narration.wav"
        if not narration.exists():
            concat_audio = self.job_dir / "audio_concat.txt"
            concat_audio.write_text(
                "\n".join(f"file '{p.resolve()}'" for p in audio_files) + "\n",
                encoding="utf-8",
            )
            run(
                [
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(concat_audio),
                    "-c:a", "pcm_s16le",
                    str(narration),
                ],
                timeout=900,
            )

        srt = self.job_dir / "captions.srt"
        if not srt.exists():
            await asyncio.to_thread(make_srt, narration, srt, SETTINGS.whisper_model)

        final = final_dir / "documentary.mp4"
        if not final.exists():
            await asyncio.to_thread(burn_subtitles, assembled, srt, final)

        write_json(
            self.job_dir / "job.json",
            {
                "topic": self.topic,
                "minutes": self.minutes,
                "title": doc.title,
                "output": str(final.resolve()),
                "research_file": str(research_path.resolve()),
                "media_manifest": str(manifest_path.resolve()),
            },
        )
        return final


async def generate(topic: str, minutes: int = 10, output_dir: Path | None = None) -> Path:
    return await DocumentaryPipeline(topic, minutes, output_dir).run()
