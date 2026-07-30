"""Small Neo4j driver boundary used by deterministic graph services."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date, datetime, time
from typing import Any, Self, TypeVar

from neo4j.exceptions import DriverError, Neo4jError

from video_context_graph.config import Settings, get_settings
from video_context_graph.contracts.video import ServiceHealth

JsonRecord = dict[str, Any]
T = TypeVar("T")


def _json_compatible(value: Any) -> Any:
    """Recursively convert Neo4j result values into tool/UI-safe JSON values."""

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_compatible(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_compatible(item) for item in value]
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    iso_format = getattr(value, "iso_format", None)
    if callable(iso_format):
        return iso_format()
    return str(value)


def _run_records(tx: Any, query: str, parameters: Mapping[str, Any]) -> list[JsonRecord]:
    return [_json_compatible(record.data()) for record in tx.run(query, dict(parameters))]


class Neo4jClient:
    """Own the Neo4j driver and expose parameterized read/write operations."""

    def __init__(
        self,
        uri: str,
        username: str,
        password: str,
        database: str = "neo4j",
        *,
        driver: Any | None = None,
    ) -> None:
        self.database = database
        self._configuration_error: str | None = None
        if driver is None:
            missing = []
            if not uri or "YOUR_INSTANCE" in uri:
                missing.append("NEO4J_URI")
            if not username:
                missing.append("NEO4J_USERNAME")
            if not password:
                missing.append("NEO4J_PASSWORD")
            if missing:
                self._configuration_error = (
                    "Neo4j configuration is incomplete: " + ", ".join(missing)
                )
            else:
                from neo4j import GraphDatabase

                driver = GraphDatabase.driver(uri, auth=(username, password))
        self._driver = driver

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> Neo4jClient:
        configured = settings or get_settings()
        return cls(
            configured.neo4j_uri,
            configured.neo4j_username,
            configured.neo4j_password,
            configured.neo4j_database,
        )

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def health_check(self) -> ServiceHealth:
        if self._configuration_error is not None:
            return ServiceHealth(
                service="neo4j",
                available=False,
                detail=self._configuration_error,
            )
        try:
            self._require_driver().verify_connectivity()
        except (DriverError, Neo4jError) as exc:
            return ServiceHealth(
                service="neo4j",
                available=False,
                detail=f"Neo4j connectivity failed ({type(exc).__name__}).",
            )
        return ServiceHealth(service="neo4j", available=True, detail="Neo4j is reachable.")

    def execute_read(
        self, query: str, parameters: Mapping[str, Any] | None = None
    ) -> list[JsonRecord]:
        with self._require_driver().session(database=self.database) as session:
            return session.execute_read(
                lambda tx: _run_records(tx, query, parameters or {})
            )

    def execute_write(
        self, query: str, parameters: Mapping[str, Any] | None = None
    ) -> list[JsonRecord]:
        with self._require_driver().session(database=self.database) as session:
            return session.execute_write(
                lambda tx: _run_records(tx, query, parameters or {})
            )

    def execute_transaction(self, operation: Callable[[Any], T]) -> T:
        with self._require_driver().session(database=self.database) as session:
            return session.execute_write(operation)

    def _require_driver(self) -> Any:
        if self._driver is None:
            raise RuntimeError(self._configuration_error or "Neo4j driver is unavailable.")
        return self._driver
