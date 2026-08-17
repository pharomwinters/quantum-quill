from pathlib import Path
from typing import Any

import pytest

from vault.model import Record
from vault.schema import Schema

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def schema_dir() -> Path:
    """Directory holding types.yaml and Folder-layout.yaml."""
    return REPO_ROOT


@pytest.fixture(scope="session")
def schema(schema_dir) -> Schema:
    return Schema.load(schema_dir)


def make_record(name: str = "Thing", folder: str = "", **frontmatter: Any) -> Record:
    """Build a record without touching disk."""
    rel = f"{folder}/{name}.md" if folder else f"{name}.md"
    return Record(
        path=Path(rel),
        frontmatter=frontmatter,
        body="",
        relative=rel,
    )


def rule_ids(findings) -> list[str]:
    return [f.rule for f in findings]
