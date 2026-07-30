# SceneThread Agent Guide

## Project Goal

SceneThread is a Python 3.11 Streamlit application that ingests video, extracts scenes, entities, speech, objects, events, and tags, stores them in a Neo4j context graph, and answers natural-language questions with timestamped evidence.

## Architecture

- Streamlit provides the demo UI.
- TwelveLabs handles video upload, segmentation, indexing, and semantic moment search.
- A code-defined coordinator visibly sequences sponsor handoffs and emits a safe trace.
- TwelveLabs ingestion and Neo4j indexing remain deterministic operations behind frozen
  service interfaces; Strands-compatible tool wrappers expose those boundaries.
- Strands Agents with OpenAI handle graph normalization and question answering.
- Pydantic models in `src/video_context_graph/contracts/` define shared interfaces.
- Neo4j writes and reads use deterministic, parameterized code.
- Local JSON artifacts and fixtures support offline development.

## Directory Ownership

- Shared: `AGENTS.md`, `README.md`, `.env.example`, `pyproject.toml`, `src/video_context_graph/config.py`, and `src/video_context_graph/contracts/`.
- Pipeline and TwelveLabs: `src/video_context_graph/pipeline/`, `src/video_context_graph/integrations/twelvelabs_client.py`, `scripts/bootstrap.py`, `scripts/replay_pipeline.py`, and related tests.
- Graph and Neo4j: `src/video_context_graph/graph/`, `src/video_context_graph/integrations/neo4j_client.py`, `scripts/init_graph.py`, and related tests.
- Agents and UI: `app.py`, `src/video_context_graph/agents/`, `src/video_context_graph/ui/`, `src/video_context_graph/integrations/strands_openai.py`, and related tests.
- Fixtures: `tests/fixtures/` are shared; coordinate schema changes before editing.
- Frozen cross-team signatures: `docs/interface_contracts.md` and
  `src/video_context_graph/contracts/services.py`.

## Contracts

- Do not change public contract field names or types without team approval.
- Do not change the frozen service signatures without team approval.
- Validate confidence values between `0` and `1`.
- Ensure timestamps satisfy `0 <= start_sec < end_sec`.
- Keep scene ordinals unique and sorted.
- Every referenced scene ID and entity ID must exist.
- Preserve source timestamps exactly when normalizing model output.
- Use stable labels such as `person_1` for unnamed people; do not invent names.

## Commands

- Install: `python -m pip install -e ".[dev]"`
- Run app: `streamlit run app.py`
- Test: `pytest -q`
- Lint: `ruff check .`
- Environment check: `python -m dotenv run -- python scripts/health_check.py`
- Neo4j schema and connectivity: `python scripts/init_graph.py`
- Fixture replay: `python scripts/replay_pipeline.py`

## Development Rules

- Inspect existing code before adding helpers or abstractions.
- Keep edits within the assigned ownership area.
- Do not rewrite unrelated working code.
- Do not change public interfaces without approval.
- Run relevant tests before finishing.
- Use fixtures when live API credentials are unavailable.
- Never log API keys, Neo4j passwords, or other secrets.
- Fail clearly when credentials or required external resources are missing.
- Avoid fake success fallbacks; fixture mode must be explicit.
- Preserve a safe, user-visible execution trace showing the Strands stage and sponsor
  handoff without exposing chain-of-thought.
- Preserve collection-level QA: recording discovery is scoped by `RecordingScope`, each
  sponsor search remains bounded per video, and every cross-video citation carries its
  `video_id`.
- Keep anonymous person labels video-local; never infer biometric identity across clips.
