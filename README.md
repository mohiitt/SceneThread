# SceneThread

SceneThread is a Python 3.11 Streamlit video-intelligence application. It sends a video
through TwelveLabs segmentation and semantic indexing, uses Strands Agents with OpenAI
to normalize the timestamped evidence into a validated graph, writes that graph to
Neo4j, and answers natural-language questions with timestamp citations.

## Implemented pipeline

```text
Code-defined Pipeline Coordinator
  -> deterministic TwelveLabs ingestion, segmentation, and Marengo indexing
  -> Strands Extraction Agent using OpenAI structured output
  -> deterministic, parameterized Neo4j graph indexing
  -> Strands QA Agent using TwelveLabs search and safe Neo4j reads
  -> AnswerResult with timestamp evidence
```

The ingestion and indexing boundaries also have Strands-compatible tool wrappers. The
pipeline coordinator itself is deterministic Python: it fixes the stage order and emits
a safe trace showing sponsor, status, duration, and compact counts. The UI does not
expose model chain-of-thought.

## Current capabilities

- Explicit fixture-only preview with no sponsor API calls.
- Hybrid mode with live Strands/OpenAI over saved sponsor data.
- Full-live direct-URL ingestion through TwelveLabs, OpenAI, and Neo4j.
- Pegasus timestamped segmentation and Marengo semantic search.
- Strict Pydantic validation for scenes, entities, events, and relationships.
- Idempotent Neo4j nodes and relationships through fixed parameterized Cypher.
- Grounded single-video and collection QA using ten bounded, read-only tools.
- Cross-video discovery by store, camera, absolute time window, or explicit video IDs.
- Evidence with video/camera provenance, relative timestamps, and absolute clock times.
- Confidence, limitations, partial-search failures, and safe pipeline traces.
- Session-backed graph tables and a candidate-video Test Lab.
- Local job and provider-artifact caching under `data/runs/<video_id>/`.

## Quick start

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
```

Fill the ignored `.env`. Never commit or paste credentials into logs.

For full-live mode, initialize the idempotent Neo4j schema and start the app:

```bash
python scripts/init_graph.py
streamlit run app.py
```

The sidebar offers three modes:

1. **Fixture preview** — saved TwelveLabs, extraction, search, and graph data; no external
   calls.
2. **Live OpenAI + saved sponsor data** — real Strands/OpenAI extraction and QA with
   saved/local TwelveLabs and graph adapters.
3. **Full live services** — real TwelveLabs, Strands/OpenAI, and Neo4j calls.

Full-live URL input must be a publicly reachable direct HTTP(S) media URL, not a YouTube,
Vimeo, Google Drive preview, or other webpage. Browser uploads are persisted under
`data/uploads/<video_id>/` before ingestion. The configured MVP duration limit is 15
minutes.

For surveillance footage, give every clip the same stable `store_id`, the physical
`camera_id`, and its timezone-aware recording start. After ingesting multiple clips,
choose **Recording collection** in **Ask** and optionally filter cameras and an absolute
time range.

## Verification

```bash
pytest -q
ruff check .
mypy src
python scripts/replay_pipeline.py
```

Credential-gated Neo4j verification:

```bash
RUN_NEO4J_LIVE=1 pytest -q tests/integration/test_neo4j_live.py
```

The last full-live browser validation on 2026-07-30 used the 52-second W3C Sintel
trailer. It produced 6 scenes, 6 entities, 7 events, 38 Neo4j nodes, 68 relationships,
eight saved TwelveLabs search results, and a six-citation chronological QA answer. This
is a recorded validation result, not a fixed output for other videos.

## Current scope and limitations

- Collection QA discovers a bounded set of indexed videos and searches each searchable
  TwelveLabs asset; it reports unsearchable videos and per-video failures.
- Anonymous labels remain video-local. Cross-video face/person re-identification is not
  implemented, so the system must not assume `person_1` in two clips is the same person.
- Day-long recordings should be divided into clips below the configured 15-minute limit.
- The UI graph explorer currently renders validated extraction tables; the graph service
  also provides a bounded visualization payload builder, but the interactive PyVis view
  is not wired into Streamlit.
- Fixture replay validates contracts and saved data; it does not claim live sponsor
  success.
- SceneThread describes unnamed people with stable anonymous labels and does not perform
  face recognition or biometric identification.

The proposed multi-day retail-surveillance demo and suitable staged/public data options
are documented in [`docs/surveillance_demo.md`](docs/surveillance_demo.md).

## Project references

- [`docs/architecture.md`](docs/architecture.md) — implemented architecture and modes.
- [`docs/interface_contracts.md`](docs/interface_contracts.md) — frozen service boundaries.
- [`docs/graph_schema.md`](docs/graph_schema.md) — Neo4j nodes and relationships.
- [`docs/demo_script.md`](docs/demo_script.md) — current demo walkthrough.
- [`docs/test_video_matrix.md`](docs/test_video_matrix.md) — candidate-video results.
- [`docs/parallel_start.md`](docs/parallel_start.md) — historical three-developer handoff.
- [`scenethread_implementation-plan.md`](scenethread_implementation-plan.md) — complete
  design, progress, and remaining roadmap.
