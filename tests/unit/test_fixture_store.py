from video_context_graph.fixture_store import load_fixture_bundle


def test_fixture_bundle_validates_all_shared_boundaries() -> None:
    bundle = load_fixture_bundle()
    ingestion = bundle.ingestion_result()

    assert bundle.segments.video_id == "fixture_video_001"
    assert len(bundle.extraction.scenes) == 2
    assert bundle.search.results[0].scene_id is None
    assert ingestion.video_id == bundle.segments.video_id
    assert ingestion.asset_id.startswith("fixture_asset_")
