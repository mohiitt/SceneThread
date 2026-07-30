"""Safe Strands tools wrapping frozen video and graph service interfaces."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from strands import tool

from video_context_graph.contracts import (
    GraphExtraction,
    GraphService,
    IngestionRequest,
    RecordingScope,
    SearchRequest,
    SearchResults,
    VideoGraphMetadata,
    VideoIntelligenceService,
)

MAX_COLLECTION_MATCHES = 30


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
        name="list_recordings",
        description=(
            "Discover recordings in one store, optionally filtered by cameras, an absolute "
            "time window, or explicit video IDs. Use this before cross-video reasoning."
        ),
    )
    def list_recordings(
        store_id: str,
        camera_ids: list[str] | None = None,
        recorded_from: str = "",
        recorded_to: str = "",
        video_ids: list[str] | None = None,
        max_videos: int = 12,
    ) -> list[dict]:
        scope = RecordingScope.model_validate(
            {
                "store_id": store_id,
                "camera_ids": camera_ids or [],
                "recorded_from": recorded_from or None,
                "recorded_to": recorded_to or None,
                "video_ids": video_ids or [],
                "max_videos": max_videos,
            }
        )
        return graph_service.list_recordings(scope)

    @tool(
        name="search_recordings",
        description=(
            "Search visual, spoken, audio, and on-screen-text evidence across a bounded "
            "store recording collection. Returns video, camera, relative timestamps, "
            "absolute timestamps when available, graph overlaps, and per-video failures."
        ),
    )
    def search_recordings(
        store_id: str,
        query: str,
        camera_ids: list[str] | None = None,
        recorded_from: str = "",
        recorded_to: str = "",
        video_ids: list[str] | None = None,
        max_videos: int = 12,
        top_k_per_video: int = 3,
    ) -> dict:
        scope = RecordingScope.model_validate(
            {
                "store_id": store_id,
                "camera_ids": camera_ids or [],
                "recorded_from": recorded_from or None,
                "recorded_to": recorded_to or None,
                "video_ids": video_ids or [],
                "max_videos": max_videos,
            }
        )
        recordings = graph_service.list_recordings(scope)
        matches: list[dict] = []
        failures: list[dict] = []
        searched_video_ids: list[str] = []
        skipped_video_ids: list[str] = []
        bounded_top_k = max(1, min(top_k_per_video, 5))
        for recording in recordings:
            video_id = str(recording["video_id"])
            if not bool(recording.get("search_available")):
                skipped_video_ids.append(video_id)
                continue
            try:
                semantic = video_service.search_video_moments(
                    SearchRequest(video_id=video_id, query=query, top_k=bounded_top_k)
                )
                overlaps = graph_service.find_scenes_overlapping_moments(
                    video_id, semantic
                )
            except Exception as exc:  # noqa: BLE001 - preserve useful results from other videos.
                failures.append(
                    {"video_id": video_id, "error_type": type(exc).__name__}
                )
                continue
            searched_video_ids.append(video_id)
            overlap_by_moment: dict[int, list[dict]] = {}
            for overlap in overlaps:
                index = int(overlap.get("moment_index", 0))
                overlap_by_moment.setdefault(index, []).append(overlap)
            recorded_at = _parse_recorded_at(recording.get("recorded_at"))
            for index, moment in enumerate(semantic.results):
                absolute_start = (
                    recorded_at + timedelta(seconds=moment.start_sec)
                    if recorded_at is not None
                    else None
                )
                absolute_end = (
                    recorded_at + timedelta(seconds=moment.end_sec)
                    if recorded_at is not None
                    else None
                )
                matches.append(
                    {
                        "video_id": video_id,
                        "store_id": recording.get("store_id"),
                        "camera_id": recording.get("camera_id"),
                        "recorded_at": recording.get("recorded_at"),
                        "scene_id": moment.scene_id,
                        "start_sec": moment.start_sec,
                        "end_sec": moment.end_sec,
                        "recorded_start_at": (
                            absolute_start.isoformat()
                            if absolute_start is not None
                            else None
                        ),
                        "recorded_end_at": (
                            absolute_end.isoformat()
                            if absolute_end is not None
                            else None
                        ),
                        "score": moment.score,
                        "summary": moment.summary,
                        "graph_scenes": overlap_by_moment.get(index, []),
                    }
                )
        matches.sort(
            key=lambda item: (
                -float(item["score"]),
                str(item.get("recorded_start_at") or ""),
                str(item["video_id"]),
            )
        )
        return {
            "query": query,
            "recordings_considered": len(recordings),
            "searched_video_ids": searched_video_ids,
            "skipped_unsearchable_video_ids": skipped_video_ids,
            "failures": failures,
            "matches": matches[:MAX_COLLECTION_MATCHES],
        }

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
        list_recordings,
        search_recordings,
        get_video_overview,
        list_video_entities,
        get_entity_timeline,
        get_scene_details,
        get_events_before_or_after,
        find_entity_connections,
        find_scenes_overlapping_moments,
    ]


def _parse_recorded_at(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        return datetime.fromisoformat(value)
    return None


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
