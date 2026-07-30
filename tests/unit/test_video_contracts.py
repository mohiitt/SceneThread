from __future__ import annotations

import pytest
from pydantic import ValidationError

from video_context_graph.contracts import SegmentCollection


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
