# Demo Script

## Current verified walkthrough

1. Start Streamlit and select **Full live services**.
2. Confirm green readiness results for TwelveLabs, OpenAI, and Neo4j.
3. Upload a short MP4 (or use a direct URL), then enter a safe `video_id`, title, shared
   `store_id`, physical `camera_id`, and timezone-aware recording start.
4. Run the full pipeline for each staged recording.
5. Explain the visible trace:
   - the coordinator starts ingestion;
   - TwelveLabs returns timestamped scenes and a searchable indexed asset;
   - the Strands Extraction Agent returns a validated OpenAI `GraphExtraction`;
   - deterministic Neo4j indexing writes the graph.
6. Point out scene, entity, event, node, and relationship counts.
7. Open **Graph Explorer** and inspect the extraction that was written through
   `GraphService`.
8. Open **Ask**, choose **Recording collection**, and select the store, optional cameras,
   and recording-time range.
9. Ask a cross-video question so the QA agent discovers the bounded collection, searches
   its TwelveLabs assets, and combines the moments with safe Neo4j reads.
10. Show the answer confidence, limitations if present, and timestamp evidence cards.

The pipeline trace shows stage/sponsor names, statuses, durations, and compact result
counts. The current UI does not expose the QA agent's internal tool-call trace or private
chain-of-thought; grounding is demonstrated through returned evidence and saved search
artifacts.

## Verified fallback

Switch to **Fixture preview** to demonstrate the same contracts and pipeline stage order
without external API calls. State clearly that this mode uses saved evidence.

The currently verified live sample is the W3C Sintel trailer. Collection search is
implemented but the staged retail footage has not yet been recorded and validated; use
the checklist in `docs/surveillance_demo.md`.
