from typing import Any

import pytest

from video_context_graph.contracts.video import VideoGraphMetadata
from video_context_graph.fixture_store import load_fixture_bundle
from video_context_graph.graph.writer import GraphWriter


class FakeResult:
    def consume(self) -> None:
        return None


class FakeTransaction:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def run(self, query: str, **parameters: Any) -> FakeResult:
        self.calls.append((query, parameters))
        return FakeResult()


class FakeClient:
    def __init__(self) -> None:
        self.transaction = FakeTransaction()
        self.transaction_count = 0

    def execute_transaction(self, operation: Any) -> Any:
        self.transaction_count += 1
        return operation(self.transaction)


class FailingClient(FakeClient):
    def execute_transaction(self, operation: Any) -> Any:
        raise RuntimeError("transaction failed")


def metadata() -> VideoGraphMetadata:
    return VideoGraphMetadata(
        video_id="fixture_video_001",
        title="Planning meeting",
        source_type="upload",
        duration_sec=38.0,
        pipeline_version="v1",
    )


def test_writer_uses_one_transaction_and_parameterized_batches() -> None:
    client = FakeClient()
    result = GraphWriter(client).index_graph(metadata(), load_fixture_bundle().extraction)  # type: ignore[arg-type]

    assert client.transaction_count == 1
    assert result.node_count == 12
    assert result.relationship_count == 16
    assert len(client.transaction.calls) == 13
    for query, parameters in client.transaction.calls:
        assert "$row" in query or "$rows" in query
        assert parameters
        assert "fixture_video_001" not in query


def test_writer_replay_produces_identical_merge_calls() -> None:
    client = FakeClient()
    writer = GraphWriter(client)  # type: ignore[arg-type]
    extraction = load_fixture_bundle().extraction

    writer.index_graph(metadata(), extraction)
    first_calls = list(client.transaction.calls)
    client.transaction.calls.clear()
    writer.index_graph(metadata(), extraction)

    assert client.transaction.calls == first_calls
    assert all("MERGE" in query for query, _ in first_calls)


def test_writer_propagates_transaction_failure_without_false_result() -> None:
    writer = GraphWriter(FailingClient())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="transaction failed"):
        writer.index_graph(metadata(), load_fixture_bundle().extraction)
