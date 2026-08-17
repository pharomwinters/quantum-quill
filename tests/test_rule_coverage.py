"""The meta-test: the schema is the source of truth for the validator too.

`types.yaml` declares which rules exist. This asserts the code matches, in
both directions, so the validator cannot quietly drift from the specification
it enforces.
"""

from vault.rules import corpus_rules, mutation_rules, record_rules  # noqa: F401
from vault.rules.registry import RULES, Scope


def test_every_declared_rule_has_an_implementation(schema):
    missing = set(schema.rules) - RULES.ids()

    assert missing == set(), f"declared in types.yaml but not implemented: {sorted(missing)}"


def test_no_rule_is_implemented_without_being_declared(schema):
    undeclared = RULES.ids() - set(schema.rules)

    assert undeclared == set(), f"implemented but absent from types.yaml: {sorted(undeclared)}"


def test_every_rule_is_reachable_by_some_scope():
    scoped = set()
    for scope in Scope:
        scoped |= RULES.ids(scope)

    assert scoped == RULES.ids()


def test_severity_counts_match_the_schema(schema):
    from vault.model import Severity

    counts = {s: sum(1 for v in schema.rules.values() if v is s) for s in Severity}

    assert counts[Severity.ERROR] == 15
    assert counts[Severity.WARN] == 9
    assert counts[Severity.INFO] == 4
    assert len(RULES.ids()) == 28
