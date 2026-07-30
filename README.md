# SceneThread

SceneThread is a hackathon video intelligence agent that watches raw video, extracts scenes, entities, objects, speech, and events, then connects them into a searchable Neo4j context graph.

Users can upload a video, build a graph from its contents, and ask natural-language questions about what happened, who appeared, what objects were involved, and how events are connected.

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
- Test multiple video types before choosing a final demo

## Goal

Build something that watches, tags, and connects.
