# Architecture

## Implemented full-live path

```text
Streamlit
  -> code-defined SceneThreadCoordinator
       -> VideoIntelligenceService
            -> TwelveLabs asset upload, Pegasus segmentation, Marengo indexing
       -> StrandsExtractionService
            -> Strands Agent + OpenAI structured GraphExtraction
       -> GraphService
            -> validated mapping + parameterized Neo4j transaction

Question
  -> StrandsQuestionAnsweringService
       -> Strands Agent + OpenAI
       -> bounded TwelveLabs semantic-search tool
       -> seven bounded Neo4j read tools
  -> validated AnswerResult with timestamp evidence
```

The coordinator fixes ingestion → extraction → indexing in deterministic Python. It emits
`PipelineTrace` events for Strands-facing stages and TwelveLabs, OpenAI, and Neo4j
handoffs. `ingest_video` and `index_graph` also exist as Strands-compatible tool wrappers,
but the current coordinator calls the frozen service interfaces directly; it is not
itself a model-driven Strands agent.

Models never receive Neo4j credentials or unrestricted write access. Writes use fixed
parameterized Cypher. QA receives only the bounded tools in
`src/video_context_graph/agents/tools.py`.

## Runtime modes

- `fixture`: all services use validated saved data and make no sponsor calls.
- `live_openai`: saved TwelveLabs/local graph adapters with real Strands/OpenAI.
- `live`: real TwelveLabs, Strands/OpenAI, and Neo4j.

All modes use the same Pydantic contracts. The Streamlit session keeps the selected
runtime and generated graph state across normal tab reruns.

## Persistence

- Pipeline state and raw provider artifacts:
  `data/runs/<video_id>/`.
- Persistent graph: Neo4j AuraDB.
- TwelveLabs asset/index identifiers: pipeline state and the Neo4j `Video` node.

## Current boundary

Ingestion and QA operate on one `video_id` at a time. Multi-day or multi-camera
surveillance needs collection metadata, absolute recording time, search across several
assets, and an explicitly confidence-bounded cross-video entity-resolution layer. Those
remain stretch work; see `docs/surveillance_demo.md`.
