from __future__ import annotations

from pydantic import BaseModel, Field, ConfigDict


class Source(BaseModel):
    title: str
    url: str
    publisher: str = ""
    license: str = ""
    author: str = ""


class Scene(BaseModel):
    id: int
    title: str
    narration: str = Field(min_length=1)
    visual_query: str
    on_screen: str = ""
    seconds: float = 8.0


class Documentary(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str
    logline: str
    tone: str = "cinematic documentary"
    estimated_minutes: int = 10
    chapters: list[str] = Field(default_factory=list)
    scenes: list[Scene] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)

    def validate_scene_count(self) -> None:
        if not self.scenes:
            raise ValueError("LLM returned no scenes")
        if len(self.scenes) > 240:
            raise ValueError("Documentary contains too many scenes")
