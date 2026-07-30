"""Fixture and live Strands question-answering services."""

from __future__ import annotations

from datetime import datetime, timedelta

from video_context_graph.agents.prompts import (
    COLLECTION_QA_SYSTEM_PROMPT,
    QA_SYSTEM_PROMPT,
    build_collection_qa_prompt,
    build_qa_prompt,
)
from video_context_graph.agents.tools import build_qa_tools
from video_context_graph.contracts import (
    AnswerResult,
    EvidenceReference,
    GraphService,
    QuestionAnsweringService,
    RecordingScope,
    ServiceHealth,
    VideoIntelligenceService,
)
from video_context_graph.fixture_store import FixtureBundle
from video_context_graph.integrations.strands_openai import StrandsOpenAIProvider


class QuestionAnsweringAgentError(RuntimeError):
    """Raised when the QA workflow cannot return a validated AnswerResult."""


class FixtureQuestionAnsweringService:
    """Explicit deterministic QA over the shared fixture evidence."""

    def __init__(self, bundle: FixtureBundle, graph_service: GraphService) -> None:
        self._bundle = bundle
        self._graph_service = graph_service

    def answer_question(self, *, video_id: str, question: str) -> AnswerResult:
        if video_id != self._bundle.segments.video_id:
            raise QuestionAnsweringAgentError(f"unknown fixture video_id: {video_id}")

        normalized = question.casefold()
        if "summar" in normalized or "overview" in normalized:
            return AnswerResult(
                answer=self._bundle.extraction.video_summary,
                evidence=[
                    EvidenceReference(
                        scene_id=scene.local_id,
                        start_sec=scene.start_sec,
                        end_sec=scene.end_sec,
                        reason=scene.summary,
                    )
                    for scene in self._bundle.extraction.scenes
                ],
                confidence=0.86,
                limitations=["Fixture mode uses saved evidence rather than live service calls."],
            )

        if any(term in normalized for term in ("jordan", "dashboard", "assigned", "follow-up")):
            moment = self._bundle.search.results[0]
            scene_id = moment.scene_id
            if scene_id is None:
                overlapping_scene = next(
                    (
                        scene
                        for scene in self._bundle.extraction.scenes
                        if scene.start_sec < moment.end_sec
                        and scene.end_sec > moment.start_sec
                    ),
                    None,
                )
                if overlapping_scene is None:
                    raise QuestionAnsweringAgentError(
                        "fixture search result does not overlap a graph scene"
                    )
                scene_id = overlapping_scene.local_id
            return AnswerResult(
                answer="Jordan was assigned the metrics dashboard follow-up.",
                evidence=[
                    EvidenceReference(
                        scene_id=scene_id,
                        start_sec=moment.start_sec,
                        end_sec=moment.end_sec,
                        reason=moment.summary,
                    )
                ],
                confidence=0.84,
                limitations=["Fixture mode uses saved evidence rather than live service calls."],
            )

        return AnswerResult(
            answer="The saved fixture evidence is not sufficient to answer that question.",
            evidence=[],
            confidence=0.2,
            limitations=[
                "The fixture contains only a short planning meeting and one saved search result.",
                "Use live mode or ask about the meeting summary or metrics dashboard assignment.",
            ],
        )

    def answer_collection_question(
        self, *, scope: RecordingScope, question: str
    ) -> AnswerResult:
        recordings = self._graph_service.list_recordings(scope)
        if not recordings:
            return AnswerResult(
                answer="No fixture recording matches the requested collection scope.",
                evidence=[],
                confidence=0.1,
                limitations=["The bounded fixture scope contained no recordings."],
            )
        recording = recordings[0]
        video_id = str(recording["video_id"])
        answer = self.answer_question(video_id=video_id, question=question)
        recorded_value = recording.get("recorded_at")
        absolute_start = (
            datetime.fromisoformat(str(recorded_value))
            if recorded_value
            else None
        )
        enriched = []
        for evidence in answer.evidence:
            enriched.append(
                evidence.model_copy(
                    update={
                        "video_id": video_id,
                        "camera_id": recording.get("camera_id"),
                        "recorded_start_at": (
                            absolute_start + timedelta(seconds=evidence.start_sec)
                            if absolute_start is not None
                            else None
                        ),
                        "recorded_end_at": (
                            absolute_start + timedelta(seconds=evidence.end_sec)
                            if absolute_start is not None
                            else None
                        ),
                    }
                )
            )
        return answer.model_copy(update={"evidence": enriched})

    def health_check(self) -> ServiceHealth:
        return ServiceHealth(
            service="strands",
            available=True,
            detail="Fixture QA is available; no model or external tool call will be made.",
        )


class StrandsQuestionAnsweringService(QuestionAnsweringService):
    """Ground answers through Strands tools and OpenAI structured output."""

    def __init__(
        self,
        *,
        provider: StrandsOpenAIProvider,
        video_service: VideoIntelligenceService,
        graph_service: GraphService,
    ) -> None:
        self._provider = provider
        self._graph_service = graph_service
        self._tools = build_qa_tools(video_service, graph_service)

    def answer_question(self, *, video_id: str, question: str) -> AnswerResult:
        if not question.strip():
            raise ValueError("question must not be empty")
        agent = self._provider.build_agent(
            name="SceneThread QA Agent",
            description="Answers questions about one video using grounded read-only tools.",
            system_prompt=QA_SYSTEM_PROMPT,
            tools=self._tools,
        )
        result = agent(
            build_qa_prompt(video_id=video_id, question=question),
            structured_output_model=AnswerResult,
        )
        if not isinstance(result.structured_output, AnswerResult):
            raise QuestionAnsweringAgentError("Strands returned no AnswerResult")
        return result.structured_output

    def answer_collection_question(
        self, *, scope: RecordingScope, question: str
    ) -> AnswerResult:
        if not question.strip():
            raise ValueError("question must not be empty")
        recordings = self._graph_service.list_recordings(scope)
        if not recordings:
            return AnswerResult(
                answer="No indexed recordings match the requested collection scope.",
                evidence=[],
                confidence=0.0,
                limitations=[
                    "Check the store, camera, and recorded-time filters or ingest matching footage."
                ],
            )
        agent = self._provider.build_agent(
            name="SceneThread Collection QA Agent",
            description=(
                "Answers questions across a bounded surveillance recording collection "
                "using grounded read-only tools."
            ),
            system_prompt=COLLECTION_QA_SYSTEM_PROMPT,
            tools=self._tools,
        )
        result = agent(
            build_collection_qa_prompt(
                scope_json=scope.model_dump_json(exclude_none=True),
                question=question,
            ),
            structured_output_model=AnswerResult,
        )
        answer = result.structured_output
        if not isinstance(answer, AnswerResult):
            raise QuestionAnsweringAgentError("Strands returned no AnswerResult")
        missing_video_ids = [
            evidence.scene_id for evidence in answer.evidence if not evidence.video_id
        ]
        if missing_video_ids:
            raise QuestionAnsweringAgentError(
                "collection answer evidence omitted video_id for scenes: "
                + ", ".join(missing_video_ids)
            )
        allowed_video_ids = {str(row["video_id"]) for row in recordings}
        outside_scope = [
            evidence.video_id
            for evidence in answer.evidence
            if evidence.video_id not in allowed_video_ids
        ]
        if outside_scope:
            raise QuestionAnsweringAgentError(
                "collection answer cited video IDs outside the authorized scope"
            )
        return answer

    def health_check(self) -> ServiceHealth:
        return self._provider.health_check()
