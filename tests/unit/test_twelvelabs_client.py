from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from video_context_graph.config import Settings
from video_context_graph.contracts.video import IngestionRequest, SearchRequest
from video_context_graph.integrations.twelvelabs_client import (
    TwelveLabsClient,
    TwelveLabsRemoteError,
)
from video_context_graph.pipeline.artifact_store import ArtifactStore
from video_context_graph.pipeline.state_store import PipelineStateStore


class FakeAssets:
    def __init__(self, *, failed: bool = False, transient_upload_failures: int = 0) -> None:
        self.failed = failed
        self.transient_upload_failures = transient_upload_failures
        self.create_calls = 0
        self.retrieve_calls = 0
        self.create_requests: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.create_calls += 1
        self.create_requests.append(kwargs)
        if self.transient_upload_failures:
            self.transient_upload_failures -= 1
            raise ConnectionError("temporary provider error")
        return SimpleNamespace(id="asset_123", status="processing")

    def retrieve(self, _: str) -> SimpleNamespace:
        self.retrieve_calls += 1
        if self.failed:
            return SimpleNamespace(
                id="asset_123",
                status="failed",
                error=SimpleNamespace(message="unsupported media"),
            )
        return SimpleNamespace(id="asset_123", status="ready", duration=18.5)


class FakeAnalyzeTasks:
    def __init__(self) -> None:
        self.create_calls = 0
        self.retrieve_calls = 0
        self.create_requests: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.create_calls += 1
        self.create_requests.append(kwargs)
        return SimpleNamespace(task_id="segment_task_123", status="queued")

    def retrieve(self, _: str) -> SimpleNamespace:
        self.retrieve_calls += 1
        return SimpleNamespace(
            task_id="segment_task_123",
            status="ready",
            result=SimpleNamespace(
                data=json.dumps(
                    {
                        "scenes": [
                            {
                                "start_time": 0,
                                "end_time": 9.5,
                                "metadata": {
                                    "summary": "A presenter introduces the launch plan.",
                                    "participants": ["presenter"],
                                    "topics": ["launch"],
                                },
                            },
                            {
                                "start_time": 9.5,
                                "end_time": 18.5,
                                "metadata": {
                                    "summary": "The team assigns a follow-up task.",
                                    "actions": ["assigns follow-up"],
                                },
                            },
                        ]
                    }
                )
            ),
        )


class FakeIndexedAssets:
    def __init__(self, *, fail_status: int | None = None) -> None:
        self.fail_status = fail_status
        self.create_calls = 0
        self.retrieve_calls = 0
        self.create_requests: list[dict[str, object]] = []

    def create(self, _: str, **kwargs: object) -> SimpleNamespace:
        self.create_calls += 1
        self.create_requests.append(kwargs)
        if self.fail_status is not None:
            raise StatusError(self.fail_status)
        return SimpleNamespace(id="indexed_asset_123", status="queued")

    def retrieve(self, _: str, __: str) -> SimpleNamespace:
        self.retrieve_calls += 1
        return SimpleNamespace(id="indexed_asset_123", status="ready")


class FakeSearch:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []

    def query(self, **kwargs: object) -> SimpleNamespace:
        self.requests.append(kwargs)
        return SimpleNamespace(
            items=[
                SimpleNamespace(
                    start=0.0,
                    end=9.5,
                    rank=1,
                    transcription="The presenter discusses the launch plan.",
                )
            ]
        )


class FakeSDK:
    def __init__(
        self,
        *,
        asset_failed: bool = False,
        transient_upload_failures: int = 0,
        indexing_failure_status: int | None = None,
    ) -> None:
        self.assets = FakeAssets(
            failed=asset_failed,
            transient_upload_failures=transient_upload_failures,
        )
        self.analyze_async = SimpleNamespace(tasks=FakeAnalyzeTasks())
        self.indexes = SimpleNamespace(
            indexed_assets=FakeIndexedAssets(fail_status=indexing_failure_status)
        )
        self.search = FakeSearch()


def _settings(tmp_path: Path, *, fixtures: bool = False) -> Settings:
    return Settings(
        app_data_dir=str(tmp_path),
        app_use_fixtures=fixtures,
        twelvelabs_api_key="test-key",
        twelvelabs_index_id="index_123",
        app_max_video_minutes=15,
    )


def _upload_request(
    source_path: Path,
    *,
    force_reprocess: bool = False,
    domain_hint: str = "Auto",
) -> IngestionRequest:
    return IngestionRequest(
        video_id="video_001",
        title="Launch meeting",
        source_type="upload",
        source_ref=str(source_path),
        domain_hint=domain_hint,
        force_reprocess=force_reprocess,
    )


