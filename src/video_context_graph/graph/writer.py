"""Transactional, idempotent Neo4j writes for validated graph extractions."""

from __future__ import annotations

from typing import Any

from video_context_graph.contracts.extraction import GraphExtraction
from video_context_graph.contracts.video import GraphWriteResult, VideoGraphMetadata
from video_context_graph.graph.mapper import GraphPayload, map_graph
from video_context_graph.integrations.neo4j_client import Neo4jClient

VIDEO_QUERY = """
MERGE (v:Video {video_id: $row.video_id})
ON CREATE SET v.created_at = datetime()
SET v += $row, v.updated_at = datetime()
"""

NODE_QUERIES = (
    ("scenes", "UNWIND $rows AS row MERGE (n:Scene {scene_id: row.scene_id}) SET n += row"),
    ("entities", "UNWIND $rows AS row MERGE (n:Entity {entity_id: row.entity_id}) SET n += row"),
    ("events", "UNWIND $rows AS row MERGE (n:Event {event_id: row.event_id}) SET n += row"),
    ("tags", "UNWIND $rows AS row MERGE (n:Tag {tag_id: row.tag_id}) SET n += row"),
)

RELATIONSHIP_QUERIES = (
    (
        "video_scenes",
        """UNWIND $rows AS row
        MATCH (v:Video {video_id: row.video_id}), (s:Scene {scene_id: row.scene_id})
        MERGE (v)-[:HAS_SCENE]->(s)""",
    ),
    (
        "next_scenes",
        """UNWIND $rows AS row
        MATCH (a:Scene {scene_id: row.source_scene_id}),
              (b:Scene {scene_id: row.target_scene_id})
        MERGE (a)-[:NEXT_SCENE]->(b)""",
    ),
    (
        "scene_events",
        """UNWIND $rows AS row
        MATCH (s:Scene {scene_id: row.scene_id}), (e:Event {event_id: row.event_id})
        MERGE (s)-[:HAS_EVENT]->(e)""",
    ),
    (
        "appearances",
        """UNWIND $rows AS row
        MATCH (e:Entity {entity_id: row.entity_id}), (s:Scene {scene_id: row.scene_id})
        MERGE (e)-[:APPEARS_IN]->(s)""",
    ),
    (
        "participants",
        """UNWIND $rows AS row
        MATCH (e:Entity {entity_id: row.entity_id}), (event:Event {event_id: row.event_id})
        MERGE (e)-[r:PARTICIPATES_IN {role: row.role}]->(event)
        SET r.edge_id = row.edge_id""",
    ),
    (
        "involved_entities",
        """UNWIND $rows AS row
        MATCH (e:Entity {entity_id: row.entity_id}), (event:Event {event_id: row.event_id})
        MERGE (e)-[r:INVOLVED_IN {role: row.role}]->(event)
        SET r.edge_id = row.edge_id""",
    ),
    (
        "scene_tags",
        """UNWIND $rows AS row
        MATCH (s:Scene {scene_id: row.scene_id}), (t:Tag {tag_id: row.tag_id})
        MERGE (s)-[:HAS_TAG]->(t)""",
    ),
    (
        "entity_relationships",
        """UNWIND $rows AS row
        MATCH (a:Entity {entity_id: row.source_entity_id}),
              (b:Entity {entity_id: row.target_entity_id})
        MERGE (a)-[r:RELATED_TO {relationship_id: row.relationship_id}]->(b)
        SET r.kind = row.kind, r.description = row.description,
            r.scene_id = row.scene_id, r.confidence = row.confidence""",
    ),
)


class GraphWriter:
    def __init__(self, client: Neo4jClient) -> None:
        self.client = client

    def index_graph(
        self, metadata: VideoGraphMetadata, extraction: GraphExtraction
    ) -> GraphWriteResult:
        payload = map_graph(metadata, extraction)
        self.client.execute_transaction(lambda tx: self._write_payload(tx, payload))
        return GraphWriteResult(
            video_id=metadata.video_id,
            node_count=payload.node_count,
            relationship_count=payload.relationship_count,
        )

    @staticmethod
    def _write_payload(tx: Any, payload: GraphPayload) -> None:
        tx.run(VIDEO_QUERY, row=payload.video).consume()
        for attribute, query in (*NODE_QUERIES, *RELATIONSHIP_QUERIES):
            rows = getattr(payload, attribute)
            if rows:
                tx.run(query, rows=rows).consume()
