# Test Video Matrix

Record extraction quality, graph usefulness, QA grounding, processing time, and sponsor
handoff visibility before choosing the final demo.

| Candidate | Domain | Mode | Scenes | Entities | Events | Graph | QA | Status |
|---|---|---|---:|---:|---:|---|---|---|
| Planning meeting fixture | Meeting | Fixture | 2 | 3 | 2 | Validated local adapter | Grounded saved answer | Passing |
| W3C Sintel trailer | Story/movie | Full live | 6 | 6 | 7 | 38 nodes / 68 relationships in Neo4j | 98% chronological answer with 6 citations | Passing |
| Staged multi-day retail footage | Surveillance/retail | Not run | — | — | — | Needs collection metadata | Needs cross-video search | Candidate |

For each future candidate, verify:

- Coordinator → TwelveLabs ingestion handoff.
- Timestamped TwelveLabs evidence → Strands/OpenAI extraction handoff.
- Validated extraction → deterministic Neo4j indexing handoff.
- At least one graph-grounded question.
- At least one semantic video-search question.
- Timestamp evidence and appropriate limitations/abstention.
- No invented identity for unnamed people.

The 2026-07-30 Sintel run used a 52.2-second direct URL. TwelveLabs completed in 51.55s,
OpenAI extraction in 24.56s, and Neo4j indexing in 1.38s. Eight semantic-search result
items were saved. Timings and model outputs vary by input and provider conditions.
