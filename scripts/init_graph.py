"""Create Neo4j constraints and indexes for SceneThread."""

from __future__ import annotations

from video_context_graph.graph.schema import initialize_schema
from video_context_graph.integrations.neo4j_client import Neo4jClient


def main() -> None:
    with Neo4jClient.from_settings() as client:
        health = client.health_check()
        if not health.available:
            raise SystemExit(health.detail)
        count = initialize_schema(client)
    print(f"SceneThread graph schema initialized ({count} statements).")


if __name__ == "__main__":
    main()
