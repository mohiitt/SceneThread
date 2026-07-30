"""Frozen cross-team service interfaces for the first implementation pass."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from video_context_graph.contracts.answers import AnswerResult
from video_context_graph.contracts.extraction import GraphExtraction
from video_context_graph.contracts.jobs import PipelineRunResult
from video_context_graph.contracts.video import (
    GraphWriteResult,
    IngestionRequest,
    IngestionResult,
    SearchRequest,
    SearchResults,
    SegmentCollection,
    ServiceHealth,
    VideoGraphMetadata,
)

JsonRecord = dict[str, Any]


@runtime_checkable
class VideoIntelligenceService(Protocol):
    def ingest_video(self, request: IngestionRequest) -> IngestionResult: ...

    def search_video_moments(self, request: SearchRequest) -> SearchResults: ...

    def health_check(self) -> ServiceHealth: ...


@runtime_checkable
class ExtractionService(Protocol):
    def extract_graph(
        self,
        *,
        title: str,
        domain_hint: str,
        segments: SegmentCollection,
    ) -> GraphExtraction: ...

    def health_check(self) -> ServiceHealth: ...


@runtime_checkable
class GraphService(Protocol):
    def index_graph(
        self,
        metadata: VideoGraphMetadata,
        extraction: GraphExtraction,
    ) -> GraphWriteResult: ...

    def get_video_overview(self, video_id: str) -> JsonRecord: ...

    def list_video_entities(
        self,
        video_id: str,
        entity_type: str | None = None,
        limit: int = 50,
    ) -> list[JsonRecord]: ...

    def get_entity_timeline(
        self,
        video_id: str,
        entity_name: str,
        limit: int = 20,
    ) -> list[JsonRecord]: ...

    def get_scene_details(self, video_id: str, scene_ids: list[str]) -> list[JsonRecord]: ...

    def get_events_before_or_after(
        self,
        video_id: str,
        timestamp: float,
        direction: str,
        limit: int = 5,
    ) -> list[JsonRecord]: ...

    def find_entity_connections(
        self,
        video_id: str,
        entity_a: str,
        entity_b: str,
        limit: int = 10,
    ) -> list[JsonRecord]: ...

    def find_scenes_overlapping_moments(
        self,
        video_id: str,
        moments: SearchResults,
    ) -> list[JsonRecord]: ...

    def health_check(self) -> ServiceHealth: ...


@runtime_checkable
class QuestionAnsweringService(Protocol):
    def answer_question(self, *, video_id: str, question: str) -> AnswerResult: ...

    def health_check(self) -> ServiceHealth: ...


@runtime_checkable
class PipelineCoordinator(Protocol):
    def process_video(self, request: IngestionRequest) -> PipelineRunResult: ...
