"""Fixture and live Strands graph-extraction services."""

from __future__ import annotations

from video_context_graph.agents.prompts import EXTRACTION_SYSTEM_PROMPT, build_extraction_prompt
from video_context_graph.contracts import GraphExtraction, SegmentCollection, ServiceHealth
from video_context_graph.fixture_store import FixtureBundle
from video_context_graph.integrations.strands_openai import StrandsOpenAIProvider


class ExtractionAgentError(RuntimeError):
    """Raised when structured graph extraction cannot produce a valid contract."""


class FixtureExtractionService:
    """Explicit offline extraction service backed by the shared validated fixture."""

    def __init__(self, bundle: FixtureBundle) -> None:
        self._bundle = bundle

    def extract_graph(
        self,
        *,
        title: str,
        domain_hint: str,
        segments: SegmentCollection,
    ) -> GraphExtraction:
        del title, domain_hint
        if segments != self._bundle.segments:
            raise ExtractionAgentError(
                "fixture extraction only accepts the shared fixture segment collection"
            )
        return self._bundle.extraction.model_copy(deep=True)

    def health_check(self) -> ServiceHealth:
        return ServiceHealth(
            service="strands",
            available=True,
            detail="Fixture extraction is available; no OpenAI request will be made.",
        )


class StrandsExtractionService:
    """Use a Strands agent and OpenAI structured output to normalize video segments."""

    def __init__(self, provider: StrandsOpenAIProvider, max_attempts: int = 2) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self._provider = provider
        self._max_attempts = max_attempts

    def extract_graph(
        self,
        *,
        title: str,
        domain_hint: str,
        segments: SegmentCollection,
    ) -> GraphExtraction:
        agent = self._provider.build_agent(
            name="SceneThread Extraction Agent",
            description="Normalizes timestamped video evidence into a context graph.",
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
        )
        prompt = build_extraction_prompt(
            title=title,
            domain_hint=domain_hint,
            segments_json=segments.model_dump_json(indent=2),
        )

        last_error: Exception | None = None
        for attempt in range(1, self._max_attempts + 1):
            corrective_prompt = prompt
            if last_error is not None:
                corrective_prompt += (
                    "\n\nThe previous structured output failed validation. Correct only these "
                    f"validation issues and return the full object:\n{last_error}"
                )
            try:
                result = agent(
                    corrective_prompt,
                    structured_output_model=GraphExtraction,
                )
                if isinstance(result.structured_output, GraphExtraction):
                    return result.structured_output
                raise ExtractionAgentError("Strands returned no GraphExtraction")
            except Exception as exc:  # noqa: BLE001 - SDK/provider failures share this retry boundary.
                last_error = exc
                if attempt == self._max_attempts:
                    break

        raise ExtractionAgentError(
            f"structured extraction failed after {self._max_attempts} attempts: {last_error}"
        ) from last_error

    def health_check(self) -> ServiceHealth:
        return self._provider.health_check()
