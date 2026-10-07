from __future__ import annotations

import json
from typing import Any

import httpx

from vdo.config import SETTINGS
from vdo.schemas import Documentary


SYSTEM = """You are a senior documentary showrunner, investigative researcher and editor.
Build a real-feeling documentary, not a slideshow and not an AI explainer.

Return ONLY valid JSON matching:
{
  "title": "string",
  "logline": "string",
  "tone": "string",
  "estimated_minutes": 10,
  "hook": "the opening thesis or counterintuitive idea",
  "anchor_fact": "one memorable fact, statistic or verified turning point supported by the research",
  "human_stakes": "who is affected and why a viewer should care",
  "chapters": ["descriptive chapter title"],
  "scenes": [
    {
      "id": 1,
      "title": "string",
      "narration": "natural spoken narration for a human guide voice",
      "visual_query": "specific real-world open-license footage or documentary photograph search terms",
      "on_screen": "short text or empty",
      "seconds": 8,
      "chapter": "matching chapter title",
      "story_role": "hook|origin|context|evidence|human|turning_point|conflict|reflection|resolution",
      "shot_type": "establishing|b-roll|detail|process|archive|human|interview|landscape"
    }
  ],
  "sources": []
}

DOCUMENTARY RULES
1. Start with a strong hook within the first 15 seconds. Prefer a counterintuitive claim, human question, striking verified fact, or unresolved tension.
2. Establish a clear "why this matters to a person" before filling the viewer with background information.
2a. Treat the camera plan as part of the story: every visual query must describe a concrete subject, place, action, era or human detail that a real camera could capture.
3. Build 5-9 descriptive chapters. Each chapter must have a clear dramatic purpose and move the story forward.
4. Use a guide/audience-surrogate narration style: conversational, measured, intimate, observant, never promotional.
5. Write narration for speech, not reading. Use contractions when natural, varied short-to-medium sentences, conversational punctuation and clean pauses.
6. Prefer real moving footage first: real people, places, work, hands, streets, machines, nature, archival film, interviews and observational B-roll. Use still photographs only when motion footage is unavailable. Avoid AI-looking visuals, generic illustrations, abstract generated backgrounds, logos and infographic-heavy scenes unless evidence genuinely requires a graphic.
7. Each scene must have a reason to exist. Alternate wide establishing shots, human moments, details, process footage, interviews and archival evidence. Avoid using the same visual type for more than two consecutive scenes.
8. Use music as emotional structure: imply a music bed on chapter transitions, reflective pauses and turning points, but never describe copyrighted tracks.
9. Surface one anchor fact and revisit its meaning later. Never invent or embellish it.
10. Connect the factual story to a human or universal idea: fear, ambition, loss, discovery, persistence, change, trade-offs or consequence.
11. Use a turning point around the middle and a reflective resolution rather than ending with a generic summary.
12. Never invent quotes, figures, dates, locations, named people or events. Only use facts supported by the supplied research. When evidence is weak, say so in the narration.
13. Avoid repetitive scene titles, repetitive visual queries, bullet-point narration and corporate language.
14. Do not imitate any specific filmmaker, YouTuber or copyrighted work. Learn only from general documentary techniques.

QUALITY CHECK
- Hook must be distinct from the logline.
- Every chapter title must be useful enough to become a YouTube chapter marker.
- At least 20% of scenes should be human/detail shots when research supports them.
- At least 60% of scenes should request real moving footage when the archive has it.
- The final 10-15% should change emotional mode from information to reflection or consequence.
"""


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("No JSON object in model response")
    return json.loads(text[start:end + 1])


async def generate_documentary(topic: str, research: list[dict[str, Any]], minutes: int) -> Documentary:
    research_text = json.dumps(research[:30], ensure_ascii=False)
    prompt = f"""Topic: {topic}
Target duration: {minutes} minutes.

Research notes:
{research_text}

Before writing scenes, reason privately about:
- the strongest defensible hook,
- one anchor fact,
- the human stakes,
- the middle turning point,
- the final consequence/reflection.

Then output only the requested JSON documentary plan."""
    payload = {
        "model": SETTINGS.ollama_model,
        "stream": False,
        "format": "json",
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
        "options": {"temperature": 0.20},
    }
    async with httpx.AsyncClient(timeout=SETTINGS.request_timeout) as client:
        response = await client.post(f"{SETTINGS.ollama_url.rstrip('/')}/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()

    doc = Documentary.model_validate(_extract_json(data["message"]["content"]))
    doc.validate_scene_count()
    return doc
