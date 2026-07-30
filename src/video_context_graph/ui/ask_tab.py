"""Grounded question-answering tab."""

from __future__ import annotations

from typing import cast

import streamlit as st

from video_context_graph.agents.qa_agent import QuestionAnsweringAgentError
from video_context_graph.contracts import AnswerResult
from video_context_graph.ui.components import render_answer, render_mode_banner
from video_context_graph.ui.runtime import FixtureRuntime

SUGGESTED_QUESTIONS = [
    "Who was assigned to the metrics dashboard?",
    "Summarize the video in chronological order.",
    "What happened before the dashboard assignment?",
]


def render_ask_tab(runtime: FixtureRuntime, mode: str) -> None:
    st.header("Ask")
    render_mode_banner(mode)

    selected_video_id = st.session_state.get("selected_video_id")
    if mode == "live" and not selected_video_id:
        st.warning("Run the full live ingestion pipeline before asking about a video.")
        return

    selected = st.selectbox("Suggested question", SUGGESTED_QUESTIONS)
    question = st.text_input("Question", value=selected)
    is_model_backed = mode in {"live_openai", "live"}
    button_label = "Ask live Strands/OpenAI" if is_model_backed else "Ask fixture"
    if st.button(button_label, type="primary", width="stretch"):
        try:
            answer = runtime.qa_service.answer_question(
                video_id=selected_video_id or runtime.bundle.segments.video_id,
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
        render_answer(stored_answer)

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
