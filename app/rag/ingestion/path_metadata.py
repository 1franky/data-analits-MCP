"""Derive document metadata from key=value directory segments in its path."""

import re
from pathlib import PurePosixPath
from typing import NamedTuple

_SEGMENT_PATTERN = re.compile(r"^[a-z][a-z0-9_]*=[A-Za-z0-9][A-Za-z0-9_.\-]*$")
_RECOGNIZED_KEYS = {"connection", "domain", "type", "version", "title"}

_DEFAULT_DOCUMENT_TYPE_BY_EXTENSION = {
    ".md": "documentation",
    ".txt": "documentation",
    ".sql": "sql_reference",
    ".json": "structured_reference",
    ".yaml": "structured_reference",
    ".yml": "structured_reference",
}


class PathDerivedMetadata(NamedTuple):
    """Metadata fields derivable from a document's relative path alone."""

    connection_id: str | None
    domain: str | None
    document_type: str
    version: str | None
    title: str


def derive_metadata_from_path(relative_path: str) -> PathDerivedMetadata:
    """Parse `key=value` directory segments, ignoring any that do not match."""
    path = PurePosixPath(relative_path)
    segments: dict[str, str] = {}
    for part in path.parts[:-1]:
        if _SEGMENT_PATTERN.match(part) is None:
            continue
        key, _, value = part.partition("=")
        if key in _RECOGNIZED_KEYS:
            segments[key] = value

    extension = path.suffix.lower()
    document_type = segments.get("type") or _DEFAULT_DOCUMENT_TYPE_BY_EXTENSION.get(
        extension,
        "documentation",
    )
    title = segments.get("title") or _default_title(path.stem)

    return PathDerivedMetadata(
        connection_id=segments.get("connection"),
        domain=segments.get("domain"),
        document_type=document_type,
        version=segments.get("version"),
        title=title,
    )


def _default_title(stem: str) -> str:
    """Turn a filename stem into a human-readable title-cased fallback."""
    words = stem.replace("_", " ").replace("-", " ").split()
    return " ".join(word.capitalize() for word in words) if words else stem
