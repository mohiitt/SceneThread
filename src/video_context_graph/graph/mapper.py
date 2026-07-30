"""Deterministic mapping from validated contracts to Neo4j record batches."""

from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256
from itertools import pairwise
from typing import Any

from video_context_graph.contracts.extraction import GraphExtraction
from video_context_graph.contracts.video import VideoGraphMetadata

JsonRecord = dict[str, Any]


@dataclass(frozen=True)
class GraphPayload:
    """JSON-compatible records consumed by the parameterized graph writer."""

    video: JsonRecord
    scenes: list[JsonRecord]
    entities: list[JsonRecord]
    events: list[JsonRecord]
    tags: list[JsonRecord]
    video_scenes: list[JsonRecord]
    next_scenes: list[JsonRecord]
    scene_events: list[JsonRecord]
    appearances: list[JsonRecord]
    participants: list[JsonRecord]
    involved_entities: list[JsonRecord]
    scene_tags: list[JsonRecord]
    entity_relationships: list[JsonRecord]

    @property
    def node_count(self) -> int:
        return 1 + len(self.scenes) + len(self.entities) + len(self.events) + len(self.tags)

    @property
    def relationship_count(self) -> int:
        batches = (
            self.video_scenes,
            self.next_scenes,
            self.scene_events,
            self.appearances,
            self.participants,
            self.involved_entities,
            self.scene_tags,
            self.entity_relationships,
        )
        return sum(len(batch) for batch in batches)


def normalize_lookup(value: str) -> str:
    """Normalize human-entered names without losing meaningful punctuation."""

    return re.sub(r"\s+", " ", value.strip()).casefold()


