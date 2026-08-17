"""The edge index the query contract specifies, in miniature.

Both directions of every link field. An inverse is never written to a file —
`meeting.attended` is authored, `person.meetings` exists only here — so the two
directions cannot disagree.

The validator needs this to answer corpus questions (does this link resolve?
does anything supersede this document?). The app will need the same structure,
which is the main reason the validator is the first module rather than a
throwaway script.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from vault.model import Record

if TYPE_CHECKING:  # pragma: no cover
    from vault.schema import Schema

WIKILINK = re.compile(r"^\[\[(.+?)(?:\|.*)?\]\]$")


@dataclass(frozen=True)
class Edge:
    source: str
    field: str
    target: str
    inverse: str | None


@dataclass
class Index:
    records: list[Record]
    by_id: dict[str, Record] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)
    _id_counts: Counter = field(default_factory=Counter)
    _out: dict[str, list[Edge]] = field(default_factory=lambda: defaultdict(list))
    _in: dict[str, list[Edge]] = field(default_factory=lambda: defaultdict(list))

    @classmethod
    def build(cls, records: list[Record], schema: Schema) -> Index:
        index = cls(records=records)

        for record in records:
            if record.id:
                index._id_counts[record.id] += 1
                index.by_id.setdefault(record.id, record)

        for record in records:
            if not record.id or not record.type:
                continue
            fields = schema.fields_for(
                record.type, record.get(schema.subtype_field(record.type) or "")
            )
            for key, fdef in fields.items():
                if not fdef.is_link or not record.has(key):
                    continue
                for raw in _as_list(record.get(key)):
                    target = normalise(raw)
                    if not target:
                        continue
                    edge = Edge(record.id, key, target, fdef.inverse)
                    index.edges.append(edge)
                    index._out[record.id].append(edge)
                    index._in[target].append(edge)

        return index

    # -- traversal ---------------------------------------------------------

    def outgoing(self, record_id: str, field_name: str | None = None) -> list[Edge]:
        edges = self._out.get(record_id, [])
        return [e for e in edges if field_name is None or e.field == field_name]

    def incoming(self, record_id: str, field_name: str | None = None) -> list[Edge]:
        edges = self._in.get(record_id, [])
        return [e for e in edges if field_name is None or e.field == field_name]

    def inverse(self, record_id: str, inverse_name: str) -> list[Record]:
        """Records reachable backwards along a named inverse."""
        return [
            self.by_id[e.source]
            for e in self._in.get(record_id, [])
            if e.inverse == inverse_name and e.source in self.by_id
        ]

    # -- integrity ---------------------------------------------------------

    def duplicates(self) -> dict[str, int]:
        return {rid: n for rid, n in self._id_counts.items() if n > 1}

    def unresolved(self) -> list[tuple[str, str, str]]:
        return [
            (e.source, e.field, e.target)
            for e in self.edges
            if e.target not in self.by_id
        ]


def normalise(value: object) -> str | None:
    """`[[Jane Doe]]` and `Jane Doe` both resolve to `jane-doe`."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    match = WIKILINK.match(text)
    if match:
        text = match.group(1)
    text = text.rsplit("/", 1)[-1]
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or None


def _as_list(value: object) -> list:
    return value if isinstance(value, list) else [value]
