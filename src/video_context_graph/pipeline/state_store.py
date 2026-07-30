"""Durable ingestion job state with explicit, validated transitions."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from video_context_graph.contracts.jobs import PipelineJob
from video_context_graph.pipeline.validators import validate_video_id

PIPELINE_STAGES = (
    "NEW",
    "VALIDATING",
    "UPLOADING_ASSET",
    "ASSET_PROCESSING",
    "ASSET_READY",
    "SEGMENTING",
    "SEGMENTS_READY",
    "INDEXING",
    "INDEX_READY",
    "NORMALIZING",
    "GRAPH_WRITING",
    "READY",
    "FAILED",
)

_NEXT_STAGES = {
    "NEW": {"VALIDATING", "FAILED"},
    "VALIDATING": {"UPLOADING_ASSET", "FAILED"},
    "UPLOADING_ASSET": {"ASSET_PROCESSING", "FAILED"},
    "ASSET_PROCESSING": {"ASSET_READY", "FAILED"},
    "ASSET_READY": {"SEGMENTING", "FAILED"},
    "SEGMENTING": {"SEGMENTS_READY", "FAILED"},
    "SEGMENTS_READY": {"INDEXING", "FAILED"},
    "INDEXING": {"INDEX_READY", "FAILED"},
    "INDEX_READY": {"NORMALIZING", "FAILED"},
    "NORMALIZING": {"GRAPH_WRITING", "FAILED"},
    "GRAPH_WRITING": {"READY", "FAILED"},
    "READY": set(),
    "FAILED": set(),
}


class PipelineStateError(RuntimeError):
    """Raised when a persisted job would move through an invalid state transition."""


class PipelineStateStore:
    """Stores one JSON job record per video with atomic writes."""

    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir).expanduser().resolve()

    def path_for(self, video_id: str) -> Path:
        validate_video_id(video_id)
        path = (self.data_dir / "runs" / video_id / "job.json").resolve()
        try:
            path.relative_to(self.data_dir)
        except ValueError as exc:
            raise PipelineStateError("pipeline state path escapes the configured data directory") from exc
        return path

    def load(self, video_id: str) -> PipelineJob | None:
        path = self.path_for(video_id)
        if not path.exists():
            return None
        return PipelineJob.model_validate_json(path.read_text(encoding="utf-8"))

    def create(
        self,
        video_id: str,
        *,
        run_id: str | None = None,
        request_fingerprint: str = "",
    ) -> PipelineJob:
        existing = self.load(video_id)
        if existing is not None:
            return existing
        now = _utcnow()
        job = PipelineJob(
            run_id=run_id or video_id,
            video_id=video_id,
            request_fingerprint=request_fingerprint,
            status="running",
            current_stage="NEW",
            stages={"NEW": "completed"},
            artifact_paths={},
            external_ids={},
            created_at=now,
            updated_at=now,
        )
        return self._save(job)

    def restart(
        self,
        video_id: str,
        *,
        run_id: str | None = None,
        request_fingerprint: str = "",
    ) -> PipelineJob:
        """Start a fresh attempt while retaining no stale identifiers or stage statuses."""
        previous = self._require_job(video_id)
        now = _utcnow()
        return self._save(
            PipelineJob(
                run_id=run_id or previous.run_id,
                video_id=video_id,
                request_fingerprint=request_fingerprint,
                status="running",
                current_stage="NEW",
                stages={"NEW": "completed"},
                artifact_paths={},
                external_ids={},
                created_at=now,
                updated_at=now,
            )
        )

    def resume_from(self, video_id: str, stage: str, *, request_fingerprint: str) -> PipelineJob:
        """Resume an interrupted ingestion from a completed provider stage."""
        if stage not in {"ASSET_READY", "SEGMENTING", "SEGMENTS_READY"}:
            raise PipelineStateError(f"stage cannot be resumed: {stage}")
        previous = self._require_job(video_id)
        stages = dict(previous.stages)
        stages[stage] = "completed"
        return self._save(
            previous.model_copy(
                update={
                    "request_fingerprint": request_fingerprint,
                    "status": "running",
                    "current_stage": stage,
                    "stages": stages,
                    "error": None,
                    "updated_at": _utcnow(),
                }
            )
        )

    def transition(self, video_id: str, stage: str) -> PipelineJob:
        if stage not in PIPELINE_STAGES:
            raise PipelineStateError(f"unknown pipeline stage: {stage}")
        job = self._require_job(video_id)
        if stage == job.current_stage:
            return job
        if stage not in _NEXT_STAGES[job.current_stage]:
            raise PipelineStateError(
                f"cannot transition pipeline job from {job.current_stage} to {stage}"
            )

        stages = dict(job.stages)
        if job.current_stage not in {"NEW", "FAILED"}:
            stages[job.current_stage] = "completed"
        stages[stage] = "failed" if stage == "FAILED" else "in_progress"
        status = (
            "failed"
            if stage == "FAILED"
            else "ready"
            if stage == "READY"
            else "ingestion_ready"
            if stage == "INDEX_READY"
            else "running"
        )
        if stage in {"READY", "INDEX_READY"}:
            stages[stage] = "completed"
        return self._save(
            job.model_copy(
                update={
                    "status": status,
                    "current_stage": stage,
                    "stages": stages,
                    "updated_at": _utcnow(),
                }
            )
        )

    def record_external_id(self, video_id: str, key: str, value: str) -> PipelineJob:
        job = self._require_job(video_id)
        external_ids = dict(job.external_ids)
        external_ids[key] = value
        return self._save(
            job.model_copy(update={"external_ids": external_ids, "updated_at": _utcnow()})
        )

    def record_artifact(self, video_id: str, key: str, path: str | Path) -> PipelineJob:
        job = self._require_job(video_id)
        artifact_paths = dict(job.artifact_paths)
        artifact_paths[key] = str(path)
        return self._save(
            job.model_copy(update={"artifact_paths": artifact_paths, "updated_at": _utcnow()})
        )

    def fail(self, video_id: str, error: Exception | str) -> PipelineJob:
        job = self._require_job(video_id)
        message = str(error)
        if job.current_stage != "FAILED":
            stages = dict(job.stages)
            stages[job.current_stage] = "failed"
            stages["FAILED"] = "completed"
            job = job.model_copy(
                update={
                    "status": "failed",
                    "current_stage": "FAILED",
                    "stages": stages,
                    "error": message,
                    "updated_at": _utcnow(),
                }
            )
        return self._save(job)

    def _require_job(self, video_id: str) -> PipelineJob:
        job = self.load(video_id)
        if job is None:
            raise PipelineStateError(f"pipeline job not found for video: {video_id}")
        return job

    def _save(self, job: PipelineJob) -> PipelineJob:
        path = self.path_for(job.video_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(job.model_dump_json(indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
        return job


def _utcnow() -> datetime:
    return datetime.now(UTC)
