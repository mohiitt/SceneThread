from __future__ import annotations

from pathlib import Path

import pytest

from video_context_graph.contracts.video import SegmentCollection
from video_context_graph.pipeline.artifact_store import ArtifactStore
from video_context_graph.pipeline.state_store import PipelineStateError, PipelineStateStore
from video_context_graph.pipeline.validators import IngestionValidationError


def test_artifact_store_round_trips_validated_segments(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    segments = SegmentCollection.model_validate(
        {
            "video_id": "video_001",
            "duration_sec": 8,
            "segments": [
                {
                    "segment_id": "segment_001",
                    "start_sec": 0,
                    "end_sec": 8,
                    "summary": "A test scene.",
                }
            ],
        }
    )

    path = store.save_segments(segments)

    assert path == tmp_path / "runs" / "video_001" / "twelvelabs_segments.json"
    assert store.load_segments("video_001") == segments


def test_state_store_persists_transitions_and_external_ids(tmp_path: Path) -> None:
    store = PipelineStateStore(tmp_path)
    store.create("video_001")
    store.transition("video_001", "VALIDATING")
    store.record_external_id("video_001", "asset_id", "asset_123")

    job = store.load("video_001")

    assert job is not None
    assert job.current_stage == "VALIDATING"
    assert job.external_ids == {"asset_id": "asset_123"}


def test_state_store_rejects_skipped_stage(tmp_path: Path) -> None:
    store = PipelineStateStore(tmp_path)
    store.create("video_001")

    with pytest.raises(PipelineStateError, match="cannot transition"):
        store.transition("video_001", "INDEXING")


def test_state_store_preserves_terminal_error(tmp_path: Path) -> None:
    store = PipelineStateStore(tmp_path)
    store.create("video_001")
    store.transition("video_001", "VALIDATING")

    job = store.fail("video_001", "asset processing failed")

    assert job.status == "failed"
    assert job.current_stage == "FAILED"
    assert job.error == "asset processing failed"


@pytest.mark.parametrize("video_id", ["../escaped", "nested/path", "nested\\path", "/absolute"])
def test_artifact_and_state_stores_reject_path_traversal(tmp_path: Path, video_id: str) -> None:
    artifacts = ArtifactStore(tmp_path)
    states = PipelineStateStore(tmp_path)

    with pytest.raises(IngestionValidationError, match="safe single path component"):
        artifacts.run_dir(video_id)
    with pytest.raises(IngestionValidationError, match="safe single path component"):
        states.path_for(video_id)


def test_state_store_keeps_ingestion_separate_from_graph_completion(tmp_path: Path) -> None:
    store = PipelineStateStore(tmp_path)
    store.create("video_001", request_fingerprint="fingerprint")
    for stage in (
        "VALIDATING",
        "UPLOADING_ASSET",
        "ASSET_PROCESSING",
        "ASSET_READY",
        "SEGMENTING",
        "SEGMENTS_READY",
        "INDEXING",
    ):
        store.transition("video_001", stage)

    ingestion = store.transition("video_001", "INDEX_READY")

    assert ingestion.status == "ingestion_ready"
    assert ingestion.current_stage == "INDEX_READY"
    assert store.transition("video_001", "NORMALIZING").status == "running"
