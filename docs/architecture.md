# Architecture

SceneThread uses a Strands-coordinated pipeline with visible sponsor handoffs:

```text
Strands Pipeline Coordinator
  -> ingest_video tool
       -> deterministic TwelveLabs upload, segmentation, and indexing
  -> Strands Extraction Agent
       -> OpenAI structured GraphExtraction
  -> index_graph tool
       -> deterministic validation and Neo4j graph write
  -> Strands QA Agent
       -> TwelveLabs semantic search and safe Neo4j read tools
  -> AnswerResult with timestamp evidence
```

The coordinator exposes stage names, sponsor names, status, duration, and safe summaries
of tool results. It does not expose chain-of-thought, credentials, raw unrestricted
Cypher, or authority to commit arbitrary model-directed writes.

Fixture and live implementations must return the same internal contracts so each sponsor
adapter can be replaced without changing downstream modules.

See `scenethread_implementation-plan.md` for the complete architecture and delivery plan.
