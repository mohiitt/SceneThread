# Graph Schema

The implemented graph is domain-neutral and uses five node labels:

- `Video` — source metadata, summary, duration, pipeline status, sponsor IDs,
  `store_id`, `camera_id`, `recorded_at`, and `search_available`.
- `Scene` — ordinal, exact source timestamps, summary, speech, text, and confidence.
- `Entity` — video-scoped canonical name, aliases, type, description, and confidence.
- `Event` — video-scoped type, description, timestamps, and confidence.
- `Tag` — normalized reusable scene label.

Relationships are fixed:

```text
(Video)-[:HAS_SCENE]->(Scene)
(Scene)-[:NEXT_SCENE]->(Scene)
(Scene)-[:HAS_EVENT]->(Event)
(Entity)-[:APPEARS_IN]->(Scene)
(Entity)-[:PARTICIPATES_IN {role}]->(Event)
(Entity)-[:INVOLVED_IN {role}]->(Event)
(Scene)-[:HAS_TAG]->(Tag)
(Entity)-[:RELATED_TO {kind, description, scene_id, confidence}]->(Entity)
```

The Strands Extraction Agent returns a validated `GraphExtraction`. Deterministic mapping
creates video-scoped SHA-256-derived identifiers, and `GraphWriter` performs one
transaction using fixed parameterized `MERGE` queries. The model does not generate write
Cypher or receive database credentials.

`scripts/init_graph.py` idempotently installs ten uniqueness constraints/index
statements. Safe read queries and the bounded visualization payload builder live under
`src/video_context_graph/graph/`.
