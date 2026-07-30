from __future__ import annotations

from typing import Any, cast

from video_context_graph.agents.tools import build_qa_tools
from video_context_graph.contracts import RecordingScope, SearchMoment, SearchResults


class FakeVideoService:
    def search_video_moments(self, request: Any) -> SearchResults:
        return SearchResults(
            query=request.query,
            results=[
                SearchMoment(
                    scene_id="source_scene_1",
                    start_sec=5,
                    end_sec=9,
                    score=0.91,
                    summary="A person moves a bag.",
                )
            ],
        )


class FakeGraphService:
    def list_recordings(self, scope: RecordingScope) -> list[dict]:
        assert scope.store_id == "store_sf"
        return [
            {
                "video_id": "day_1_entrance",
                "store_id": "store_sf",
                "camera_id": "entrance",
                "recorded_at": "2026-07-30T09:00:00-07:00",
                "search_available": True,
            },
            {
                "video_id": "day_1_stockroom",
                "store_id": "store_sf",
                "camera_id": "stockroom",
                "recorded_at": "2026-07-30T09:00:00-07:00",
                "search_available": False,
            },
        ]

    def find_scenes_overlapping_moments(
        self, video_id: str, moments: SearchResults
    ) -> list[dict]:
        return [{"moment_index": 0, "scene_id": "graph_scene_1", "overlap_sec": 4}]


def test_collection_search_returns_cross_video_provenance_and_absolute_time() -> None:
    tools = build_qa_tools(
        cast(Any, FakeVideoService()),
        cast(Any, FakeGraphService()),
    )
    search_tool = next(tool for tool in tools if tool.tool_name == "search_recordings")

    result = search_tool._tool_func(  # type: ignore[attr-defined]
        store_id="store_sf",
        query="Who moved the bag?",
    )

    assert result["searched_video_ids"] == ["day_1_entrance"]
    assert result["skipped_unsearchable_video_ids"] == ["day_1_stockroom"]
    assert result["matches"][0]["camera_id"] == "entrance"
    assert result["matches"][0]["recorded_start_at"] == "2026-07-30T09:00:05-07:00"
    assert result["matches"][0]["graph_scenes"][0]["scene_id"] == "graph_scene_1"


def test_collection_tools_accept_unbounded_time_filters_without_null_schema_defaults() -> None:
    tools = build_qa_tools(
        cast(Any, FakeVideoService()),
        cast(Any, FakeGraphService()),
    )

    for tool_name in ("list_recordings", "search_recordings"):
        collection_tool = next(tool for tool in tools if tool.tool_name == tool_name)
        properties = collection_tool.tool_spec["inputSchema"]["json"]["properties"]

        assert properties["recorded_from"] == {
            "default": "",
            "description": "Parameter recorded_from",
            "type": "string",
        }
        assert properties["recorded_to"] == {
            "default": "",
            "description": "Parameter recorded_to",
            "type": "string",
        }
