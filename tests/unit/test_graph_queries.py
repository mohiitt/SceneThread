from typing import Any

import pytest

from video_context_graph.fixture_store import load_fixture_bundle
from video_context_graph.graph.queries import GraphQueries


class FakeClient:
    def __init__(self, responses: list[list[dict[str, Any]]] | None = None) -> None:
        self.responses = list(responses or [])
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def execute_read(self, query: str, parameters: dict[str, Any]) -> list[dict[str, Any]]:
        self.calls.append((query, parameters))
        return self.responses.pop(0) if self.responses else []


def test_list_entities_normalizes_type_and_caps_limit() -> None:
    client = FakeClient()
    queries = GraphQueries(client)  # type: ignore[arg-type]

    queries.list_video_entities("video-1", " person ", 500)

    query, parameters = client.calls[0]
    assert "$video_id" in query
    assert parameters == {"video_id": "video-1", "entity_type": "PERSON", "limit": 100}
    assert "video-1" not in query


def test_timeline_normalizes_entity_name() -> None:
    client = FakeClient()
    GraphQueries(client).get_entity_timeline("video-1", "  Speaker   ONE ")  # type: ignore[arg-type]

    assert client.calls[0][1]["entity_name"] == "speaker one"


def test_before_query_reverses_nearest_first_results_into_chronological_order() -> None:
    client = FakeClient([[{"start_sec": 8}, {"start_sec": 4}]])
    rows = GraphQueries(client).get_events_before_or_after(  # type: ignore[arg-type]
        "video-1", 10, "before"
    )

    assert rows == [{"start_sec": 4}, {"start_sec": 8}]
    assert "event.end_sec <= $timestamp" in client.calls[0][0]


def test_after_query_uses_fixed_safe_comparison() -> None:
    client = FakeClient()
    GraphQueries(client).get_events_before_or_after("video-1", 10, "after")  # type: ignore[arg-type]

    assert "event.start_sec >= $timestamp" in client.calls[0][0]


@pytest.mark.parametrize("timestamp", [float("nan"), float("inf"), -1.0])
def test_event_query_rejects_invalid_timestamps(timestamp: float) -> None:
    with pytest.raises(ValueError, match="finite non-negative"):
        GraphQueries(FakeClient()).get_events_before_or_after(  # type: ignore[arg-type]
            "video-1", timestamp, "before"
        )


@pytest.mark.parametrize("direction", ["sideways", "", "BEFORE OR DELETE"])
def test_event_query_rejects_invalid_direction(direction: str) -> None:
    with pytest.raises(ValueError, match="direction"):
        GraphQueries(FakeClient()).get_events_before_or_after(  # type: ignore[arg-type]
            "video-1", 10, direction
        )


def test_scene_details_deduplicates_requested_ids() -> None:
    client = FakeClient()
    GraphQueries(client).get_scene_details("video-1", ["scene-1", "scene-1"])  # type: ignore[arg-type]

    assert client.calls[0][1]["scene_ids"] == ["scene-1"]


def test_overlap_query_passes_validated_moments_as_parameters() -> None:
    client = FakeClient()
    moments = load_fixture_bundle().search
    GraphQueries(client).find_scenes_overlapping_moments("video-1", moments)  # type: ignore[arg-type]

    query, parameters = client.calls[0]
    assert "$moments" in query
    assert parameters["moments"][0]["scene_id"] == moments.results[0].scene_id
    assert parameters["moments"][0]["start_sec"] == 12.5


def test_connections_return_flat_compact_records() -> None:
    connection = {"connection_type": "relationship", "kind": "ASSIGNED_TO"}
    client = FakeClient([[{"connection": connection}]])

    rows = GraphQueries(client).find_entity_connections(  # type: ignore[arg-type]
        "video-1", "Jordan", "Dashboard"
    )

    assert rows == [connection]
    assert client.calls[0][1]["entity_a"] == "jordan"


def test_overview_combines_compact_statistics() -> None:
    client = FakeClient(
        [
            [{"video_id": "video-1", "summary": "summary"}],
            [{"scene_count": 2}],
            [{"type": "PERSON", "count": 2}],
            [{"type": "ASSIGNS", "count": 1}],
            [{"name": "meeting", "count": 1}],
        ]
    )
    overview = GraphQueries(client).get_video_overview("video-1")  # type: ignore[arg-type]

    assert overview["scene_count"] == 2
    assert overview["entity_count"] == 2
    assert overview["event_count"] == 1
    assert overview["entity_counts"] == [{"type": "PERSON", "count": 2}]
    assert len(client.calls) == 5
