from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import httpx


COMMONS_API = "https://commons.wikimedia.org/w/api.php"
IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp"}
VIDEO_MIMES = {"video/mp4", "video/webm", "video/ogg"}
SUPPORTED = IMAGE_MIMES | VIDEO_MIMES


def _query_tokens(query: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9]{3,}", query.lower())
        if token not in {"video", "footage", "documentary", "real", "life"}
    ]


async def _search_commons(client: httpx.AsyncClient, query: str, limit: int = 10) -> list[dict]:
    response = await client.get(
        COMMONS_API,
        params={
            "action": "query",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": 6,
            "gsrlimit": limit,
            "prop": "imageinfo",
            "iiprop": "url|mime|extmetadata|size|duration|width|height",
            "iiurlwidth": 1920,
            "format": "json",
        },
    )
    response.raise_for_status()
    pages = response.json().get("query", {}).get("pages", {})
    assets = []
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        mime = info.get("mime", "")
        if mime not in SUPPORTED:
            continue
        meta = info.get("extmetadata", {})
        license_name = (meta.get("LicenseShortName") or {}).get("value", "").strip()
        assets.append(
            {
                "title": page.get("title", ""),
                "url": info.get("url"),
                "thumb_url": info.get("thumburl"),
                "mime": mime,
                "license": license_name,
                "author": (meta.get("Artist") or {}).get("value", ""),
                "description": re.sub(r"<[^>]+>", " ", description),
                "source": "Wikimedia Commons",
                "size": info.get("size", 0),
                "duration": info.get("duration", 0),
                "width": info.get("width", 0),
                "height": info.get("height", 0),
                "description_url": info.get("descriptionurl", ""),
            }
        )
    return assets


def _rank(asset: dict, query_tokens: list[str] | None = None, real_footage_first: bool = True) -> tuple:
    license_text = asset.get("license", "").lower()
    clear_license = 0 if (
        "public domain" in license_text
        or "cc0" in license_text
        or "cc by 4.0" in license_text
        or "cc by 3.0" in license_text
    ) else 1

    is_video = asset.get("mime") in VIDEO_MIMES
    title = str(asset.get("title", "")).lower()
    description = str(asset.get("description", "")).lower()
    query_tokens = query_tokens or _query_tokens(title)
    relevance = sum(1 for token in query_tokens if token in f"{title} {description}")

    width = int(asset.get("width") or 0)
    height = int(asset.get("height") or 0)
    if width >= 1920 and height >= 1080:
        resolution_rank = 0
    elif width >= 1280 and height >= 720:
        resolution_rank = 1
    else:
        resolution_rank = 2

    duration = float(asset.get("duration") or 0)
    useful_motion = 0 if is_video and 6 <= duration <= 180 else 1
    size_rank = 0 if int(asset.get("size") or 0) < 80_000_000 else 1
    generic_graphic = any(
        token in title for token in ("logo", "icon", "diagram", "illustration", "map", "poster")
    )
    graphic_rank = 1 if generic_graphic and not is_video else 0
    motion_rank = 0 if is_video else 1

    if real_footage_first:
        return (graphic_rank, -relevance, motion_rank, clear_license, resolution_rank, useful_motion, size_rank)
    return (graphic_rank, -relevance, clear_license, resolution_rank, motion_rank, useful_motion, size_rank)


async def download_assets(
    scenes: list[dict],
    output_dir: Path,
    workers: int = 8,
    real_footage_first: bool = True,
) -> list[dict]:
    output_dir.mkdir(parents=True, exist_ok=True)
    semaphore = asyncio.Semaphore(workers)

    async with httpx.AsyncClient(
        timeout=90,
        headers={"User-Agent": "VDO/2.0 open-source cinematic documentary engine"},
    ) as client:

        async def one(scene: dict) -> dict:
            scene_id = int(scene["id"])
            existing = [
                p for p in output_dir.glob(f"scene_{scene_id:03d}.*")
                if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".webm", ".ogg"}
            ]
            if existing:
                return {"scene_id": scene_id, "path": str(existing[0]), "source": "cache"}

            base_query = str(scene["visual_query"]).strip()
            shot_type = str(scene.get("shot_type", "b-roll")).strip().lower()
            story_role = str(scene.get("story_role", "context")).strip().lower()

            searches = [
                base_query,
                f"{base_query} documentary footage",
                f"{base_query} video",
                f"{base_query} moving footage",
            ]
            if shot_type in {"human", "interview"} or story_role == "human":
                searches.insert(0, f"{base_query} people real life")
            if shot_type in {"archive", "process"}:
                searches.insert(0, f"{base_query} archival footage")
            found: dict[str, dict] = {}
            for query in searches:
                for candidate in await _search_commons(client, query):
                    key = candidate.get("description_url") or candidate.get("url")
                    if key:
                        found[key] = candidate

            candidates = list(found.values())
            candidates.sort(
                key=lambda item: _rank(
                    item,
                    _query_tokens(base_query),
                    real_footage_first,
                )
            )
            if not candidates:
                return {"scene_id": scene_id, "path": None, "source": "none"}

            asset = candidates[0]
            ext = (
                ".mp4" if asset["mime"] == "video/mp4"
                else ".webm" if asset["mime"] == "video/webm"
                else ".ogg" if asset["mime"] == "video/ogg"
                else ".png" if asset["mime"] == "image/png"
                else ".webp" if asset["mime"] == "image/webp"
                else ".jpg"
            )
            path = output_dir / f"scene_{scene_id:03d}{ext}"

            download_url = asset["url"] if asset["mime"] in VIDEO_MIMES else (asset.get("thumb_url") or asset["url"])
            async with semaphore:
                response = await client.get(download_url, follow_redirects=True)
                response.raise_for_status()
                if len(response.content) > 80_000_000:
                    if asset.get("thumb_url"):
                        response = await client.get(asset["thumb_url"], follow_redirects=True)
                        response.raise_for_status()
                        asset["fallback_reason"] = "video-too-large"
                        ext = ".jpg"
                        path = output_dir / f"scene_{scene_id:03d}{ext}"
                    else:
                        return {"scene_id": scene_id, "path": None, "source": "asset-too-large", **asset}
                path.write_bytes(response.content)

            metadata = output_dir / f"scene_{scene_id:03d}.json"
            metadata.write_text(json.dumps(asset, ensure_ascii=False, indent=2), encoding="utf-8")
            return {"scene_id": scene_id, "path": str(path), **asset}

        return list(await asyncio.gather(*[one(scene) for scene in scenes]))


def save_manifest(path: Path, assets: list[dict]) -> None:
    path.write_text(json.dumps(assets, ensure_ascii=False, indent=2), encoding="utf-8")
