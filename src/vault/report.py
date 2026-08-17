"""Turns findings into something readable, or into JSON."""

from __future__ import annotations

import json
from collections import Counter

from vault.model import Finding, Severity

MARK = {Severity.ERROR: "ERROR", Severity.WARN: "WARN ", Severity.INFO: "INFO "}


def counts(findings: list[Finding]) -> dict[str, int]:
    tally = Counter(f.severity for f in findings)
    return {s.value: tally.get(s, 0) for s in Severity}


def as_text(findings: list[Finding], *, group_by_rule: bool = False) -> str:
    if not findings:
        return "No findings.\n"

    lines: list[str] = []
    if group_by_rule:
        by_rule: dict[str, list[Finding]] = {}
        for f in findings:
            by_rule.setdefault(f.rule, []).append(f)
        for rule, group in sorted(by_rule.items(),
                                  key=lambda kv: (kv[1][0].severity, kv[0])):
            lines.append(f"{MARK[group[0].severity]}  {rule}  ({len(group)})")
            for f in group[:10]:
                lines.append(f"         {f.target}  — {f.message}")
            if len(group) > 10:
                lines.append(f"         … and {len(group) - 10} more")
            lines.append("")
    else:
        for f in findings:
            lines.append(f"{MARK[f.severity]}  {f.rule}")
            lines.append(f"         {f.target}")
            lines.append(f"         {f.message}")
            lines.append("")

    tally = counts(findings)
    lines.append(
        f"{tally['error']} error, {tally['warn']} warn, {tally['info']} info"
        f"  ({len(findings)} findings)"
    )
    return "\n".join(lines) + "\n"


def as_json(findings: list[Finding]) -> str:
    return json.dumps(
        {
            "counts": counts(findings),
            "total": len(findings),
            "findings": [f.as_dict() for f in findings],
        },
        indent=2,
    )
