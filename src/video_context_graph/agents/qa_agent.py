"""Fixture and live Strands question-answering services."""

from __future__ import annotations

from video_context_graph.agents.prompts import QA_SYSTEM_PROMPT, build_qa_prompt
from video_context_graph.agents.tools import build_qa_tools
from video_context_graph.contracts import (
    AnswerResult,
    EvidenceReference,
    GraphService,
    QuestionAnsweringService,
    ServiceHealth,
    VideoIntelligenceService,
)
from video_context_graph.fixture_store import FixtureBundle
from video_context_graph.integrations.strands_openai import StrandsOpenAIProvider


class QuestionAnsweringAgentError(RuntimeError):
    """Raised when the QA workflow cannot return a validated AnswerResult."""


class FixtureQuestionAnsweringService:
    """Explicit deterministic QA over the shared fixture evidence."""

    def __init__(self, bundle: FixtureBundle) -> None:
        self._bundle = bundle

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

    def health_check(self) -> ServiceHealth:
        return self._provider.health_check()
