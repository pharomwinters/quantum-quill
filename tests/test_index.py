from conftest import make_record

from vault.index import Index

PEOPLE = "50-59C Contacts/51 People"
MEETINGS = "60-69N Notes, Journal & Tasks/62 Meetings"


def build(schema, *records) -> Index:
    return Index.build(list(records), schema)


def test_resolves_a_forward_link(schema):
    jane = make_record("Jane", folder=PEOPLE, type="person", id="jane",
                       created="2026-08-17", relationship=["colleague"])
    standup = make_record("Standup", folder=MEETINGS, type="meeting",
                          id="standup", created="2026-08-17",
                          date="2026-08-17", attended=["jane"])

    index = build(schema, jane, standup)

    assert [e.target for e in index.outgoing("standup")] == ["jane"]


def test_exposes_the_named_inverse(schema):
    """`meeting.attended` is authored; `person.meetings` exists only here."""
    jane = make_record("Jane", folder=PEOPLE, type="person", id="jane",
                       created="2026-08-17", relationship=["colleague"])
    standup = make_record("Standup", folder=MEETINGS, type="meeting",
                          id="standup", created="2026-08-17",
                          date="2026-08-17", attended=["jane"])

    index = build(schema, jane, standup)

    assert [r.id for r in index.inverse("jane", "meetings")] == ["standup"]


def test_reports_ids_claimed_more_than_once(schema):
    a = make_record("A", folder=PEOPLE, type="person", id="jane",
                    created="2026-08-17", relationship=["friend"])
    b = make_record("B", folder=PEOPLE, type="person", id="jane",
                    created="2026-08-17", relationship=["friend"])

    index = build(schema, a, b)

    assert index.duplicates() == {"jane": 2}


def test_knows_when_a_link_target_is_missing(schema):
    standup = make_record("Standup", folder=MEETINGS, type="meeting",
                          id="standup", created="2026-08-17",
                          date="2026-08-17", attended=["nobody"])

    index = build(schema, standup)

    assert index.unresolved() == [("standup", "attended", "nobody")]


def test_strips_wikilink_brackets_from_targets(schema):
    """Legacy material writes `[[Jane]]`; the index resolves the slug."""
    jane = make_record("Jane", folder=PEOPLE, type="person", id="jane",
                       created="2026-08-17", relationship=["colleague"])
    standup = make_record("Standup", folder=MEETINGS, type="meeting",
                          id="standup", created="2026-08-17",
                          date="2026-08-17", attended=["[[Jane]]"])

    index = build(schema, jane, standup)

    assert index.unresolved() == []
