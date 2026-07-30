# SceneThread

SceneThread is a hackathon video intelligence agent that watches raw video, extracts scenes, entities, objects, speech, and events, then connects them into a searchable Neo4j context graph.

Users can upload a video, build a graph from its contents, and ask natural-language questions about what happened, who appeared, what objects were involved, and how events are connected.

## Agent Pipeline

Strands makes each sponsor handoff visible while deterministic Python performs external
operations safely:

```text
Strands Pipeline Coordinator
  -> TwelveLabs ingestion tool
  -> Strands Extraction Agent using OpenAI
  -> Neo4j indexing tool
  -> Strands QA Agent using TwelveLabs search and safe Neo4j reads
  -> grounded answer with timestamp evidence
```

The interface will show a concise execution trace naming each stage and sponsor. It will
not expose private chain-of-thought.

The first-pass cross-team method signatures are frozen in
[`docs/interface_contracts.md`](docs/interface_contracts.md).
Copy-ready teammate setup and Codex scopes are in
[`docs/parallel_start.md`](docs/parallel_start.md).

## Stack

- TwelveLabs — video understanding
- OpenAI — reasoning and structured extraction
- Neo4j — context graph storage
- Strands Agents — workflow orchestration
- Streamlit — demo UI

## Core Features

- Upload and analyze videos
- Extract scenes, entities, tags, objects, and events
- Store relationships in Neo4j
- Ask questions over the video graph
- Show Strands orchestration and sponsor handoffs in the pipeline trace
- Test multiple video types before choosing a final demo

## Goal

Build something that watches, tags, and connects.
