"""Dependency assembly for fixture, hybrid, and full-live UI modes."""

from __future__ import annotations

from dataclasses import dataclass

from video_context_graph.agents.coordinator import SceneThreadCoordinator
from video_context_graph.agents.extraction_agent import (
    FixtureExtractionService,
    StrandsExtractionService,
)
from video_context_graph.agents.fixture_runtime import (
    FixtureGraphService,
    FixtureVideoIntelligenceService,
)
from video_context_graph.agents.qa_agent import (
    FixtureQuestionAnsweringService,
    StrandsQuestionAnsweringService,
)
from video_context_graph.config import Settings
from video_context_graph.contracts import (
    ExtractionService,
    GraphService,
    QuestionAnsweringService,
    VideoIntelligenceService,
)
from video_context_graph.fixture_store import FixtureBundle, load_fixture_bundle
from video_context_graph.graph.service import Neo4jGraphService
from video_context_graph.integrations.neo4j_client import Neo4jClient
from video_context_graph.integrations.strands_openai import StrandsOpenAIProvider
from video_context_graph.integrations.twelvelabs_client import TwelveLabsClient


@dataclass
class FixtureRuntime:
    app_data_dir: str
    bundle: FixtureBundle
    video_service: VideoIntelligenceService
    graph_service: GraphService
    extraction_service: ExtractionService
    qa_service: QuestionAnsweringService
    coordinator: SceneThreadCoordinator


def create_fixture_runtime(settings: Settings) -> FixtureRuntime:
    bundle = load_fixture_bundle()
    video_service = FixtureVideoIntelligenceService(bundle)
    graph_service = FixtureGraphService(bundle)
    extraction_service = FixtureExtractionService(bundle)
    qa_service = FixtureQuestionAnsweringService(bundle)
    coordinator = SceneThreadCoordinator(
        video_service=video_service,
        extraction_service=extraction_service,
        graph_service=graph_service,
        mode="fixture",
        pipeline_version=settings.pipeline_version,
    )
    return FixtureRuntime(
        app_data_dir=settings.app_data_dir,
        bundle=bundle,
        video_service=video_service,
        graph_service=graph_service,
        extraction_service=extraction_service,
        qa_service=qa_service,
        coordinator=coordinator,
    )


def create_live_openai_runtime(settings: Settings) -> FixtureRuntime:
    """Use saved sponsor inputs with real Strands/OpenAI extraction and QA.

    This mode deliberately does not imply live TwelveLabs or Neo4j connectivity.
    It lets Developer C validate the model-backed handoffs while the other service
    adapters are still being implemented.
    """

    bundle = load_fixture_bundle()
    video_service = FixtureVideoIntelligenceService(bundle)
    graph_service = FixtureGraphService(bundle)
    provider = StrandsOpenAIProvider(settings)
    extraction_service = StrandsExtractionService(provider)
    qa_service = StrandsQuestionAnsweringService(
        provider=provider,
        video_service=video_service,
        graph_service=graph_service,
    )
    coordinator = SceneThreadCoordinator(
        video_service=video_service,
        extraction_service=extraction_service,
        graph_service=graph_service,
        mode="live",
        pipeline_version=settings.pipeline_version,
    )
    return FixtureRuntime(
        app_data_dir=settings.app_data_dir,
        bundle=bundle,
        video_service=video_service,
        graph_service=graph_service,
        extraction_service=extraction_service,
        qa_service=qa_service,
        coordinator=coordinator,
    )


def create_live_runtime(settings: Settings) -> FixtureRuntime:
    """Assemble the real TwelveLabs, OpenAI, and Neo4j service pipeline."""

    bundle = load_fixture_bundle()
    video_service = TwelveLabsClient(settings=settings)
    graph_service = Neo4jGraphService(Neo4jClient.from_settings(settings))
    provider = StrandsOpenAIProvider(settings)
    extraction_service = StrandsExtractionService(provider)
    qa_service = StrandsQuestionAnsweringService(
        provider=provider,
        video_service=video_service,
        graph_service=graph_service,
    )
    coordinator = SceneThreadCoordinator(
        video_service=video_service,
        extraction_service=extraction_service,
        graph_service=graph_service,
        mode="live",
        pipeline_version=settings.pipeline_version,
    )
    return FixtureRuntime(
        app_data_dir=settings.app_data_dir,
        bundle=bundle,
        video_service=video_service,
        graph_service=graph_service,
        extraction_service=extraction_service,
        qa_service=qa_service,
        coordinator=coordinator,
    )
