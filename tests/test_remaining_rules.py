import datetime as dt

from conftest import make_record, rule_ids

from vault.context import Context
from vault.index import Index
from vault.model import Record
from vault.rules import corpus_rules, mutation_rules, record_rules  # noqa: F401
from vault.rules.registry import RULES, Scope

DOCS = "30-39D Documents/32 Income & Employment"
PROJECTS = "10-19P Projects/11 Work Projects"


def record_check(schema, record, **ctx_kwargs) -> list:
    ctx = Context(schema=schema, records=[record], **ctx_kwargs)
    return [f for rule in RULES.all(Scope.RECORD) for f in rule.fn(record, ctx)]


def corpus_check(schema, records, **ctx_kwargs) -> list:
    ctx = Context(schema=schema, records=records, **ctx_kwargs)
    ctx.index = Index.build(records, schema)
    return [f for rule in RULES.all(Scope.CORPUS) for f in rule.fn(ctx)]


# -- empty-field-normally-filled ----------------------------------------------


def test_empty_field_normally_filled_fires_for_an_empty_string(schema):
    """The vault's real defect: `related: ""` on 15 person notes."""
    record = make_record(type="person", id="jane", created="2026-08-17",
                         relationship=["colleague"], related="")

    assert "empty-field-normally-filled" in rule_ids(record_check(schema, record))


def test_absent_field_is_not_an_empty_field(schema):
    record = make_record(type="person", id="jane", created="2026-08-17",
                         relationship=["colleague"])

    assert "empty-field-normally-filled" not in rule_ids(record_check(schema, record))


# -- finished-project-without-result ------------------------------------------


def test_finished_project_without_result_warns(schema):
    record = make_record("P", folder=f"{PROJECTS}/11.01 P", type="project",
                         id="p", created="2026-08-17", status="done",
                         scope="work", end="2026-08-17",
                         archived_on="2026-08-17")

    assert "finished-project-without-result" in rule_ids(record_check(schema, record))


# -- stale --------------------------------------------------------------------


def test_stale_reports_a_record_untouched_beyond_the_threshold(schema):
    record = make_record(type="note", id="old", created="2020-01-01",
                         note_type="note")

    findings = record_check(schema, record, today=dt.date(2026, 8, 17))

    assert "stale" in rule_ids(findings)


def test_recent_record_is_not_stale(schema):
    record = make_record(type="note", id="new", created="2026-08-01",
                         note_type="note")

    findings = record_check(schema, record, today=dt.date(2026, 8, 17))

    assert "stale" not in rule_ids(findings)


# -- missing-payload ----------------------------------------------------------


def test_missing_payload_warns_when_the_binary_is_absent(tmp_path, schema):
    path = tmp_path / "Payslip.md"
    path.write_text("---\n---\n", encoding="utf-8")
    record = Record(path=path, relative="Payslip.md", body="", frontmatter={
        "type": "document", "id": "p", "created": "2026-08-17",
        "doc_type": "paystub", "doc_date": "2026-08-17", "file": "payslip.pdf",
    })

    assert "missing-payload" in rule_ids(record_check(schema, record))


def test_present_payload_is_fine(tmp_path, schema):
    (tmp_path / "payslip.pdf").write_bytes(b"%PDF")
    path = tmp_path / "Payslip.md"
    path.write_text("---\n---\n", encoding="utf-8")
    record = Record(path=path, relative="Payslip.md", body="", frontmatter={
        "type": "document", "id": "p", "created": "2026-08-17",
        "doc_type": "paystub", "doc_date": "2026-08-17", "file": "payslip.pdf",
    })

    assert "missing-payload" not in rule_ids(record_check(schema, record))


# -- untyped-binary -----------------------------------------------------------


def test_untyped_binary_reports_a_file_no_record_claims(tmp_path, schema):
    (tmp_path / "orphan.pdf").write_bytes(b"%PDF")

    findings = corpus_check(schema, [], root=tmp_path)

    assert "untyped-binary" in rule_ids(findings)


def test_claimed_binary_is_not_reported(tmp_path, schema):
    (tmp_path / "payslip.pdf").write_bytes(b"%PDF")
    path = tmp_path / "Payslip.md"
    path.write_text("---\n---\n", encoding="utf-8")
    record = Record(path=path, relative="Payslip.md", body="", frontmatter={
        "type": "document", "id": "p", "created": "2026-08-17",
        "doc_type": "paystub", "doc_date": "2026-08-17", "file": "payslip.pdf",
    })

    findings = corpus_check(schema, [record], root=tmp_path)

    assert "untyped-binary" not in rule_ids(findings)


# -- first-instance-of-provisional --------------------------------------------


def test_first_instance_of_provisional_type_is_reported(schema):
    """`group` is marked provisional; the first real one triggers review."""
    record = make_record(type="group", id="paint-crew", created="2026-08-17",
                         members=["jane"])

    findings = corpus_check(schema, [record])

    assert "first-instance-of-provisional" in rule_ids(findings)


def test_derived_type_does_not_trigger_provisional_review(schema):
    record = make_record(type="person", id="jane", created="2026-08-17",
                         relationship=["colleague"])

    findings = corpus_check(schema, [record])

    assert "first-instance-of-provisional" not in rule_ids(findings)


# -- mutation rules -----------------------------------------------------------


def mutation_check(schema, before, after) -> list:
    ctx = Context(schema=schema, records=[after])
    return [f for rule in RULES.all(Scope.MUTATION) for f in rule.fn(before, after, ctx)]


def test_id_changed_fires(schema):
    before = make_record(type="note", id="old-id", created="2026-08-17",
                         note_type="note")
    after = make_record(type="note", id="new-id", created="2026-08-17",
                        note_type="note")

    assert "id-changed" in rule_ids(mutation_check(schema, before, after))


def test_illegal_transition_fires(schema):
    """done is terminal for a task except via reopen; done -> blocked is not legal."""
    before = make_record(type="task", id="t", created="2026-08-17", state="done")
    after = make_record(type="task", id="t", created="2026-08-17",
                        state="blocked", blocked_by=["x"])

    assert "illegal-transition" in rule_ids(mutation_check(schema, before, after))


def test_legal_transition_is_accepted(schema):
    before = make_record(type="task", id="t", created="2026-08-17", state="open")
    after = make_record(type="task", id="t", created="2026-08-17",
                        state="in-progress")

    assert "illegal-transition" not in rule_ids(mutation_check(schema, before, after))
