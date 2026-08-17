"""Rules that need one record and nothing else."""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Any, Iterator

from vault.context import Context
from vault.model import Finding, Record, Severity
from vault.rules.registry import RULES, Scope

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _finding(rule: str, record: Record, ctx: Context, message: str,
             **context: Any) -> Finding:
    """Severity is read from the schema, never hard-coded here."""
    return Finding(
        rule=rule,
        severity=ctx.schema.rules[rule],
        target=record.relative or str(record.path),
        message=message,
        context=context,
    )


@RULES.rule("missing-required-field", Scope.RECORD)
def missing_required_field(record: Record, ctx: Context) -> Iterator[Finding]:
    type_id = record.type
    if not type_id or type_id not in ctx.schema.types:
        return
    for key in sorted(ctx.schema.required(type_id)):
        if ctx.import_mode and ctx.schema.is_derivable(type_id, key):
            continue
        if not record.has(key):
            yield _finding(
                "missing-required-field", record, ctx,
                f"{type_id} requires `{key}`",
                field=key, type=type_id,
            )


@RULES.rule("value-outside-closed-vocabulary", Scope.RECORD)
def value_outside_closed_vocabulary(record: Record, ctx: Context) -> Iterator[Finding]:
    schema = ctx.schema

    type_id = record.type
    if type_id and type_id not in schema.types:
        yield _finding(
            "value-outside-closed-vocabulary", record, ctx,
            f"`{type_id}` is not a core type",
            field="type", value=type_id,
        )
        return
    if not type_id:
        return

    for key, fdef in schema.fields_for(type_id, record.get(schema.subtype_field(type_id))).items():
        if not fdef.of or not record.has(key):
            continue
        allowed = schema.vocabulary(fdef.of)
        values = record.get(key)
        for value in values if isinstance(values, list) else [values]:
            if value not in allowed:
                yield _finding(
                    "value-outside-closed-vocabulary", record, ctx,
                    f"`{value}` is not in `{fdef.of}`",
                    field=key, value=value, vocabulary=fdef.of,
                )


@RULES.rule("malformed-date", Scope.RECORD)
def malformed_date(record: Record, ctx: Context) -> Iterator[Finding]:
    type_id = record.type
    if not type_id:
        return
    subtype = record.get(ctx.schema.subtype_field(type_id) or "")
    for key, fdef in ctx.schema.fields_for(type_id, subtype).items():
        if not fdef.is_date or not record.has(key):
            continue
        for value in _as_list(record.get(key)):
            if not _is_iso_date(value):
                yield _finding(
                    "malformed-date", record, ctx,
                    f"`{key}` is not a valid YYYY-MM-DD date",
                    field=key, value=str(value),
                )


@RULES.rule("wrong-folder", Scope.RECORD)
def wrong_folder(record: Record, ctx: Context) -> Iterator[Finding]:
    expected = ctx.schema.expected_folder(record)
    if expected is None:
        return
    actual = ctx.schema.folder_for_path(record.relative)
    if actual is None or actual.id == expected:
        return
    yield _finding(
        "wrong-folder", record, ctx,
        f"sits in `{actual.id}` but routes to `{expected}`",
        expected=expected, actual=actual.id,
    )


@RULES.rule("container-id-mismatch", Scope.RECORD)
def container_id_mismatch(record: Record, ctx: Context) -> Iterator[Finding]:
    if record.type not in ctx.schema.containers or not record.id:
        return
    parent = Path(record.relative).parent.name
    if not parent:
        return
    folder_slug = slugify(parent.split(" ", 1)[1] if " " in parent else parent)
    if folder_slug and folder_slug != record.id:
        yield _finding(
            "container-id-mismatch", record, ctx,
            f"container id `{record.id}` does not match its folder `{folder_slug}`",
            record_id=record.id, folder_id=folder_slug,
        )


@RULES.rule("subtype-field-on-wrong-subtype", Scope.RECORD)
def subtype_field_on_wrong_subtype(record: Record, ctx: Context) -> Iterator[Finding]:
    type_id = record.type
    subtype_field = ctx.schema.subtype_field(type_id or "")
    if not subtype_field:
        return
    subtype = record.get(subtype_field)
    allowed = set(ctx.schema.fields_for(type_id, subtype))
    foreign = ctx.schema.subtype_add_keys(subtype_field) - allowed
    for key in sorted(foreign & set(record.frontmatter)):
        yield _finding(
            "subtype-field-on-wrong-subtype", record, ctx,
            f"`{key}` belongs to another {subtype_field}, not `{subtype}`",
            field=key, subtype=subtype,
        )


