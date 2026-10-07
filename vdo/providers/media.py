from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx


COMMONS_API = "https://commons.wikimedia.org/w/api.php"
IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp"}
VIDEO_MIMES = {"video/mp4", "video/webm", "video/ogg"}
SUPPORTED = IMAGE_MIMES | VIDEO_MIMES


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
                "source": "Wikimedia Commons",
                "size": info.get("size", 0),
                "duration": info.get("duration", 0),
                "width": info.get("width", 0),
                "height": info.get("height", 0),
                "description_url": info.get("descriptionurl", ""),
            }
        )
    return assets


def _rank(asset: dict) -> tuple:
    license_text = asset.get("license", "").lower()
    clear_license = 0 if (
        "public domain" in license_text
        or "cc0" in license_text
        or "cc by 4.0" in license_text
        or "cc by 3.0" in license_text
    ) else 1
    is_video = asset.get("mime") in VIDEO_MIMES
    motion_rank = 0 if is_video else 1
    # Avoid tiny clips and huge originals; prefer 720p+ video where available.
    resolution_rank = 0 if (
        asset.get("width", 0) >= 1280 and asset.get("height", 0) >= 720
    ) else 1
    duration = float(asset.get("duration") or 0)
    useful_motion = 0 if is_video and 4 <= duration <= 180 else 1
    size = int(asset.get("size") or 0)
    size_rank = 0 if size < 60_000_000 else 1
    return (motion_rank, clear_license, useful_motion, resolution_rank, size_rank)


async def download_assets(scenes: list[dict], output_dir: Path, workers: int = 8) -> list[dict]:
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
            searches = [base_query, f"{base_query} video"]
            found: dict[str, dict] = {}
            for query in searches:
                for candidate in await _search_commons(client, query):
                    key = candidate.get("description_url") or candidate.get("url")
                    if key:
                        found[key] = candidate

            candidates = list(found.values())
            candidates.sort(key=_rank)
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

            async with semaphore:
                response = await client.get(asset["url"], follow_redirects=True)
                response.raise_for_status()
                if len(response.content) > 60_000_000:
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
