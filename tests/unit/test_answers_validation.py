from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from video_context_graph.contracts import AnswerResult


def test_answer_result_validates_timestamped_evidence() -> None:
    answer = AnswerResult.model_validate(
        {
            "answer": "Jordan was assigned to the metrics dashboard.",
            "confidence": 0.84,
            "evidence": [
                {
                    "scene_id": "scene_002",
                    "start_sec": 12.5,
                    "end_sec": 38.0,
                    "reason": "The assignment is discussed in this scene.",
                }
            ],
        }
    )

    assert answer.evidence[0].scene_id == "scene_002"


def test_answer_result_rejects_confidence_outside_range() -> None:
    with pytest.raises(ValidationError):
        AnswerResult.model_validate(
            {
                "answer": "Unknown.",
                "confidence": 1.5,
                "evidence": [],
            }
        )


def test_collection_evidence_validates_absolute_recording_times() -> None:
    answer = AnswerResult.model_validate(
        {
            "answer": "An item was moved.",
            "confidence": 0.8,
            "evidence": [
                {
                    "video_id": "day_1_entrance",
                    "camera_id": "entrance",
                    "scene_id": "scene_3",
                    "start_sec": 5,
                    "end_sec": 8,
                    "recorded_start_at": datetime(2026, 7, 30, 9, 0, 5, tzinfo=UTC),
                    "recorded_end_at": datetime(2026, 7, 30, 9, 0, 8, tzinfo=UTC),
                    "reason": "The item changes location.",
                }
            ],
        }
    )

    assert answer.evidence[0].video_id == "day_1_entrance"

    raw = answer.model_dump()
    raw["evidence"][0]["recorded_end_at"] = None
    with pytest.raises(ValidationError, match="supplied together"):
        AnswerResult.model_validate(raw)
