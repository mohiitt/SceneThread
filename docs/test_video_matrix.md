# Test Video Matrix

Track candidate videos, extraction quality, graph usefulness, QA grounding, processing time, and estimated API usage.

Also record whether the demo trace clearly shows each handoff:

- Strands coordinator to TwelveLabs ingestion.
- TwelveLabs evidence to the OpenAI-backed Extraction Agent.
- Validated graph extraction to deterministic Neo4j indexing.
- Strands QA Agent to TwelveLabs search and safe Neo4j reads.
- Tool evidence to the final timestamped answer.
