# Parallel Implementation Start

Start parallel work only after the preparation changes are reviewed and committed. All
three teammates must begin from that same commit.

## Local setup for every teammate

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
pytest -q
ruff check .
python scripts/replay_pipeline.py
```

Each teammate fills their own ignored `.env`. Do not send credentials through Git, chat
prompts, logs, screenshots, or fixture files.

Expected fixture baseline:

```text
SceneThread fixture mode: validated
Segments: 2
Entities: 3
Events: 2
Search moments: 1
```

## Teammate A prompt: TwelveLabs and pipeline

```text
Read AGENTS.md, docs/interface_contracts.md, docs/architecture.md, and the implementation
plan. You own only src/video_context_graph/pipeline/,
src/video_context_graph/integrations/twelvelabs_client.py, scripts/bootstrap.py,
scripts/replay_pipeline.py, and related pipeline/TwelveLabs tests.

Implement VideoIntelligenceService using fixtures first, then TwelveLabs. Preserve the
frozen Pydantic contracts and public signatures. Do not edit contracts, graph, agents, UI,
app.py, config.py, pyproject.toml, fixtures, or shared documentation. Keep upload, polling,
segmentation, indexing, caching, retries, and state transitions deterministic. Fixture
mode must be explicit and live failures must not be reported as success.

Run your owned tests, Ruff, and MyPy. Report changed files, current fixture behavior, live
integration status, and any requested shared-file change without making that shared
change yourself.
```

## Teammate B prompt: Neo4j and graph

```text
Read AGENTS.md, docs/interface_contracts.md, docs/graph_schema.md, and the implementation
plan. You own only src/video_context_graph/graph/,
src/video_context_graph/integrations/neo4j_client.py, scripts/init_graph.py, and related
graph/Neo4j tests.

Implement GraphService against the frozen contracts. Start with graph mapping and mocked
or fixture-backed tests, then connect Neo4j. Writes must be deterministic, idempotent,
transactional, and parameterized. Read methods must use predefined parameterized Cypher,
enforce limits, and return compact JSON-compatible dictionaries. Do not edit contracts,
pipeline, agents, UI, app.py, config.py, pyproject.toml, fixtures, or shared documentation.

Run your owned tests, Ruff, and MyPy. Report changed files, graph counts, live Neo4j status,
and any requested shared-file change without making that shared change yourself.
```

## Teammate C prompt: Strands, OpenAI, QA, and UI

```text
Read AGENTS.md, docs/interface_contracts.md, docs/architecture.md, docs/demo_script.md,
and the implementation plan. You own app.py, src/video_context_graph/agents/,
src/video_context_graph/ui/, src/video_context_graph/integrations/strands_openai.py, and
related agent/UI tests. You are also the integration owner for shared-file requests.

Implement ExtractionService, QuestionAnsweringService, and PipelineCoordinator against
the frozen contracts. Use fixture data first, then connect Strands and OpenAI. Make the
Strands coordinator and sponsor handoffs visible through safe PipelineTrace events. Keep
TwelveLabs operations and Neo4j writes behind the other owners' deterministic services.
Never expose chain-of-thought, credentials, or unrestricted write Cypher.

Do not rewrite working pipeline or graph modules. Run your owned tests, Ruff, and MyPy.
Report changed files, fixture flow status, live OpenAI/Strands status, and integration
requests.
```

## First integration checkpoint

Each teammate hands their changes to the integration owner only after:

- Their implementation satisfies the assigned runtime-checkable Protocol.
- Their fixture-backed tests pass.
- They did not change frozen contracts or another teammate's owned files.
- `pytest -q`, `ruff check .`, and `mypy src` pass in their checkout.
- Live integration status is reported separately from fixture success.

At the checkpoint, the integration owner combines:

```text
VideoIntelligenceService.ingest_video
  -> ExtractionService.extract_graph
  -> GraphService.index_graph
  -> QuestionAnsweringService.answer_question
```

The first integrated result must show the same safe `PipelineTrace` stage names in fixture
and live modes.
