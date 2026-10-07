from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx


COMMONS_API = "https://commons.wikimedia.org/w/api.php"
ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp"}
LICENSE_PRIORITY = (
    "public domain",
    "cc0",
    "cc by",
    "cc by-sa",
)


async def _search_commons(
    client: httpx.AsyncClient,
    query: str,
    limit: int = 6,
) -> list[dict]:
    response = await client.get(
        COMMONS_API,
        params={
            "action": "query",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": 6,
            "gsrlimit": limit,
            "prop": "imageinfo",
            "iiprop": "url|mime|extmetadata",
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
        if mime not in ALLOWED_IMAGE_MIMES:
            continue
        meta = info.get("extmetadata", {})
        license_name = (meta.get("LicenseShortName") or {}).get("value", "").strip()
        assets.append(
            {
                "title": page.get("title", ""),
                "url": info.get("thumburl") or info.get("url"),
                "original_url": info.get("url"),
                "mime": mime,
                "license": license_name,
                "author": (meta.get("Artist") or {}).get("value", ""),
                "source": "Wikimedia Commons",
            }
        )
    assets.sort(
        key=lambda item: next(
            (i for i, label in enumerate(LICENSE_PRIORITY) if label in item["license"].lower()),
            99,
        )
    )
    return assets


async def download_assets(scenes: list[dict], output_dir: Path, workers: int = 8) -> list[dict]:
    output_dir.mkdir(parents=True, exist_ok=True)
    semaphore = asyncio.Semaphore(workers)

    async with httpx.AsyncClient(
        timeout=60,
        headers={"User-Agent": "VDO/1.0 open-source documentary engine"},
    ) as client:

        async def one(scene: dict) -> dict:
            scene_id = int(scene["id"])
            existing = list(output_dir.glob(f"scene_{scene_id:03d}.*"))
            if existing:
                return {"scene_id": scene_id, "path": str(existing[0]), "source": "cache"}

            assets = await _search_commons(client, scene["visual_query"])
            if not assets:
                return {"scene_id": scene_id, "path": None, "source": "none"}

            asset = assets[0]
            suffix = ".png" if asset["mime"] == "image/png" else ".webp" if asset["mime"] == "image/webp" else ".jpg"
            path = output_dir / f"scene_{scene_id:03d}{suffix}"

            async with semaphore:
                response = await client.get(asset["url"], follow_redirects=True)
                response.raise_for_status()
                if len(response.content) > 20_000_000:
                    return {"scene_id": scene_id, "path": None, "source": "asset-too-large", **asset}
                path.write_bytes(response.content)

            (output_dir / f"scene_{scene_id:03d}.json").write_text(
                json.dumps(asset, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return {"scene_id": scene_id, "path": str(path), **asset}

        return await asyncio.gather(*[one(scene) for scene in scenes])


def save_manifest(path: Path, assets: list[dict]) -> None:
    path.write_text(json.dumps(assets, ensure_ascii=False, indent=2), encoding="utf-8")
