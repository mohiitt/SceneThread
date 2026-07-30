"""Deterministic video identity helpers."""

from __future__ import annotations

from hashlib import sha256


def generate_video_id(file_bytes: bytes, pipeline_version: str = "v1") -> str:
    digest = sha256(file_bytes + pipeline_version.encode("utf-8")).hexdigest()
    return digest[:16]
