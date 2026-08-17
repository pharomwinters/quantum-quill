"""The two YAML files checked against each other.

These were five throwaway scripts run by hand while the schema was being
written. Every one of them caught a real defect at least once — a subtype with
no category, an inverse name colliding on its target, a state nothing could
reach. Making them permanent is the point of the `check` command.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterator

from vault.model import Finding, Severity
from vault.rules.registry import SCHEMA_RULES, Scope
from vault.schema import Schema


def _finding(rule: str, where: str, message: str, severity: Severity = Severity.ERROR,
             **context: Any) -> Finding:
    return Finding(rule=rule, severity=severity, target=where,
                   message=message, context=context)


def run_all(schema: Schema) -> list[Finding]:
    findings: list[Finding] = []
    for rule in SCHEMA_RULES.all(Scope.SCHEMA):
        findings.extend(rule.fn(schema))
    return findings


# -- routing ------------------------------------------------------------------


def _routing_keys(schema: Schema) -> dict[str, list[str]]:
    """Every key the layout should route, mapped to the categories claiming it."""
    claimed: dict[str, list[str]] = defaultdict(list)
    for folder in schema.folders.values():
        for key in folder.types:
            if key != "*":
                claimed[key].append(folder.id)
    return claimed


def _unconditionally_explicit(schema: Schema) -> set[str]:
    """Types whose routing REPLACES the layout lookup rather than supplementing it.

    `document` has an explicit entry too, but it is conditional (`when:
    attaches_to is set`) — with the field empty it still routes by doc_type,
    so its vocabulary must still be covered by the layout.
    """
    return {
        r["type"] for r in schema.routing_overrides if "when" not in r
    }


def _expected_keys(schema: Schema) -> set[str]:
    explicit = _unconditionally_explicit(schema)
    keys: set[str] = set()
    for type_def in schema.types.values():
        if type_def.id in explicit:
            continue
        if type_def.subtype:
            keys |= set(schema.vocabulary(type_def.subtype))
        else:
            keys.add(type_def.id)
    return keys


@SCHEMA_RULES.rule("subtype-routes-nowhere", Scope.SCHEMA)
def subtype_routes_nowhere(schema: Schema) -> Iterator[Finding]:
    claimed = _routing_keys(schema)
    for key in sorted(_expected_keys(schema)):
        if key not in claimed:
            yield _finding("subtype-routes-nowhere", "types.yaml",
                           f"`{key}` is declared but no category accepts it",
                           key=key)


@SCHEMA_RULES.rule("subtype-routes-ambiguously", Scope.SCHEMA)
def subtype_routes_ambiguously(schema: Schema) -> Iterator[Finding]:
    explicit = _unconditionally_explicit(schema)
    for key, folders in sorted(_routing_keys(schema).items()):
        if key in explicit:
            continue  # `project` in three categories is by design, routed by scope
        if len(folders) > 1:
            yield _finding("subtype-routes-ambiguously", "Folder-layout.yaml",
                           f"`{key}` is claimed by {folders}",
                           key=key, folders=folders)


# -- Johnny Decimal -----------------------------------------------------------


@SCHEMA_RULES.rule("duplicate-jd", Scope.SCHEMA)
def duplicate_jd(schema: Schema) -> Iterator[Finding]:
    seen: dict[str, list[str]] = defaultdict(list)
    for folder in schema.folders.values():
        seen[folder.jd].append(folder.id)
    for jd, ids in sorted(seen.items()):
        if len(ids) > 1:
            yield _finding("duplicate-jd", "Folder-layout.yaml",
                           f"number {jd} is used by {ids}", jd=jd)


@SCHEMA_RULES.rule("x0-slot-used", Scope.SCHEMA)
def x0_slot_used(schema: Schema) -> Iterator[Finding]:
    """`x0` is reserved for each area's own meta — rule `x0-reserved`."""
    for folder in sorted(schema.folders.values(), key=lambda f: f.jd):
        if folder.jd.endswith("0") and len(folder.jd) == 2:
            yield _finding("x0-slot-used", "Folder-layout.yaml",
                           f"category {folder.jd} ({folder.id}) uses a reserved x0 slot",
                           jd=folder.jd)


# -- fields and links ---------------------------------------------------------


def _all_fields(schema: Schema) -> Iterator[tuple[str, str, Any]]:
    for key, fdef in schema.universal.items():
        yield "*universal*", key, fdef
    for type_def in schema.types.values():
        for key, fdef in type_def.fields.items():
            yield type_def.id, key, fdef
    for voc_name, values in schema.subtype_adds.items():
        for value, adds in values.items():
            for key, fdef in adds.items():
                yield f"{voc_name}/{value}", key, fdef


@SCHEMA_RULES.rule("link-target-unknown", Scope.SCHEMA)
def link_target_unknown(schema: Schema) -> Iterator[Finding]:
    for owner, key, fdef in _all_fields(schema):
        if not fdef.is_link:
            continue
        for target in fdef.to:
            if target != "*" and target not in schema.types:
                yield _finding("link-target-unknown", "types.yaml",
                               f"{owner}.{key} points at unknown type `{target}`",
                               owner=owner, field=key, target=target)


