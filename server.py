from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

from vdo.pipeline import generate


app = FastAPI(title="VDO Documentary API", version="1.0.0")


class GenerateRequest(BaseModel):
    topic: str
    minutes: int = 10
    output_dir: str | None = None


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/generate")
async def create(req: GenerateRequest) -> dict:
    output = await generate(
        req.topic,
        req.minutes,
        Path(req.output_dir) if req.output_dir else None,
    )
    return {"status": "completed", "output": str(output)}
