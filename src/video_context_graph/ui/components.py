"""Shared Streamlit components for grounded evidence and safe sponsor traces."""

from __future__ import annotations

import streamlit as st

from video_context_graph.contracts import (
    AnswerResult,
    GraphExtraction,
    PipelineTrace,
    ServiceHealth,
)


def format_timestamp(seconds: float) -> str:
    total_seconds = max(0, round(seconds))
    minutes, remaining = divmod(total_seconds, 60)
    return f"{minutes:02d}:{remaining:02d}"


def render_mode_banner(mode: str) -> None:
    if mode == "fixture":
        st.info(
            "Fixture mode is explicit: saved evidence is used and no sponsor API calls are made."
        )
    elif mode == "live_openai":
        st.info(
            "Developer C live mode: Strands calls OpenAI now; TwelveLabs evidence and the "
            "graph adapter remain saved/local until the other service adapters arrive."
        )
    else:
        st.success(
            "Full live mode: TwelveLabs, Strands/OpenAI, and Neo4j calls use configured "
            "external services."
        )


def render_service_health(health: ServiceHealth) -> None:
    icon = "✅" if health.available else "⚠️"
    st.write(f"{icon} **{health.service.title()}** — {health.detail}")


def render_extraction_metrics(extraction: GraphExtraction) -> None:
    columns = st.columns(4)
    columns[0].metric("Scenes", len(extraction.scenes))
    columns[1].metric("Entities", len(extraction.entities))
    columns[2].metric("Events", len(extraction.events))
    columns[3].metric("Relationships", len(extraction.relationships))


def render_trace(trace: PipelineTrace) -> None:
    st.subheader("Safe Strands execution trace")
    for event in trace.events:
        duration = "" if event.duration_ms is None else f" · {event.duration_ms} ms"
        status_icon = {
            "started": "▶️",
            "completed": "✅",
            "failed": "❌",
            "skipped": "⏭️",
        }[event.status]
        with st.container(border=True):
            st.markdown(
                f"{status_icon} **{event.stage.title()} · {event.sponsor}** "
                f"— {event.status}{duration}"
            )
            st.caption(event.summary)
            if event.details:
                st.json(event.details)


def render_answer(answer: AnswerResult) -> None:
    st.markdown(answer.answer)
    st.progress(answer.confidence, text=f"Answer confidence: {answer.confidence:.0%}")
    if answer.evidence:
        st.subheader("Timestamp evidence")
        for evidence in answer.evidence:
            with st.container(border=True):
                st.markdown(
                    f"**{evidence.scene_id} · "
                    f"{format_timestamp(evidence.start_sec)}–"
                    f"{format_timestamp(evidence.end_sec)}**"
                )
                st.caption(evidence.reason)
    if answer.limitations:
        with st.expander("Limitations", expanded=True):
            for limitation in answer.limitations:
                st.write(f"- {limitation}")
