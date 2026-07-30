"""Idempotent Neo4j schema initialization helpers."""

from __future__ import annotations

from importlib.resources import files

from video_context_graph.integrations.neo4j_client import Neo4jClient


def load_schema_statements() -> list[str]:
    schema = files("video_context_graph.graph").joinpath("schema.cypher").read_text("utf-8")
    return [statement.strip() for statement in schema.split(";") if statement.strip()]


def initialize_schema(client: Neo4jClient) -> int:
    statements = load_schema_statements()
    for statement in statements:
        client.execute_write(statement)
    return len(statements)
