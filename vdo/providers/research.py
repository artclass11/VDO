from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import quote

import httpx


WIKI_API = "https://en.wikipedia.org/w/api.php"


async def _search(client: httpx.AsyncClient, query: str, limit: int = 8) -> list[dict[str, Any]]:
    r = await client.get(
        WIKI_API,
        params={
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": limit,
            "format": "json",
            "utf8": 1,
        },
    )
    r.raise_for_status()
    return r.json().get("query", {}).get("search", [])


async def _summary(client: httpx.AsyncClient, title: str) -> dict[str, Any]:
    r = await client.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title)}")
    return r.json() if r.status_code < 400 else {}


async def research_topic(topic: str, limit: int = 8) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(
        timeout=30,
        headers={"User-Agent": "VDO/1.0 open-source documentary engine"},
    ) as client:
        results = await _search(client, topic, limit)
        summaries = await asyncio.gather(
            *[_summary(client, item["title"]) for item in results],
            return_exceptions=True,
        )
    out = []
    for item, summary in zip(results, summaries):
        if isinstance(summary, Exception) or not summary:
            continue
        out.append({
            "title": item.get("title", ""),
            "extract": summary.get("extract", ""),
            "url": summary.get("content_urls", {}).get("desktop", {}).get("page", ""),
            "publisher": "Wikipedia",
            "license": "Check the specific page license/attribution requirements before redistribution.",
        })
    return out
