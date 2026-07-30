"""Concrete implementation of the frozen GraphService protocol."""

from __future__ import annotations

from video_context_graph.contracts.extraction import GraphExtraction
from video_context_graph.contracts.video import (
    GraphWriteResult,
    RecordingScope,
    SearchResults,
    ServiceHealth,
    VideoGraphMetadata,
)
from video_context_graph.graph.queries import GraphQueries
from video_context_graph.graph.writer import GraphWriter
from video_context_graph.integrations.neo4j_client import Neo4jClient


class Neo4jGraphService:
    def __init__(self, client: Neo4jClient) -> None:
        self.client = client
        self.writer = GraphWriter(client)
        self.queries = GraphQueries(client)

    @classmethod
    def from_settings(cls) -> Neo4jGraphService:
        return cls(Neo4jClient.from_settings())

    def close(self) -> None:
        self.client.close()

    def health_check(self) -> ServiceHealth:
        return self.client.health_check()

    def index_graph(
        self, metadata: VideoGraphMetadata, extraction: GraphExtraction
    ) -> GraphWriteResult:
        return self.writer.index_graph(metadata, extraction)

    def list_recordings(self, scope: RecordingScope) -> list[dict]:
        return self.queries.list_recordings(scope)

    def get_video_overview(self, video_id: str) -> dict:
        return self.queries.get_video_overview(video_id)

    def list_video_entities(
        self, video_id: str, entity_type: str | None = None, limit: int = 50
    ) -> list[dict]:
        return self.queries.list_video_entities(video_id, entity_type, limit)

    def get_entity_timeline(
        self, video_id: str, entity_name: str, limit: int = 20
    ) -> list[dict]:
        return self.queries.get_entity_timeline(video_id, entity_name, limit)

    def get_scene_details(self, video_id: str, scene_ids: list[str]) -> list[dict]:
        return self.queries.get_scene_details(video_id, scene_ids)

    def get_events_before_or_after(
        self, video_id: str, timestamp: float, direction: str, limit: int = 5
    ) -> list[dict]:
        return self.queries.get_events_before_or_after(video_id, timestamp, direction, limit)

    def find_entity_connections(
        self,
        video_id: str,
        entity_a: str,
        entity_b: str,
        limit: int = 10,
    ) -> list[dict]:
        return self.queries.find_entity_connections(video_id, entity_a, entity_b, limit)

    def find_scenes_overlapping_moments(
        self, video_id: str, moments: SearchResults
    ) -> list[dict]:
        return self.queries.find_scenes_overlapping_moments(video_id, moments)
