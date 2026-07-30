"""Graph exploration tables for validated extraction data."""

from __future__ import annotations

import streamlit as st

from video_context_graph.contracts import PipelineRunResult
from video_context_graph.ui.components import render_extraction_metrics, render_mode_banner
from video_context_graph.ui.runtime import FixtureRuntime


def render_graph_tab(runtime: FixtureRuntime, mode: str) -> None:
    st.header("Graph Explorer")
    render_mode_banner(mode)

    pipeline_result = st.session_state.get("pipeline_result")
    if isinstance(pipeline_result, PipelineRunResult):
        extraction = pipeline_result.extraction
    elif mode == "live":
        st.warning("Run the full live ingestion pipeline to populate the graph explorer.")
        return
    else:
        extraction = runtime.bundle.extraction
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
            [relationship.model_dump(mode="json") for relationship in extraction.relationships],
            width="stretch",
            hide_index=True,
        )

    st.caption("These tables show the validated extraction written through GraphService.")
