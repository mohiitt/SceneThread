from typing import Any

import pytest

from video_context_graph.graph.visualization import GraphVisualizationBuilder


class FakeClient:
    def __init__(self, responses: list[list[dict[str, Any]]]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def execute_read(self, query: str, parameters: dict[str, Any]) -> list[dict[str, Any]]:
        self.calls.append((query, parameters))
        return self.responses.pop(0)


def test_builder_caps_nodes_and_only_fetches_edges_between_selected_nodes() -> None:
    nodes = [
        {"id": "video-1", "type": "Video", "properties": {}},
        {"id": "scene-1", "type": "Scene", "properties": {}},
        {"id": "scene-2", "type": "Scene", "properties": {}},
    ]
    edges = [{"source": "video-1", "target": "scene-1", "type": "HAS_SCENE"}]
    client = FakeClient([nodes, edges])

    result = GraphVisualizationBuilder(client, default_limit=2).build("video-1")  # type: ignore[arg-type]

    assert result["truncated"] is True
    assert [node["id"] for node in result["nodes"]] == ["video-1", "scene-1"]
    assert client.calls[1][1]["node_ids"] == ["video-1", "scene-1"]
    assert client.calls[0][1]["fetch_limit"] == 3
    assert "WHEN node:Scene THEN node.scene_id" in client.calls[0][0]


def test_builder_normalizes_focus_entity() -> None:
    client = FakeClient([[]])
    GraphVisualizationBuilder(client).build("video-1", entity_name="  Jordan  ")  # type: ignore[arg-type]

    assert client.calls[0][1]["entity_name"] == "jordan"


def test_builder_rejects_unknown_node_type() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        GraphVisualizationBuilder(FakeClient([])).build(  # type: ignore[arg-type]
            "video-1", node_types=["Secret"]
        )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1.0])
def test_builder_rejects_invalid_time_filters(value: float) -> None:
    with pytest.raises(ValueError, match="finite and non-negative"):
        GraphVisualizationBuilder(FakeClient([])).build(  # type: ignore[arg-type]
            "video-1", start_sec=value
        )


def test_builder_rejects_boolean_limit() -> None:
    with pytest.raises(ValueError, match="positive integer"):
        GraphVisualizationBuilder(FakeClient([])).build("video-1", limit=True)  # type: ignore[arg-type]
