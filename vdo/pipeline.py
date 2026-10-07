from __future__ import annotations

import asyncio
import json
from pathlib import Path

from vdo.config import SETTINGS
from vdo.music import generate_ambient_bed
from vdo.providers.llm import generate_documentary
from vdo.providers.media import download_assets, save_manifest
from vdo.providers.research import research_topic
from vdo.providers.tts import synthesize_scenes
from vdo.render import burn_subtitles, concatenate, mix_music, render_scene
from vdo.schemas import Documentary, Source
from vdo.subtitles import make_srt
from vdo.utils import run, write_json


PIPELINE_VERSION = "3.0-real-documentary-story-engine"


def _job_dir(topic: str, root: Path) -> Path:
    import hashlib
    slug = hashlib.sha1(topic.strip().lower().encode()).hexdigest()[:16]
    return root / slug


def _normalize_timing(doc: Documentary, minutes: int) -> None:
    target = max(60.0, minutes * 60.0)
    current = sum(max(4.0, scene.seconds) for scene in doc.scenes)
    scale = target / max(current, 1.0)
    for scene in doc.scenes:
        scene.seconds = max(4.0, min(20.0, scene.seconds * scale))


def _reset_if_needed(job_dir: Path) -> None:
    marker = job_dir / "pipeline.version"
    old = marker.read_text(encoding="utf-8").strip() if marker.exists() else ""
    if old == PIPELINE_VERSION:
        return

    for pattern in (
        "documentary.json",
        "chapters.txt",
        "scenes/*.mp4",
        "final/*.mp4",
        "audio/*.wav",
        "media/manifest.json",
        "media/*.json",
        "media/*.jpg",
        "media/*.jpeg",
        "media/*.png",
        "media/*.webp",
        "media/*.mp4",
        "media/*.webm",
        "media/*.ogg",
        "narration.wav",
        "captions.srt",
        "ambient_music.m4a",
    ):
        for path in job_dir.glob(pattern):
            path.unlink(missing_ok=True)

    marker.write_text(PIPELINE_VERSION, encoding="utf-8")


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


class DocumentaryPipeline:
    def __init__(self, topic: str, minutes: int = 10, output_dir: Path | None = None) -> None:
        self.topic = topic.strip()
        if not self.topic:
            raise ValueError("Topic cannot be empty")
        self.minutes = max(1, min(180, minutes))
        self.job_dir = _job_dir(self.topic, output_dir or SETTINGS.root)
        self.job_dir.mkdir(parents=True, exist_ok=True)

    async def run(self) -> Path:
        _reset_if_needed(self.job_dir)

        plan_path = self.job_dir / "documentary.json"
        research_path = self.job_dir / "research.json"
        media_dir = self.job_dir / "media"
        audio_dir = self.job_dir / "audio"
        scenes_dir = self.job_dir / "scenes"
        final_dir = self.job_dir / "final"
        final_dir.mkdir(parents=True, exist_ok=True)

        if plan_path.exists() and research_path.exists():
            doc = Documentary.model_validate_json(plan_path.read_text(encoding="utf-8"))
        else:
            research = await research_topic(self.topic)
            write_json(research_path, research)
            doc = await generate_documentary(self.topic, research, self.minutes)
            doc.sources = [
                Source(
                    title=item["title"],
                    url=item["url"],
                    publisher=item.get("publisher", ""),
                    license=item.get("license", ""),
                )
                for item in research
                if item.get("url")
            ]
            _normalize_timing(doc, self.minutes)
            write_json(plan_path, doc.model_dump())

        scenes = [s.model_dump() for s in doc.scenes]

        manifest_path = media_dir / "manifest.json"
        if manifest_path.exists():
            assets = json.loads(manifest_path.read_text(encoding="utf-8"))
        else:
            assets = await download_assets(scenes, media_dir, SETTINGS.media_workers)
            save_manifest(manifest_path, assets)

        audio_files = await synthesize_scenes(scenes, audio_dir, workers=1)

        scene_files = [scenes_dir / f"scene_{int(s['id']):03d}.mp4" for s in scenes]
        scenes_dir.mkdir(parents=True, exist_ok=True)
        semaphore = asyncio.Semaphore(SETTINGS.workers)

        async def render_one(index: int, scene: dict, audio: Path, out: Path) -> Path:
            if out.exists() and out.stat().st_size > 1000:
                return out
            asset = next(
                (x for x in assets if int(x["scene_id"]) == int(scene["id"])),
                {},
            )
            async with semaphore:
                await asyncio.to_thread(
                    render_scene,
                    asset.get("path"),
                    audio,
                    scene["title"],
                    out,
                    opening=index == 0,
                    on_screen=scene.get("on_screen", ""),
                    story_role=scene.get("story_role", "context"),
                )
            return out

        await asyncio.gather(
            *[
                render_one(index, scene, audio, out)
                for index, (scene, audio, out) in enumerate(zip(scenes, audio_files, scene_files))
            ]
        )

        assembled = final_dir / "documentary_clean.mp4"
        if not assembled.exists():
            await asyncio.to_thread(concatenate, scene_files, assembled)

        chapters_path = self.job_dir / "chapters.txt"
        elapsed = 0.0
        seen_chapters: set[str] = set()
        chapter_lines: list[str] = []
        for scene, rendered in zip(scenes, scene_files):
            chapter = str(scene.get("chapter", "")).strip()
            if chapter and chapter not in seen_chapters:
                minutes_mark, seconds_mark = divmod(int(elapsed), 60)
                chapter_lines.append(f"{minutes_mark:02d}:{seconds_mark:02d} {chapter}")
                seen_chapters.add(chapter)
            elapsed += _duration(rendered)
        chapters_path.write_text("\n".join(chapter_lines) + ("\n" if chapter_lines else ""), encoding="utf-8")

        narration = self.job_dir / "narration.wav"
        if not narration.exists():
            concat_audio = self.job_dir / "audio_concat.txt"
            concat_audio.write_text(
                "\n".join(f"file '{p.resolve()}'" for p in audio_files) + "\n",
                encoding="utf-8",
            )
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

        srt = self.job_dir / "captions.srt"
        if not srt.exists():
            await asyncio.to_thread(make_srt, narration, srt, SETTINGS.whisper_model)

        scored = final_dir / "documentary_scored.mp4"
        if not scored.exists():
            duration = _duration(assembled)
            music = self.job_dir / "ambient_music.m4a"
            await asyncio.to_thread(generate_ambient_bed, duration, music)
            await asyncio.to_thread(mix_music, assembled, music, scored)

        final = final_dir / "documentary.mp4"
        if not final.exists():
            await asyncio.to_thread(burn_subtitles, scored, srt, final)

        write_json(
            self.job_dir / "job.json",
            {
                "pipeline_version": PIPELINE_VERSION,
                "topic": self.topic,
                "minutes_target": self.minutes,
                "title": doc.title,
                "tts_provider": SETTINGS.tts_provider,
                "cinematic": SETTINGS.cinematic,
                "transition_seconds": SETTINGS.transition_seconds,
                "output": str(final.resolve()),
                "chapters_file": str(chapters_path.resolve()),
                "hook": doc.hook,
                "anchor_fact": doc.anchor_fact,
                "human_stakes": doc.human_stakes,
                "research_file": str(research_path.resolve()),
                "media_manifest": str(manifest_path.resolve()),
            },
        )
        return final


async def generate(topic: str, minutes: int = 10, output_dir: Path | None = None) -> Path:
    return await DocumentaryPipeline(topic, minutes, output_dir).run()
