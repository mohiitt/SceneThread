from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol, cast

from video_context_graph.agents.domain_profiles import get_domain_guidance, list_domain_profiles
from video_context_graph.agents.tools import build_pipeline_tools, build_qa_tools
from video_context_graph.config import Settings
from video_context_graph.contracts import (
    ExtractionService,
    GraphService,
    IngestionRequest,
    PipelineCoordinator,
    QuestionAnsweringService,
    RecordingScope,
    VideoIntelligenceService,
)
from video_context_graph.ui.components import format_timestamp
from video_context_graph.ui.runtime import create_fixture_runtime


class NamedTool(Protocol):
    tool_name: str


def build_runtime():
    return create_fixture_runtime(Settings(app_use_fixtures=True))


def test_fixture_runtime_satisfies_frozen_service_interfaces() -> None:
    runtime = build_runtime()

    assert isinstance(runtime.video_service, VideoIntelligenceService)
    assert isinstance(runtime.extraction_service, ExtractionService)
    assert isinstance(runtime.graph_service, GraphService)
    assert isinstance(runtime.qa_service, QuestionAnsweringService)
    assert isinstance(runtime.coordinator, PipelineCoordinator)


def test_fixture_coordinator_runs_all_sponsor_handoffs() -> None:
    runtime = build_runtime()
    result = runtime.coordinator.process_video(
        IngestionRequest(
            video_id=runtime.bundle.segments.video_id,
            title="Planning fixture",
            source_type="upload",
            source_ref="fixture.mp4",
            domain_hint="Meeting",
        )
    )

    assert result.graph_write.node_count > 0
    assert result.graph_write.relationship_count > 0
    assert [(event.stage, event.sponsor, event.status) for event in result.trace.events] == [
        ("ingestion", "Strands", "started"),
        ("ingestion", "TwelveLabs", "completed"),
        ("extraction", "Strands", "started"),
        ("extraction", "OpenAI", "completed"),
        ("indexing", "Strands", "started"),
        ("indexing", "Neo4j", "completed"),
    ]


def test_fixture_collection_qa_uses_indexed_recording_identity() -> None:
    runtime = build_runtime()
    runtime.coordinator.process_video(
        IngestionRequest(
            video_id=runtime.bundle.segments.video_id,
            title="Planning fixture",
            source_type="upload",
            source_ref="fixture.mp4",
            store_id="store_sf",
            camera_id="meeting_room",
            recorded_at=datetime(2026, 7, 30, 9, tzinfo=UTC),
        )
    )

    answer = runtime.qa_service.answer_collection_question(
        scope=RecordingScope(store_id="store_sf"),
        question="Who was assigned to the dashboard?",
    )

    assert answer.evidence[0].video_id == runtime.bundle.segments.video_id
    assert answer.evidence[0].camera_id == "meeting_room"
    assert answer.evidence[0].recorded_start_at is not None


def test_fixture_qa_returns_timestamped_evidence_and_abstains_when_needed() -> None:
    runtime = build_runtime()
    supported = runtime.qa_service.answer_question(
        video_id=runtime.bundle.segments.video_id,
        question="Who was assigned to the metrics dashboard?",
    )
    unsupported = runtime.qa_service.answer_question(
        video_id=runtime.bundle.segments.video_id,
        question="What color was the car?",
    )

    assert "Jordan" in supported.answer
    assert supported.evidence[0].scene_id == "scene_002"
    assert unsupported.evidence == []
    assert unsupported.confidence < 0.5
    assert unsupported.limitations


def test_fixture_graph_exposes_compact_safe_queries() -> None:
    runtime = build_runtime()
    video_id = runtime.bundle.segments.video_id

    overview = runtime.graph_service.get_video_overview(video_id)
    entities = runtime.graph_service.list_video_entities(video_id, "PERSON")
    timeline = runtime.graph_service.get_entity_timeline(video_id, "Jordan")

    assert overview["scene_count"] == 2
    assert {entity["canonical_name"] for entity in entities} == {"presenter", "Jordan"}
    assert timeline[0]["scene_id"] == "scene_002"


def test_registered_tools_make_sponsor_boundaries_visible() -> None:
    runtime = build_runtime()
    qa_names = {
        cast(NamedTool, tool).tool_name
        for tool in build_qa_tools(runtime.video_service, runtime.graph_service)
    }
    pipeline_names = {
        cast(NamedTool, tool).tool_name
        for tool in build_pipeline_tools(runtime.video_service, runtime.graph_service)
    }

    assert "search_video_moments" in qa_names
    assert "index_graph" not in qa_names
    assert pipeline_names == {"ingest_video", "index_graph"}


def test_domain_profiles_and_timestamp_formatting_are_stable() -> None:
    assert "Meeting" in list_domain_profiles()
    assert "decisions" in get_domain_guidance("Meeting")
    assert get_domain_guidance("unknown") == get_domain_guidance("Auto")
    assert format_timestamp(125) == "02:05"