class StatusError(RuntimeError):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"status {status_code}")
        self.status_code = status_code


def test_fixture_ingestion_persists_cache_and_reuses_it(tmp_path: Path) -> None:
    client = TwelveLabsClient(settings=_settings(tmp_path, fixtures=True), sleep=lambda _: None)
    request = IngestionRequest(
        video_id="fixture_request_001",
        title="Fixture video",
        source_type="url",
        source_ref="https://example.com/video.mp4",
    )

    first = client.ingest_video(request)
    second = client.ingest_video(request)

    assert second == first
    assert first.video_id == "fixture_request_001"
    assert (tmp_path / "runs" / request.video_id / "ingestion_result.json").exists()
    assert PipelineStateStore(tmp_path).load(request.video_id).current_stage == "INDEX_READY"  # type: ignore[union-attr]


def test_live_ingestion_uploads_segments_indexes_and_caches(tmp_path: Path) -> None:
    source = tmp_path / "meeting.mp4"
    source.write_bytes(b"fake-video")
    sdk = FakeSDK()
    client = TwelveLabsClient(settings=_settings(tmp_path), sdk_client=sdk, sleep=lambda _: None)

    result = client.ingest_video(_upload_request(source))
    cached = client.ingest_video(_upload_request(source))

    assert result == cached
    assert result.asset_id == "asset_123"
    assert result.indexed_asset_id == "indexed_asset_123"
    assert [segment.start_sec for segment in result.segments.segments] == [0, 9.5]
    assert sdk.assets.create_calls == 1
    assert sdk.analyze_async.tasks.create_calls == 1
    assert sdk.indexes.indexed_assets.create_calls == 1
    assert sdk.indexes.indexed_assets.create_requests[0]["user_metadata"] == {
        "scenethread_video_id": "video_001",
        "title": "Launch meeting",
        "domain_hint": "Auto",
    }
    response_format = sdk.analyze_async.tasks.create_requests[0]["response_format"]
    description = response_format.segment_definitions[0].description
    assert "domain context" not in description
    assert (tmp_path / "videos" / "video_001" / "source.mp4").read_bytes() == b"fake-video"
    assert (tmp_path / "runs" / "video_001" / "twelvelabs_segmentation_raw.json").exists()


def test_domain_hint_is_passed_as_safe_segmentation_context(tmp_path: Path) -> None:
    source = tmp_path / "cooking.mp4"
    source.write_bytes(b"fake-video")
    sdk = FakeSDK()
    client = TwelveLabsClient(settings=_settings(tmp_path), sdk_client=sdk, sleep=lambda _: None)

    client.ingest_video(_upload_request(source, domain_hint="Cooking"))

    response_format = sdk.analyze_async.tasks.create_requests[0]["response_format"]
    description = response_format.segment_definitions[0].description
    assert "optional domain context 'Cooking'" in description
    assert "do not infer facts" in description


def test_live_ingestion_marks_job_failed_when_asset_fails(tmp_path: Path) -> None:
    source = tmp_path / "broken.mp4"
    source.write_bytes(b"broken")
    client = TwelveLabsClient(
        settings=_settings(tmp_path),
        sdk_client=FakeSDK(asset_failed=True),
        sleep=lambda _: None,
    )

    with pytest.raises(TwelveLabsRemoteError, match="unsupported media"):
        client.ingest_video(_upload_request(source))

    job = PipelineStateStore(tmp_path).load("video_001")
    assert job is not None
    assert job.status == "failed"
    assert job.current_stage == "FAILED"


def test_live_ingestion_retries_a_transient_upload_failure(tmp_path: Path) -> None:
    source = tmp_path / "meeting.mp4"
    source.write_bytes(b"fake-video")
    sdk = FakeSDK(transient_upload_failures=1)
    client = TwelveLabsClient(settings=_settings(tmp_path), sdk_client=sdk, sleep=lambda _: None)

    result = client.ingest_video(_upload_request(source))

    assert result.asset_id == "asset_123"
    assert sdk.assets.create_calls == 2


@pytest.mark.parametrize("status_code", [400, 401])
def test_retry_does_not_repeat_non_retryable_provider_errors(
    tmp_path: Path,
    status_code: int,
) -> None:
    client = TwelveLabsClient(settings=_settings(tmp_path), sleep=lambda _: None)
    attempts = 0

    def fail() -> None:
        nonlocal attempts
        attempts += 1
        raise StatusError(status_code)

    with pytest.raises(StatusError):
        client._retry("test", fail)

    assert attempts == 1


