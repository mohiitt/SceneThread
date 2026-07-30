"""Explicit fixture-only service adapters for the integrated Developer C preview."""

from __future__ import annotations

from video_context_graph.contracts import (
    GraphExtraction,
    GraphWriteResult,
    IngestionRequest,
    IngestionResult,
    SearchRequest,
    SearchResults,
    ServiceHealth,
    VideoGraphMetadata,
)
from video_context_graph.fixture_store import FixtureBundle


class FixtureVideoIntelligenceService:
    def __init__(self, bundle: FixtureBundle) -> None:
        self._bundle = bundle

    def ingest_video(self, request: IngestionRequest) -> IngestionResult:
        if request.video_id != self._bundle.segments.video_id:
            raise ValueError(
                f"fixture mode requires video_id {self._bundle.segments.video_id}"
            )
        return self._bundle.ingestion_result()

    def search_video_moments(self, request: SearchRequest) -> SearchResults:
        if request.video_id != self._bundle.segments.video_id:
            raise ValueError(f"unknown fixture video_id: {request.video_id}")
        supported_terms = ("jordan", "dashboard", "assigned", "follow-up")
        if any(term in request.query.casefold() for term in supported_terms):
            return SearchResults(
                query=request.query,
                results=self._bundle.search.results[: request.top_k],
            )
        return SearchResults(query=request.query, results=[])

    def health_check(self) -> ServiceHealth:
        return ServiceHealth(
            service="twelvelabs",
            available=True,
            detail="Fixture TwelveLabs evidence is loaded; no live request will be made.",
        )


