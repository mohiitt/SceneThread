from video_context_graph.pipeline.video_identity import generate_video_id


def test_generate_video_id_is_stable_for_same_bytes_and_version() -> None:
    first = generate_video_id(b"video bytes", pipeline_version="v1")
    second = generate_video_id(b"video bytes", pipeline_version="v1")

    assert first == second
    assert len(first) == 16


def test_generate_video_id_changes_with_pipeline_version() -> None:
    assert generate_video_id(b"video bytes", "v1") != generate_video_id(b"video bytes", "v2")