@pytest.mark.parametrize("status_code", [429, 500])
def test_retry_repeats_transient_provider_errors(tmp_path: Path, status_code: int) -> None:
    client = TwelveLabsClient(settings=_settings(tmp_path), sleep=lambda _: None)
    attempts = 0

    def succeed_after_retry() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise StatusError(status_code)
        return "ok"

    assert client._retry("test", succeed_after_retry) == "ok"
    assert attempts == 2


def test_indexing_failure_preserves_segments_for_graph_processing(tmp_path: Path) -> None:
    source = tmp_path / "meeting.mp4"
    source.write_bytes(b"fake-video")
    sdk = FakeSDK(indexing_failure_status=500)
    client = TwelveLabsClient(settings=_settings(tmp_path), sdk_client=sdk, sleep=lambda _: None)

    result = client.ingest_video(_upload_request(source))

    assert result.search_available is False
    assert result.index_id is None
    assert result.indexed_asset_id is None
    assert len(result.segments.segments) == 2
    job = PipelineStateStore(tmp_path).load("video_001")
    assert job is not None
    assert job.current_stage == "INDEX_READY"
    assert "indexed_asset_id" not in job.external_ids
    assert (tmp_path / "runs" / "video_001" / "twelvelabs_index_error.json").exists()
    ArtifactStore(tmp_path).invalidate_ingestion("video_001")
    recovered = client._load_cached_result("video_001", job.request_fingerprint)
    assert recovered is not None
    assert recovered.search_available is False


def test_changed_source_or_pipeline_version_invalidates_completed_cache(tmp_path: Path) -> None:
    source = tmp_path / "meeting.mp4"
    source.write_bytes(b"first-video")
    sdk = FakeSDK()
    client = TwelveLabsClient(settings=_settings(tmp_path), sdk_client=sdk, sleep=lambda _: None)
    client.ingest_video(_upload_request(source))

    source.write_bytes(b"changed-video")
    client.ingest_video(_upload_request(source))

    assert sdk.assets.create_calls == 2
    versioned_settings = _settings(tmp_path).model_copy(update={"pipeline_version": "v2"})
    TwelveLabsClient(settings=versioned_settings, sdk_client=sdk, sleep=lambda _: None).ingest_video(
        _upload_request(source)
    )
    assert sdk.assets.create_calls == 3


def test_failed_force_reprocess_does_not_restore_stale_cached_result(tmp_path: Path) -> None:
    source = tmp_path / "meeting.mp4"
    source.write_bytes(b"fake-video")
    sdk = FakeSDK()
    client = TwelveLabsClient(settings=_settings(tmp_path), sdk_client=sdk, sleep=lambda _: None)
    first = client.ingest_video(_upload_request(source))

    sdk.assets.failed = True
    with pytest.raises(TwelveLabsRemoteError):
        client.ingest_video(_upload_request(source, force_reprocess=True))
    assert ArtifactStore(tmp_path).load_ingestion("video_001") is None

    sdk.assets.failed = False
    recovered = client.ingest_video(_upload_request(source))
    assert recovered == first
    assert sdk.analyze_async.tasks.create_calls == 2


def test_failed_run_resumes_from_persisted_segments_without_reuploading(tmp_path: Path) -> None:
    source = tmp_path / "meeting.mp4"
    source.write_bytes(b"fake-video")
    sdk = FakeSDK()
    client = TwelveLabsClient(settings=_settings(tmp_path), sdk_client=sdk, sleep=lambda _: None)
    client.ingest_video(_upload_request(source))
    ArtifactStore(tmp_path).invalidate_ingestion("video_001")
    PipelineStateStore(tmp_path).fail("video_001", "coordinator interrupted after segmentation")

    client.ingest_video(_upload_request(source))

    assert sdk.assets.create_calls == 1
    assert sdk.analyze_async.tasks.create_calls == 1
    assert sdk.indexes.indexed_assets.create_calls == 2


def test_live_search_filters_to_local_video_and_maps_scene(tmp_path: Path) -> None:
    source = tmp_path / "meeting.mp4"
    source.write_bytes(b"fake-video")
    sdk = FakeSDK()
    client = TwelveLabsClient(settings=_settings(tmp_path), sdk_client=sdk, sleep=lambda _: None)
    client.ingest_video(_upload_request(source))

    results = client.search_video_moments(
        SearchRequest(video_id="video_001", query="What is the launch plan?", top_k=3)
    )

    assert results.results[0].scene_id is None
    assert results.results[0].score == 1
    assert sdk.search.requests[0]["filter"] == '{"scenethread_video_id": "video_001"}'
