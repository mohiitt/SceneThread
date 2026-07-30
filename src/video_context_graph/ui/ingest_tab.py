"""Ingestion UI with an executable fixture-first coordinator preview."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal, cast
from zoneinfo import ZoneInfo

import streamlit as st
from streamlit.runtime.uploaded_file_manager import UploadedFile

from video_context_graph.agents.coordinator import PipelineExecutionError
from video_context_graph.agents.domain_profiles import list_domain_profiles
from video_context_graph.config import get_settings
from video_context_graph.contracts import IngestionRequest, PipelineRunResult
from video_context_graph.pipeline.validators import validate_video_id
from video_context_graph.ui.components import (
    render_extraction_metrics,
    render_mode_banner,
    render_trace,
)
from video_context_graph.ui.runtime import FixtureRuntime

VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".avi"}


def render_ingest_tab(runtime: FixtureRuntime, mode: str) -> None:
    st.header("Ingest")
    render_mode_banner(mode)

    title = st.text_input(
        "Video title",
        value="Planning meeting fixture" if mode != "live" else "Live video",
    )
    video_id = (
        runtime.bundle.segments.video_id
        if mode == "fixture"
        else st.text_input(
            "Video ID",
            value=(
                runtime.bundle.segments.video_id
                if mode == "live_openai"
                else "live_video_001"
            ),
            help="Use letters, numbers, periods, underscores, or hyphens.",
        )
    )
    domain_hint = st.selectbox("Domain profile", list_domain_profiles())
    st.subheader("Recording identity")
    recording_columns = st.columns(2)
    store_id = recording_columns[0].text_input(
        "Store ID",
        value="aws-builder-loft-sf",
        help="Shared collection identifier used for cross-video discovery.",
    )
    camera_id = recording_columns[1].text_input(
        "Camera ID",
        value="camera_01",
        help="Stable physical camera identifier, such as entrance_cam.",
    )
    date_column, time_column, timezone_column = st.columns(3)
    recorded_date = date_column.date_input("Recording date")
    recorded_time = time_column.time_input("Recording start time")
    timezone_name = timezone_column.selectbox(
        "Timezone",
        ["America/Los_Angeles", "UTC"],
        help="The timestamp represents the beginning of this video.",
    )
    source_type = cast(
        Literal["upload", "url"],
        st.radio("Source type", ["upload", "url"], horizontal=True),
    )
    if mode == "live_openai":
        st.warning(
            "This mode uses saved TwelveLabs fixture evidence. Switch the sidebar to "
            "Full live services to ingest your own uploaded video."
        )
    if source_type == "upload":
        uploaded = st.file_uploader("Video file", type=["mp4", "mov", "m4v", "webm", "avi"])
        source_ref = "fixture_planning_meeting.mp4"
    else:
        uploaded = None
        source_ref = st.text_input(
            "Direct video URL",
            value=(
                "https://example.invalid/fixture_planning_meeting.mp4"
                if mode != "live"
                else ""
            ),
        )
    force_reprocess = st.checkbox("Force reprocess", value=False)

    is_live_openai = mode == "live_openai"
    button_label = {
        "fixture": "Run fixture pipeline",
        "live_openai": "Run live Strands/OpenAI pipeline",
        "live": "Run full live pipeline",
    }[mode]
    if st.button(button_label, type="primary", width="stretch"):
        try:
            if source_type == "upload" and mode != "fixture" and uploaded is None:
                raise ValueError(
                    "Choose a video file before running live ingestion."
                )
            if uploaded is not None:
                settings = get_settings()
                if uploaded.size > settings.app_max_video_mb * 1024 * 1024:
                    raise ValueError(
                        f"Upload exceeds the configured "
                        f"{settings.app_max_video_mb} MB limit."
                    )
                source_ref = _persist_uploaded_video(
                    uploaded,
                    video_id=video_id,
                    app_data_dir=runtime.app_data_dir,
                )
            request = IngestionRequest(
                video_id=video_id,
                title=title,
                source_type=source_type,
                source_ref=source_ref,
                domain_hint=domain_hint,
                force_reprocess=force_reprocess,
                store_id=store_id,
                camera_id=camera_id,
                recorded_at=datetime.combine(
                    recorded_date,
                    recorded_time,
                    tzinfo=ZoneInfo(timezone_name),
                ),
            )
            result = runtime.coordinator.process_video(request)
        except PipelineExecutionError as exc:
            st.session_state["pipeline_trace"] = exc.trace
            st.error(str(exc))
        except (OSError, ValueError) as exc:
            st.error(str(exc))
        else:
            st.session_state["pipeline_result"] = result
            st.session_state["pipeline_trace"] = result.trace
            st.session_state["selected_video_id"] = result.ingestion.video_id
            if uploaded is not None or source_type == "url":
                video_sources = st.session_state.setdefault("video_sources", {})
                video_sources[result.ingestion.video_id] = source_ref
            st.session_state["selected_store_id"] = store_id
            if is_live_openai:
                st.success(
                    "Live Strands/OpenAI extraction completed; saved TwelveLabs input and "
                    "the local graph adapter completed their handoffs."
                )
            elif mode == "fixture":
                st.success("Fixture pipeline completed through all frozen service boundaries.")
            else:
                st.success(
                    "Full live pipeline completed through TwelveLabs, Strands/OpenAI, "
                    "and Neo4j."
                )

    stored_result = cast(PipelineRunResult | None, st.session_state.get("pipeline_result"))
    if stored_result is not None:
        render_extraction_metrics(stored_result.extraction)
        st.caption(stored_result.extraction.video_summary)
        columns = st.columns(2)
        columns[0].metric("Graph nodes", stored_result.graph_write.node_count)
        columns[1].metric(
            "Graph relationships",
            stored_result.graph_write.relationship_count,
        )

    trace = st.session_state.get("pipeline_trace")
    if trace is not None:
        render_trace(trace)


def _persist_uploaded_video(
    uploaded: UploadedFile,
    *,
    video_id: str,
    app_data_dir: str,
) -> str:
    """Persist an uploaded video so ingestion and later scene playback share one source."""
    validate_video_id(video_id)
    suffix = Path(uploaded.name).suffix.lower()
    if suffix not in VIDEO_EXTENSIONS:
        raise ValueError(f"unsupported video extension: {suffix or '(none)'}")

    upload_root = (Path(app_data_dir).expanduser().resolve() / "ui_uploads").resolve()
    target = (upload_root / video_id / f"source{suffix}").resolve()
    try:
        target.relative_to(upload_root)
    except ValueError as exc:
        raise ValueError("uploaded video path escapes the configured data directory") from exc

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(f"{target.suffix}.tmp")
    temporary.write_bytes(uploaded.getvalue())
    temporary.replace(target)
    return str(target)
