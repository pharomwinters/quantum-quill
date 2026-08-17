"""Rules that cannot be decided from one record.

Everything here reads the index: does this link resolve, does anything
supersede this document, does this finished project still have work attached.
"""

from __future__ import annotations

from typing import Any, Iterator

from vault.context import Context
from vault.model import Finding, Record
from vault.rules.registry import RULES, Scope

OPEN_TASK_STATES = {"open", "in-progress", "blocked", "deferred"}


def _finding(rule: str, ctx: Context, where: str, message: str,
             **context: Any) -> Finding:
    # `where` rather than `target` — several rules carry a `target` in context.
    return Finding(
        rule=rule,
        severity=ctx.schema.rules[rule],
        target=where,
        message=message,
        context=context,
    )


def _where(ctx: Context, record_id: str) -> str:
    record = ctx.index.by_id.get(record_id)
    return record.relative if record else record_id


def _typed(ctx: Context, type_id: str) -> list[Record]:
    return [r for r in ctx.records if r.type == type_id]


@RULES.rule("duplicate-id", Scope.CORPUS)
def duplicate_id(ctx: Context) -> Iterator[Finding]:
    for record_id, count in sorted(ctx.index.duplicates().items()):
        paths = [r.relative for r in ctx.records if r.id == record_id]
        yield _finding(
            "duplicate-id", ctx, paths[0],
            f"`{record_id}` is claimed by {count} records",
            id=record_id, paths=paths,
        )


@RULES.rule("unresolvable-link", Scope.CORPUS)
def unresolvable_link(ctx: Context) -> Iterator[Finding]:
    for source, field_name, target in ctx.index.unresolved():
        yield _finding(
            "unresolvable-link", ctx, _where(ctx, source),
            f"`{field_name}` points at `{target}`, which does not exist",
            field=field_name, target=target,
        )


@RULES.rule("link-to-archived-record", Scope.CORPUS)
def link_to_archived_record(ctx: Context) -> Iterator[Finding]:
    for edge in ctx.index.edges:
        target = ctx.index.by_id.get(edge.target)
        source = ctx.index.by_id.get(edge.source)
        if not target or not source or not target.has("archived_on"):
            continue
        if source.has("archived_on"):
            continue  # archived things may reference each other freely
        yield _finding(
            "link-to-archived-record", ctx, source.relative,
            f"`{edge.field}` points at archived `{edge.target}`",
            field=edge.field, target=edge.target,
        )


@RULES.rule("project-done-with-open-tasks", Scope.CORPUS)
def project_done_with_open_tasks(ctx: Context) -> Iterator[Finding]:
    """The guard the lifecycle declares, evaluated over the `tasks` inverse."""
    for project in _typed(ctx, "project"):
        if project.get("status") not in {"done", "cancelled"} or not project.id:
            continue
        open_tasks = [
            task for task in ctx.index.inverse(project.id, "tasks")
            if task.get("state") in OPEN_TASK_STATES
        ]
        if open_tasks:
            yield _finding(
                "project-done-with-open-tasks", ctx, project.relative,
                f"{len(open_tasks)} task(s) still open on a finished project",
                count=len(open_tasks),
                tasks=[t.id for t in open_tasks],
            )


@RULES.rule("area-closed-with-active-projects", Scope.CORPUS)
def area_closed_with_active_projects(ctx: Context) -> Iterator[Finding]:
    for area in _typed(ctx, "area"):
        if area.get("status") != "closed" or not area.id:
            continue
        active = [
            p for p in ctx.index.inverse(area.id, "projects")
            if p.get("status") == "active"
        ]
        if active:
            yield _finding(
                "area-closed-with-active-projects", ctx, area.relative,
                f"area is closed but {len(active)} project(s) still active",
                projects=[p.id for p in active],
            )


@RULES.rule("superseded-without-successor", Scope.CORPUS)
def superseded_without_successor(ctx: Context) -> Iterator[Finding]:
    """Checked against the index: nothing may be superseded by nothing."""
    for doc in _typed(ctx, "document"):
        if doc.get("status") != "superseded" or not doc.id:
            continue
        if not ctx.index.inverse(doc.id, "superseded_by"):
            yield _finding(
                "superseded-without-successor", ctx, doc.relative,
                "marked superseded but no document declares `supersedes` at it",
            )


@RULES.rule("world-entry-without-world", Scope.CORPUS)
def world_entry_without_world(ctx: Context) -> Iterator[Finding]:
    for entry in _typed(ctx, "world-entry"):
        target = entry.get("appears_in")
        resolved = ctx.index.by_id.get(_slug(target)) if target else None
        if resolved is None or resolved.type != "world":
            yield _finding(
                "world-entry-without-world", ctx, entry.relative,
                f"`appears_in` does not resolve to a world (got {target!r})",
                appears_in=target,
            )


@RULES.rule("world-archived-with-entries", Scope.CORPUS)
def world_archived_with_entries(ctx: Context) -> Iterator[Finding]:
    for world in _typed(ctx, "world"):
        if not world.has("archived_on") or not world.id:
            continue
        entries = [e for e in ctx.index.inverse(world.id, "entries")
                   if not e.has("archived_on")]
        if entries:
            yield _finding(
                "world-archived-with-entries", ctx, world.relative,
                f"{len(entries)} live entries still attached to an archived world",
                count=len(entries),
            )


@RULES.rule("orphan", Scope.CORPUS)
def orphan(ctx: Context) -> Iterator[Finding]:
    for record in ctx.records:
        if not record.id or record.type in {"area", "system"}:
            continue
        if ctx.index.outgoing(record.id) or ctx.index.incoming(record.id):
            continue
        yield _finding(
            "orphan", ctx, record.relative,
            "no links in either direction",
        )


@RULES.rule("untyped-binary", Scope.CORPUS)
def untyped_binary(ctx: Context) -> Iterator[Finding]:
    """A binary in the typed zone that no document record claims."""
    if ctx.root is None:
        return
    claimed = {
        (r.path.parent / str(r.get("file"))).resolve()
        for r in ctx.records
        if r.type == "document" and r.has("file")
    }
    for path in sorted(ctx.root.rglob("*")):
        if not path.is_file() or path.suffix.lower() in {".md", ""}:
            continue
        relative = path.relative_to(ctx.root).as_posix()
        if ctx.is_excluded(relative) or path.resolve() in claimed:
            continue
        yield _finding(
            "untyped-binary", ctx, relative,
            "binary with no document record",
        )


@RULES.rule("first-instance-of-provisional", Scope.CORPUS)
def first_instance_of_provisional(ctx: Context) -> Iterator[Finding]:
    """The provenance review trigger, as a rule rather than a good intention."""
    seen: set[str] = set()
    for record in ctx.records:
        type_def = ctx.schema.types.get(record.type or "")
        if not type_def or type_def.provenance != "provisional":
            continue
        if type_def.id in seen:
            continue
        seen.add(type_def.id)
        yield _finding(
            "first-instance-of-provisional", ctx, record.relative,
            f"first `{type_def.id}` record — the type is provisional, review it now",
            type=type_def.id,
        )


def _slug(value: Any) -> str | None:
    from vault.index import normalise

    return normalise(value)
