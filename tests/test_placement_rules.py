from conftest import make_record, rule_ids

from vault.context import Context
from vault.rules import record_rules  # noqa: F401
from vault.rules.registry import RULES, Scope

DOCS = "30-39D Documents/32 Income & Employment"
PEOPLE = "50-59C Contacts/51 People"
PROJECTS = "10-19P Projects/11 Work Projects"


def check(schema, record) -> list:
    ctx = Context(schema=schema, records=[record])
    findings = []
    for rule in RULES.all(Scope.RECORD):
        findings.extend(rule.fn(record, ctx))
    return findings


# -- wrong-folder -------------------------------------------------------------


def test_wrong_folder_fires_when_the_category_rejects_the_subtype(schema):
    record = make_record("Payslip", folder=PEOPLE, type="document", id="p",
                         created="2026-08-17", doc_type="paystub",
                         doc_date="2026-08-17", file="p.pdf")

    assert "wrong-folder" in rule_ids(check(schema, record))


def test_correct_folder_raises_nothing(schema):
    record = make_record("Payslip", folder=DOCS, type="document", id="p",
                         created="2026-08-17", doc_type="paystub",
                         doc_date="2026-08-17", file="p.pdf")

    assert "wrong-folder" not in rule_ids(check(schema, record))


def test_container_attached_document_may_sit_outside_its_category(schema):
    """`attaches_to` routes to the container, so 32 is not expected."""
    record = make_record("PFMEA", folder=f"{PROJECTS}/11.01 Paint Line",
                         type="document", id="pfmea", created="2026-08-17",
                         doc_type="analysis", doc_date="2026-08-17",
                         file="pfmea.xlsx", attaches_to="paint-line")

    assert "wrong-folder" not in rule_ids(check(schema, record))


# -- container-id-mismatch ----------------------------------------------------


def test_container_id_must_match_its_folder(schema):
    record = make_record("Paint Line", folder=f"{PROJECTS}/11.01 Paint Line",
                         type="project", id="something-else",
                         created="2026-08-17", status="active", scope="work")

    assert "container-id-mismatch" in rule_ids(check(schema, record))


def test_container_id_matching_its_folder_is_fine(schema):
    record = make_record("Paint Line", folder=f"{PROJECTS}/11.01 Paint Line",
                         type="project", id="paint-line", created="2026-08-17",
                         status="active", scope="work")

    assert "container-id-mismatch" not in rule_ids(check(schema, record))


# -- subtype-field-on-wrong-subtype -------------------------------------------


def test_subtype_field_on_wrong_subtype_fires(schema):
    """`gross` belongs to paystub; a deed has no business carrying it."""
    record = make_record("Deed", folder="30-39D Documents/35 Property & Vehicle",
                         type="document", id="d", created="2026-08-17",
                         doc_type="deed", doc_date="2026-08-17", file="d.pdf",
                         gross=1234)

    assert "subtype-field-on-wrong-subtype" in rule_ids(check(schema, record))


def test_subtype_field_on_its_own_subtype_is_fine(schema):
    record = make_record("Payslip", folder=DOCS, type="document", id="p",
                         created="2026-08-17", doc_type="paystub",
                         doc_date="2026-08-17", file="p.pdf", gross=1234)

    assert "subtype-field-on-wrong-subtype" not in rule_ids(check(schema, record))


# -- blocked-task-without-blocker ---------------------------------------------


def test_blocked_task_without_blocker_fires(schema):
    record = make_record(type="task", id="t", created="2026-08-17",
                         state="blocked")

    assert "blocked-task-without-blocker" in rule_ids(check(schema, record))


def test_blocked_task_with_a_blocker_is_fine(schema):
    record = make_record(type="task", id="t", created="2026-08-17",
                         state="blocked", blocked_by=["other-task"])

    assert "blocked-task-without-blocker" not in rule_ids(check(schema, record))


# -- transition-requirement-unmet ---------------------------------------------


def test_done_project_without_result_is_an_unmet_requirement(schema):
    record = make_record("P", folder=f"{PROJECTS}/11.01 P", type="project",
                         id="p", created="2026-08-17", status="done",
                         scope="work", end="2026-08-17")

    assert "transition-requirement-unmet" in rule_ids(check(schema, record))


def test_done_project_with_everything_required_is_fine(schema):
    record = make_record("P", folder=f"{PROJECTS}/11.01 P", type="project",
                         id="p", created="2026-08-17", status="done",
                         scope="work", end="2026-08-17", result="shipped",
                         archived_on="2026-08-17")

    assert "transition-requirement-unmet" not in rule_ids(check(schema, record))


# -- terminal-record-not-archived ---------------------------------------------


def test_terminal_record_not_archived_fires(schema):
    record = make_record("P", folder=f"{PROJECTS}/11.01 P", type="project",
                         id="p", created="2026-08-17", status="done",
                         scope="work", end="2026-08-17", result="shipped")

    assert "terminal-record-not-archived" in rule_ids(check(schema, record))


def test_active_record_is_not_expected_to_be_archived(schema):
    record = make_record("P", folder=f"{PROJECTS}/11.01 P", type="project",
                         id="p", created="2026-08-17", status="active",
                         scope="work")

    assert "terminal-record-not-archived" not in rule_ids(check(schema, record))


# -- person-without-relationship / organization-as-text -----------------------


def test_person_without_relationship_warns(schema):
    record = make_record("Jane", folder=PEOPLE, type="person", id="jane",
                         created="2026-08-17")

    assert "person-without-relationship" in rule_ids(check(schema, record))


def test_organization_as_text_warns(schema):
    record = make_record("Jane", folder=PEOPLE, type="person", id="jane",
                         created="2026-08-17", relationship=["colleague"],
                         organization="Schneider Electric")

    assert "organization-as-text" in rule_ids(check(schema, record))
