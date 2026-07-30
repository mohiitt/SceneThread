from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Self

import pytest
from neo4j.exceptions import ServiceUnavailable

from video_context_graph.integrations.neo4j_client import Neo4jClient


class FakeRecord:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def data(self) -> dict[str, Any]:
        return self._data


class FakeTransaction:
    def __init__(self, result: dict[str, Any] | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.result = result or {"ok": True}

    def run(self, query: str, parameters: dict[str, Any]) -> list[FakeRecord]:
        self.calls.append((query, parameters))
        return [FakeRecord(self.result)]


class FakeSession:
    def __init__(self, transaction: FakeTransaction) -> None:
        self.transaction = transaction

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def execute_read(self, operation: Any) -> Any:
        return operation(self.transaction)

    def execute_write(self, operation: Any) -> Any:
        return operation(self.transaction)


class FakeDriver:
    def __init__(
        self,
        connectivity_error: Exception | None = None,
        result: dict[str, Any] | None = None,
    ) -> None:
        self.transaction = FakeTransaction(result)
        self.connectivity_error = connectivity_error
        self.database: str | None = None
        self.closed = False

    def session(self, *, database: str) -> FakeSession:
        self.database = database
        return FakeSession(self.transaction)

    def verify_connectivity(self) -> None:
        if self.connectivity_error:
            raise self.connectivity_error

    def close(self) -> None:
        self.closed = True


def test_client_runs_parameterized_reads_in_selected_database() -> None:
    driver = FakeDriver()
    client = Neo4jClient("uri", "user", "password", "custom", driver=driver)

    result = client.execute_read("RETURN $value AS value", {"value": 3})

    assert result == [{"ok": True}]
    assert driver.database == "custom"
    assert driver.transaction.calls == [("RETURN $value AS value", {"value": 3})]


def test_client_converts_temporal_and_nested_values_to_json() -> None:
    timestamp = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
    driver = FakeDriver(result={"created_at": timestamp, "items": [(1, timestamp)]})
    client = Neo4jClient("uri", "user", "password", driver=driver)

    result = client.execute_read("RETURN 1")

    assert result == [
        {"created_at": timestamp.isoformat(), "items": [[1, timestamp.isoformat()]]}
    ]


def test_health_check_does_not_expose_exception_message() -> None:
    client = Neo4jClient(
        "uri", "user", "password", driver=FakeDriver(ServiceUnavailable("secret details"))
    )

    health = client.health_check()

    assert health.available is False
    assert "secret details" not in health.detail
    assert "ServiceUnavailable" in health.detail


def test_context_manager_closes_driver() -> None:
    driver = FakeDriver()
    with Neo4jClient("uri", "user", "password", driver=driver):
        pass
    assert driver.closed is True


def test_missing_configuration_returns_unavailable_without_network_call() -> None:
    client = Neo4jClient(
        "neo4j+s://YOUR_INSTANCE.databases.neo4j.io", "neo4j", ""
    )

    health = client.health_check()

    assert health.available is False
    assert "NEO4J_URI" in health.detail
    assert "NEO4J_PASSWORD" in health.detail
    with pytest.raises(RuntimeError, match="configuration is incomplete"):
        client.execute_read("RETURN 1")
