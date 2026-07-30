"""Safe, user-visible Strands orchestration trace contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PipelineTraceEvent(BaseModel):
    stage: Literal["ingestion", "extraction", "indexing", "qa"]
    sponsor: Literal["Strands", "TwelveLabs", "OpenAI", "Neo4j"]
    status: Literal["started", "completed", "failed", "skipped"]
    summary: str = Field(min_length=1)
    occurred_at: datetime
    duration_ms: int | None = Field(default=None, ge=0)
    details: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class PipelineTrace(BaseModel):
    mode: Literal["fixture", "live"]
    events: list[PipelineTraceEvent] = Field(default_factory=list)
