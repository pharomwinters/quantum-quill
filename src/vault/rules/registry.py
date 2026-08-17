"""Maps rule ids to implementations.

Every rule id declared in `types.yaml` has exactly one function here, and a
test asserts the two sets match in both directions. That is what stops the
validator drifting from the schema it enforces.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable


class Scope(Enum):
    """How much context a rule needs to decide."""

    SCHEMA = "schema"       # the two YAML files against each other
    RECORD = "record"       # one record, in isolation
    CORPUS = "corpus"       # needs the index: duplicates, backlinks, counts
    MUTATION = "mutation"   # needs a before AND an after

    # MUTATION exists because two declared rules — `illegal-transition` and
    # `id-changed` — cannot be decided by looking at a record at rest. A scan
    # sees only the after. They are registered and tested, but a scan skips
    # them; the app calls them when it writes.


@dataclass(frozen=True)
class Rule:
    id: str
    scope: Scope
    fn: Callable


class Registry:
    def __init__(self) -> None:
        self._rules: dict[str, Rule] = {}

    def rule(self, rule_id: str, scope: Scope) -> Callable:
        def register(fn: Callable) -> Callable:
            if rule_id in self._rules:
                raise ValueError(f"duplicate rule id: {rule_id}")
            self._rules[rule_id] = Rule(id=rule_id, scope=scope, fn=fn)
            return fn

        return register

    def get(self, rule_id: str) -> Rule:
        return self._rules[rule_id]

    def ids(self, scope: Scope | None = None) -> set[str]:
        if scope is None:
            return set(self._rules)
        return {r.id for r in self._rules.values() if r.scope is scope}

    def all(self, scope: Scope | None = None) -> list[Rule]:
        rules = self._rules.values()
        if scope is not None:
            rules = [r for r in rules if r.scope is scope]
        return sorted(rules, key=lambda r: r.id)


RULES = Registry()
"""Rules declared in `types.yaml`. A test asserts this matches, both ways."""

SCHEMA_RULES = Registry()
"""Consistency checks on the two YAML files themselves.

Deliberately a separate registry: these are not declared in `types.yaml`,
because a schema that declared the rules for checking itself would have no
outside vantage point. They are code-owned, and the code says so.
"""
