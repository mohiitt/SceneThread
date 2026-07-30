"""Session-backed candidate video evaluation matrix."""

from __future__ import annotations

from datetime import UTC, datetime

import streamlit as st

from video_context_graph.ui.components import render_mode_banner
from video_context_graph.ui.runtime import FixtureRuntime

RATING_FIELDS = [
    "Scene segmentation quality",
    "Entity extraction quality",
    "Event sequence quality",
    "Graph usefulness",
    "QA grounding",
]


def render_test_lab_tab(runtime: FixtureRuntime, mode: str) -> None:
    st.header("Test Lab")
    render_mode_banner(mode)
    st.caption("Rate candidate videos before selecting the final demo.")

    with st.form("test_lab_form"):
        ratings = {
            field: st.slider(field, min_value=1, max_value=5, value=3)
            for field in RATING_FIELDS
        }
        on_screen_text = st.select_slider(
            "On-screen text extraction",
            options=["N/A", "1", "2", "3", "4", "5"],
            value="N/A",
        )
        speech = st.select_slider(
            "Speech understanding",
            options=["N/A", "1", "2", "3", "4", "5"],
            value="3",
        )
        notes = st.text_area("Notes")
        submitted = st.form_submit_button("Save session evaluation")

    if submitted:
        evaluations = st.session_state.setdefault("test_lab_evaluations", [])
        evaluations.append(
            {
                "video_id": st.session_state.get(
                    "selected_video_id",
                    runtime.bundle.segments.video_id,
                ),
                "mode": mode,
                "recorded_at": datetime.now(UTC).isoformat(),
                "ratings": ratings,
                "on_screen_text": on_screen_text,
                "speech": speech,
                "notes": notes,
            }
        )
        st.success("Evaluation saved in this Streamlit session.")

    evaluations = st.session_state.get("test_lab_evaluations", [])
    if evaluations:
        st.dataframe(evaluations, width="stretch", hide_index=True)
