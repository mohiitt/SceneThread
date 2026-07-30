"""Safe Strands tools wrapping frozen video and graph service interfaces."""

from __future__ import annotations

from typing import Literal

from strands import tool

from video_context_graph.contracts import (
    GraphExtraction,
    GraphService,
    IngestionRequest,
    SearchRequest,
    SearchResults,
    VideoGraphMetadata,
    VideoIntelligenceService,
)


def build_qa_tools(
    video_service: VideoIntelligenceService,
    graph_service: GraphService,
) -> list[object]:
    @tool(
        name="search_video_moments",
        description=(
            "Search the selected video for visual, spoken, audio, or on-screen-text evidence. "
            "Returns timestamped semantic matches."
        ),
    )
    def search_video_moments(video_id: str, query: str, top_k: int = 5) -> dict:
        return video_service.search_video_moments(
            SearchRequest(video_id=video_id, query=query, top_k=top_k)
        ).model_dump(mode="json")

    @tool(
        name="get_video_overview",
        description="Return the selected video's summary and compact graph statistics.",
    )
    def get_video_overview(video_id: str) -> dict:
        return graph_service.get_video_overview(video_id)

    @tool(
        name="list_video_entities",
        description="List canonical entities in the selected video with occurrence counts.",
    )
    def list_video_entities(
        video_id: str,
        entity_type: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        return graph_service.list_video_entities(video_id, entity_type, limit)

    @tool(
        name="get_entity_timeline",
        description="Return timestamped scenes and events involving one matched entity.",
    )
    def get_entity_timeline(
        video_id: str,
        entity_name: str,
        limit: int = 20,
    ) -> list[dict]:
        return graph_service.get_entity_timeline(video_id, entity_name, limit)

    @tool(
        name="get_scene_details",
        description="Return evidence details for specific scene IDs in the selected video.",
    )
    def get_scene_details(video_id: str, scene_ids: list[str]) -> list[dict]:
        return graph_service.get_scene_details(video_id, scene_ids)

    @tool(
        name="get_events_before_or_after",
        description="Return chronological graph events before or after a timestamp.",
    )
    def get_events_before_or_after(
        video_id: str,
        timestamp: float,
        direction: Literal["before", "after"],
        limit: int = 5,
    ) -> list[dict]:
        return graph_service.get_events_before_or_after(
            video_id,
            timestamp,
            direction,
            limit,
        )

    @tool(
        name="find_entity_connections",
        description="Return direct relationships, shared scenes, and shared events for two entities.",
    )
    def find_entity_connections(
        video_id: str,
        entity_a: str,
        entity_b: str,
        limit: int = 10,
    ) -> list[dict]:
        return graph_service.find_entity_connections(
            video_id,
            entity_a,
            entity_b,
            limit,
        )

    @tool(
        name="find_scenes_overlapping_moments",
        description="Map semantic video-search moments to overlapping graph scenes.",
    )
    def find_scenes_overlapping_moments(
        video_id: str,
        moments: dict,
    ) -> list[dict]:
        return graph_service.find_scenes_overlapping_moments(
            video_id,
            SearchResults.model_validate(moments),
        )

    return [
        search_video_moments,
        get_video_overview,
        list_video_entities,
        get_entity_timeline,
        get_scene_details,
        get_events_before_or_after,
        find_entity_connections,
        find_scenes_overlapping_moments,
    ]


def build_pipeline_tools(
    video_service: VideoIntelligenceService,
    graph_service: GraphService,
) -> list[object]:
    @tool(
        name="ingest_video",
        description=(
            "Run deterministic TwelveLabs ingestion for an already approved video source. "
            "Used by the fixed pipeline coordinator, not by the QA agent."
        ),
    )
    def ingest_video(request: dict) -> dict:
        validated = IngestionRequest.model_validate(request)
        return video_service.ingest_video(validated).model_dump(mode="json")

    @tool(
        name="index_graph",
        description=(
            "Write an already validated GraphExtraction through deterministic Neo4j code. "
            "Used by the fixed pipeline coordinator, not by the QA agent."
        ),
    )
    def index_graph(metadata: dict, extraction: dict) -> dict:
        return graph_service.index_graph(
            VideoGraphMetadata.model_validate(metadata),
            GraphExtraction.model_validate(extraction),
        ).model_dump(mode="json")

    return [ingest_video, index_graph]
