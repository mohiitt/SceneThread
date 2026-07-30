from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from video_context_graph.contracts import IngestionRequest, RecordingScope, SegmentCollection


def test_segment_collection_accepts_timestamps_within_video() -> None:
    collection = SegmentCollection.model_validate(
        {
            "video_id": "video_1",
            "duration_sec": 10,
            "segments": [
                {
                    "segment_id": "segment_1",
                    "start_sec": 0,
                    "end_sec": 10,
                    "summary": "A complete test scene.",
                }
            ],
        }
    )

    assert collection.segments[0].segment_id == "segment_1"


def test_segment_collection_rejects_duplicate_ids() -> None:
    with pytest.raises(ValidationError, match="segment IDs must be unique"):
        SegmentCollection.model_validate(
            {
                "video_id": "video_1",
                "duration_sec": 10,
                "segments": [
                    {
                        "segment_id": "duplicate",
                        "start_sec": 0,
                        "end_sec": 4,
                        "summary": "First scene.",
                    },
                    {
                        "segment_id": "duplicate",
                        "start_sec": 4,
                        "end_sec": 8,
                        "summary": "Second scene.",
                    },
                ],
            }
        )


def test_segment_collection_rejects_segment_past_duration() -> None:
    with pytest.raises(ValidationError, match="exceed video duration"):
        SegmentCollection.model_validate(
            {
                "video_id": "video_1",
                "duration_sec": 10,
                "segments": [
                    {
                        "segment_id": "segment_1",
                        "start_sec": 8,
                        "end_sec": 11,
                        "summary": "Scene extends past the video.",
                    }
                ],
            }
        )


def test_recording_metadata_requires_timezone_aware_start() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        IngestionRequest(
            video_id="video_1",
            title="Camera footage",
            source_type="url",
            source_ref="https://example.com/video.mp4",
            recorded_at=datetime.fromisoformat("2026-07-30T09:00:00"),
        )


def test_recording_scope_deduplicates_filters_and_validates_window() -> None:
    scope = RecordingScope(
        store_id="store_sf",
        camera_ids=["entrance", "entrance"],
        recorded_from=datetime(2026, 7, 30, 9, tzinfo=UTC),
        recorded_to=datetime(2026, 7, 30, 10, tzinfo=UTC),
    )

    assert scope.camera_ids == ["entrance"]

    with pytest.raises(ValidationError, match="earlier"):
        RecordingScope(
            store_id="store_sf",
            recorded_from=datetime(2026, 7, 30, 10, tzinfo=UTC),
            recorded_to=datetime(2026, 7, 30, 9, tzinfo=UTC),
        )
