"""Reads a markdown record off disk.

Frontmatter is the data; the body is prose and is never parsed for meaning.
A record with no frontmatter is not a record, but reading one must not crash —
the validator's job is to report that, not to fall over on it.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator

import yaml

from vault.model import Record

FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


def read_record(path: Path | str, relative: str = "") -> Record:
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    match = FRONTMATTER.match(text)

    if match is None:
        return Record(path=path, frontmatter={}, body=text, relative=relative)

    body = text[match.end():]
    try:
        loaded = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return Record(
            path=path, frontmatter={}, body=body,
            relative=relative, malformed=True,
        )

    frontmatter = loaded if isinstance(loaded, dict) else {}
    return Record(path=path, frontmatter=frontmatter, body=body, relative=relative)


def walk(root: Path | str, exclude: list[str] | None = None) -> Iterator[Record]:
    """Yield every markdown record under `root`, skipping excluded paths."""
    root = Path(root)
    exclude = [e.rstrip("/\\").lower() for e in (exclude or [])]

    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root).as_posix()
        low = rel.lower()
        if any(low == e or low.startswith(e + "/") for e in exclude):
            continue
        yield read_record(path, relative=rel)
