"""Runs the rules over a tree.

Three passes, matching the three scopes: parse everything, judge each record
alone, then judge the corpus with the index built. Mutation rules are not run
here — a scan has no before-state to compare against.
"""

from __future__ import annotations

from pathlib import Path

from vault.context import Context
from vault.index import Index
from vault.model import Finding, Severity
from vault.parse import walk
from vault.rules import corpus_rules, mutation_rules, record_rules  # noqa: F401
from vault.rules import schema_rules
from vault.rules.registry import RULES, Scope
from vault.schema import Schema

DEFAULT_EXCLUDE = [".git", ".obsidian", ".trash", "node_modules"]


def check(schema: Schema) -> list[Finding]:
    """The two schema files against each other."""
    return schema_rules.run_all(schema)


def validate(
    root: Path | str,
    schema: Schema,
    *,
    import_mode: bool = False,
    exclude: list[str] | None = None,
) -> list[Finding]:
    root = Path(root)
    excluded = (exclude or []) + DEFAULT_EXCLUDE
    records = list(walk(root, exclude=excluded))

    ctx = Context(
        schema=schema,
        records=records,
        root=root,
        exclude=excluded,
        import_mode=import_mode,
    )
    ctx.index = Index.build(records, schema)

    findings: list[Finding] = []
    for record in records:
        if not record.type:
            continue  # untyped files are not records; `untyped-binary` covers files
        for rule in RULES.all(Scope.RECORD):
            findings.extend(rule.fn(record, ctx))

    for rule in RULES.all(Scope.CORPUS):
        findings.extend(rule.fn(ctx))

    return sorted(findings, key=lambda f: (f.severity, f.target, f.rule))


def worst(findings: list[Finding]) -> Severity | None:
    return min((f.severity for f in findings), default=None)
