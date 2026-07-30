"""Shared Pydantic contracts."""

from video_context_graph.contracts.answers import AnswerResult, EvidenceReference
from video_context_graph.contracts.extraction import (
    EntityExtraction,
    EntityRelationshipExtraction,
    EventExtraction,
    EventParticipant,
    GraphExtraction,
    SceneExtraction,
)
from video_context_graph.contracts.jobs import PipelineJob, PipelineRunResult
from video_context_graph.contracts.services import (
    ExtractionService,
    GraphService,
    PipelineCoordinator,
    QuestionAnsweringService,
    VideoIntelligenceService,
)
from video_context_graph.contracts.traces import PipelineTrace, PipelineTraceEvent
from video_context_graph.contracts.video import (
    GraphWriteResult,
    IngestionRequest,
    IngestionResult,
    RecordingScope,
    SearchMoment,
    SearchRequest,
    SearchResults,
    SegmentCollection,
    ServiceHealth,
    VideoGraphMetadata,
    VideoSegment,
)

__all__ = [
    "AnswerResult",
    "EntityExtraction",
    "EntityRelationshipExtraction",
    "EventExtraction",
    "EventParticipant",
    "EvidenceReference",
    "ExtractionService",
    "GraphExtraction",
    "GraphService",
    "GraphWriteResult",
    "IngestionRequest",
    "IngestionResult",
    "PipelineCoordinator",
    "PipelineJob",
    "PipelineRunResult",
    "PipelineTrace",
    "PipelineTraceEvent",
    "QuestionAnsweringService",
    "RecordingScope",
    "SceneExtraction",
    "SearchMoment",
    "SearchRequest",
    "SearchResults",
    "SegmentCollection",
    "ServiceHealth",
    "VideoGraphMetadata",
    "VideoIntelligenceService",
    "VideoSegment",
]
