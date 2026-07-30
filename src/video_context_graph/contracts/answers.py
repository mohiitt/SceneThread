"""Question-answering contracts."""

from pydantic import BaseModel, Field, model_validator


class EvidenceReference(BaseModel):
    scene_id: str
    start_sec: float
    end_sec: float
    reason: str

    @model_validator(mode="after")
    def validate_timestamp_order(self) -> "EvidenceReference":
        if self.start_sec < 0:
            raise ValueError("start_sec must be greater than or equal to 0")
        if self.start_sec >= self.end_sec:
            raise ValueError("start_sec must be less than end_sec")
        return self


class AnswerResult(BaseModel):
    answer: str
    evidence: list[EvidenceReference]
    confidence: float = Field(ge=0, le=1)
    limitations: list[str] = Field(default_factory=list)
