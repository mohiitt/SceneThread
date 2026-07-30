"""Local, atomic persistence for replayable ingestion artifacts."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from video_context_graph.contracts.video import IngestionResult, SegmentCollection
from video_context_graph.pipeline.validators import validate_video_id


class ArtifactStore:
    """Owns cached source files and JSON artifacts for a single application data directory."""

    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir).expanduser().resolve()

    def video_dir(self, video_id: str) -> Path:
        return self._contained_path("videos", video_id)

    def run_dir(self, video_id: str) -> Path:
        return self._contained_path("runs", video_id)

    def source_path(self, video_id: str, suffix: str) -> Path:
        return self.video_dir(video_id) / f"source{suffix.lower()}"

    def artifact_path(self, video_id: str, name: str) -> Path:
        path = self.run_dir(video_id) / name
        if Path(name).name != name or not name.endswith(".json"):
            raise ValueError("artifact name must be a JSON filename without path components")
        return self._assert_contained(path)

    def persist_source(self, video_id: str, source_path: str | Path) -> Path:
        source = Path(source_path)
        target = self.source_path(video_id, source.suffix)
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        return target

    def save_json(self, video_id: str, name: str, payload: Any) -> Path:
        path = self.artifact_path(video_id, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(payload, indent=2, sort_keys=True, default=_json_default)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(serialized + "\n", encoding="utf-8")
        temporary.replace(path)
        return path

    def load_json(self, video_id: str, name: str) -> dict[str, Any] | list[Any] | None:
        path = self.artifact_path(video_id, name)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def save_segments(self, segments: SegmentCollection) -> Path:
        return self.save_json(
            segments.video_id,
            "twelvelabs_segments.json",
            segments.model_dump(mode="json"),
        )

    def load_segments(self, video_id: str) -> SegmentCollection | None:
        payload = self.load_json(video_id, "twelvelabs_segments.json")
        if payload is None:
            return None
        return SegmentCollection.model_validate(payload)

    def save_ingestion(self, result: IngestionResult) -> Path:
        return self.save_json(
            result.video_id,
            "ingestion_result.json",
            result.model_dump(mode="json"),
        )

    def load_ingestion(self, video_id: str) -> IngestionResult | None:
        payload = self.load_json(video_id, "ingestion_result.json")
        if payload is None:
            return None
        return IngestionResult.model_validate(payload)

    def invalidate_ingestion(self, video_id: str) -> None:
        path = self.artifact_path(video_id, "ingestion_result.json")
        if path.exists():
            path.unlink()

    def _contained_path(self, category: str, video_id: str) -> Path:
        validate_video_id(video_id)
        return self._assert_contained(self.data_dir / category / video_id)

    def _assert_contained(self, path: Path) -> Path:
        resolved = path.resolve()
        try:
            resolved.relative_to(self.data_dir)
        except ValueError as exc:
            raise ValueError("artifact path escapes the configured data directory") from exc
        return resolved


def _json_default(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    raise TypeError(f"cannot serialize {type(value).__name__} to JSON")
