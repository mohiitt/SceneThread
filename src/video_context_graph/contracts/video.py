"""Video ingestion, search, health, and graph-write boundary contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


def _require_timezone(value: datetime | None, field_name: str) -> None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise ValueError(f"{field_name} must include a timezone")


class IngestionRequest(BaseModel):
    video_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_type: Literal["upload", "url"]
    source_ref: str = Field(min_length=1)
    domain_hint: str = "Auto"
    force_reprocess: bool = False
    store_id: str | None = Field(default=None, min_length=1)
    camera_id: str | None = Field(default=None, min_length=1)
    recorded_at: datetime | None = None

    @model_validator(mode="after")
    def validate_recording_identity(self) -> IngestionRequest:
        _require_timezone(self.recorded_at, "recorded_at")
        return self


class VideoSegment(BaseModel):
    segment_id: str = Field(min_length=1)
    start_sec: float = Field(ge=0)
    end_sec: float
    summary: str = Field(min_length=1)
    location: str | None = None
    participants: list[str] = Field(default_factory=list)
    objects: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    speech_summary: str | None = None
    on_screen_text: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    sentiment: str = "unknown"

    @model_validator(mode="after")
    def validate_timestamp_order(self) -> VideoSegment:
        if self.start_sec >= self.end_sec:
            raise ValueError("start_sec must be less than end_sec")
        return self


class SegmentCollection(BaseModel):
    video_id: str = Field(min_length=1)
    duration_sec: float = Field(gt=0)
    segments: list[VideoSegment]

    @model_validator(mode="after")
    def validate_segments(self) -> SegmentCollection:
        segment_ids = [segment.segment_id for segment in self.segments]
        if len(segment_ids) != len(set(segment_ids)):
            raise ValueError("segment IDs must be unique")

        starts = [segment.start_sec for segment in self.segments]
        if starts != sorted(starts):
            raise ValueError("segments must be sorted by start_sec")

        outside_video = [
            segment.segment_id
            for segment in self.segments
            if segment.end_sec > self.duration_sec
        ]
        if outside_video:
            raise ValueError(f"segments exceed video duration: {outside_video}")
        return self


class IngestionResult(BaseModel):
    video_id: str = Field(min_length=1)
    asset_id: str = Field(min_length=1)
    index_id: str | None = None
    indexed_asset_id: str | None = None
    segmentation_task_id: str = Field(min_length=1)
    segments: SegmentCollection
    search_available: bool = True

    @model_validator(mode="after")
    def validate_video_identity(self) -> IngestionResult:
        if self.video_id != self.segments.video_id:
            raise ValueError("ingestion result and segment collection video IDs must match")
        if self.search_available and (not self.index_id or not self.indexed_asset_id):
            raise ValueError("search-available results require index_id and indexed_asset_id")
        return self


class SearchRequest(BaseModel):
    video_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class SearchMoment(BaseModel):
    scene_id: str | None = None
    start_sec: float = Field(ge=0)
    end_sec: float
    score: float = Field(ge=0, le=1)
    summary: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_timestamp_order(self) -> SearchMoment:
        if self.start_sec >= self.end_sec:
            raise ValueError("start_sec must be less than end_sec")
        return self


class SearchResults(BaseModel):
    query: str = Field(min_length=1)
    results: list[SearchMoment]


class VideoGraphMetadata(BaseModel):
    video_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    file_name: str = ""
    source_type: Literal["upload", "url"]
    domain_hint: str = "Auto"
    duration_sec: float = Field(gt=0)
    external_ids: dict[str, str] = Field(default_factory=dict)
    pipeline_version: str = Field(min_length=1)
    store_id: str | None = Field(default=None, min_length=1)
    camera_id: str | None = Field(default=None, min_length=1)
    recorded_at: datetime | None = None
    search_available: bool = True

    @model_validator(mode="after")
    def validate_recording_identity(self) -> VideoGraphMetadata:
        _require_timezone(self.recorded_at, "recorded_at")
        return self


class RecordingScope(BaseModel):
    """Bounded collection selector for cross-video discovery and QA."""

    store_id: str = Field(min_length=1)
    camera_ids: list[str] = Field(default_factory=list, max_length=20)
    recorded_from: datetime | None = None
    recorded_to: datetime | None = None
    video_ids: list[str] = Field(default_factory=list, max_length=100)
    max_videos: int = Field(default=12, ge=1, le=50)

    @model_validator(mode="after")
    def validate_time_window(self) -> RecordingScope:
        _require_timezone(self.recorded_from, "recorded_from")
        _require_timezone(self.recorded_to, "recorded_to")
        if (
            self.recorded_from is not None
            and self.recorded_to is not None
            and self.recorded_from >= self.recorded_to
        ):
            raise ValueError("recorded_from must be earlier than recorded_to")
        self.camera_ids = list(dict.fromkeys(self.camera_ids))
        self.video_ids = list(dict.fromkeys(self.video_ids))
        return self


class GraphWriteResult(BaseModel):
    video_id: str = Field(min_length=1)
    node_count: int = Field(ge=0)
    relationship_count: int = Field(ge=0)


class ServiceHealth(BaseModel):
    service: Literal["twelvelabs", "openai", "strands", "neo4j"]
    available: bool
    detail: str
