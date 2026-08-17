from conftest import make_record, rule_ids

from vault.context import Context
from vault.rules import record_rules  # noqa: F401  (registers the rules)
from vault.rules.registry import RULES, Scope


def check(schema, record) -> list:
    """Run every record-scope rule against one record."""
    ctx = Context(schema=schema, records=[record])
    findings = []
    for rule in RULES.all(Scope.RECORD):
        findings.extend(rule.fn(record, ctx))
    return findings


# -- missing-required-field ---------------------------------------------------


def test_missing_required_field_fires_for_an_absent_field(schema):
    record = make_record(type="meeting", id="standup", created="2026-08-17",
                         attended=["jane-doe"])  # no `date`

    assert "missing-required-field" in rule_ids(check(schema, record))


def test_missing_required_field_treats_empty_string_as_absent(schema):
    record = make_record(type="meeting", id="standup", created="2026-08-17",
                         date="2026-08-17", attended="")

    assert "missing-required-field" in rule_ids(check(schema, record))


def test_complete_record_raises_no_missing_field(schema):
    record = make_record(type="meeting", id="standup", created="2026-08-17",
                         date="2026-08-17", attended=["jane-doe"])

    assert "missing-required-field" not in rule_ids(check(schema, record))


# -- value-outside-closed-vocabulary ------------------------------------------


def test_value_outside_closed_vocabulary_fires_for_an_unknown_subtype(schema):
    record = make_record(type="document", id="x", created="2026-08-17",
                         doc_type="not-a-real-doc-type", doc_date="2026-08-17",
                         file="x.pdf")

    assert "value-outside-closed-vocabulary" in rule_ids(check(schema, record))


def test_known_vocabulary_value_is_accepted(schema):
    record = make_record(type="document", id="x", created="2026-08-17",
                         doc_type="paystub", doc_date="2026-08-17", file="x.pdf")

    assert "value-outside-closed-vocabulary" not in rule_ids(check(schema, record))


def test_unknown_core_type_fires(schema):
    record = make_record(type="sandwich", id="x", created="2026-08-17")

    assert "value-outside-closed-vocabulary" in rule_ids(check(schema, record))


# -- malformed-date -----------------------------------------------------------


def test_malformed_date_fires_for_american_format(schema):
    record = make_record(type="note", id="x", created="06/01/2026",
                         note_type="note")

    assert "malformed-date" in rule_ids(check(schema, record))


def test_iso_date_is_accepted(schema):
    record = make_record(type="note", id="x", created="2026-06-01",
                         note_type="note")

    assert "malformed-date" not in rule_ids(check(schema, record))


def test_impossible_date_fires_even_though_shaped_correctly(schema):
    record = make_record(type="note", id="x", created="2026-02-30",
                         note_type="note")

    assert "malformed-date" in rule_ids(check(schema, record))
