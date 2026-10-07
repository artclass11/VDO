from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx


COMMONS_API = "https://commons.wikimedia.org/w/api.php"
IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp"}
VIDEO_MIMES = {"video/mp4", "video/webm", "video/ogg"}


async def _search_commons(client: httpx.AsyncClient, query: str, limit: int = 8) -> list[dict]:
    response = await client.get(
        COMMONS_API,
        params={
            "action": "query",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": 6,
            "gsrlimit": limit,
            "prop": "imageinfo",
            "iiprop": "url|mime|extmetadata|size|duration",
            "iiurlwidth": 1800,
            "format": "json",
        },
    )
    response.raise_for_status()
    pages = response.json().get("query", {}).get("pages", {})
    assets = []
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        mime = info.get("mime", "")
        if mime not in IMAGE_MIMES | VIDEO_MIMES:
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
                "description_url": info.get("descriptionurl", ""),
            }
        )
    return assets


def _rank(asset: dict) -> tuple:
    license_text = asset.get("license", "").lower()
    # Prefer clear open/public-domain licenses, then video for documentary motion.
    license_rank = 0 if ("public domain" in license_text or "cc0" in license_text) else 1
    motion_rank = 0 if asset["mime"] in VIDEO_MIMES else 1
    size_rank = 0 if asset.get("size", 0) < 50_000_000 else 1
    return (license_rank, motion_rank, size_rank)


async def download_assets(scenes: list[dict], output_dir: Path, workers: int = 8) -> list[dict]:
    output_dir.mkdir(parents=True, exist_ok=True)
    semaphore = asyncio.Semaphore(workers)

    async with httpx.AsyncClient(
        timeout=90,
        headers={"User-Agent": "VDO/1.1 open-source documentary engine"},
    ) as client:

        async def one(scene: dict) -> dict:
            scene_id = int(scene["id"])
            existing = [
                p for p in output_dir.glob(f"scene_{scene_id:03d}.*")
                if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".webm", ".ogg"}
            ]
            if existing:
                return {"scene_id": scene_id, "path": str(existing[0]), "source": "cache"}

            candidates = await _search_commons(client, scene["visual_query"])
            candidates.sort(key=_rank)
            if not candidates:
                return {"scene_id": scene_id, "path": None, "source": "none"}

            asset = candidates[0]
            ext = ".mp4" if asset["mime"] == "video/mp4" else (
                ".webm" if asset["mime"] == "video/webm" else
                ".ogg" if asset["mime"] == "video/ogg" else
                ".png" if asset["mime"] == "image/png" else
                ".webp" if asset["mime"] == "image/webp" else ".jpg"
            )
            path = output_dir / f"scene_{scene_id:03d}{ext}"

            async with semaphore:
                response = await client.get(asset["url"], follow_redirects=True)
                response.raise_for_status()
                if len(response.content) > 60_000_000:
                    # Fall back to a still image thumbnail if the video is too large.
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

        assets = await asyncio.gather(*[one(scene) for scene in scenes])
        return list(assets)


def save_manifest(path: Path, assets: list[dict]) -> None:
    path.write_text(json.dumps(assets, ensure_ascii=False, indent=2), encoding="utf-8")
