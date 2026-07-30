"""Optional domain hints that refine extraction priorities without changing the schema."""

from __future__ import annotations

DOMAIN_PROFILES: dict[str, str] = {
    "Auto": (
        "Use domain-neutral extraction. Prioritize only salient people, places, objects, "
        "speech, on-screen text, and events supported by the video."
    ),
    "Meeting": (
        "Emphasize speakers, decisions, assignments, dates, documents, action items, and "
        "discussion topics."
    ),
    "Cooking": (
        "Emphasize ingredients, tools, transformations, actions, quantities when visible, "
        "and chronological preparation steps."
    ),
    "Sports": (
        "Emphasize players, teams, possessions, scores, significant actions, locations, "
        "and chronological play."
    ),
    "Story or movie": (
        "Emphasize characters, locations, props, dialogue meaning, motivations supported "
        "by evidence, and plot events."
    ),
    "Surveillance-style activity": (
        "Emphasize stable unnamed-person labels, movement, entrances, exits, objects, "
        "interactions, and timestamps. Do not infer identity."
    ),
    "Lecture or tutorial": (
        "Emphasize speakers, concepts, demonstrations, ordered steps, slides, written text, "
        "and conclusions."
    ),
    "Retail or product demo": (
        "Emphasize products, visible features, comparisons, prices when shown, interactions, "
        "and claims made in speech or text."
    ),
}


def list_domain_profiles() -> list[str]:
    return list(DOMAIN_PROFILES)


def get_domain_guidance(profile: str) -> str:
    return DOMAIN_PROFILES.get(profile, DOMAIN_PROFILES["Auto"])
