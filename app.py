"""Streamlit entrypoint for the SceneThread demo app."""

import streamlit as st

from video_context_graph.config import get_settings
from video_context_graph.integrations.strands_openai import StrandsOpenAIProvider
from video_context_graph.ui import (
    render_ask_tab,
    render_graph_tab,
    render_ingest_tab,
    render_test_lab_tab,
)
from video_context_graph.ui.components import render_service_health
from video_context_graph.ui.runtime import (
    create_fixture_runtime,
    create_live_openai_runtime,
    create_live_runtime,
)

st.set_page_config(page_title="SceneThread", page_icon="ST", layout="wide")
st.title("SceneThread")
st.caption("Watch, tag, connect, and question video with timestamped evidence.")

settings = get_settings()

with st.sidebar:
    st.header("Runtime")
    default_mode = 0 if settings.app_use_fixtures or not settings.openai_api_key else 1
    mode_label = st.radio(
        "Mode",
        ["Fixture preview", "Live OpenAI + saved sponsor data", "Full live services"],
        index=default_mode,
    )
    mode = {
        "Fixture preview": "fixture",
        "Live OpenAI + saved sponsor data": "live_openai",
        "Full live services": "live",
    }[mode_label]
    if st.session_state.get("_runtime_mode") != mode:
        st.session_state["_runtime_mode"] = mode
        runtime_factories = {
            "fixture": create_fixture_runtime,
            "live_openai": create_live_openai_runtime,
            "live": create_live_runtime,
        }
        st.session_state["_runtime"] = runtime_factories[mode](settings)
        for state_key in (
            "pipeline_result",
            "pipeline_trace",
            "selected_video_id",
            "latest_answer",
            "qa_history",
        ):
            st.session_state.pop(state_key, None)
    runtime = st.session_state["_runtime"]
    st.divider()
    st.subheader("Service readiness")
    if mode == "fixture":
        render_service_health(runtime.video_service.health_check())
        render_service_health(runtime.extraction_service.health_check())
        render_service_health(runtime.graph_service.health_check())
        render_service_health(runtime.qa_service.health_check())
    elif mode == "live_openai":
        render_service_health(runtime.video_service.health_check())
        render_service_health(StrandsOpenAIProvider(settings).health_check())
        render_service_health(runtime.graph_service.health_check())
        st.caption(
            "Only Strands/OpenAI calls are live in this mode. TwelveLabs input and "
            "Neo4j storage are explicit saved-data adapters."
        )
    else:
        render_service_health(runtime.video_service.health_check())
        render_service_health(StrandsOpenAIProvider(settings).health_check())
        render_service_health(runtime.graph_service.health_check())
        st.caption("All sponsor adapters are live in this mode.")

ingest_tab, ask_tab, graph_tab, test_lab_tab = st.tabs(
    ["Ingest", "Ask", "Graph Explorer", "Test Lab"]
)
with ingest_tab:
    render_ingest_tab(runtime, mode)
with ask_tab:
    render_ask_tab(runtime, mode)
with graph_tab:
    render_graph_tab(runtime, mode)
with test_lab_tab:
    render_test_lab_tab(runtime, mode)