@SCHEMA_RULES.rule("link-without-inverse", Scope.SCHEMA)
def link_without_inverse(schema: Schema) -> Iterator[Finding]:
    for owner, key, fdef in _all_fields(schema):
        if fdef.is_link and not fdef.inverse:
            yield _finding("link-without-inverse", "types.yaml",
                           f"{owner}.{key} is a link with no declared inverse",
                           owner=owner, field=key)


def _inverses_by_target(schema: Schema) -> dict[str, dict[str, list[str]]]:
    table: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for owner, key, fdef in _all_fields(schema):
        if not fdef.is_link or not fdef.inverse:
            continue
        for target in fdef.to:
            table[target][fdef.inverse].append(f"{owner}.{key}")
    return table


@SCHEMA_RULES.rule("inverse-collision", Scope.SCHEMA)
def inverse_collision(schema: Schema) -> Iterator[Finding]:
    """An inverse name must be unique on its TARGET, not globally."""
    for target, names in sorted(_inverses_by_target(schema).items()):
        for name, sources in sorted(names.items()):
            if len(sources) > 1:
                yield _finding("inverse-collision", "types.yaml",
                               f"`{name}` on `{target}` is claimed by {sources}",
                               target=target, inverse=name)


@SCHEMA_RULES.rule("inverse-table-stale", Scope.SCHEMA)
def inverse_table_stale(schema: Schema) -> Iterator[Finding]:
    """The documented `by_target` table must match the declared fields."""
    documented = schema.raw_types.get("query", {}).get("inverses", {}).get("by_target", {})
    actual = {t: sorted(names) for t, names in _inverses_by_target(schema).items()}
    for target in sorted(set(documented) | set(actual)):
        declared = sorted(set(documented.get(target, [])))
        found = actual.get(target, [])
        if declared != found:
            yield _finding("inverse-table-stale", "types.yaml",
                           f"by_target[{target}] says {declared}, fields say {found}",
                           target=target)


@SCHEMA_RULES.rule("enum-vocabulary-unknown", Scope.SCHEMA)
def enum_vocabulary_unknown(schema: Schema) -> Iterator[Finding]:
    for owner, key, fdef in _all_fields(schema):
        if fdef.of and fdef.of not in schema.vocabularies:
            yield _finding("enum-vocabulary-unknown", "types.yaml",
                           f"{owner}.{key} references unknown vocabulary `{fdef.of}`",
                           owner=owner, field=key, vocabulary=fdef.of)


# -- lifecycle ----------------------------------------------------------------


@SCHEMA_RULES.rule("state-unreachable", Scope.SCHEMA)
def state_unreachable(schema: Schema) -> Iterator[Finding]:
    for machine in schema.lifecycle.get("machines", []):
        type_def = schema.types.get(machine["type"])
        if not type_def:
            continue
        fdef = type_def.fields.get(machine["field"])
        if not fdef or not fdef.of:
            continue
        states = set(schema.vocabulary(fdef.of))
        reachable = {
            state
            for t in machine["transitions"]
            for state in (t["to"] if isinstance(t["to"], list) else [t["to"]])
        }
        reachable.add(machine.get("initial"))
        for state in sorted(states - reachable):
            yield _finding("state-unreachable", "types.yaml",
                           f"{machine['type']}: `{state}` has no transition into it",
                           type=machine["type"], state=state)


@SCHEMA_RULES.rule("type-without-lifecycle", Scope.SCHEMA)
def type_without_lifecycle(schema: Schema) -> Iterator[Finding]:
    machined = {m["type"] for m in schema.lifecycle.get("machines", [])}
    stateless = set(schema.lifecycle.get("stateless", {}).get("types", []))
    for type_id in sorted(set(schema.types) - machined - stateless):
        yield _finding("type-without-lifecycle", "types.yaml",
                       f"`{type_id}` is in neither `machines` nor `stateless`",
                       type=type_id)
    for type_id in sorted(machined & stateless):
        yield _finding("type-without-lifecycle", "types.yaml",
                       f"`{type_id}` is both machined and stateless",
                       type=type_id)


# -- provenance ---------------------------------------------------------------


@SCHEMA_RULES.rule("provenance-missing", Scope.SCHEMA)
def provenance_missing(schema: Schema) -> Iterator[Finding]:
    levels = set(schema.raw_types.get("provenance_levels", {}))

    for type_def in schema.types.values():
        raw = next(t for t in schema.raw_types["types"] if t["id"] == type_def.id)
        if raw.get("provenance") not in levels:
            yield _finding("provenance-missing", "types.yaml",
                           f"type `{type_def.id}` has no valid provenance marker",
                           subject=type_def.id)

    for name, voc in schema.raw_types["vocabularies"].items():
        if voc.get("provenance") not in levels:
            yield _finding("provenance-missing", "types.yaml",
                           f"vocabulary `{name}` has no valid provenance marker",
                           subject=name)

    for machine in schema.lifecycle.get("machines", []):
        if machine.get("provenance") not in levels:
            yield _finding("provenance-missing", "types.yaml",
                           f"machine `{machine['type']}` has no valid provenance marker",
                           subject=machine["type"])

    for area in schema.raw_layout["areas"]:
        if area.get("provenance") not in levels:
            yield _finding("provenance-missing", "Folder-layout.yaml",
                           f"area `{area['id']}` has no valid provenance marker",
                           subject=area["id"])
