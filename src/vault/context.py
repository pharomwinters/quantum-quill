"""What a rule is given to decide with."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vault.model import Record
from vault.schema import Schema

STALE_AFTER_DAYS = 365
"""Not schema-declared. types.yaml says `stale` fires "beyond a threshold"
without naming one, so the number lives here and is overridable per run."""


@dataclass
class Context:
    schema: Schema
    records: list[Record] = field(default_factory=list)
    index: Any = None
    import_mode: bool = False
    root: Path | None = None
    exclude: list[str] = field(default_factory=list)
    today: dt.date = field(default_factory=dt.date.today)
    stale_after_days: int = STALE_AFTER_DAYS

    def is_excluded(self, relative: str) -> bool:
        low = relative.replace("\\", "/").lower()
        return any(
            low == e or low.startswith(e + "/")
            for e in (p.rstrip("/\\").lower() for p in self.exclude)
        )

    def by_id(self, record_id: str) -> Record | None:
        for record in self.records:
            if record.id == record_id:
                return record
        return None
