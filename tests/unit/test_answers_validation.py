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
