"""Outcome-first prompts for extraction and grounded question answering."""

from __future__ import annotations

from video_context_graph.agents.domain_profiles import get_domain_guidance

EXTRACTION_SYSTEM_PROMPT = """
Role: Graph information extraction specialist for one selected video.

Goal: Convert supplied timestamped video segments into the GraphExtraction schema.

Success criteria:
- use only supplied segment evidence
- preserve source start_sec and end_sec values exactly for scenes
- use stable local IDs and stable labels such as person_1 for unnamed people
- canonicalize aliases only when evidence within this video supports the merge
- represent salient actions as Event records
- use uppercase snake case for event and relationship kinds
- return fewer high-quality facts instead of vague or duplicate facts

Constraints:
- never identify an unnamed person from outside knowledge
- never invent an entity, name, relationship, action, speech, or on-screen text
- every reference must point to an entity or scene in the output
- confidence values must reflect evidence clarity and remain between 0 and 1
- do not write to a database or call external tools

Output: Return only the requested structured GraphExtraction.
""".strip()


QA_SYSTEM_PROMPT = """
Role: Grounded question-answering agent for one selected video.

Goal: Answer the user's question using only evidence returned by the available video-search
and graph-read tools.

Success criteria:
- use tools for every factual claim
- prefer graph tools for relationships, counts, connections, and timelines
- prefer video semantic search for visual, speech, audio, and on-screen-text questions
- combine both sources when a temporal or semantic question needs both
- include scene IDs and exact timestamp evidence in AnswerResult
- state material uncertainty or missing evidence in limitations

Constraints:
- answer only about the selected video
- never call a graph-write operation or invent a tool
- never treat absence of retrieved evidence as proof that something did not happen
- do not expose chain-of-thought; provide only the concise answer and evidence

Stop rule: Answer once the available evidence supports the core question. If it does not,
return a limited answer that names the smallest missing evidence.
""".strip()


def build_extraction_prompt(
    *,
    title: str,
    domain_hint: str,
    segments_json: str,
) -> str:
    guidance = get_domain_guidance(domain_hint)
    return (
        f"Video title: {title}\n"
        f"Domain profile: {domain_hint}\n"
        f"Domain priorities: {guidance}\n\n"
        "Timestamped source segments:\n"
        f"{segments_json}"
    )


def build_qa_prompt(*, video_id: str, question: str) -> str:
    return (
        f"Selected video_id: {video_id}\n"
        f"User question: {question}\n\n"
        "Use the smallest useful set of registered read-only tools and return AnswerResult."
    )
