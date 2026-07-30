"""Predefined, parameterized graph reads exposed to the QA layer."""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping
from time import perf_counter
from typing import Any

from video_context_graph.contracts.video import RecordingScope, SearchResults
from video_context_graph.graph.mapper import normalize_lookup
from video_context_graph.integrations.neo4j_client import Neo4jClient

JsonRecord = dict[str, Any]
MAX_QUERY_LIMIT = 100
logger = logging.getLogger(__name__)


def _limit(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("limit must be a positive integer")
    return min(value, MAX_QUERY_LIMIT)


class GraphQueries:
    def __init__(self, client: Neo4jClient) -> None:
        self.client = client

    def _read(
        self, query_name: str, query: str, parameters: Mapping[str, Any]
    ) -> list[JsonRecord]:
        started = perf_counter()
        try:
            return self.client.execute_read(query, parameters)
        finally:
            duration_ms = (perf_counter() - started) * 1000
            logger.info("Neo4j query %s completed in %.1f ms", query_name, duration_ms)

    def list_recordings(self, scope: RecordingScope) -> list[JsonRecord]:
        """Discover a bounded recording collection without constructing dynamic Cypher."""

        return self._read(
            "list_recordings",
            """MATCH (v:Video)
            WHERE v.store_id = $store_id
              AND (size($camera_ids) = 0 OR v.camera_id IN $camera_ids)
              AND (size($video_ids) = 0 OR v.video_id IN $video_ids)
              AND ($recorded_from IS NULL OR
                   (v.recorded_at <> '' AND datetime(v.recorded_at) >= datetime($recorded_from)))
              AND ($recorded_to IS NULL OR
                   (v.recorded_at <> '' AND datetime(v.recorded_at) < datetime($recorded_to)))
            RETURN v.video_id AS video_id, v.title AS title, v.store_id AS store_id,
                   v.camera_id AS camera_id, v.recorded_at AS recorded_at,
                   v.duration_sec AS duration_sec, v.status AS status,
                   coalesce(v.search_available, false) AS search_available
            ORDER BY v.recorded_at ASC, v.camera_id ASC, v.video_id ASC
            LIMIT $limit""",
            {
                "store_id": scope.store_id,
                "camera_ids": scope.camera_ids,
                "video_ids": scope.video_ids,
                "recorded_from": (
                    scope.recorded_from.isoformat()
                    if scope.recorded_from is not None
                    else None
                ),
                "recorded_to": (
                    scope.recorded_to.isoformat()
                    if scope.recorded_to is not None
                    else None
                ),
                "limit": _limit(scope.max_videos),
            },
        )

    def get_video_overview(self, video_id: str) -> JsonRecord:
        video_rows = self._read(
            "get_video_overview.video",
            """MATCH (v:Video {video_id: $video_id})
            RETURN v.video_id AS video_id, v.title AS title, v.summary AS summary,
                   v.duration_sec AS duration_sec, v.status AS status,
                   v.store_id AS store_id, v.camera_id AS camera_id,
                   v.recorded_at AS recorded_at,
                   coalesce(v.search_available, false) AS search_available""",
            {"video_id": video_id},
        )
        if not video_rows:
            return {}
        overview = dict(video_rows[0])
        count_rows = self._read(
            "get_video_overview.scenes",
            """MATCH (v:Video {video_id: $video_id})
            OPTIONAL MATCH (v)-[:HAS_SCENE]->(s:Scene)
            RETURN count(DISTINCT s) AS scene_count""",
            {"video_id": video_id},
        )
        overview.update(count_rows[0] if count_rows else {})
        overview["entity_counts"] = self._read(
            "get_video_overview.entities",
            """MATCH (e:Entity {video_id: $video_id})
            RETURN e.entity_type AS type, count(*) AS count
            ORDER BY count DESC, type ASC""",
            {"video_id": video_id},
        )
        overview["entity_count"] = sum(
            int(row.get("count", 0)) for row in overview["entity_counts"]
        )
        overview["event_counts"] = self._read(
            "get_video_overview.events",
            """MATCH (e:Event {video_id: $video_id})
            RETURN e.event_type AS type, count(*) AS count
            ORDER BY count DESC, type ASC""",
            {"video_id": video_id},
        )
        overview["event_count"] = sum(
            int(row.get("count", 0)) for row in overview["event_counts"]
        )
        overview["top_tags"] = self._read(
            "get_video_overview.tags",
            """MATCH (:Scene {video_id: $video_id})-[:HAS_TAG]->(tag:Tag)
            RETURN tag.name AS name, count(*) AS count
            ORDER BY count DESC, name ASC LIMIT 10""",
            {"video_id": video_id},
        )
        return overview

    def list_video_entities(
        self, video_id: str, entity_type: str | None = None, limit: int = 50
    ) -> list[JsonRecord]:
        return self._read(
            "list_video_entities",
            """MATCH (e:Entity {video_id: $video_id})
            WHERE $entity_type IS NULL OR e.entity_type = $entity_type
            OPTIONAL MATCH (e)-[:APPEARS_IN]->(s:Scene)
            RETURN e.entity_id AS entity_id, e.canonical_name AS canonical_name,
                   e.entity_type AS entity_type, e.aliases AS aliases,
                   e.description AS description, e.confidence AS confidence,
                   count(DISTINCT s) AS occurrence_count
            ORDER BY occurrence_count DESC, canonical_name ASC
            LIMIT $limit""",
            {
                "video_id": video_id,
                "entity_type": entity_type.strip().upper() if entity_type else None,
                "limit": _limit(limit),
            },
        )

    def get_entity_timeline(
        self, video_id: str, entity_name: str, limit: int = 20
    ) -> list[JsonRecord]:
        normalized_name = normalize_lookup(entity_name)
        if not normalized_name:
            raise ValueError("entity_name must not be empty")
        return self._read(
            "get_entity_timeline",
            """MATCH (entity:Entity {video_id: $video_id})
            WHERE entity.normalized_name = $entity_name
               OR $entity_name IN coalesce(entity.normalized_aliases, [])
            MATCH (scene:Scene {video_id: $video_id})
            WHERE EXISTS { MATCH (entity)-[:APPEARS_IN]->(scene) }
               OR EXISTS {
                    MATCH (scene)-[:HAS_EVENT]->(:Event)
                          <-[:PARTICIPATES_IN|INVOLVED_IN]-(entity)
               }
            OPTIONAL MATCH (scene)-[:HAS_EVENT]->(event:Event)
            WHERE EXISTS { MATCH (entity)-[:PARTICIPATES_IN|INVOLVED_IN]->(event) }
            RETURN scene.scene_id AS scene_id, scene.source_local_id AS source_scene_id,
                   scene.start_sec AS start_sec, scene.end_sec AS end_sec,
                   scene.summary AS summary,
                   collect(DISTINCT CASE WHEN event IS NULL THEN NULL ELSE {
                       event_id: event.event_id, event_type: event.event_type,
                       description: event.description, start_sec: event.start_sec,
                       end_sec: event.end_sec
                   } END) AS events
            ORDER BY start_sec ASC LIMIT $limit""",
            {"video_id": video_id, "entity_name": normalized_name, "limit": _limit(limit)},
        )

    def get_scene_details(self, video_id: str, scene_ids: list[str]) -> list[JsonRecord]:
        if not scene_ids:
            return []
        unique_scene_ids = list(dict.fromkeys(scene_ids))[:MAX_QUERY_LIMIT]
        return self._read(
            "get_scene_details",
            """MATCH (scene:Scene {video_id: $video_id})
            WHERE scene.scene_id IN $scene_ids OR scene.source_local_id IN $scene_ids
            OPTIONAL MATCH (entity:Entity)-[:APPEARS_IN]->(scene)
            OPTIONAL MATCH (scene)-[:HAS_EVENT]->(event:Event)
            OPTIONAL MATCH (scene)-[:HAS_TAG]->(tag:Tag)
            RETURN scene.scene_id AS scene_id, scene.source_local_id AS source_scene_id,
                   scene.ordinal AS ordinal, scene.start_sec AS start_sec,
                   scene.end_sec AS end_sec, scene.summary AS summary,
                   scene.location AS location, scene.speech_summary AS speech_summary,
                   scene.on_screen_text AS on_screen_text, scene.sentiment AS sentiment,
                   collect(DISTINCT CASE WHEN entity IS NULL THEN NULL ELSE {
                       entity_id: entity.entity_id, name: entity.canonical_name,
                       type: entity.entity_type
                   } END) AS entities,
                   collect(DISTINCT CASE WHEN event IS NULL THEN NULL ELSE {
                       event_id: event.event_id, type: event.event_type,
                       description: event.description, start_sec: event.start_sec,
                       end_sec: event.end_sec
                   } END) AS events,
                   collect(DISTINCT CASE WHEN tag IS NULL THEN NULL ELSE tag.name END) AS tags
            ORDER BY ordinal ASC""",
            {"video_id": video_id, "scene_ids": unique_scene_ids},
        )

    def get_events_before_or_after(
        self, video_id: str, timestamp: float, direction: str, limit: int = 5
    ) -> list[JsonRecord]:
        normalized_direction = direction.strip().lower()
        if normalized_direction not in {"before", "after"}:
            raise ValueError("direction must be 'before' or 'after'")
        if not math.isfinite(timestamp) or timestamp < 0:
            raise ValueError("timestamp must be a finite non-negative number")
        comparison = (
            "event.end_sec <= $timestamp"
            if normalized_direction == "before"
            else "event.start_sec >= $timestamp"
        )
        ordering = (
            "event.start_sec DESC"
            if normalized_direction == "before"
            else "event.start_sec ASC"
        )
        query = f"""MATCH (event:Event {{video_id: $video_id}})
        WHERE {comparison}
        MATCH (scene:Scene)-[:HAS_EVENT]->(event)
        OPTIONAL MATCH (entity:Entity)-[:PARTICIPATES_IN|INVOLVED_IN]->(event)
        RETURN event.event_id AS event_id, event.event_type AS event_type,
               event.description AS description, event.start_sec AS start_sec,
               event.end_sec AS end_sec, scene.scene_id AS scene_id,
               scene.source_local_id AS source_scene_id,
               collect(DISTINCT CASE WHEN entity IS NULL THEN NULL ELSE
                   entity.canonical_name END) AS entities
        ORDER BY {ordering} LIMIT $limit"""
        rows = self._read(
            f"get_events_{normalized_direction}",
            query,
            {"video_id": video_id, "timestamp": timestamp, "limit": _limit(limit)},
        )
        if normalized_direction == "before":
            rows.reverse()
        return rows

    def find_entity_connections(
        self,
        video_id: str,
        entity_a: str,
        entity_b: str,
        limit: int = 10,
    ) -> list[JsonRecord]:
        normalized_a = normalize_lookup(entity_a)
        normalized_b = normalize_lookup(entity_b)
        if not normalized_a or not normalized_b:
            raise ValueError("entity names must not be empty")
        rows = self._read(
            "find_entity_connections",
            """MATCH (a:Entity {video_id: $video_id}), (b:Entity {video_id: $video_id})
            WHERE (a.normalized_name = $entity_a OR $entity_a IN coalesce(a.normalized_aliases, []))
              AND (b.normalized_name = $entity_b OR $entity_b IN coalesce(b.normalized_aliases, []))
            OPTIONAL MATCH (a)-[direct:RELATED_TO]-(b)
            OPTIONAL MATCH (a)-[:APPEARS_IN]->(shared_scene:Scene)<-[:APPEARS_IN]-(b)
            OPTIONAL MATCH (a)-[:PARTICIPATES_IN|INVOLVED_IN]->(shared_event:Event)
                           <-[:PARTICIPATES_IN|INVOLVED_IN]-(b)
            WITH a, b,
                 collect(DISTINCT CASE WHEN direct IS NULL THEN NULL ELSE {
                     connection_type: 'relationship', kind: direct.kind,
                     description: direct.description, confidence: direct.confidence,
                     scene_id: direct.scene_id
                 } END) AS relationships,
                 collect(DISTINCT CASE WHEN shared_scene IS NULL THEN NULL ELSE {
                     connection_type: 'shared_scene', scene_id: shared_scene.scene_id,
                     source_scene_id: shared_scene.source_local_id,
                     start_sec: shared_scene.start_sec, end_sec: shared_scene.end_sec,
                     summary: shared_scene.summary
                 } END) AS scenes,
                 collect(DISTINCT CASE WHEN shared_event IS NULL THEN NULL ELSE {
                     connection_type: 'shared_event', event_id: shared_event.event_id,
                     event_type: shared_event.event_type,
                     start_sec: shared_event.start_sec, end_sec: shared_event.end_sec,
                     description: shared_event.description
                 } END) AS events
            UNWIND relationships + scenes + events AS connection
            WITH connection WHERE connection IS NOT NULL
            RETURN connection ORDER BY coalesce(connection.start_sec, 0) ASC LIMIT $limit""",
            {
                "video_id": video_id,
                "entity_a": normalized_a,
                "entity_b": normalized_b,
                "limit": _limit(limit),
            },
        )
        return [row.get("connection", row) for row in rows]

    def find_scenes_overlapping_moments(
        self, video_id: str, moments: SearchResults
    ) -> list[JsonRecord]:
        if not moments.results:
            return []
        moment_rows = [
            {
                "moment_index": index,
                "scene_id": moment.scene_id,
                "start_sec": moment.start_sec,
                "end_sec": moment.end_sec,
                "score": moment.score,
                "summary": moment.summary,
            }
            for index, moment in enumerate(moments.results[:20])
        ]
        return self._read(
            "find_scenes_overlapping_moments",
            """UNWIND $moments AS moment
            MATCH (scene:Scene {video_id: $video_id})
            WHERE (moment.scene_id IS NOT NULL AND
                   (scene.scene_id = moment.scene_id OR scene.source_local_id = moment.scene_id))
               OR (scene.start_sec < moment.end_sec AND scene.end_sec > moment.start_sec)
            WITH moment, scene,
                 CASE WHEN scene.end_sec < moment.end_sec THEN scene.end_sec ELSE moment.end_sec END
                 - CASE WHEN scene.start_sec > moment.start_sec
                        THEN scene.start_sec ELSE moment.start_sec END AS overlap_sec
            RETURN moment.moment_index AS moment_index, moment.score AS search_score,
                   moment.summary AS moment_summary, moment.start_sec AS moment_start_sec,
                   moment.end_sec AS moment_end_sec, scene.scene_id AS scene_id,
                   scene.source_local_id AS source_scene_id, scene.ordinal AS ordinal,
                   scene.start_sec AS start_sec, scene.end_sec AS end_sec,
                   scene.summary AS scene_summary, overlap_sec
            ORDER BY moment_index ASC, overlap_sec DESC, ordinal ASC""",
            {"video_id": video_id, "moments": moment_rows},
        )
