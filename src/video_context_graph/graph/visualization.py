"""Bounded, JSON-compatible graph data preparation for UI visualization."""

from __future__ import annotations

import math
from typing import Any

from video_context_graph.graph.mapper import normalize_lookup
from video_context_graph.integrations.neo4j_client import Neo4jClient

JsonRecord = dict[str, Any]
ALLOWED_NODE_TYPES = {"Video", "Scene", "Entity", "Event", "Tag"}


class GraphVisualizationBuilder:
    def __init__(self, client: Neo4jClient, default_limit: int = 100) -> None:
        if default_limit < 1:
            raise ValueError("default_limit must be positive")
        self.client = client
        self.default_limit = min(default_limit, 500)

    def list_videos(self, limit: int = 50) -> list[JsonRecord]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be a positive integer")
        return self.client.execute_read(
            """MATCH (video:Video)
            RETURN video.video_id AS video_id, video.title AS title,
                   video.store_id AS store_id, video.camera_id AS camera_id,
                   video.recorded_at AS recorded_at, video.duration_sec AS duration_sec,
                   video.status AS status
            ORDER BY video.updated_at DESC, video.recorded_at DESC, video.video_id ASC
            LIMIT $limit""",
            {"limit": min(limit, 100)},
        )

    def build(
        self,
        video_id: str,
        *,
        node_types: list[str] | None = None,
        entity_name: str | None = None,
        start_sec: float | None = None,
        end_sec: float | None = None,
        limit: int | None = None,
    ) -> JsonRecord:
        selected_types = list(dict.fromkeys(node_types or sorted(ALLOWED_NODE_TYPES)))
        invalid_types = set(selected_types) - ALLOWED_NODE_TYPES
        if invalid_types:
            raise ValueError(f"unsupported node types: {sorted(invalid_types)}")
        if start_sec is not None and (not math.isfinite(start_sec) or start_sec < 0):
            raise ValueError("start_sec must be finite and non-negative")
        if end_sec is not None and (not math.isfinite(end_sec) or end_sec < 0):
            raise ValueError("end_sec must be finite and non-negative")
        if start_sec is not None and end_sec is not None and start_sec >= end_sec:
            raise ValueError("start_sec must be less than end_sec")
        requested_limit = self.default_limit if limit is None else limit
        if (
            isinstance(requested_limit, bool)
            or not isinstance(requested_limit, int)
            or requested_limit < 1
        ):
            raise ValueError("limit must be a positive integer")
        bounded_limit = min(requested_limit, 500)
        normalized_entity = normalize_lookup(entity_name) if entity_name else None

        nodes = self.client.execute_read(
            """MATCH (node)
            WHERE any(label IN labels(node) WHERE label IN $node_types)
              AND (
                  node.video_id = $video_id OR
                  (node:Tag AND EXISTS {
                      MATCH (:Scene {video_id: $video_id})-[:HAS_TAG]->(node)
                  })
              )
              AND ($start_sec IS NULL OR NOT (node:Scene OR node:Event)
                   OR node.end_sec > $start_sec)
              AND ($end_sec IS NULL OR NOT (node:Scene OR node:Event)
                   OR node.start_sec < $end_sec)
              AND ($entity_name IS NULL OR
                   (node:Entity AND (node.normalized_name = $entity_name OR
                       $entity_name IN coalesce(node.normalized_aliases, []))) OR
                   EXISTS {
                       MATCH (focus:Entity {video_id: $video_id})-[*1..2]-(node)
                       WHERE focus.normalized_name = $entity_name
                          OR $entity_name IN coalesce(focus.normalized_aliases, [])
                   })
            WITH node, CASE
                 WHEN node:Video THEN node.video_id
                 WHEN node:Scene THEN node.scene_id
                 WHEN node:Entity THEN node.entity_id
                 WHEN node:Event THEN node.event_id
                 ELSE node.tag_id END AS id
            RETURN id, head(labels(node)) AS type, properties(node) AS properties
            ORDER BY CASE
                     WHEN node:Video THEN 0
                     WHEN node:Scene THEN 1
                     WHEN node:Entity THEN 2
                     WHEN node:Event THEN 3
                     ELSE 4 END ASC,
                     coalesce(node.ordinal, node.start_sec, 0) ASC, id ASC
            LIMIT $fetch_limit""",
            {
                "video_id": video_id,
                "node_types": selected_types,
                "entity_name": normalized_entity,
                "start_sec": start_sec,
                "end_sec": end_sec,
                "fetch_limit": bounded_limit + 1,
            },
        )
        truncated = len(nodes) > bounded_limit
        nodes = nodes[:bounded_limit]
        node_ids = [row["id"] for row in nodes]
        edges = []
        if node_ids:
            edges = self.client.execute_read(
                """MATCH (source)-[relationship]->(target)
                WITH source, relationship, target,
                     CASE WHEN source:Video THEN source.video_id
                          WHEN source:Scene THEN source.scene_id
                          WHEN source:Entity THEN source.entity_id
                          WHEN source:Event THEN source.event_id
                          ELSE source.tag_id END AS source_id,
                     CASE WHEN target:Video THEN target.video_id
                          WHEN target:Scene THEN target.scene_id
                          WHEN target:Entity THEN target.entity_id
                          WHEN target:Event THEN target.event_id
                          ELSE target.tag_id END AS target_id
                WHERE source_id IN $node_ids AND target_id IN $node_ids
                RETURN source_id AS source, target_id AS target,
                       type(relationship) AS type, properties(relationship) AS properties
                ORDER BY source ASC, type ASC, target ASC""",
                {"node_ids": node_ids},
            )
        return {
            "nodes": nodes,
            "edges": edges,
            "truncated": truncated,
            "limit": bounded_limit,
        }
