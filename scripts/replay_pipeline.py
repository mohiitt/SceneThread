"""Validate the explicit fixture-mode inputs before parallel implementation."""

from __future__ import annotations

from video_context_graph.fixture_store import load_fixture_bundle


def main() -> None:
    bundle = load_fixture_bundle()
    ingestion = bundle.ingestion_result()

    print("SceneThread fixture mode: validated")
    print(f"Video: {bundle.segments.video_id}")
    print(f"Segments: {len(bundle.segments.segments)}")
    print(f"Entities: {len(bundle.extraction.entities)}")
    print(f"Events: {len(bundle.extraction.events)}")
    print(f"Search moments: {len(bundle.search.results)}")
    print(f"Fixture asset: {ingestion.asset_id}")
    print("Live sponsor calls and downstream graph/QA execution are not run by this check.")


if __name__ == "__main__":
    main()
