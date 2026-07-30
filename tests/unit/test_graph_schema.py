from typing import Any

from video_context_graph.contracts.services import GraphService
from video_context_graph.contracts.video import ServiceHealth
from video_context_graph.graph.schema import initialize_schema, load_schema_statements
from video_context_graph.graph.service import Neo4jGraphService


class FakeClient:
    def __init__(self) -> None:
        self.writes: list[tuple[str, Any]] = []

    def execute_write(self, query: str, parameters: Any = None) -> list[dict]:
        self.writes.append((query, parameters))
        return []

    def health_check(self) -> ServiceHealth:
        return ServiceHealth(service="neo4j", available=True, detail="fixture")

    def close(self) -> None:
        return None


def test_schema_loader_returns_idempotent_constraints_and_indexes() -> None:
    statements = load_schema_statements()

    assert len(statements) == 8
    assert all("IF NOT EXISTS" in statement for statement in statements)
    assert sum(statement.startswith("CREATE CONSTRAINT") for statement in statements) == 5
    assert sum(statement.startswith("CREATE INDEX") for statement in statements) == 3


def test_schema_initializer_executes_every_statement() -> None:
    client = FakeClient()

    count = initialize_schema(client)  # type: ignore[arg-type]

    assert count == 8
    assert len(client.writes) == 8


def test_concrete_service_satisfies_frozen_graph_protocol() -> None:
    service = Neo4jGraphService(FakeClient())  # type: ignore[arg-type]

    assert isinstance(service, GraphService)
    assert service.health_check().available is True
