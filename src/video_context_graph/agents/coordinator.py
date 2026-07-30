"""Code-defined sponsor orchestration with safe, user-visible Strands traces."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import PurePosixPath
from time import perf_counter
from typing import Literal

from video_context_graph.contracts import (
    ExtractionService,
    GraphService,
    IngestionRequest,
    PipelineRunResult,
    PipelineTrace,
    PipelineTraceEvent,
    VideoGraphMetadata,
    VideoIntelligenceService,
)


class PipelineExecutionError(RuntimeError):
    """Pipeline failure that retains a safe partial execution trace."""

    def __init__(self, message: str, trace: PipelineTrace) -> None:
        super().__init__(message)
        self.trace = trace


class SceneThreadCoordinator:
    """Run the fixed ingestion, extraction, and indexing handoff sequence."""

    def __init__(
        self,
        *,
        video_service: VideoIntelligenceService,
        extraction_service: ExtractionService,
        graph_service: GraphService,
        mode: Literal["fixture", "live"],
        pipeline_version: str,
    ) -> None:
        self._video_service = video_service
        self._extraction_service = extraction_service
        self._graph_service = graph_service
        self._mode = mode
        self._pipeline_version = pipeline_version

    def process_video(self, request: IngestionRequest) -> PipelineRunResult:
        trace = PipelineTrace(mode=self._mode)
        self._append(trace, "ingestion", "Strands", "started", "Coordinator called ingest_video.")

        stage = "ingestion"
        sponsor: Literal["TwelveLabs", "OpenAI", "Neo4j"] = "TwelveLabs"
        started = perf_counter()
        try:
            ingestion = self._video_service.ingest_video(request)
            self._append(
                trace,
                "ingestion",
                "TwelveLabs",
                "completed",
                f"TwelveLabs returned {len(ingestion.segments.segments)} timestamped scenes.",
                started,
                {"search_available": ingestion.search_available},
            )

            stage = "extraction"
            sponsor = "OpenAI"
            self._append(
                trace,
                "extraction",
                "Strands",
                "started",
                "Coordinator handed timestamped evidence to the Extraction Agent.",
            )
            started = perf_counter()
            extraction = self._extraction_service.extract_graph(
                title=request.title,
                domain_hint=request.domain_hint,
                segments=ingestion.segments,
            )
            self._append(
                trace,
                "extraction",
                "OpenAI",
                "completed",
                "Extraction Agent returned a validated GraphExtraction.",
                started,
                {
                    "scenes": len(extraction.scenes),
                    "entities": len(extraction.entities),
                    "events": len(extraction.events),
                },
            )

            stage = "indexing"
            sponsor = "Neo4j"
            self._append(
                trace,
                "indexing",
                "Strands",
                "started",
                "Coordinator called index_graph with validated graph data.",
            )
            started = perf_counter()
            graph_write = self._graph_service.index_graph(
                self._metadata(request, ingestion),
                extraction,
            )
            self._append(
                trace,
                "indexing",
                "Neo4j",
                "completed",
                "Neo4j indexing completed through deterministic parameterized writes.",
                started,
                {
                    "nodes": graph_write.node_count,
                    "relationships": graph_write.relationship_count,
                },
            )
            return PipelineRunResult(
                ingestion=ingestion,
                extraction=extraction,
                graph_write=graph_write,
                trace=trace,
            )
        except Exception as exc:
            self._append(
                trace,
                stage,  # type: ignore[arg-type]
                sponsor,
                "failed",
                f"{sponsor} stage failed; completed prior stages remain recoverable.",
                started,
                {"error_type": type(exc).__name__},
            )
            raise PipelineExecutionError(
                f"{stage} failed: {type(exc).__name__}: {exc}",
                trace,
            ) from exc

    def _metadata(self, request: IngestionRequest, ingestion: object) -> VideoGraphMetadata:
        from video_context_graph.contracts import IngestionResult

        validated = IngestionResult.model_validate(ingestion)
        file_name = PurePosixPath(request.source_ref).name
        external_ids = {
            "twelvelabs_asset_id": validated.asset_id,
            "segmentation_task_id": validated.segmentation_task_id,
        }
        if validated.index_id is not None:
            external_ids["twelvelabs_index_id"] = validated.index_id
        if validated.indexed_asset_id is not None:
            external_ids["twelvelabs_indexed_asset_id"] = validated.indexed_asset_id
        return VideoGraphMetadata(
            video_id=request.video_id,
            title=request.title,
            file_name=file_name,
            source_type=request.source_type,
            domain_hint=request.domain_hint,
            duration_sec=validated.segments.duration_sec,
            external_ids=external_ids,
            pipeline_version=self._pipeline_version,
        )

    @staticmethod
    def _append(
        trace: PipelineTrace,
        stage: Literal["ingestion", "extraction", "indexing", "qa"],
        sponsor: Literal["Strands", "TwelveLabs", "OpenAI", "Neo4j"],
        status: Literal["started", "completed", "failed", "skipped"],
        summary: str,
        started: float | None = None,
        details: dict[str, str | int | float | bool | None] | None = None,
    ) -> None:
        duration_ms = None if started is None else round((perf_counter() - started) * 1000)
        trace.events.append(
            PipelineTraceEvent(
                stage=stage,
                sponsor=sponsor,
                status=status,
                summary=summary,
                occurred_at=datetime.now(UTC),
                duration_ms=duration_ms,
                details=details or {},
            )
        )
