"""Question-answering contracts."""

from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class EvidenceReference(BaseModel):
    scene_id: str
    start_sec: float
    end_sec: float
    reason: str
    video_id: str | None = None
    camera_id: str | None = None
    recorded_start_at: datetime | None = None
    recorded_end_at: datetime | None = None

    @model_validator(mode="after")
    def validate_timestamp_order(self) -> "EvidenceReference":
        if self.start_sec < 0:
            raise ValueError("start_sec must be greater than or equal to 0")
        if self.start_sec >= self.end_sec:
            raise ValueError("start_sec must be less than end_sec")
        absolute_times = (self.recorded_start_at, self.recorded_end_at)
        if any(
            value is not None and (value.tzinfo is None or value.utcoffset() is None)
            for value in absolute_times
        ):
            raise ValueError("recorded evidence timestamps must include a timezone")
        if (self.recorded_start_at is None) != (self.recorded_end_at is None):
            raise ValueError("recorded evidence timestamps must be supplied together")
        if (
            self.recorded_start_at is not None
            and self.recorded_end_at is not None
            and self.recorded_start_at >= self.recorded_end_at
        ):
            raise ValueError("recorded_start_at must be earlier than recorded_end_at")
        return self


class AnswerResult(BaseModel):
    answer: str
    evidence: list[EvidenceReference]
    confidence: float = Field(ge=0, le=1)
    limitations: list[str] = Field(default_factory=list)
