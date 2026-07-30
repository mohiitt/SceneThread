from video_context_graph.ui.interactive_graph import build_interactive_graph_html


def graph_payload() -> dict:
    return {
        "nodes": [
            {
                "id": "video-1",
                "type": "Video",
                "properties": {"title": "Day 1", "duration_sec": 45},
            },
            {
                "id": "scene-1",
                "type": "Scene",
                "properties": {
                    "ordinal": 1,
                    "start_sec": 0,
                    "end_sec": 12,
                    "summary": "A laptop is visible.",
                },
            },
            {
                "id": "entity-1",
                "type": "Entity",
                "properties": {"canonical_name": "laptop", "entity_type": "OBJECT"},
            },
        ],
        "edges": [
            {
                "source": "video-1",
                "target": "scene-1",
                "type": "HAS_SCENE",
                "properties": {},
            },
            {
                "source": "entity-1",
                "target": "scene-1",
                "type": "APPEARS_IN",
                "properties": {},
            },
        ],
        "truncated": False,
        "limit": 100,
    }


def test_interactive_graph_contains_expand_controls_and_details() -> None:
    rendered = build_interactive_graph_html(graph_payload(), root_id="video-1")

    assert "SceneThread Graph" in rendered
    assert "function revealNeighbors" in rendered
    assert "function expandAll" in rendered
    assert "function resetGraph" in rendered
    assert "HAS_SCENE" in rendered
    assert "A laptop is visible." in rendered


def test_interactive_graph_hides_non_root_nodes_initially() -> None:
    rendered = build_interactive_graph_html(graph_payload(), root_id="video-1")

    assert '"id": "video-1", "label": "Day 1"' in rendered
    assert '"id": "scene-1", "label": "Scene 1\\n00:00\\u201300:12"' in rendered
    assert '"hidden": true' in rendered


def test_interactive_graph_neutralizes_script_closing_text_in_details() -> None:
    graph = graph_payload()
    graph["nodes"][1]["properties"]["summary"] = "</script><script>alert(1)</script>"

    rendered = build_interactive_graph_html(graph, root_id="video-1")

    assert "</script><script>alert(1)</script>" not in rendered
