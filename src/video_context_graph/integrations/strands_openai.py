"""Strands/OpenAI Responses provider construction and credential checks."""

from __future__ import annotations

from collections.abc import Sequence

from strands import Agent
from strands.models.openai_responses import OpenAIResponsesModel

from video_context_graph.config import Settings
from video_context_graph.contracts import ServiceHealth


class StrandsOpenAIConfigurationError(RuntimeError):
    """Raised when live Strands/OpenAI mode is requested without valid configuration."""


class StrandsOpenAIProvider:
    """Build isolated Strands agents backed by the OpenAI Responses API."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def health_check(self) -> ServiceHealth:
        if not self._settings.openai_api_key:
            return ServiceHealth(
                service="openai",
                available=False,
                detail="OPENAI_API_KEY is missing; fixture mode remains available.",
            )
        if not self._settings.openai_model:
            return ServiceHealth(
                service="openai",
                available=False,
                detail="OPENAI_MODEL is missing.",
            )
        return ServiceHealth(
            service="openai",
            available=True,
            detail=(
                "OpenAI configuration is present. Live connectivity is verified on the "
                "first model request."
            ),
        )

    def build_model(self) -> OpenAIResponsesModel:
        health = self.health_check()
        if not health.available:
            raise StrandsOpenAIConfigurationError(health.detail)

        return OpenAIResponsesModel(
            client_args={"api_key": self._settings.openai_api_key},
            model_id=self._settings.openai_model,
            params={
                "reasoning": {"effort": self._settings.openai_reasoning_effort},
                "store": False,
            },
            stateful=False,
        )

    def build_agent(
        self,
        *,
        name: str,
        description: str,
        system_prompt: str,
        tools: Sequence[object] | None = None,
    ) -> Agent:
        return Agent(
            model=self.build_model(),
            name=name,
            description=description,
            system_prompt=system_prompt,
            tools=list(tools or []),
            callback_handler=None,
        )
