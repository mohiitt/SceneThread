import pytest

from video_context_graph.contracts.extraction import GraphExtraction
from video_context_graph.contracts.video import VideoGraphMetadata
from video_context_graph.fixture_store import load_fixture_bundle
from video_context_graph.graph.mapper import deterministic_id, map_graph, normalize_lookup


def metadata() -> VideoGraphMetadata:
    return VideoGraphMetadata(
        video_id="fixture_video_001",
        title="Planning meeting",
        file_name="meeting.mp4",
        source_type="upload",
        domain_hint="Meeting",
        duration_sec=38.0,
        external_ids={"asset_id": "asset-1", "index_id": "index-1"},
        pipeline_version="v1",
    )


def test_mapper_creates_stable_deduplicated_batches() -> None:
    extraction = load_fixture_bundle().extraction

    first = map_graph(metadata(), extraction)
    second = map_graph(metadata(), extraction)

    assert first == second
    assert first.node_count == 12
    assert first.relationship_count == 16
    assert [row["ordinal"] for row in first.scenes] == [1, 2]
    assert first.next_scenes == [
        {
            "source_scene_id": first.scenes[0]["scene_id"],
            "target_scene_id": first.scenes[1]["scene_id"],
        }
    ]
    assert first.video["twelvelabs_asset_id"] == "asset-1"


def test_entity_identity_uses_video_type_and_normalized_name() -> None:
    extraction = load_fixture_bundle().extraction
    payload = map_graph(metadata(), extraction)
    presenter = payload.entities[0]

    assert presenter["normalized_name"] == "presenter"
    assert presenter["normalized_aliases"] == ["speaker 1"]
    assert presenter["entity_id"] == deterministic_id(
        "entity", "fixture_video_001", "PERSON", "presenter"
    )


def test_normalize_lookup_collapses_spacing_and_case() -> None:
    assert normalize_lookup("  Metrics   DASHBOARD ") == "metrics dashboard"


def test_mapper_rejects_scenes_outside_video_duration() -> None:
    too_short = metadata().model_copy(update={"duration_sec": 20.0})

    with pytest.raises(ValueError, match="scene timestamps exceed"):
        map_graph(too_short, load_fixture_bundle().extraction)


def test_mapper_rejects_empty_entity_names_before_writing() -> None:
    raw = load_fixture_bundle().extraction.model_dump()
    raw["entities"][0]["canonical_name"] = "   "
    extraction = GraphExtraction.model_validate(raw)

    with pytest.raises(ValueError, match="empty canonical names"):
        map_graph(metadata(), extraction)
