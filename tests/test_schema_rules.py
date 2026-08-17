import copy

import pytest

from vault.rules import schema_rules  # noqa: F401
from vault.rules.registry import SCHEMA_RULES
from vault.schema import Schema


def run(schema) -> list[str]:
    return [f.rule for f in schema_rules.run_all(schema)]


@pytest.fixture
def raw(schema_dir):
    import yaml

    with (schema_dir / "types.yaml").open(encoding="utf-8") as fh:
        types = yaml.safe_load(fh)
    with (schema_dir / "Folder-layout.yaml").open(encoding="utf-8") as fh:
        layout = yaml.safe_load(fh)
    return types, layout


def broken(raw, mutate):
    types, layout = copy.deepcopy(raw[0]), copy.deepcopy(raw[1])
    mutate(types, layout)
    return Schema.from_dicts(types, layout)


# -- the real schema ----------------------------------------------------------


def test_the_shipped_schema_passes_every_check(schema):
    assert run(schema) == []


def test_there_are_schema_checks_to_run():
    assert len(SCHEMA_RULES.ids()) >= 10


# -- each check catches its own defect ----------------------------------------


def test_catches_a_subtype_that_routes_nowhere(raw):
    def mutate(types, layout):
        types["vocabularies"]["doc_type"]["values"].append({"id": "invented"})

    assert "subtype-routes-nowhere" in run(broken(raw, mutate))


def test_catches_a_subtype_claimed_by_two_categories(raw):
    def mutate(types, layout):
        for area in layout["areas"]:
            for cat in area.get("categories", []):
                if cat["id"] == "people":
                    cat["types"].append("paystub")

    assert "subtype-routes-ambiguously" in run(broken(raw, mutate))


def test_catches_a_duplicate_jd_number(raw):
    def mutate(types, layout):
        for area in layout["areas"]:
            for cat in area.get("categories", []):
                if cat["id"] == "people":
                    cat["jd"] = "32"

    assert "duplicate-jd" in run(broken(raw, mutate))


def test_catches_a_category_using_the_reserved_x0_slot(raw):
    def mutate(types, layout):
        for area in layout["areas"]:
            for cat in area.get("categories", []):
                if cat["id"] == "people":
                    cat["jd"] = "50"

    assert "x0-slot-used" in run(broken(raw, mutate))


def test_catches_a_link_pointing_at_a_type_that_does_not_exist(raw):
    def mutate(types, layout):
        for t in types["types"]:
            if t["id"] == "meeting":
                t["fields"][1]["to"] = "unicorn"

    assert "link-target-unknown" in run(broken(raw, mutate))


def test_catches_a_link_field_with_no_inverse(raw):
    def mutate(types, layout):
        for t in types["types"]:
            if t["id"] == "group":
                for f in t["fields"]:
                    f.pop("inverse", None)

    assert "link-without-inverse" in run(broken(raw, mutate))


def test_catches_two_inverses_colliding_on_one_target(raw):
    def mutate(types, layout):
        for t in types["types"]:
            if t["id"] == "group":
                for f in t["fields"]:
                    if f["key"] == "members":
                        f["inverse"] = "meetings"  # already used on person

    assert "inverse-collision" in run(broken(raw, mutate))


def test_catches_an_enum_referencing_a_missing_vocabulary(raw):
    def mutate(types, layout):
        for t in types["types"]:
            if t["id"] == "task":
                t["fields"][0]["of"] = "no-such-vocabulary"

    assert "enum-vocabulary-unknown" in run(broken(raw, mutate))


def test_catches_an_unreachable_lifecycle_state(raw):
    def mutate(types, layout):
        types["vocabularies"]["task_state"]["values"].append("marinating")

    assert "state-unreachable" in run(broken(raw, mutate))


def test_catches_a_type_with_neither_machine_nor_stateless(raw):
    def mutate(types, layout):
        types["lifecycle"]["stateless"]["types"].remove("meeting")

    assert "type-without-lifecycle" in run(broken(raw, mutate))


def test_catches_a_type_missing_its_provenance_marker(raw):
    def mutate(types, layout):
        for t in types["types"]:
            if t["id"] == "note":
                t.pop("provenance", None)

    assert "provenance-missing" in run(broken(raw, mutate))


def test_catches_a_by_target_table_that_has_drifted(raw):
    def mutate(types, layout):
        types["query"]["inverses"]["by_target"]["person"] = ["meetings"]

    assert "inverse-table-stale" in run(broken(raw, mutate))
