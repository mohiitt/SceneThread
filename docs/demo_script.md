# Demo Script

## Current verified walkthrough

1. Start Streamlit and select **Full live services**.
2. Confirm green readiness results for TwelveLabs, OpenAI, and Neo4j.
3. Choose URL input, enter a short direct media URL, a safe `video_id`, and a title.
4. Run the full pipeline.
5. Explain the visible trace:
   - the coordinator starts ingestion;
   - TwelveLabs returns timestamped scenes and a searchable indexed asset;
   - the Strands Extraction Agent returns a validated OpenAI `GraphExtraction`;
   - deterministic Neo4j indexing writes the graph.
6. Point out scene, entity, event, node, and relationship counts.
7. Open **Graph Explorer** and inspect the extraction that was written through
   `GraphService`.
8. Open **Ask** and request a chronological summary with timestamp evidence.
9. Ask one visual or semantic question so the QA agent can combine TwelveLabs search with
   safe Neo4j reads.
10. Show the answer confidence, limitations if present, and timestamp evidence cards.

The pipeline trace shows stage/sponsor names, statuses, durations, and compact result
counts. The current UI does not expose the QA agent's internal tool-call trace or private
chain-of-thought; grounding is demonstrated through returned evidence and saved search
artifacts.

## Verified fallback

Switch to **Fixture preview** to demonstrate the same contracts and pipeline stage order
without external API calls. State clearly that this mode uses saved evidence.

The currently verified live sample is the W3C Sintel trailer. A staged retail-surveillance
scenario is a candidate, but cross-video/day-range questions require the work listed in
`docs/surveillance_demo.md`.
