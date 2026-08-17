"""`vault check` and `vault validate`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from vault.model import Finding, Severity
from vault.report import as_json, as_text
from vault.schema import Schema
from vault.validate import check, validate

DEFAULT_SCHEMA_DIR = Path(__file__).resolve().parent.parent.parent


def build_parser() -> argparse.ArgumentParser:
    # Shared flags go on a parent parser so they are accepted both before and
    # after the subcommand — argparse does not do that on its own, and
    # `vault validate . --json` is how anyone would actually type it.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_DIR,
                        help="directory holding types.yaml and Folder-layout.yaml")
    common.add_argument("--json", action="store_true", help="machine-readable output")
    common.add_argument("--severity", choices=[s.value for s in Severity],
                        help="show this severity and worse")
    common.add_argument("--rule", action="append", help="only this rule (repeatable)")

    parser = argparse.ArgumentParser(
        prog="vault",
        parents=[common],
        description="Validate a typed personal information manager against its schema.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", parents=[common],
                   help="the two schema files against each other")

    val = sub.add_parser("validate", parents=[common],
                         help="records against the schema")
    val.add_argument("path", type=Path, help="tree to validate")
    val.add_argument("--import", dest="import_mode", action="store_true",
                     help="apply the derivations types.yaml declares, then validate")
    val.add_argument("--exclude", action="append", default=[],
                     help="path to skip entirely (repeatable)")
    return parser


def _filter(findings: list[Finding], args: argparse.Namespace) -> list[Finding]:
    if args.severity:
        cutoff = Severity(args.severity)
        findings = [f for f in findings if not cutoff < f.severity]
    if args.rule:
        wanted = set(args.rule)
        findings = [f for f in findings if f.rule in wanted]
    return findings


def main(argv: list[str] | None = None) -> int:
    # Global flags are declared before the subcommand but users type them after,
    # so parse them from either position.
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    schema = Schema.load(args.schema)

    if args.command == "check":
        findings = check(schema)
    else:
        findings = validate(
            args.path, schema,
            import_mode=args.import_mode,
            exclude=args.exclude,
        )

    findings = _filter(findings, args)
    output = as_json(findings) if args.json else as_text(
        findings, group_by_rule=(args.command == "validate")
    )
    print(output)

    return 1 if any(f.severity is Severity.ERROR for f in findings) else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
