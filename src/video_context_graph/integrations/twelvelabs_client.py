"""Deterministic TwelveLabs ingestion and semantic-search service."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from video_context_graph.config import Settings, get_settings
from video_context_graph.contracts.video import (
    IngestionRequest,
    IngestionResult,
    SearchMoment,
    SearchRequest,
    SearchResults,
    SegmentCollection,
    ServiceHealth,
    VideoSegment,
)
from video_context_graph.fixture_store import load_fixture_bundle
from video_context_graph.pipeline.artifact_store import ArtifactStore
from video_context_graph.pipeline.state_store import PipelineStateStore
from video_context_graph.pipeline.validators import (
    ingestion_request_fingerprint,
    validate_ingestion_source,
    validate_video_id,
)

_POLL_READY = "ready"
_POLL_FAILED = "failed"


class TwelveLabsError(RuntimeError):
    """Base class for errors that make a TwelveLabs request unsuccessful."""


class TwelveLabsConfigurationError(TwelveLabsError):
    """Raised when a live request lacks the required local configuration."""


class TwelveLabsRemoteError(TwelveLabsError):
    """Raised when TwelveLabs reports an unsuccessful terminal operation."""


class TwelveLabsPollingTimeout(TwelveLabsError):
    """Raised when an asynchronous TwelveLabs operation does not finish in time."""


class TwelveLabsResponseError(TwelveLabsError):
    """Raised when a successful provider response cannot satisfy local contracts."""


class TwelveLabsClient:
    """Implements the frozen ``VideoIntelligenceService`` contract.

    The SDK is imported lazily so fixture development and tests do not require credentials
    or the optional external package to be installed.
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        artifact_store: ArtifactStore | None = None,
        state_store: PipelineStateStore | None = None,
        sdk_client: Any | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_poll_attempts: int = 60,
        poll_interval_seconds: float = 2.0,
        request_attempts: int = 3,
    ) -> None:
        self.settings = settings or get_settings()
        self.artifacts = artifact_store or ArtifactStore(self.settings.app_data_dir)
        self.states = state_store or PipelineStateStore(self.settings.app_data_dir)
        self._sdk_client = sdk_client
        self._sleep = sleep
        self.max_poll_attempts = max_poll_attempts
        self.poll_interval_seconds = poll_interval_seconds
        self.request_attempts = request_attempts

    def ingest_video(self, request: IngestionRequest) -> IngestionResult:
        """Upload, segment, index, and persist one video, reusing a completed cache by default."""
        validate_video_id(request.video_id)
        source_path = validate_ingestion_source(
            request,
            max_upload_bytes=self.settings.app_max_video_mb * 1024 * 1024,
        )
        fingerprint = ingestion_request_fingerprint(
            request,
            pipeline_version=self.settings.pipeline_version,
            source_path=source_path,
        )
        existing_job = self.states.load(request.video_id)
        if not request.force_reprocess:
            cached = self._load_cached_result(request.video_id, fingerprint)
            if cached is not None:
                return cached

        resume_stage = self._resume_stage(existing_job, request.video_id, fingerprint)
        if request.force_reprocess or (existing_job and resume_stage is None):
            self.artifacts.invalidate_ingestion(request.video_id)
            if existing_job is None:
                self.states.create(request.video_id, request_fingerprint=fingerprint)
            else:
                self.states.restart(request.video_id, request_fingerprint=fingerprint)
            resume_stage = None
        elif resume_stage is not None:
            self.states.resume_from(
                request.video_id,
                resume_stage,
                request_fingerprint=fingerprint,
            )
        elif existing_job is None:
            self.states.create(request.video_id, request_fingerprint=fingerprint)

        try:
            if resume_stage == "SEGMENTS_READY":
                segments = self.artifacts.load_segments(request.video_id)
                if segments is None:
                    raise TwelveLabsResponseError("persisted segments were unavailable for resume")
                return self._index_segments(
                    self._live_client(),
                    request,
                    self._resume_asset_id(request.video_id),
                    self._resume_task_id(request.video_id),
                    segments,
                )
            if resume_stage == "ASSET_READY":
                return self._resume_from_asset(request)
            if resume_stage == "SEGMENTING":
                return self._resume_from_segmentation(request)

            self.states.transition(request.video_id, "VALIDATING")
            if source_path is not None:
                persisted_source = self.artifacts.persist_source(request.video_id, source_path)
                self.states.record_artifact(request.video_id, "source", persisted_source)

            if self.settings.app_use_fixtures:
                return self._ingest_fixture(request)
            return self._ingest_live(request, source_path)
        except Exception as exc:
            self.states.fail(request.video_id, exc)
            raise

    def search_video_moments(self, request: SearchRequest) -> SearchResults:
        """Return semantic video moments for one locally tracked video."""
        if self.settings.app_use_fixtures:
            return load_fixture_bundle().search.model_copy(update={"query": request.query})

        ingestion = self._load_cached_result_for_search(request.video_id)
        if ingestion is None:
            raise TwelveLabsError(f"video has not been ingested: {request.video_id}")
        if not ingestion.search_available:
            raise TwelveLabsError(f"semantic search is unavailable for video: {request.video_id}")
        if ingestion.index_id is None:
            raise TwelveLabsError(f"search index is unavailable for video: {request.video_id}")

        client = self._live_client()
        filter_payload = json.dumps({"scenethread_video_id": request.video_id})
        response = self._retry(
            "search request",
            lambda: client.search.query(
                index_id=ingestion.index_id,
                search_options=["visual", "audio", "transcription"],
                query_text=request.query,
                page_limit=request.top_k,
                filter=filter_payload,
            ),
        )
        raw = self._as_jsonable(response)
        self.artifacts.save_json(request.video_id, "twelvelabs_search_samples.json", raw)
        moments = self._parse_search_results(request, response)
        return SearchResults(query=request.query, results=moments)

    def health_check(self) -> ServiceHealth:
        if self.settings.app_use_fixtures:
            return ServiceHealth(
                service="twelvelabs",
                available=True,
                detail="Fixture mode enabled; no live TwelveLabs request was made.",
            )
        if not self.settings.twelvelabs_api_key:
            return ServiceHealth(
                service="twelvelabs",
                available=False,
                detail="TWELVELABS_API_KEY is not configured.",
            )
        if not self.settings.twelvelabs_index_id:
            return ServiceHealth(
                service="twelvelabs",
                available=False,
                detail="TWELVELABS_INDEX_ID is not configured.",
            )
        try:
            self._retry(
                "index health check",
                lambda: self._live_client().indexes.retrieve(self.settings.twelvelabs_index_id),
            )
        except Exception as exc:  # noqa: BLE001 - health check converts all provider failures to status.
            return ServiceHealth(service="twelvelabs", available=False, detail=str(exc))
        return ServiceHealth(service="twelvelabs", available=True, detail="TwelveLabs index is reachable.")

    def _ingest_fixture(self, request: IngestionRequest) -> IngestionResult:
        self.states.transition(request.video_id, "UPLOADING_ASSET")
        self.states.transition(request.video_id, "ASSET_PROCESSING")
        self.states.transition(request.video_id, "ASSET_READY")
        self.states.transition(request.video_id, "SEGMENTING")

        fixture_segments = load_fixture_bundle().segments.model_copy(update={"video_id": request.video_id})
        asset_id = f"fixture_asset_{request.video_id}"
        task_id = f"fixture_segmentation_{request.video_id}"
        self.states.record_external_id(request.video_id, "asset_id", asset_id)
        self.states.record_external_id(request.video_id, "segmentation_task_id", task_id)
        raw_path = self.artifacts.save_json(
            request.video_id,
            "twelvelabs_segmentation_raw.json",
            {"mode": "fixture", "segments": fixture_segments.model_dump(mode="json")},
        )
        segments_path = self.artifacts.save_segments(fixture_segments)
        self.states.record_artifact(request.video_id, "twelvelabs_segmentation_raw", raw_path)
        self.states.record_artifact(request.video_id, "twelvelabs_segments", segments_path)
        self.states.transition(request.video_id, "SEGMENTS_READY")

        self.states.transition(request.video_id, "INDEXING")
        index_id = self.settings.twelvelabs_index_id or "fixture_index"
        indexed_asset_id = f"fixture_indexed_asset_{request.video_id}"
        self.states.record_external_id(request.video_id, "index_id", index_id)
        self.states.record_external_id(request.video_id, "indexed_asset_id", indexed_asset_id)
        result = IngestionResult(
            video_id=request.video_id,
            asset_id=asset_id,
            index_id=index_id,
            indexed_asset_id=indexed_asset_id,
            segmentation_task_id=task_id,
            segments=fixture_segments,
        )
        result_path = self.artifacts.save_ingestion(result)
        self.states.record_artifact(request.video_id, "ingestion_result", result_path)
        self.states.transition(request.video_id, "INDEX_READY")
        return result

    def _ingest_live(self, request: IngestionRequest, source_path: Path | None) -> IngestionResult:
        self._require_live_settings()
        client = self._live_client()
        self.states.transition(request.video_id, "UPLOADING_ASSET")
        asset = self._create_asset(client, request, source_path)
        asset_id = self._required_value(asset, "id", "asset upload response")
        self.states.record_external_id(request.video_id, "asset_id", asset_id)
        asset_path = self.artifacts.save_json(request.video_id, "twelvelabs_asset.json", self._as_jsonable(asset))
        self.states.record_artifact(request.video_id, "twelvelabs_asset", asset_path)

        self.states.transition(request.video_id, "ASSET_PROCESSING")
        asset = self._poll(
            operation="asset processing",
            retrieve=lambda: client.assets.retrieve(asset_id),
        )
        duration_sec = self._as_duration(asset)
        if duration_sec > self.settings.app_max_video_minutes * 60:
            raise TwelveLabsResponseError(
                f"asset duration exceeds the configured {self.settings.app_max_video_minutes} minute limit"
            )
        self.states.transition(request.video_id, "ASSET_READY")
        return self._segment_asset(client, request, asset_id, duration_sec)

    def _resume_from_asset(self, request: IngestionRequest) -> IngestionResult:
        client = self._live_client()
        asset_id = self._resume_asset_id(request.video_id)
        asset = self._poll(
            operation="asset processing",
            retrieve=lambda: client.assets.retrieve(asset_id),
        )
        return self._segment_asset(client, request, asset_id, self._as_duration(asset))

    def _segment_asset(
        self,
        client: Any,
        request: IngestionRequest,
        asset_id: str,
        duration_sec: float,
    ) -> IngestionResult:
        self.states.transition(request.video_id, "SEGMENTING")
        task = self._create_segmentation_task(client, asset_id, request)
        task_id = self._required_value(task, "task_id", "segmentation task response")
        self.states.record_external_id(request.video_id, "segmentation_task_id", task_id)
        return self._complete_segmentation_task(client, request, asset_id, duration_sec, task_id)

    def _resume_from_segmentation(self, request: IngestionRequest) -> IngestionResult:
        client = self._live_client()
        asset_id = self._resume_asset_id(request.video_id)
        asset = self._poll(
            operation="asset processing",
            retrieve=lambda: client.assets.retrieve(asset_id),
        )
        return self._complete_segmentation_task(
            client,
            request,
            asset_id,
            self._as_duration(asset),
            self._resume_task_id(request.video_id),
        )

    def _complete_segmentation_task(
        self,
        client: Any,
        request: IngestionRequest,
        asset_id: str,
        duration_sec: float,
        task_id: str,
    ) -> IngestionResult:
        task = self._poll(
            operation="segmentation",
            retrieve=lambda: client.analyze_async.tasks.retrieve(task_id),
        )
        raw_task_path = self.artifacts.save_json(
            request.video_id,
            "twelvelabs_segmentation_raw.json",
            self._as_jsonable(task),
        )
        self.states.record_artifact(request.video_id, "twelvelabs_segmentation_raw", raw_task_path)
        segments = self._parse_segments(request.video_id, duration_sec, task)
        segments_path = self.artifacts.save_segments(segments)
        self.states.record_artifact(request.video_id, "twelvelabs_segments", segments_path)
        self.states.transition(request.video_id, "SEGMENTS_READY")
        return self._index_segments(client, request, asset_id, task_id, segments)

    def _index_segments(
        self,
        client: Any,
        request: IngestionRequest,
        asset_id: str,
        task_id: str,
        segments: SegmentCollection,
    ) -> IngestionResult:
        self.states.transition(request.video_id, "INDEXING")
        try:
            indexed_asset = self._retry(
                "create indexed asset",
                lambda: client.indexes.indexed_assets.create(
                    self.settings.twelvelabs_index_id,
                    asset_id=asset_id,
                    user_metadata={
                        "scenethread_video_id": request.video_id,
                        "title": request.title,
                        "domain_hint": request.domain_hint,
                        **(
                            {"store_id": request.store_id}
                            if request.store_id is not None
                            else {}
                        ),
                        **(
                            {"camera_id": request.camera_id}
                            if request.camera_id is not None
                            else {}
                        ),
                        **(
                            {"recorded_at": request.recorded_at.isoformat()}
                            if request.recorded_at is not None
                            else {}
                        ),
                    },
                ),
            )
            indexed_asset_id = self._required_value(indexed_asset, "id", "indexed asset response")
            indexed_asset = self._poll(
                operation="Marengo indexing",
                retrieve=lambda: client.indexes.indexed_assets.retrieve(
                    self.settings.twelvelabs_index_id,
                    indexed_asset_id,
                ),
            )
            self.states.record_external_id(request.video_id, "index_id", self.settings.twelvelabs_index_id)
            self.states.record_external_id(request.video_id, "indexed_asset_id", indexed_asset_id)
            indexed_path = self.artifacts.save_json(
                request.video_id,
                "twelvelabs_indexed_asset.json",
                self._as_jsonable(indexed_asset),
            )
            self.states.record_artifact(request.video_id, "twelvelabs_indexed_asset", indexed_path)
            result = IngestionResult(
                video_id=request.video_id,
                asset_id=asset_id,
                index_id=self.settings.twelvelabs_index_id,
                indexed_asset_id=indexed_asset_id,
                segmentation_task_id=task_id,
                segments=segments,
                search_available=True,
            )
        except Exception as exc:  # noqa: BLE001 - indexing is optional once validated segments exist.
            error_path = self.artifacts.save_json(
                request.video_id,
                "twelvelabs_index_error.json",
                {"error": str(exc)},
            )
            self.states.record_artifact(request.video_id, "twelvelabs_index_error", error_path)
            result = IngestionResult(
                video_id=request.video_id,
                asset_id=asset_id,
                segmentation_task_id=task_id,
                segments=segments,
                search_available=False,
            )
        result_path = self.artifacts.save_ingestion(result)
        self.states.record_artifact(request.video_id, "ingestion_result", result_path)
        self.states.transition(request.video_id, "INDEX_READY")
        return result

    def _create_asset(self, client: Any, request: IngestionRequest, source_path: Path | None) -> Any:
        metadata = json.dumps(
            {
                "scenethread_video_id": request.video_id,
                "title": request.title,
                "domain_hint": request.domain_hint,
                "store_id": request.store_id,
                "camera_id": request.camera_id,
                "recorded_at": (
                    request.recorded_at.isoformat()
                    if request.recorded_at is not None
                    else None
                ),
            }
        )
        if request.source_type == "url":
            return self._retry(
                "asset upload",
                lambda: client.assets.create(
                    method="url",
                    url=request.source_ref,
                    user_metadata=metadata,
                ),
            )
        if source_path is None:
            raise TwelveLabsResponseError("upload request did not resolve to a local source path")

        def upload() -> Any:
            with source_path.open("rb") as source_file:
                return client.assets.create(
                    method="direct",
                    file=source_file,
                    filename=source_path.name,
                    user_metadata=metadata,
                )

        return self._retry("asset upload", upload)

    def _create_segmentation_task(self, client: Any, asset_id: str, request: IngestionRequest) -> Any:
        video, response_format = self._segmentation_inputs(asset_id, request.domain_hint)
        return self._retry(
            "create segmentation task",
            lambda: client.analyze_async.tasks.create(
                model_name="pegasus1.5",
                video=video,
                custom_id=f"scenethread_{request.video_id}"[:64],
                analysis_mode="time_based_metadata",
                response_format=response_format,
                min_segment_duration=2,
                max_segment_duration=120,
            ),
        )

    def _segmentation_inputs(self, asset_id: str, domain_hint: str) -> tuple[Any, Any]:
        fields: list[dict[str, Any]] = [
            {"name": "summary", "type": "string", "description": "Concise, evidence-based scene summary."},
            {"name": "location", "type": "string", "description": "Visible or strongly supported setting."},
            {"name": "participants", "type": "array", "items": {"type": "string"}, "description": "People, teams, speakers, or characters."},
            {"name": "objects", "type": "array", "items": {"type": "string"}, "description": "Important visible objects, products, tools, or props."},
            {"name": "actions", "type": "array", "items": {"type": "string"}, "description": "Major supported actions or events."},
            {"name": "speech_summary", "type": "string", "description": "Meaning of supported spoken content."},
            {"name": "on_screen_text", "type": "array", "items": {"type": "string"}, "description": "Visible signs, slides, labels, captions, or text."},
            {"name": "topics", "type": "array", "items": {"type": "string"}, "description": "Topics or concepts present in the scene."},
            {"name": "tags", "type": "array", "items": {"type": "string"}, "description": "General searchable labels."},
            {"name": "sentiment", "type": "string", "enum": ["positive", "negative", "neutral", "mixed", "unknown"], "description": "Overall scene sentiment, or unknown."},
        ]
        domain_context = ""
        if domain_hint.strip().lower() != "auto":
            domain_context = (
                f" Use the optional domain context '{domain_hint}' only to prioritize relevant "
                "details; do not infer facts that are not supported by the video."
            )
        response_format_payload: dict[str, Any] = {
            "type": "segment_definitions",
            "segment_time_format": "seconds",
            "segment_definitions": [
                {
                    "id": "scenes",
                    "description": (
                        "Segment the video at meaningful changes in location, participants, activity, "
                        "topic, or visual composition. Extract only information supported by the video."
                        f"{domain_context}"
                    ),
                    "fields": fields,
                }
            ],
        }
        try:
            from twelvelabs.types import (  # type: ignore[import-not-found]
                AsyncResponseFormat,
                SegmentDefinition,
                SegmentField,
                SegmentFieldItems,
                VideoContext_AssetId,
            )
        except ImportError:
            return {"asset_id": asset_id}, response_format_payload

        typed_fields = [
            SegmentField(
                name=field["name"],
                type=field["type"],
                description=field["description"],
                items=SegmentFieldItems(**field["items"]) if "items" in field else None,
                enum=field.get("enum"),
            )
            for field in fields
        ]
        return (
            VideoContext_AssetId(asset_id=asset_id),
            AsyncResponseFormat(
                type="segment_definitions",
                segment_time_format="seconds",
                segment_definitions=[
                    SegmentDefinition(
                        id="scenes",
                        description=response_format_payload["segment_definitions"][0]["description"],
                        fields=typed_fields,
                    )
                ],
            ),
        )

    def _parse_segments(self, video_id: str, duration_sec: float, task: Any) -> SegmentCollection:
        result = self._value(task, "result")
        data = self._value(result, "data")
        if isinstance(data, str):
            try:
                payload = json.loads(data)
            except json.JSONDecodeError as exc:
                raise TwelveLabsResponseError("segmentation result is not valid JSON") from exc
        elif isinstance(data, dict):
            payload = data
        else:
            raise TwelveLabsResponseError("segmentation result did not contain segment data")

        raw_segments = payload.get("scenes")
        if not isinstance(raw_segments, list) or not raw_segments:
            raise TwelveLabsResponseError("segmentation result did not contain any scenes")
        task_id = self._required_value(task, "task_id", "segmentation result")
        segments: list[VideoSegment] = []
        for ordinal, raw_segment in enumerate(raw_segments, start=1):
            if not isinstance(raw_segment, dict):
                raise TwelveLabsResponseError("segmentation scene was not an object")
            metadata = raw_segment.get("metadata")
            if not isinstance(metadata, dict):
                raise TwelveLabsResponseError("segmentation scene did not contain metadata")
            summary = metadata.get("summary")
            if not isinstance(summary, str) or not summary.strip():
                raise TwelveLabsResponseError("segmentation scene did not contain a summary")
            segments.append(
                VideoSegment(
                    segment_id=f"{task_id}:scene:{ordinal:03d}",
                    start_sec=self._as_float(raw_segment.get("start_time"), "scene start_time"),
                    end_sec=self._as_float(raw_segment.get("end_time"), "scene end_time"),
                    summary=summary.strip(),
                    location=self._as_optional_text(metadata.get("location")),
                    participants=self._as_text_list(metadata.get("participants")),
                    objects=self._as_text_list(metadata.get("objects")),
                    actions=self._as_text_list(metadata.get("actions")),
                    speech_summary=self._as_optional_text(metadata.get("speech_summary")),
                    on_screen_text=self._as_text_list(metadata.get("on_screen_text")),
                    topics=self._as_text_list(metadata.get("topics")),
                    tags=self._as_text_list(metadata.get("tags")),
                    sentiment=self._as_optional_text(metadata.get("sentiment")) or "unknown",
                )
            )
        segments.sort(key=lambda segment: segment.start_sec)
        return SegmentCollection(video_id=video_id, duration_sec=duration_sec, segments=segments)

    def _parse_search_results(
        self,
        request: SearchRequest,
        response: Any,
    ) -> list[SearchMoment]:
        items = self._value(response, "items")
        if items is None and isinstance(response, list):
            items = response
        if not isinstance(items, list):
            return []
        moments: list[SearchMoment] = []
        for position, item in enumerate(items[: request.top_k], start=1):
            start = self._value(item, "start")
            end = self._value(item, "end")
            if start is None or end is None:
                continue
            try:
                start_sec = self._as_float(start, "search start")
                end_sec = self._as_float(end, "search end")
            except TwelveLabsResponseError:
                continue
            if end_sec <= start_sec:
                continue
            rank = self._value(item, "rank") or position
            try:
                score = 1 / max(int(rank), 1)
            except (TypeError, ValueError):
                score = 1 / position
            transcript = self._as_optional_text(self._value(item, "transcription"))
            moments.append(
                SearchMoment(
                    # Raw TwelveLabs moments are not Neo4j graph-scene identifiers.
                    scene_id=None,
                    start_sec=start_sec,
                    end_sec=end_sec,
                    score=score,
                    summary=transcript or "Matching video moment returned by TwelveLabs.",
                )
            )
        return moments

    def _load_cached_result(self, video_id: str, fingerprint: str) -> IngestionResult | None:
        job = self.states.load(video_id)
        if (
            job is None
            or job.request_fingerprint != fingerprint
            or job.current_stage not in {"INDEX_READY", "READY"}
        ):
            return None
        cached = self.artifacts.load_ingestion(video_id)
        if cached is not None:
            return cached
        segments = self.artifacts.load_segments(video_id)
        if segments is None:
            return None
        needed_ids = ("asset_id", "segmentation_task_id")
        if any(key not in job.external_ids for key in needed_ids):
            return None
        index_id = job.external_ids.get("index_id")
        indexed_asset_id = job.external_ids.get("indexed_asset_id")
        result = IngestionResult(
            video_id=video_id,
            asset_id=job.external_ids["asset_id"],
            index_id=index_id,
            indexed_asset_id=indexed_asset_id,
            segmentation_task_id=job.external_ids["segmentation_task_id"],
            segments=segments,
            search_available=bool(index_id and indexed_asset_id),
        )
        self.artifacts.save_ingestion(result)
        return result

    def _load_cached_result_for_search(self, video_id: str) -> IngestionResult | None:
        job = self.states.load(video_id)
        if job is None or job.current_stage not in {"INDEX_READY", "READY"}:
            return None
        cached = self.artifacts.load_ingestion(video_id)
        if cached is not None:
            return cached
        return self._load_cached_result(video_id, job.request_fingerprint)

    def _resume_stage(self, job: Any, video_id: str, fingerprint: str) -> str | None:
        if job is None or job.request_fingerprint != fingerprint:
            return None
        if self.artifacts.load_segments(video_id) is not None and {
            "asset_id",
            "segmentation_task_id",
        }.issubset(job.external_ids):
            return "SEGMENTS_READY"
        if "asset_id" in job.external_ids and "segmentation_task_id" in job.external_ids:
            return "SEGMENTING"
        if "asset_id" in job.external_ids:
            return "ASSET_READY"
        return None

    def _resume_asset_id(self, video_id: str) -> str:
        job = self.states.load(video_id)
        if job is None or "asset_id" not in job.external_ids:
            raise TwelveLabsResponseError("persisted asset ID was unavailable for resume")
        return job.external_ids["asset_id"]

    def _resume_task_id(self, video_id: str) -> str:
        job = self.states.load(video_id)
        if job is None or "segmentation_task_id" not in job.external_ids:
            raise TwelveLabsResponseError("persisted segmentation task ID was unavailable for resume")
        return job.external_ids["segmentation_task_id"]

    def _live_client(self) -> Any:
        if self._sdk_client is not None:
            return self._sdk_client
        self._require_live_settings()
        try:
            from twelvelabs import TwelveLabs  # type: ignore[import-not-found]
        except ImportError as exc:
            raise TwelveLabsConfigurationError(
                "The twelvelabs package is not installed. Install project dependencies first."
            ) from exc
        self._sdk_client = TwelveLabs(api_key=self.settings.twelvelabs_api_key)
        return self._sdk_client

    def _require_live_settings(self) -> None:
        if not self.settings.twelvelabs_api_key:
            raise TwelveLabsConfigurationError("TWELVELABS_API_KEY is required for live ingestion")
        if not self.settings.twelvelabs_index_id:
            raise TwelveLabsConfigurationError("TWELVELABS_INDEX_ID is required for live ingestion")

    def _poll(self, *, operation: str, retrieve: Callable[[], Any]) -> Any:
        for attempt in range(1, self.max_poll_attempts + 1):
            response = self._retry(f"{operation} status", retrieve)
            status = self._as_optional_text(self._value(response, "status"))
            if status == _POLL_READY:
                return response
            if status == _POLL_FAILED:
                error = self._value(response, "error")
                detail = self._as_optional_text(self._value(error, "message")) or "no error detail"
                raise TwelveLabsRemoteError(f"{operation} failed: {detail}")
            if attempt < self.max_poll_attempts:
                self._sleep(min(self.poll_interval_seconds * (2 ** (attempt - 1)), 30.0))
        raise TwelveLabsPollingTimeout(
            f"{operation} did not reach ready after {self.max_poll_attempts} polling attempts"
        )

    def _retry(self, operation: str, action: Callable[[], Any]) -> Any:
        for attempt in range(1, self.request_attempts + 1):
            try:
                return action()
            except Exception as exc:
                if not self._is_retryable_error(exc) or attempt == self.request_attempts:
                    raise
                self._sleep(min(self.poll_interval_seconds * (2 ** (attempt - 1)), 10.0))
        raise AssertionError(f"retry loop exited unexpectedly for {operation}")

    @staticmethod
    def _is_retryable_error(exc: Exception) -> bool:
        status_code = getattr(exc, "status_code", None)
        if isinstance(status_code, int):
            return status_code == 429 or status_code >= 500
        return isinstance(exc, (TimeoutError, ConnectionError, OSError))

    @staticmethod
    def _value(payload: Any, key: str) -> Any:
        if payload is None:
            return None
        if isinstance(payload, dict):
            if key in payload:
                return payload[key]
            return payload.get(f"_{key}")
        return getattr(payload, key, None)

    def _required_value(self, payload: Any, key: str, context: str) -> str:
        value = self._value(payload, key)
        if not isinstance(value, str) or not value:
            raise TwelveLabsResponseError(f"{context} did not contain {key}")
        return value

    @staticmethod
    def _as_float(value: Any, context: str) -> float:
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise TwelveLabsResponseError(f"{context} was not a number") from exc

    def _as_duration(self, asset: Any) -> float:
        duration = self._as_float(self._value(asset, "duration"), "asset duration")
        if duration <= 0:
            raise TwelveLabsResponseError("asset duration must be positive")
        return duration

    @staticmethod
    def _as_optional_text(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        stripped = value.strip()
        return stripped or None

    @classmethod
    def _as_text_list(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [text for item in value if (text := cls._as_optional_text(item)) is not None]

    @classmethod
    def _as_jsonable(cls, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, dict):
            return {str(key): cls._as_jsonable(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._as_jsonable(item) for item in value]
        if hasattr(value, "model_dump"):
            return cls._as_jsonable(value.model_dump(mode="json"))
        if hasattr(value, "__dict__"):
            return cls._as_jsonable(vars(value))
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)
