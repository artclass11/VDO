from __future__ import annotations

import json
from typing import Any

import httpx

from vdo.config import SETTINGS
from vdo.schemas import Documentary


SYSTEM = """You are a senior documentary showrunner, researcher and editor.
Return ONLY valid JSON matching:
{
  "title": "string",
  "logline": "string",
  "tone": "string",
  "estimated_minutes": 10,
  "chapters": ["string"],
  "scenes": [
    {
      "id": 1,
      "title": "string",
      "narration": "spoken narration, factual and natural",
      "visual_query": "specific archival/open-license visual search terms",
      "on_screen": "short text or empty",
      "seconds": 8
    }
  ],
  "sources": []
}
Create a strong hook, logical chapters, chronology or causal structure,
varied pacing and a memorable conclusion. Never invent quotes, figures,
dates or named facts. Use cautious wording when evidence is uncertain.
"""


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("No JSON object in model response")
    return json.loads(text[start:end + 1])


async def generate_documentary(topic: str, research: list[dict[str, Any]], minutes: int) -> Documentary:
    research_text = json.dumps(research[:20], ensure_ascii=False)
    prompt = f"""Topic: {topic}
Target duration: {minutes} minutes.
Research notes:
{research_text}
Write the full documentary plan now."""
    payload = {
        "model": SETTINGS.ollama_model,
        "stream": False,
        "format": "json",
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
        "options": {"temperature": 0.25},
    }
    async with httpx.AsyncClient(timeout=SETTINGS.request_timeout) as client:
        response = await client.post(f"{SETTINGS.ollama_url.rstrip('/')}/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()
    doc = Documentary.model_validate(_extract_json(data["message"]["content"]))
    doc.validate_scene_count()
    return doc
