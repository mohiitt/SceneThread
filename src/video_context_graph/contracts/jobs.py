"""Pipeline job state contract."""

from datetime import datetime

from pydantic import BaseModel


class PipelineJob(BaseModel):
    run_id: str
    video_id: str
    status: str
    current_stage: str
    stages: dict[str, str]
    artifact_paths: dict[str, str]
    external_ids: dict[str, str]
    error: str | None = None
    created_at: datetime
    updated_at: datetime