@RULES.rule("blocked-task-without-blocker", Scope.RECORD)
def blocked_task_without_blocker(record: Record, ctx: Context) -> Iterator[Finding]:
    if record.type == "task" and record.get("state") == "blocked" \
            and not record.has("blocked_by"):
        yield _finding(
            "blocked-task-without-blocker", record, ctx,
            "state is `blocked` but `blocked_by` is empty",
        )


@RULES.rule("transition-requirement-unmet", Scope.RECORD)
def transition_requirement_unmet(record: Record, ctx: Context) -> Iterator[Finding]:
    """Checks the requirements of the state a record is IN.

    A transition needs a before and an after; a scan only sees the after. What
    is checkable at rest is the projection: whatever every route into this
    state demands must be present now.
    """
    machine = ctx.schema.machine(record.type or "")
    if not machine:
        return
    state = record.get(machine["field"])
    if not state:
        return

    requirement_sets = [
        set(t.get("requires", []))
        for t in machine["transitions"]
        if state in _as_list(t["to"])
    ]
    if not requirement_sets:
        return
    always_required = set.intersection(*requirement_sets)

    for key in sorted(always_required):
        if not record.has(key):
            yield _finding(
                "transition-requirement-unmet", record, ctx,
                f"state `{state}` requires `{key}`",
                state=state, field=key,
            )


@RULES.rule("terminal-record-not-archived", Scope.RECORD)
def terminal_record_not_archived(record: Record, ctx: Context) -> Iterator[Finding]:
    machine = ctx.schema.machine(record.type or "")
    if not machine:
        return
    state = record.get(machine["field"])
    if state in machine.get("terminal", []) and not record.has("archived_on"):
        yield _finding(
            "terminal-record-not-archived", record, ctx,
            f"state `{state}` is terminal but the record is still live",
            state=state,
        )


@RULES.rule("person-without-relationship", Scope.RECORD)
def person_without_relationship(record: Record, ctx: Context) -> Iterator[Finding]:
    if record.type == "person" and not record.has("relationship"):
        yield _finding(
            "person-without-relationship", record, ctx,
            "`relationship` is required on create and empty here",
        )


@RULES.rule("organization-as-text", Scope.RECORD)
def organization_as_text(record: Record, ctx: Context) -> Iterator[Finding]:
    if record.type != "person" or not record.has("organization"):
        return
    value = record.get("organization")
    if isinstance(value, str) and not SLUG.match(value):
        yield _finding(
            "organization-as-text", record, ctx,
            f"employer `{value}` is free text, not a link to an organization",
            value=value,
        )


@RULES.rule("empty-field-normally-filled", Scope.RECORD)
def empty_field_normally_filled(record: Record, ctx: Context) -> Iterator[Finding]:
    """A key present with an empty value.

    The vault's most common real defect: `related: ""` on all 15 person notes,
    where a list belongs. Declaring a field and leaving it blank is worse than
    omitting it — it looks answered.
    """
    for key, value in sorted(record.frontmatter.items()):
        if value is None or (isinstance(value, (str, list, dict)) and len(value) == 0):
            yield _finding(
                "empty-field-normally-filled", record, ctx,
                f"`{key}` is present but empty",
                field=key,
            )


@RULES.rule("finished-project-without-result", Scope.RECORD)
def finished_project_without_result(record: Record, ctx: Context) -> Iterator[Finding]:
    """Overlaps `transition-requirement-unmet` for projects — see NOTES."""
    if record.type != "project":
        return
    if record.get("status") in {"done", "cancelled"} and not record.has("result"):
        yield _finding(
            "finished-project-without-result", record, ctx,
            "finished without a result written",
            status=record.get("status"),
        )


@RULES.rule("stale", Scope.RECORD)
def stale(record: Record, ctx: Context) -> Iterator[Finding]:
    touched = record.get("updated") or record.get("created")
    if not _is_iso_date(touched):
        return
    when = touched if isinstance(touched, dt.date) else dt.date.fromisoformat(touched)
    age = (ctx.today - when).days
    if age > ctx.stale_after_days:
        yield _finding(
            "stale", record, ctx,
            f"untouched for {age} days",
            days=age,
        )


@RULES.rule("missing-payload", Scope.RECORD)
def missing_payload(record: Record, ctx: Context) -> Iterator[Finding]:
    if record.type != "document" or not record.has("file"):
        return
    payload = record.path.parent / str(record.get("file"))
    if not payload.exists():
        yield _finding(
            "missing-payload", record, ctx,
            f"`file` points at `{record.get('file')}`, which is not there",
            file=str(record.get("file")),
        )


def slugify(text: str) -> str:
    lowered = re.sub(r"[^a-z0-9]+", "-", text.lower())
    return lowered.strip("-")


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else [value]


def _is_iso_date(value: Any) -> bool:
    if isinstance(value, dt.date):
        return True
    if not isinstance(value, str) or not ISO_DATE.match(value):
        return False
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        return False
    return True
