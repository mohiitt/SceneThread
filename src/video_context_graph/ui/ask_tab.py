"""Grounded question-answering tab."""

from __future__ import annotations

from typing import cast

import streamlit as st

from video_context_graph.agents.qa_agent import QuestionAnsweringAgentError
from video_context_graph.contracts import AnswerResult, RecordingScope
from video_context_graph.ui.components import render_answer, render_mode_banner
from video_context_graph.ui.runtime import FixtureRuntime

SUGGESTED_QUESTIONS = [
    "When did the suspicious activity occur across these recordings?",
    "What objects were moved, and what happened immediately before and after?",
    "Which cameras captured the same sequence of events?",
]


def render_ask_tab(runtime: FixtureRuntime, mode: str) -> None:
    st.header("Ask")
    render_mode_banner(mode)

    scope_mode = st.radio(
        "Question scope",
        ["One video", "Recording collection"],
        horizontal=True,
    )
    selected_video_id = st.session_state.get("selected_video_id")
    if scope_mode == "One video" and mode == "live" and not selected_video_id:
        st.warning("Run the full live ingestion pipeline before asking about a video.")
        return

    scope_values: dict[str, object] | None = None
    if scope_mode == "Recording collection":
        store_id = st.text_input(
            "Collection store ID",
            value=st.session_state.get("selected_store_id", "aws-builder-loft-sf"),
        )
        camera_text = st.text_input(
            "Camera IDs (optional, comma-separated)",
            help="Leave empty to search every indexed camera in the store.",
        )
        range_columns = st.columns(2)
        recorded_from = range_columns[0].text_input(
            "Recorded from (optional)",
            placeholder="2026-07-30T09:00:00-07:00",
        )
        recorded_to = range_columns[1].text_input(
            "Recorded to, exclusive (optional)",
            placeholder="2026-07-31T09:00:00-07:00",
        )
        scope_values = {
            "store_id": store_id,
            "camera_ids": [
                item.strip() for item in camera_text.split(",") if item.strip()
            ],
            "recorded_from": recorded_from or None,
            "recorded_to": recorded_to or None,
        }

    selected = st.selectbox("Suggested question", SUGGESTED_QUESTIONS)
    question = st.text_input("Question", value=selected)
    is_model_backed = mode in {"live_openai", "live"}
    button_label = "Ask live Strands/OpenAI" if is_model_backed else "Ask fixture"
    if st.button(button_label, type="primary", width="stretch"):
        try:
            if scope_values is None:
                answer = runtime.qa_service.answer_question(
                    video_id=selected_video_id or runtime.bundle.segments.video_id,
                    question=question,
                )
            else:
                answer = runtime.qa_service.answer_collection_question(
                    scope=RecordingScope.model_validate(scope_values),
                    question=question,
                )
        except (QuestionAnsweringAgentError, ValueError, RuntimeError) as exc:
            st.error(f"{type(exc).__name__}: {exc}")
        else:
            st.session_state["latest_answer"] = answer
            history = st.session_state.setdefault("qa_history", [])
            history.append({"question": question, "answer": answer})

    stored_answer = cast(AnswerResult | None, st.session_state.get("latest_answer"))
    if stored_answer is not None:
        answer_video_id = selected_video_id or runtime.bundle.segments.video_id
        video_source = st.session_state.get("video_sources", {}).get(answer_video_id)
        render_answer(stored_answer, video_source=video_source)

    history = st.session_state.get("qa_history", [])
    if history:
        history_label = (
            "Live OpenAI question history"
            if is_model_backed
            else "Fixture question history"
        )
        with st.expander(history_label):
            for item in reversed(history):
                st.markdown(f"**Q:** {item['question']}")
                st.write(item["answer"].answer)
