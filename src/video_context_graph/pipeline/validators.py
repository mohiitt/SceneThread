"""Deterministic validation helpers for ingestion inputs."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from video_context_graph.contracts.video import IngestionRequest

SUPPORTED_VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".m4v", ".webm", ".avi"})
_SAFE_VIDEO_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")


class IngestionValidationError(ValueError):
    """Raised when a requested video source cannot be safely submitted."""


def validate_video_id(video_id: str) -> str:
    """Require a portable, single-component identifier before it reaches the filesystem."""
    if not _SAFE_VIDEO_ID.fullmatch(video_id) or ".." in video_id:
        raise IngestionValidationError("video_id must be a safe single path component")
    return video_id


def validate_ingestion_source(
    request: IngestionRequest,
    *,
    max_upload_bytes: int,
) -> Path | None:
    """Validate a request and return a local upload path when one is required."""
    if request.source_type == "url":
        parsed = urlparse(request.source_ref)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise IngestionValidationError("source_ref must be a direct HTTP(S) media URL")
        return None

    source_path = Path(request.source_ref).expanduser()
    if not source_path.is_file():
        raise IngestionValidationError(f"upload source does not exist: {source_path}")
    if source_path.suffix.lower() not in SUPPORTED_VIDEO_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_VIDEO_EXTENSIONS))
        raise IngestionValidationError(f"unsupported video extension; expected one of: {supported}")
    if source_path.stat().st_size > max_upload_bytes:
        raise IngestionValidationError(
            f"upload exceeds the configured {max_upload_bytes // (1024 * 1024)} MB limit"
        )
    return source_path


def ingestion_request_fingerprint(
    request: IngestionRequest,
    *,
    pipeline_version: str,
    source_path: Path | None,
) -> str:
    """Hash all inputs that can change an ingestion result or its search metadata."""
    source_identity: dict[str, str]
    if source_path is None:
        source_identity = {"kind": "url", "value": request.source_ref}
    else:
        source_identity = {
            "kind": "upload",
            "content_sha256": _file_sha256(source_path),
            "suffix": source_path.suffix.lower(),
        }
    payload = {
        "source": source_identity,
        "title": request.title,
        "domain_hint": request.domain_hint,
        "pipeline_version": pipeline_version,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
