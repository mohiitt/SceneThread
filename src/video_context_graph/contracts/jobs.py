"""Pipeline job state contract."""

from datetime import datetime

from pydantic import BaseModel

from video_context_graph.contracts.extraction import GraphExtraction
from video_context_graph.contracts.traces import PipelineTrace
from video_context_graph.contracts.video import GraphWriteResult, IngestionResult


class PipelineJob(BaseModel):
    run_id: str
    video_id: str
    request_fingerprint: str = ""
    status: str
    current_stage: str
    stages: dict[str, str]
    artifact_paths: dict[str, str]
    external_ids: dict[str, str]
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class PipelineRunResult(BaseModel):
    ingestion: IngestionResult
    extraction: GraphExtraction
    graph_write: GraphWriteResult
    trace: PipelineTrace
