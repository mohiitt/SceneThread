# Frozen Interface Contracts

These interfaces are frozen for the first parallel implementation pass. Teammates may add
private helpers inside their owned directories, but public names, arguments, and return
types below require team approval to change.

The executable definitions are in `src/video_context_graph/contracts/services.py` and the
Pydantic payloads are exported from `src/video_context_graph/contracts/`.

## Developer A: video intelligence

```python
ingest_video(request: IngestionRequest) -> IngestionResult
search_video_moments(request: SearchRequest) -> SearchResults
health_check() -> ServiceHealth
```

Fixture and live implementations must satisfy `VideoIntelligenceService`. The fixture
implementation reads the validated `SegmentCollection`; the live implementation performs
TwelveLabs upload, polling, segmentation, and Marengo indexing.

When segmentation succeeds but Marengo indexing fails, `ingest_video` still returns the
validated segments with `search_available=False`; `index_id` and `indexed_asset_id` are
then `None`. The coordinator may continue with graph extraction and writing.

## Developer B: graph

```python
index_graph(
    metadata: VideoGraphMetadata,
    extraction: GraphExtraction,
) -> GraphWriteResult

get_video_overview(video_id: str) -> dict
list_video_entities(video_id: str, entity_type: str | None = None, limit: int = 50) -> list[dict]
get_entity_timeline(video_id: str, entity_name: str, limit: int = 20) -> list[dict]
get_scene_details(video_id: str, scene_ids: list[str]) -> list[dict]
get_events_before_or_after(
    video_id: str,
    timestamp: float,
    direction: str,
    limit: int = 5,
) -> list[dict]
find_entity_connections(
    video_id: str,
    entity_a: str,
    entity_b: str,
    limit: int = 10,
) -> list[dict]
find_scenes_overlapping_moments(
    video_id: str,
    moments: SearchResults,
) -> list[dict]
health_check() -> ServiceHealth
```

Implementations must satisfy `GraphService`. Writes accept only validated contracts and
use fixed, parameterized Cypher. Read methods return compact JSON-compatible dictionaries.

## Developer C: extraction, QA, coordinator, and UI

```python
extract_graph(
    *,
    title: str,
    domain_hint: str,
    segments: SegmentCollection,
) -> GraphExtraction

answer_question(*, video_id: str, question: str) -> AnswerResult
process_video(request: IngestionRequest) -> PipelineRunResult
```

Implementations must satisfy `ExtractionService`, `QuestionAnsweringService`, and
`PipelineCoordinator`.

The Strands coordinator calls the services in this fixed order:

```text
VideoIntelligenceService.ingest_video
  -> ExtractionService.extract_graph
  -> GraphService.index_graph
```

Question answering may call TwelveLabs search and the safe graph reads. It may not call
graph writes.

## Fixture boundary

Run:

```bash
python scripts/replay_pipeline.py
```

This command validates all three shared fixture files and clearly reports fixture mode. It
does not claim that live sponsor calls, Neo4j persistence, or QA have succeeded.

Fixture and live paths must produce the same Pydantic return types and the same
`PipelineTrace` stage names.

## Current implementation status

All three service groups are implemented and integrated:

- `TwelveLabsClient` implements live ingestion, polling, segmentation, indexing, caching,
  resume state, semantic search, and health checks.
- `Neo4jGraphService` implements transactional idempotent writes, safe reads, health
  checks, schema initialization, and bounded visualization data.
- Fixture and live Strands/OpenAI extraction and QA services are wired through
  `SceneThreadCoordinator` and the Streamlit runtime factories.

The contracts remain single-video: `SearchRequest`, graph reads, and QA require one
`video_id`. Collection-level search requires an approved contract extension.

## Parallel editing rule

- Developer A edits pipeline and TwelveLabs-owned paths.
- Developer B edits graph and Neo4j-owned paths.
- Developer C edits agents, UI, Strands/OpenAI, and shared integration paths.
- Only the integration owner changes contracts, `pyproject.toml`, `.env.example`,
  `AGENTS.md`, or shared documentation after this freeze point.
- Every agent runs its owned tests before handing work to the integration owner.
