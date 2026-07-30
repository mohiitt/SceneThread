"""Graph extraction contracts shared across pipeline, graph, and agent code."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class EntityExtraction(BaseModel):
    local_id: str
    canonical_name: str
    entity_type: str
    aliases: list[str] = Field(default_factory=list)
    description: str = ""
    confidence: float = Field(ge=0, le=1)


class SceneExtraction(BaseModel):
    local_id: str
    ordinal: int
    start_sec: float
    end_sec: float
    summary: str
    location: str | None = None
    speech_summary: str | None = None
    on_screen_text: list[str] = Field(default_factory=list)
    sentiment: str = "unknown"
    entity_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_timestamp_order(self) -> SceneExtraction:
        if self.start_sec < 0:
            raise ValueError("start_sec must be greater than or equal to 0")
        if self.start_sec >= self.end_sec:
            raise ValueError("start_sec must be less than end_sec")
        return self


class EventParticipant(BaseModel):
    entity_id: str
    role: str


class EventExtraction(BaseModel):
    local_id: str
    scene_id: str
    event_type: str
    description: str
    start_sec: float
    end_sec: float
    participants: list[EventParticipant] = Field(default_factory=list)
    involved_entities: list[EventParticipant] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_timestamp_order(self) -> EventExtraction:
        if self.start_sec < 0:
            raise ValueError("start_sec must be greater than or equal to 0")
        if self.start_sec >= self.end_sec:
            raise ValueError("start_sec must be less than end_sec")
        return self


class EntityRelationshipExtraction(BaseModel):
    source_entity_id: str
    target_entity_id: str
    kind: str
    description: str
    scene_id: str | None = None
    confidence: float = Field(ge=0, le=1)


class GraphExtraction(BaseModel):
    video_summary: str
    entities: list[EntityExtraction]
    scenes: list[SceneExtraction]
    events: list[EventExtraction]
    relationships: list[EntityRelationshipExtraction]

    @model_validator(mode="after")
    def validate_references(self) -> GraphExtraction:
        entity_local_ids = [entity.local_id for entity in self.entities]
        if len(entity_local_ids) != len(set(entity_local_ids)):
            raise ValueError("entity local IDs must be unique")

        scene_local_ids = [scene.local_id for scene in self.scenes]
        if len(scene_local_ids) != len(set(scene_local_ids)):
            raise ValueError("scene local IDs must be unique")

        event_local_ids = [event.local_id for event in self.events]
        if len(event_local_ids) != len(set(event_local_ids)):
            raise ValueError("event local IDs must be unique")

        entity_ids = {entity.local_id for entity in self.entities}
        scene_ids = {scene.local_id for scene in self.scenes}
        scenes_by_id = {scene.local_id: scene for scene in self.scenes}

        ordinals = [scene.ordinal for scene in self.scenes]
        if ordinals != sorted(ordinals):
            raise ValueError("scene ordinals must be sorted")
        if len(ordinals) != len(set(ordinals)):
            raise ValueError("scene ordinals must be unique")

        for scene in self.scenes:
            unknown = set(scene.entity_ids) - entity_ids
            if unknown:
                raise ValueError(f"scene {scene.local_id} references unknown entities: {unknown}")

        for event in self.events:
            if event.scene_id not in scene_ids:
                raise ValueError(f"event {event.local_id} references unknown scene: {event.scene_id}")
            scene = scenes_by_id[event.scene_id]
            if event.start_sec < scene.start_sec or event.end_sec > scene.end_sec:
                raise ValueError(
                    f"event {event.local_id} timestamps must be within scene {event.scene_id}"
                )
            if not event.description.strip():
                raise ValueError(f"event {event.local_id} description must not be empty")
            referenced = {participant.entity_id for participant in event.participants}
            referenced.update(participant.entity_id for participant in event.involved_entities)
            unknown = referenced - entity_ids
            if unknown:
                raise ValueError(f"event {event.local_id} references unknown entities: {unknown}")

        for relationship in self.relationships:
            if relationship.source_entity_id == relationship.target_entity_id:
                raise ValueError("relationship self-loops are not allowed")
            if relationship.source_entity_id not in entity_ids:
                raise ValueError(
                    "relationship references unknown source entity: "
                    f"{relationship.source_entity_id}"
                )
            if relationship.target_entity_id not in entity_ids:
                raise ValueError(
                    "relationship references unknown target entity: "
                    f"{relationship.target_entity_id}"
                )
            if relationship.scene_id is not None and relationship.scene_id not in scene_ids:
                raise ValueError(
                    f"relationship references unknown scene: {relationship.scene_id}"
                )

        return self