class FixtureGraphService:
    def __init__(self, bundle: FixtureBundle) -> None:
        self._bundle = bundle
        self._extraction: GraphExtraction | None = None

    @property
    def extraction(self) -> GraphExtraction:
        return self._extraction or self._bundle.extraction

    def index_graph(
        self,
        metadata: VideoGraphMetadata,
        extraction: GraphExtraction,
    ) -> GraphWriteResult:
        if metadata.video_id != self._bundle.segments.video_id:
            raise ValueError(f"unknown fixture video_id: {metadata.video_id}")
        self._extraction = extraction.model_copy(deep=True)
        tags = {tag for scene in extraction.scenes for tag in scene.tags}
        node_count = 1 + len(extraction.scenes) + len(extraction.entities) + len(
            extraction.events
        ) + len(tags)
        relationship_count = (
            len(extraction.scenes)
            + max(0, len(extraction.scenes) - 1)
            + len(extraction.events)
            + sum(len(scene.entity_ids) for scene in extraction.scenes)
            + sum(
                len(event.participants) + len(event.involved_entities)
                for event in extraction.events
            )
            + sum(len(scene.tags) for scene in extraction.scenes)
            + len(extraction.relationships)
        )
        return GraphWriteResult(
            video_id=metadata.video_id,
            node_count=node_count,
            relationship_count=relationship_count,
        )

    def get_video_overview(self, video_id: str) -> dict:
        self._validate_video(video_id)
        extraction = self.extraction
        entity_counts: dict[str, int] = {}
        event_counts: dict[str, int] = {}
        tag_counts: dict[str, int] = {}
        for entity in extraction.entities:
            entity_counts[entity.entity_type] = entity_counts.get(entity.entity_type, 0) + 1
        for event in extraction.events:
            event_counts[event.event_type] = event_counts.get(event.event_type, 0) + 1
        for scene in extraction.scenes:
            for tag in scene.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        return {
            "video_id": video_id,
            "summary": extraction.video_summary,
            "scene_count": len(extraction.scenes),
            "entity_counts": entity_counts,
            "event_counts": event_counts,
            "top_tags": sorted(tag_counts, key=lambda tag: tag_counts[tag], reverse=True)[:10],
        }

    def list_video_entities(
        self,
        video_id: str,
        entity_type: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        self._validate_video(video_id)
        occurrences = {
            entity.local_id: sum(
                entity.local_id in scene.entity_ids for scene in self.extraction.scenes
            )
            for entity in self.extraction.entities
        }
        records = [
            {
                "entity_id": entity.local_id,
                "canonical_name": entity.canonical_name,
                "entity_type": entity.entity_type,
                "occurrence_count": occurrences[entity.local_id],
                "confidence": entity.confidence,
            }
            for entity in self.extraction.entities
            if entity_type is None or entity.entity_type == entity_type
        ]
        return records[:limit]

    def get_entity_timeline(
        self,
        video_id: str,
        entity_name: str,
        limit: int = 20,
    ) -> list[dict]:
        self._validate_video(video_id)
        normalized = entity_name.casefold()
        matched_ids = {
            entity.local_id
            for entity in self.extraction.entities
            if normalized in entity.canonical_name.casefold()
            or any(normalized in alias.casefold() for alias in entity.aliases)
        }
        return [
            {
                "scene_id": scene.local_id,
                "start_sec": scene.start_sec,
                "end_sec": scene.end_sec,
                "summary": scene.summary,
            }
            for scene in self.extraction.scenes
            if matched_ids.intersection(scene.entity_ids)
        ][:limit]

    def get_scene_details(self, video_id: str, scene_ids: list[str]) -> list[dict]:
        self._validate_video(video_id)
        selected = set(scene_ids)
        events_by_scene: dict[str, list[dict]] = {}
        for event in self.extraction.events:
            events_by_scene.setdefault(event.scene_id, []).append(event.model_dump(mode="json"))
        return [
            {
                **scene.model_dump(mode="json"),
                "events": events_by_scene.get(scene.local_id, []),
            }
            for scene in self.extraction.scenes
            if scene.local_id in selected
        ]

    def get_events_before_or_after(
        self,
        video_id: str,
        timestamp: float,
        direction: str,
        limit: int = 5,
    ) -> list[dict]:
        self._validate_video(video_id)
        if direction not in {"before", "after"}:
            raise ValueError("direction must be 'before' or 'after'")
        events = [
            event
            for event in self.extraction.events
            if (event.end_sec <= timestamp if direction == "before" else event.start_sec >= timestamp)
        ]
        events.sort(key=lambda event: event.start_sec, reverse=direction == "before")
        return [event.model_dump(mode="json") for event in events[:limit]]

    def find_entity_connections(
        self,
        video_id: str,
        entity_a: str,
        entity_b: str,
        limit: int = 10,
    ) -> list[dict]:
        self._validate_video(video_id)
        names = {entity_a.casefold(), entity_b.casefold()}
        ids = {
            entity.local_id
            for entity in self.extraction.entities
            if entity.canonical_name.casefold() in names
        }
        if len(ids) < 2:
            return []
        records = [
            relationship.model_dump(mode="json")
            for relationship in self.extraction.relationships
            if {relationship.source_entity_id, relationship.target_entity_id} == ids
        ]
        for scene in self.extraction.scenes:
            if ids.issubset(set(scene.entity_ids)):
                records.append(
                    {
                        "kind": "SHARED_SCENE",
                        "scene_id": scene.local_id,
                        "start_sec": scene.start_sec,
                        "end_sec": scene.end_sec,
                    }
                )
        return records[:limit]

    def find_scenes_overlapping_moments(
        self,
        video_id: str,
        moments: SearchResults,
    ) -> list[dict]:
        self._validate_video(video_id)
        return [
            scene.model_dump(mode="json")
            for scene in self.extraction.scenes
            if any(
                scene.start_sec < moment.end_sec and scene.end_sec > moment.start_sec
                for moment in moments.results
            )
        ]

    def health_check(self) -> ServiceHealth:
        return ServiceHealth(
            service="neo4j",
            available=True,
            detail="Fixture graph adapter is available; no Neo4j request will be made.",
        )

    def _validate_video(self, video_id: str) -> None:
        if video_id != self._bundle.segments.video_id:
            raise ValueError(f"unknown fixture video_id: {video_id}")
