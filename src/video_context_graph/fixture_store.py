"""Explicit fixture bundle loading for offline development."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ValidationError, model_validator

from video_context_graph.contracts import (
    GraphExtraction,
    IngestionResult,
    SearchResults,
    SegmentCollection,
)

DEFAULT_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures"


class FixtureLoadError(RuntimeError):
    """Raised when fixture mode cannot load or validate its declared inputs."""


class FixtureBundle(BaseModel):
    segments: SegmentCollection
    extraction: GraphExtraction
    search: SearchResults

    @model_validator(mode="after")
    def validate_cross_fixture_references(self) -> FixtureBundle:
        if any(scene.end_sec > self.segments.duration_sec for scene in self.extraction.scenes):
            raise ValueError("graph extraction scenes must be within fixture video duration")

        graph_scene_ids = {scene.local_id for scene in self.extraction.scenes}
        unknown_search_scenes = {
            moment.scene_id
            for moment in self.search.results
            if moment.scene_id is not None and moment.scene_id not in graph_scene_ids
        }
        if unknown_search_scenes:
            raise ValueError(
                f"search results reference unknown graph scenes: {unknown_search_scenes}"
            )
        return self

    def ingestion_result(self, index_id: str = "fixture_index") -> IngestionResult:
        return IngestionResult(
            video_id=self.segments.video_id,
            asset_id=f"fixture_asset_{self.segments.video_id}",
            index_id=index_id,
            indexed_asset_id=f"fixture_indexed_asset_{self.segments.video_id}",
            segmentation_task_id=f"fixture_segmentation_{self.segments.video_id}",
            segments=self.segments,
            search_available=True,
        )


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FixtureLoadError(f"fixture file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise FixtureLoadError(f"fixture file is not valid JSON: {path}") from exc


def load_fixture_bundle(fixture_dir: Path | None = None) -> FixtureBundle:
    directory = fixture_dir or DEFAULT_FIXTURE_DIR
    try:
        return FixtureBundle(
            segments=SegmentCollection.model_validate(
                _load_json(directory / "twelvelabs_segments.json")
            ),
            extraction=GraphExtraction.model_validate(
                _load_json(directory / "graph_extraction.json")
            ),
            search=SearchResults.model_validate(_load_json(directory / "search_results.json")),
        )
    except ValidationError as exc:
        raise FixtureLoadError(f"fixture contract validation failed: {exc}") from exc
