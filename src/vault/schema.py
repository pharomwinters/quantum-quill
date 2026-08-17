"""Loads the two schema files into one resolved object.

`Folder-layout.yaml` says where a record lives; `types.yaml` says what it is.
Nothing else in the package reads either file directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from vault.model import Severity

TYPES_FILE = "types.yaml"
LAYOUT_FILE = "Folder-layout.yaml"

LINK_TYPES = {"link", "list[link]"}


@dataclass(frozen=True)
class FieldDef:
    key: str
    type: Any
    required: bool = False
    on_create: bool = False
    derived: bool = False
    of: str | None = None
    to: list[str] = field(default_factory=list)
    inverse: str | None = None

    @property
    def is_link(self) -> bool:
        if isinstance(self.type, list):
            return "link" in self.type
        return self.type in LINK_TYPES

    @property
    def is_list(self) -> bool:
        return isinstance(self.type, str) and self.type.startswith("list[")

    @property
    def is_date(self) -> bool:
        # `type` may be a list for union fields, so compare rather than look up.
        return self.type == "date"


@dataclass(frozen=True)
class TypeDef:
    id: str
    name: str
    kind: str
    subtype: str | None
    fields: dict[str, FieldDef]
    provenance: str


@dataclass(frozen=True)
class FolderDef:
    id: str
    jd: str
    name: str
    area: str
    zone: str
    types: list[str]
    sensitive: bool = False


@dataclass(frozen=True)
class Schema:
    types: dict[str, TypeDef]
    rules: dict[str, Severity]
    universal: dict[str, FieldDef]
    vocabularies: dict[str, list[str]]
    subtype_adds: dict[str, dict[str, dict[str, FieldDef]]]
    folders: dict[str, FolderDef]
    routing: dict[str, str]
    lifecycle: dict[str, Any]
    containers: list[str]
    imports: dict[str, Any]
    raw_types: dict[str, Any] = field(default_factory=dict, repr=False)
    raw_layout: dict[str, Any] = field(default_factory=dict, repr=False)

    # -- accessors ---------------------------------------------------------

    def required(self, type_id: str) -> set[str]:
        """Fields that must be present and non-empty. Excludes derived ones."""
        keys = {k for k, f in self.universal.items() if f.required and not f.derived}
        type_def = self.types.get(type_id)
        if type_def:
            keys |= {k for k, f in type_def.fields.items() if f.required}
        return keys

    def required_on_create(self, type_id: str) -> set[str]:
        type_def = self.types.get(type_id)
        if not type_def:
            return set()
        return {k for k, f in type_def.fields.items() if f.on_create}

    def vocabulary(self, name: str) -> list[str]:
        return self.vocabularies.get(name, [])

    def subtype_field(self, type_id: str) -> str | None:
        type_def = self.types.get(type_id)
        return type_def.subtype if type_def else None

    def route(self, key: str) -> str | None:
        """Folder id for a subtype value (or a type id with no subtype)."""
        return self.routing.get(key)

    def fields_for(self, type_id: str, subtype: str | None = None) -> dict[str, FieldDef]:
        """Type fields plus whatever the subtype value adds."""
        type_def = self.types.get(type_id)
        if not type_def:
            return dict(self.universal)
        merged = {**self.universal, **type_def.fields}
        if subtype and type_def.subtype:
            merged.update(self.subtype_adds.get(type_def.subtype, {}).get(subtype, {}))
        return merged

    def link_fields(self, type_id: str) -> dict[str, list[str]]:
        return {
            key: f.to
            for key, f in self.fields_for(type_id).items()
            if f.is_link
        }

    def is_derivable(self, type_id: str, key: str) -> bool:
        """True if `import.derived` declares where this field's value comes from.

        Used only in --import mode: a legacy record missing `note_type` is not
        a defect if the schema already says the value is a constant.
        """
        declared = {d["field"] for d in self.imports.get("derived", [])}
        return f"{type_id}.{key}" in declared or f"*.{key}" in declared

    def machine(self, type_id: str) -> dict[str, Any] | None:
        for m in self.lifecycle.get("machines", []):
            if m["type"] == type_id:
                return m
        return None

    # -- placement ---------------------------------------------------------

    def folder_for_path(self, relative: str) -> FolderDef | None:
        """Deepest path segment that names a known category.

        `11.01 Paint Line` is an item folder, not a category, so it is skipped
        and `11 Work Projects` is returned.
        """
        by_jd = {f.jd: f for f in self.folders.values()}
        found = None
        for segment in Path(relative).parts[:-1]:
            token = segment.split(" ", 1)[0]
            if token in by_jd:
                found = by_jd[token]
        return found

    def expected_folder(self, record: Any) -> str | None:
        """Folder id a record should live in, or None when unconstrained.

        Returns None for container-relative routing — a document with
        `attaches_to`, or any world-entry — because those live inside another
        record's folder rather than in a category.
        """
        type_id = record.type
        if not type_id or type_id not in self.types:
            return None
        if record.has("attaches_to") or type_id == "world-entry":
            return None

        for explicit in self.routing_overrides:
            if explicit.get("type") != type_id or "map" not in explicit:
                continue
            return explicit["map"].get(record.get(explicit["routes_by"]))

        if type_id == "area":
            return record.id

        subtype_field = self.subtype_field(type_id)
        key = record.get(subtype_field) if subtype_field else type_id
        return self.route(key) if isinstance(key, str) else None

    @property
    def routing_overrides(self) -> list[dict[str, Any]]:
        return self.raw_types.get("routing", {}).get("explicit", [])

    def subtype_add_keys(self, subtype_field: str) -> set[str]:
        """Every field any value of this vocabulary contributes."""
        return {
            key
            for adds in self.subtype_adds.get(subtype_field, {}).values()
            for key in adds
        }

    # -- loading -----------------------------------------------------------

    @classmethod
    def load(cls, directory: Path | str) -> Schema:
        root = Path(directory)
        return cls.from_dicts(_read(root / TYPES_FILE), _read(root / LAYOUT_FILE))

    @classmethod
    def from_dicts(cls, t_raw: dict[str, Any], l_raw: dict[str, Any]) -> Schema:
        universal = {f["key"]: _field(f) for f in t_raw["universal"]}

        types: dict[str, TypeDef] = {}
        for t in t_raw["types"]:
            types[t["id"]] = TypeDef(
                id=t["id"],
                name=t["name"],
                kind=t.get("kind", ""),
                subtype=t.get("subtype"),
                fields={f["key"]: _field(f) for f in t.get("fields", [])},
                provenance=t.get("provenance", "provisional"),
            )

        vocabularies: dict[str, list[str]] = {}
        subtype_adds: dict[str, dict[str, dict[str, FieldDef]]] = {}
        for name, voc in t_raw["vocabularies"].items():
            values, adds = [], {}
            for entry in voc["values"]:
                if isinstance(entry, dict):
                    values.append(entry["id"])
                    if entry.get("adds"):
                        adds[entry["id"]] = {
                            f["key"]: _field(f) for f in entry["adds"]
                        }
                else:
                    values.append(entry)
            vocabularies[name] = values
            if adds:
                subtype_adds[name] = adds

        folders: dict[str, FolderDef] = {}
        routing: dict[str, str] = {}
        for area in l_raw["areas"]:
            for cat in area.get("categories", []):
                folders[cat["id"]] = FolderDef(
                    id=cat["id"],
                    jd=cat["jd"],
                    name=cat["name"],
                    area=area["id"],
                    zone=area["zone"],
                    types=list(cat.get("types") or []),
                    sensitive=bool(cat.get("sensitive")),
                )
                for key in cat.get("types") or []:
                    if key != "*":
                        routing[key] = cat["id"]

        rules = {
            rule_id: severity
            for severity in Severity
            for rule_id in t_raw["validation"].get(severity.value, [])
        }

        return cls(
            types=types,
            rules=rules,
            universal=universal,
            vocabularies=vocabularies,
            subtype_adds=subtype_adds,
            folders=folders,
            routing=routing,
            lifecycle=t_raw.get("lifecycle", {}),
            containers=list(t_raw.get("containers", {}).get("types", [])),
            imports=t_raw.get("import", {}),
            raw_types=t_raw,
            raw_layout=l_raw,
        )


def _field(raw: dict[str, Any]) -> FieldDef:
    to = raw.get("to")
    return FieldDef(
        key=raw["key"],
        type=raw.get("type"),
        required=raw.get("required") is True,
        on_create=raw.get("required") == "on-create",
        derived=bool(raw.get("derived_from")),
        of=raw.get("of"),
        to=to if isinstance(to, list) else ([to] if to else []),
        inverse=raw.get("inverse"),
    )


def _read(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)
