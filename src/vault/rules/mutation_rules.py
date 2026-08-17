"""Rules that need a before AND an after.

Two of the schema's declared rules cannot be decided by a scan. A scan sees a
record at rest — it has no idea what the record used to be, so it cannot know
whether the change that produced it was legal or whether the id moved. These
are registered and tested like any other rule; the difference is who calls
them. The app calls them when it writes.
"""

from __future__ import annotations

from typing import Any, Iterator

from vault.context import Context
from vault.model import Finding, Record
from vault.rules.registry import RULES, Scope


def _finding(rule: str, ctx: Context, record: Record, message: str,
             **context: Any) -> Finding:
    return Finding(
        rule=rule,
        severity=ctx.schema.rules[rule],
        target=record.relative or str(record.path),
        message=message,
        context=context,
    )


@RULES.rule("id-changed", Scope.MUTATION)
def id_changed(before: Record, after: Record, ctx: Context) -> Iterator[Finding]:
    """`id` is immutable. A changed one is corruption, not an edit."""
    if before.id and after.id and before.id != after.id:
        yield _finding(
            "id-changed", ctx, after,
            f"id changed from `{before.id}` to `{after.id}` — ids are immutable",
            was=before.id, now=after.id,
        )


@RULES.rule("illegal-transition", Scope.MUTATION)
def illegal_transition(before: Record, after: Record, ctx: Context) -> Iterator[Finding]:
    machine = ctx.schema.machine(after.type or "")
    if not machine:
        return
    field_name = machine["field"]
    was, now = before.get(field_name), after.get(field_name)
    if not was or not now or was == now:
        return

    for transition in machine["transitions"]:
        if was in _as_list(transition["from"]) and now in _as_list(transition["to"]):
            return

    yield _finding(
        "illegal-transition", ctx, after,
        f"`{was}` -> `{now}` is not a legal {after.type} transition",
        was=was, now=now,
    )


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else [value]
