"""Credential-gated verification of the live TwelveLabs ingestion boundary."""

from __future__ import annotations

import os
from hashlib import sha256
from pathlib import Path

import pytest

from video_context_graph.config import Settings
from video_context_graph.contracts.video import IngestionRequest, SearchRequest
from video_context_graph.integrations.twelvelabs_client import TwelveLabsClient


def test_live_ingestion_and_search(tmp_path: Path) -> None:
    """Run only with a small, licensed direct-media URL and an expected search query."""
    video_url = os.getenv("TWELVELABS_LIVE_TEST_URL")
    search_query = os.getenv("TWELVELABS_LIVE_TEST_QUERY")
    if not video_url or not search_query:
        pytest.skip("set TWELVELABS_LIVE_TEST_URL and TWELVELABS_LIVE_TEST_QUERY to run live")

    settings = Settings(app_data_dir=str(tmp_path), app_use_fixtures=False)
    if not settings.twelvelabs_api_key or not settings.twelvelabs_index_id:
        pytest.skip("TwelveLabs credentials and index ID are required for live verification")

    video_id = f"live_{sha256(video_url.encode('utf-8')).hexdigest()[:16]}"
    client = TwelveLabsClient(
        settings=settings,
        max_poll_attempts=180,
        poll_interval_seconds=2,
    )
    result = client.ingest_video(
        IngestionRequest(
            video_id=video_id,
            title="TwelveLabs live integration fixture",
            source_type="url",
            source_ref=video_url,
            domain_hint="Auto",
            force_reprocess=True,
        )
    )

    assert result.segments.segments
    assert all(segment.start_sec < segment.end_sec for segment in result.segments.segments)
    assert (tmp_path / "runs" / video_id / "twelvelabs_segmentation_raw.json").exists()
    assert result.search_available
    assert result.indexed_asset_id

    search = client.search_video_moments(SearchRequest(video_id=video_id, query=search_query))
    assert search.results
    assert all(moment.scene_id is None for moment in search.results)
