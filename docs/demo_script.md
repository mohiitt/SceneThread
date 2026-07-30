# Demo Script

The final video and questions will be chosen after candidate videos have been tested, but
the sponsor handoff sequence is fixed:

1. Upload or select a prepared video.
2. Show the Strands Pipeline Coordinator calling the TwelveLabs ingestion tool.
3. Show the handoff from timestamped TwelveLabs scenes to the Strands Extraction Agent.
4. Show OpenAI returning a validated structured graph extraction.
5. Show the coordinator calling the deterministic Neo4j indexing tool.
6. Open the graph and focus on a repeated entity, event, or object.
7. Ask graph-only, semantic-search, and combined temporal questions.
8. Show which safe TwelveLabs and Neo4j tools the Strands QA Agent used.
9. Display the final answer with scene IDs and timestamp evidence.

The visible trace should contain sponsor and stage names, statuses, durations, and compact
result summaries. It must not display credentials, raw prompts containing secrets, or
private chain-of-thought.