def deterministic_id(prefix: str, *parts: object) -> str:
    """Create a stable, compact identifier from scoped identity components."""

    material = "\x1f".join(str(part) for part in parts)
    digest = sha256(material.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"


def _deduplicate(records: list[JsonRecord], key: str) -> list[JsonRecord]:
    unique: dict[str, JsonRecord] = {}
    for record in records:
        unique.setdefault(str(record[key]), record)
    return list(unique.values())


def map_graph(metadata: VideoGraphMetadata, extraction: GraphExtraction) -> GraphPayload:
    """Map validated extraction data to deterministic Neo4j node and edge batches."""

    video_id = metadata.video_id
    external_ids = metadata.external_ids
    scenes_outside_video = [
        scene.local_id for scene in extraction.scenes if scene.end_sec > metadata.duration_sec
    ]
    if scenes_outside_video:
        raise ValueError(
            "scene timestamps exceed video duration: " + ", ".join(scenes_outside_video)
        )
    empty_entities = [
        entity.local_id
        for entity in extraction.entities
        if not normalize_lookup(entity.canonical_name)
    ]
    if empty_entities:
        raise ValueError("entities have empty canonical names: " + ", ".join(empty_entities))
    video = {
        "video_id": video_id,
        "title": metadata.title,
        "file_name": metadata.file_name,
        "source_type": metadata.source_type,
        "domain_hint": metadata.domain_hint,
        "duration_sec": metadata.duration_sec,
        "store_id": metadata.store_id or "",
        "camera_id": metadata.camera_id or "",
        "recorded_at": (
            metadata.recorded_at.isoformat() if metadata.recorded_at is not None else ""
        ),
        "search_available": metadata.search_available,
        "status": "READY",
        "summary": extraction.video_summary,
        "twelvelabs_asset_id": external_ids.get("twelvelabs_asset_id", external_ids.get("asset_id", "")),
        "twelvelabs_index_id": external_ids.get("twelvelabs_index_id", external_ids.get("index_id", "")),
        "twelvelabs_indexed_asset_id": external_ids.get(
            "twelvelabs_indexed_asset_id", external_ids.get("indexed_asset_id", "")
        ),
        "segmentation_task_id": external_ids.get("segmentation_task_id", ""),
        "pipeline_version": metadata.pipeline_version,
    }

    entity_ids: dict[str, str] = {}
    entities: list[JsonRecord] = []
    for entity in extraction.entities:
        normalized_name = normalize_lookup(entity.canonical_name)
        entity_id = deterministic_id(
            "entity", video_id, entity.entity_type.upper(), normalized_name
        )
        entity_ids[entity.local_id] = entity_id
        entities.append(
            {
                "entity_id": entity_id,
                "source_local_id": entity.local_id,
                "video_id": video_id,
                "canonical_name": entity.canonical_name,
                "normalized_name": normalized_name,
                "entity_type": entity.entity_type.upper(),
                "aliases": entity.aliases,
                "normalized_aliases": [normalize_lookup(alias) for alias in entity.aliases],
                "description": entity.description,
                "confidence": entity.confidence,
            }
        )

    scene_ids: dict[str, str] = {}
    scenes: list[JsonRecord] = []
    for scene in extraction.scenes:
        scene_id = deterministic_id("scene", video_id, scene.local_id)
        scene_ids[scene.local_id] = scene_id
        scenes.append(
            {
                "scene_id": scene_id,
                "source_local_id": scene.local_id,
                "video_id": video_id,
                "ordinal": scene.ordinal,
                "start_sec": scene.start_sec,
                "end_sec": scene.end_sec,
                "summary": scene.summary,
                "location": scene.location,
                "speech_summary": scene.speech_summary,
                "on_screen_text": scene.on_screen_text,
                "sentiment": scene.sentiment,
                "confidence": scene.confidence,
            }
        )

    event_ids: dict[str, str] = {}
    events: list[JsonRecord] = []
    scene_events: list[JsonRecord] = []
    participants: list[JsonRecord] = []
    involved_entities: list[JsonRecord] = []
    for event in extraction.events:
        event_id = deterministic_id("event", video_id, event.local_id)
        event_ids[event.local_id] = event_id
        events.append(
            {
                "event_id": event_id,
                "source_local_id": event.local_id,
                "video_id": video_id,
                "event_type": event.event_type.upper(),
                "description": event.description,
                "start_sec": event.start_sec,
                "end_sec": event.end_sec,
                "confidence": event.confidence,
            }
        )
        scene_events.append({"scene_id": scene_ids[event.scene_id], "event_id": event_id})
        participants.extend(
            {
                "entity_id": entity_ids[item.entity_id],
                "event_id": event_id,
                "role": item.role,
            }
            for item in event.participants
        )
        involved_entities.extend(
            {
                "entity_id": entity_ids[item.entity_id],
                "event_id": event_id,
                "role": item.role,
            }
            for item in event.involved_entities
        )

    video_scenes = [{"video_id": video_id, "scene_id": row["scene_id"]} for row in scenes]
    ordered_scenes = sorted(scenes, key=lambda item: int(item["ordinal"]))
    next_scenes = [
        {"source_scene_id": first["scene_id"], "target_scene_id": second["scene_id"]}
        for first, second in pairwise(ordered_scenes)
    ]

    appearances: list[JsonRecord] = []
    tags_by_id: dict[str, JsonRecord] = {}
    scene_tags: list[JsonRecord] = []
    for scene in extraction.scenes:
        scene_id = scene_ids[scene.local_id]
        appearances.extend(
            {"entity_id": entity_ids[local_id], "scene_id": scene_id}
            for local_id in scene.entity_ids
        )
        for tag_name in scene.tags:
            normalized_name = normalize_lookup(tag_name)
            if not normalized_name:
                continue
            tag_id = deterministic_id("tag", normalized_name)
            tags_by_id.setdefault(
                tag_id,
                {
                    "tag_id": tag_id,
                    "name": tag_name.strip(),
                    "normalized_name": normalized_name,
                    "category": "general",
                },
            )
            scene_tags.append({"scene_id": scene_id, "tag_id": tag_id})

    entity_relationships: list[JsonRecord] = []
    for relationship in extraction.relationships:
        source_id = entity_ids[relationship.source_entity_id]
        target_id = entity_ids[relationship.target_entity_id]
        mapped_scene_id = scene_ids.get(relationship.scene_id or "")
        relationship_id = deterministic_id(
            "relationship",
            video_id,
            source_id,
            target_id,
            relationship.kind.upper(),
            mapped_scene_id or "",
            relationship.description,
        )
        entity_relationships.append(
            {
                "relationship_id": relationship_id,
                "source_entity_id": source_id,
                "target_entity_id": target_id,
                "kind": relationship.kind.upper(),
                "description": relationship.description,
                "scene_id": mapped_scene_id,
                "confidence": relationship.confidence,
            }
        )

    return GraphPayload(
        video=video,
        scenes=_deduplicate(scenes, "scene_id"),
        entities=_deduplicate(entities, "entity_id"),
        events=_deduplicate(events, "event_id"),
        tags=list(tags_by_id.values()),
        video_scenes=_deduplicate(video_scenes, "scene_id"),
        next_scenes=next_scenes,
        scene_events=_deduplicate(scene_events, "event_id"),
        appearances=_deduplicate(
            [dict(row, edge_id=f"{row['entity_id']}:{row['scene_id']}") for row in appearances],
            "edge_id",
        ),
        participants=_deduplicate(
            [dict(row, edge_id=f"{row['entity_id']}:{row['event_id']}:{row['role']}") for row in participants],
            "edge_id",
        ),
        involved_entities=_deduplicate(
            [dict(row, edge_id=f"{row['entity_id']}:{row['event_id']}:{row['role']}") for row in involved_entities],
            "edge_id",
        ),
        scene_tags=_deduplicate(
            [dict(row, edge_id=f"{row['scene_id']}:{row['tag_id']}") for row in scene_tags],
            "edge_id",
        ),
        entity_relationships=_deduplicate(entity_relationships, "relationship_id"),
    )
