"""Interactive Neo4j graph explorer with a fixture-table fallback."""

from __future__ import annotations

from typing import Any

import streamlit as st

from video_context_graph.config import get_settings
from video_context_graph.contracts import GraphExtraction, PipelineRunResult
from video_context_graph.graph.service import Neo4jGraphService
from video_context_graph.graph.visualization import (
    ALLOWED_NODE_TYPES,
    GraphVisualizationBuilder,
)
from video_context_graph.ui.components import render_extraction_metrics, render_mode_banner
from video_context_graph.ui.interactive_graph import build_interactive_graph_html
from video_context_graph.ui.runtime import FixtureRuntime


def render_graph_tab(runtime: FixtureRuntime, mode: str) -> None:
    st.header("Graph Explorer")
    render_mode_banner(mode)

    if mode == "live" and isinstance(runtime.graph_service, Neo4jGraphService):
        _render_live_graph(runtime.graph_service)
        return

    st.info(
        "Interactive uploaded-video graphs are available in Full live services mode. "
        "This runtime shows the validated local extraction tables."
    )
    pipeline_result = st.session_state.get("pipeline_result")
    extraction = (
        pipeline_result.extraction
        if isinstance(pipeline_result, PipelineRunResult)
        else runtime.bundle.extraction
    )
    _render_extraction_tables(extraction)


def _render_live_graph(graph_service: Neo4jGraphService) -> None:
    settings = get_settings()
    builder = GraphVisualizationBuilder(
        graph_service.client,
        default_limit=settings.app_graph_node_limit,
    )
    try:
        videos = builder.list_videos()
    except (RuntimeError, ValueError) as exc:
        st.error(f"Could not load Neo4j videos: {exc}")
        return
    if not videos:
        st.warning("Neo4j contains no uploaded video graphs yet. Ingest a video first.")
        return

    video_by_id = {str(video["video_id"]): video for video in videos}
    video_ids = list(video_by_id)
    preferred_id = st.session_state.get("selected_video_id")
    selected_index = video_ids.index(preferred_id) if preferred_id in video_ids else 0
    selected_video_id = st.selectbox(
        "Uploaded video graph",
        video_ids,
        index=selected_index,
        format_func=lambda video_id: _video_label(video_by_id[video_id]),
    )
    selected_video = video_by_id[selected_video_id]
    metadata_columns = st.columns(4)
    metadata_columns[0].metric("Video ID", selected_video_id)
    metadata_columns[1].metric("Store", selected_video.get("store_id") or "—")
    metadata_columns[2].metric("Camera", selected_video.get("camera_id") or "—")
    metadata_columns[3].metric(
        "Duration",
        _duration_label(selected_video.get("duration_sec")),
    )
    if selected_video.get("recorded_at"):
        st.caption(f"Recording started: {selected_video['recorded_at']}")

    with st.expander("Graph filters", expanded=False):
        selected_types = st.multiselect(
            "Node types",
            sorted(ALLOWED_NODE_TYPES),
            default=sorted(ALLOWED_NODE_TYPES),
            help="Hide node categories before loading the visualization.",
        )
        filter_columns = st.columns(3)
        entity_name = filter_columns[0].text_input(
            "Focus entity (optional)",
            help="Match an entity name or alias and nodes within two graph hops.",
        )
        start_sec = filter_columns[1].number_input(
            "Start second",
            min_value=0.0,
            value=0.0,
            step=1.0,
        )
        use_end = filter_columns[2].checkbox("Set end second")
        end_sec = (
            filter_columns[2].number_input(
                "End second",
                min_value=0.1,
                value=max(
                    1.0,
                    float(selected_video.get("duration_sec") or 1.0),
                ),
                step=1.0,
            )
            if use_end
            else None
        )
        node_limit = st.slider(
            "Maximum nodes",
            min_value=20,
            max_value=300,
            value=min(max(settings.app_graph_node_limit, 20), 300),
            step=10,
        )

    if not selected_types:
        st.warning("Select at least one node type.")
        return
    try:
        graph = builder.build(
            selected_video_id,
            node_types=selected_types,
            entity_name=entity_name or None,
            start_sec=start_sec if start_sec > 0 else None,
            end_sec=end_sec,
            limit=node_limit,
        )
    except (RuntimeError, ValueError) as exc:
        st.error(f"Could not build graph visualization: {exc}")
        return

    node_count = len(graph["nodes"])
    edge_count = len(graph["edges"])
    count_columns = st.columns(3)
    count_columns[0].metric("Loaded nodes", node_count)
    count_columns[1].metric("Relationships", edge_count)
    count_columns[2].metric("Node limit", graph["limit"])
    if graph["truncated"]:
        st.warning(
            "This graph reached the node limit. Increase the limit or narrow the filters."
        )
    if node_count == 0:
        st.warning("No graph nodes matched the selected filters.")
        return

    st.caption(
        "Click a node to reveal its direct neighbors and inspect its properties. "
        "Double-click to focus; use Reset to return to the video root."
    )
    st.iframe(
        build_interactive_graph_html(graph, root_id=selected_video_id),
        height=740,
        width="stretch",
    )

    with st.expander("Raw graph records"):
        raw_tabs = st.tabs(["Nodes", "Relationships"])
        with raw_tabs[0]:
            st.dataframe(
                [_flatten_node(row) for row in graph["nodes"]],
                width="stretch",
                hide_index=True,
            )
        with raw_tabs[1]:
            st.dataframe(graph["edges"], width="stretch", hide_index=True)


def _render_extraction_tables(extraction: GraphExtraction) -> None:
    render_extraction_metrics(extraction)
    entity_types = ["All", *sorted({entity.entity_type for entity in extraction.entities})]
    selected_type = st.selectbox("Entity type", entity_types)
    entities = [
        entity.model_dump(mode="json")
        for entity in extraction.entities
        if selected_type == "All" or entity.entity_type == selected_type
    ]
    tabs = st.tabs(["Entities", "Scenes", "Events", "Relationships"])
    with tabs[0]:
        st.dataframe(entities, width="stretch", hide_index=True)
    with tabs[1]:
        st.dataframe(
            [scene.model_dump(mode="json") for scene in extraction.scenes],
            width="stretch",
            hide_index=True,
        )
    with tabs[2]:
        st.dataframe(
            [event.model_dump(mode="json") for event in extraction.events],
            width="stretch",
            hide_index=True,
        )
    with tabs[3]:
        st.dataframe(
            [
                relationship.model_dump(mode="json")
                for relationship in extraction.relationships
            ],
            width="stretch",
            hide_index=True,
        )


def _video_label(video: dict[str, Any]) -> str:
    title = str(video.get("title") or video["video_id"])
    camera = str(video.get("camera_id") or "camera unknown")
    recorded = str(video.get("recorded_at") or "time unknown")
    return f"{title} · {camera} · {recorded}"


def _duration_label(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "—"
    minutes, seconds = divmod(round(float(value)), 60)
    return f"{minutes:02d}:{seconds:02d}"


def _flatten_node(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": node.get("id"),
        "type": node.get("type"),
        **dict(node.get("properties") or {}),
    }
