from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from video_context_graph.contracts import GraphExtraction


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def load_graph_fixture() -> dict:
    return json.loads((FIXTURE_DIR / "graph_extraction.json").read_text())


def test_graph_extraction_fixture_validates() -> None:
    graph = GraphExtraction.model_validate(load_graph_fixture())

    assert graph.video_summary.startswith("A short planning meeting")
    assert [scene.ordinal for scene in graph.scenes] == [1, 2]


def test_graph_extraction_rejects_unknown_scene_reference() -> None:
    payload = load_graph_fixture()
    payload["events"][0]["scene_id"] = "missing_scene"

    with pytest.raises(ValidationError, match="unknown scene"):
        GraphExtraction.model_validate(payload)


def test_graph_extraction_rejects_unknown_entity_reference() -> None:
    payload = load_graph_fixture()
    payload["scenes"][0]["entity_ids"].append("missing_entity")

    with pytest.raises(ValidationError, match="unknown entities"):
        GraphExtraction.model_validate(payload)


def test_graph_extraction_rejects_unsorted_scene_ordinals() -> None:
    payload = load_graph_fixture()
    payload["scenes"][0]["ordinal"] = 2
    payload["scenes"][1]["ordinal"] = 1

    with pytest.raises(ValidationError, match="ordinals must be sorted"):
        GraphExtraction.model_validate(payload)
