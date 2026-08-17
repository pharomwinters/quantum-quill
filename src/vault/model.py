"""Core value types shared across the package."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Severity(Enum):
    ERROR = "error"
    WARN = "warn"
    INFO = "info"

    def __lt__(self, other: Severity) -> bool:
        order = [Severity.ERROR, Severity.WARN, Severity.INFO]
        return order.index(self) < order.index(other)


@dataclass(frozen=True)
class Finding:
    """One rule firing against one target."""

    rule: str
    severity: Severity
    target: str
    message: str
    context: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        out = {
            "rule": self.rule,
            "severity": self.severity.value,
            "target": self.target,
            "message": self.message,
        }
        if self.context:
            out["context"] = self.context
        return out


@dataclass
class Record:
    """A markdown file with frontmatter, as read off disk."""

    path: Path
    frontmatter: dict[str, Any]
    body: str
    relative: str = ""
    malformed: bool = False

    @property
    def type(self) -> str | None:
        value = self.frontmatter.get("type")
        return value if isinstance(value, str) else None

    @property
    def id(self) -> str | None:
        value = self.frontmatter.get("id")
        return value if isinstance(value, str) else None

    @property
    def title(self) -> str:
        """Derived from the filename — 0 of 129 real records carried one."""
        declared = self.frontmatter.get("title")
        if isinstance(declared, str) and declared:
            return declared
        return self.path.stem

    def get(self, key: str, default: Any = None) -> Any:
        return self.frontmatter.get(key, default)

    def has(self, key: str) -> bool:
        """Present AND non-empty. A bare key with no value is not a value."""
        if key not in self.frontmatter:
            return False
        value = self.frontmatter[key]
        if value is None:
            return False
        if isinstance(value, (str, list, dict)) and len(value) == 0:
            return False
        return True
