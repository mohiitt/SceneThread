from __future__ import annotations

import pytest

from video_context_graph.agents.prompts import (
    EXTRACTION_SYSTEM_PROMPT,
    QA_SYSTEM_PROMPT,
    build_extraction_prompt,
)
from video_context_graph.config import Settings
from video_context_graph.integrations.strands_openai import (
    StrandsOpenAIConfigurationError,
    StrandsOpenAIProvider,
)


def test_provider_fails_clearly_without_api_key() -> None:
    provider = StrandsOpenAIProvider(Settings(openai_api_key=""))

    assert provider.health_check().available is False
    with pytest.raises(StrandsOpenAIConfigurationError, match="OPENAI_API_KEY"):
        provider.build_model()


def test_provider_builds_responses_model_without_network_call() -> None:
    provider = StrandsOpenAIProvider(
        Settings(
            openai_api_key="test-key-not-used",
            openai_model="gpt-5.6-terra",
            openai_reasoning_effort="low",
        )
    )

    model = provider.build_model()

    assert model.get_config()["model_id"] == "gpt-5.6-terra"
    assert model.get_config()["params"] == {
        "reasoning": {"effort": "low"},
        "store": False,
    }


def test_prompts_preserve_evidence_and_safety_contracts() -> None:
    prompt = build_extraction_prompt(
        title="Example",
        domain_hint="Meeting",
        segments_json='{"start_sec": 1.25, "end_sec": 4.5}',
    )

    assert "preserve source start_sec and end_sec values exactly" in EXTRACTION_SYSTEM_PROMPT
    assert "never identify an unnamed person" in EXTRACTION_SYSTEM_PROMPT
    assert "never call a graph-write operation" in QA_SYSTEM_PROMPT
    assert '"start_sec": 1.25' in prompt
