import pytest

from vault.rules.registry import Registry, Scope


def test_registers_a_rule_under_its_id():
    registry = Registry()

    @registry.rule("orphan", Scope.CORPUS)
    def find_orphans(ctx):
        return []

    assert registry.get("orphan").fn is find_orphans
    assert registry.get("orphan").scope is Scope.CORPUS


def test_rejects_a_duplicate_rule_id():
    registry = Registry()

    @registry.rule("orphan", Scope.CORPUS)
    def first(ctx):
        return []

    with pytest.raises(ValueError, match="orphan"):

        @registry.rule("orphan", Scope.RECORD)
        def second(ctx):
            return []


def test_lists_rule_ids_filtered_by_scope():
    registry = Registry()

    @registry.rule("orphan", Scope.CORPUS)
    def a(ctx):
        return []

    @registry.rule("malformed-date", Scope.RECORD)
    def b(ctx):
        return []

    assert registry.ids(Scope.RECORD) == {"malformed-date"}
    assert registry.ids() == {"orphan", "malformed-date"}
