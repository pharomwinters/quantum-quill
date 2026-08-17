from conftest import make_record, rule_ids

from vault.context import Context
from vault.index import Index
from vault.rules import corpus_rules  # noqa: F401
from vault.rules.registry import RULES, Scope

PEOPLE = "50-59C Contacts/51 People"
MEETINGS = "60-69N Notes, Journal & Tasks/62 Meetings"
TASKS = "60-69N Notes, Journal & Tasks/64 Tasks"
PROJECTS = "10-19P Projects/11 Work Projects"
AREAS = "20-29A Areas/22 Money"
CREATIVE = "10-19P Projects/13 Creative Projects"


def check(schema, *records) -> list:
    ctx = Context(schema=schema, records=list(records))
    ctx.index = Index.build(list(records), schema)
    findings = []
    for rule in RULES.all(Scope.CORPUS):
        findings.extend(rule.fn(ctx))
    return findings


def person(pid, **extra):
    return make_record(pid.title(), folder=PEOPLE, type="person", id=pid,
                       created="2026-08-17", relationship=["colleague"], **extra)


def project(pid, **extra):
    return make_record(pid, folder=f"{PROJECTS}/11.01 {pid}", type="project",
                       id=pid, created="2026-08-17", scope="work", **extra)


# -- duplicate-id -------------------------------------------------------------


def test_duplicate_id_fires(schema):
    assert "duplicate-id" in rule_ids(check(schema, person("jane"), person("jane")))


def test_distinct_ids_are_fine(schema):
    assert "duplicate-id" not in rule_ids(check(schema, person("jane"), person("sam")))


# -- unresolvable-link --------------------------------------------------------


def test_unresolvable_link_fires(schema):
    meeting = make_record("Standup", folder=MEETINGS, type="meeting",
                          id="standup", created="2026-08-17",
                          date="2026-08-17", attended=["ghost"])

    assert "unresolvable-link" in rule_ids(check(schema, meeting))


def test_resolvable_link_is_fine(schema):
    meeting = make_record("Standup", folder=MEETINGS, type="meeting",
                          id="standup", created="2026-08-17",
                          date="2026-08-17", attended=["jane"])

    assert "unresolvable-link" not in rule_ids(check(schema, person("jane"), meeting))


# -- link-to-archived-record --------------------------------------------------


def test_link_to_archived_record_warns(schema):
    archived = person("jane", archived_on="2026-01-01")
    meeting = make_record("Standup", folder=MEETINGS, type="meeting",
                          id="standup", created="2026-08-17",
                          date="2026-08-17", attended=["jane"])

    assert "link-to-archived-record" in rule_ids(check(schema, archived, meeting))


# -- project-done-with-open-tasks ---------------------------------------------


def test_project_done_with_open_tasks_warns(schema):
    done = project("paint-line", status="done", end="2026-08-17",
                   result="shipped", archived_on="2026-08-17")
    task = make_record("T", folder=TASKS, type="task", id="t",
                       created="2026-08-17", state="open",
                       projects=["paint-line"])

    assert "project-done-with-open-tasks" in rule_ids(check(schema, done, task))


def test_project_done_with_only_finished_tasks_is_fine(schema):
    done = project("paint-line", status="done", end="2026-08-17",
                   result="shipped", archived_on="2026-08-17")
    task = make_record("T", folder=TASKS, type="task", id="t",
                       created="2026-08-17", state="done",
                       projects=["paint-line"])

    assert "project-done-with-open-tasks" not in rule_ids(check(schema, done, task))


# -- area-closed-with-active-projects -----------------------------------------


def test_area_closed_with_active_projects_fires(schema):
    area = make_record("Money", folder=AREAS, type="area", id="money",
                       created="2026-08-17", status="closed",
                       standard="stay solvent")
    active = project("paint-line", status="active", serves=["money"])

    assert "area-closed-with-active-projects" in rule_ids(check(schema, area, active))


# -- superseded-without-successor ---------------------------------------------


def test_superseded_without_successor_fires(schema):
    doc = make_record("PFMEA v1",
                      folder="30-39D Documents/39 Work Products",
                      type="document", id="pfmea-v1", created="2026-08-17",
                      doc_type="analysis", doc_date="2026-08-17",
                      file="a.xlsx", status="superseded")

    assert "superseded-without-successor" in rule_ids(check(schema, doc))


def test_superseded_with_a_successor_is_fine(schema):
    old = make_record("PFMEA v1", folder="30-39D Documents/39 Work Products",
                      type="document", id="pfmea-v1", created="2026-08-17",
                      doc_type="analysis", doc_date="2026-08-17",
                      file="a.xlsx", status="superseded")
    new = make_record("PFMEA v2", folder="30-39D Documents/39 Work Products",
                      type="document", id="pfmea-v2", created="2026-08-17",
                      doc_type="analysis", doc_date="2026-08-17",
                      file="b.xlsx", status="active", supersedes="pfmea-v1")

    assert "superseded-without-successor" not in rule_ids(check(schema, old, new))


# -- world-entry-without-world / world-archived-with-entries ------------------


def test_world_entry_without_world_fires(schema):
    entry = make_record("Aelisa", folder=f"{CREATIVE}/13.01 Empire",
                        type="world-entry", id="aelisa", created="2026-08-17",
                        entry_type="polity", appears_in="no-such-world")

    assert "world-entry-without-world" in rule_ids(check(schema, entry))


def test_world_archived_with_entries_warns(schema):
    world = make_record("Empire", folder=f"{CREATIVE}/13.01 Empire",
                        type="world", id="empire", created="2026-08-17",
                        status="done", archived_on="2026-08-17")
    entry = make_record("Aelisa", folder=f"{CREATIVE}/13.01 Empire",
                        type="world-entry", id="aelisa", created="2026-08-17",
                        entry_type="polity", appears_in="empire")

    assert "world-archived-with-entries" in rule_ids(check(schema, world, entry))


# -- orphan -------------------------------------------------------------------


def test_orphan_reports_a_record_with_no_links_either_way(schema):
    lonely = make_record("Idea", folder="60-69N Notes, Journal & Tasks/63 Notes",
                         type="note", id="idea", created="2026-08-17",
                         note_type="note")

    assert "orphan" in rule_ids(check(schema, lonely))


def test_linked_record_is_not_an_orphan(schema):
    meeting = make_record("Standup", folder=MEETINGS, type="meeting",
                          id="standup", created="2026-08-17",
                          date="2026-08-17", attended=["jane"])

    assert "orphan" not in rule_ids(check(schema, person("jane"), meeting))
