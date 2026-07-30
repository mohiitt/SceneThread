"""Opt-in AuraDB smoke test for the complete Developer B graph service."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest

from video_context_graph.contracts.video import VideoGraphMetadata
from video_context_graph.fixture_store import load_fixture_bundle
from video_context_graph.graph.mapper import map_graph
from video_context_graph.graph.schema import initialize_schema
from video_context_graph.graph.service import Neo4jGraphService
from video_context_graph.graph.visualization import GraphVisualizationBuilder
from video_context_graph.integrations.neo4j_client import Neo4jClient

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_NEO4J_LIVE") != "1",
    reason="set RUN_NEO4J_LIVE=1 with Neo4j credentials to run the AuraDB smoke test",
)


def test_fixture_round_trip_against_live_neo4j() -> None:
    bundle = load_fixture_bundle()
    video_id = f"integration_{uuid4().hex}"
    metadata = VideoGraphMetadata(
        video_id=video_id,
        title="SceneThread integration fixture",
        file_name="fixture.mp4",
        source_type="upload",
        domain_hint="Meeting",
        duration_sec=bundle.segments.duration_sec,
        external_ids={"asset_id": "integration-asset"},
        pipeline_version="integration-test",
    )
    payload = map_graph(metadata, bundle.extraction)
    client = Neo4jClient.from_settings()
    service = Neo4jGraphService(client)
    connected = False

    try:
        health = service.health_check()
        assert health.available, health.detail
        connected = True
        assert initialize_schema(client) == 8

        first = service.index_graph(metadata, bundle.extraction)
        second = service.index_graph(metadata, bundle.extraction)
        assert first == second
        assert first.node_count == payload.node_count
        assert first.relationship_count == payload.relationship_count

        overview = service.get_video_overview(video_id)
        assert overview["scene_count"] == 2
        assert overview["entity_count"] == 3
        assert overview["event_count"] == 2
        assert len(service.list_video_entities(video_id)) == 3
        assert len(service.get_entity_timeline(video_id, "presenter")) == 1
        assert len(service.get_scene_details(video_id, ["scene_002"])) == 1
        assert len(service.get_events_before_or_after(video_id, 38.0, "before")) == 2
        assert service.find_entity_connections(
            video_id, "Jordan", "metrics dashboard"
        )
        assert service.find_scenes_overlapping_moments(video_id, bundle.search)

        visualization = GraphVisualizationBuilder(client).build(video_id)
        assert len(visualization["nodes"]) == payload.node_count
        assert len(visualization["edges"]) == payload.relationship_count
    finally:
        if connected:
            client.execute_write(
                "MATCH (node) WHERE node.video_id = $video_id DETACH DELETE node",
                {"video_id": video_id},
            )
            client.execute_write(
                """MATCH (tag:Tag) WHERE tag.tag_id IN $tag_ids
                AND NOT (tag)<-[:HAS_TAG]-() DELETE tag""",
                {"tag_ids": [tag["tag_id"] for tag in payload.tags]},
            )
        client.close()
