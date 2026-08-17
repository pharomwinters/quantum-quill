import json

from vault.model import Severity
from vault.report import as_json, as_text
from vault.validate import validate

PEOPLE = "50-59C Contacts/51 People"


def write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_validates_a_tree_and_returns_findings(tmp_path, schema):
    write(tmp_path, f"{PEOPLE}/Jane Doe.md",
          "---\ntype: person\nid: jane-doe\ncreated: 2026-08-17\n"
          "relationship: [colleague]\n---\n")

    findings = validate(tmp_path, schema)

    assert all(f.rule in schema.rules for f in findings)


def test_reports_a_missing_required_field_from_a_real_file(tmp_path, schema):
    write(tmp_path, f"{PEOPLE}/Jane Doe.md", "---\ntype: person\n---\n")

    rules = {f.rule for f in validate(tmp_path, schema)}

    assert "missing-required-field" in rules


def test_import_mode_suppresses_derivable_fields(tmp_path, schema):
    """`id` is derivable from the filename, so --import must not report it."""
    write(tmp_path, f"{PEOPLE}/Jane Doe.md",
          "---\ntype: person\ncreated: 2026-08-17\nrelationship: [colleague]\n---\n")

    strict = {f.context.get("field") for f in validate(tmp_path, schema)
              if f.rule == "missing-required-field"}
    lenient = {f.context.get("field") for f in validate(tmp_path, schema, import_mode=True)
               if f.rule == "missing-required-field"}

    assert "id" in strict
    assert "id" not in lenient


def test_mutation_rules_are_not_run_by_a_scan(tmp_path, schema):
    write(tmp_path, f"{PEOPLE}/Jane Doe.md",
          "---\ntype: person\nid: jane-doe\ncreated: 2026-08-17\n"
          "relationship: [colleague]\n---\n")

    rules = {f.rule for f in validate(tmp_path, schema)}

    assert "illegal-transition" not in rules
    assert "id-changed" not in rules


def test_excluded_paths_are_not_read(tmp_path, schema):
    write(tmp_path, "private/Secret.md", "---\ntype: nonsense\n---\n")

    findings = validate(tmp_path, schema, exclude=["private"])

    assert findings == []


def test_binary_scan_honours_exclusions_too(tmp_path, schema):
    """Corpus rules walk the tree themselves and must respect the same list."""
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("x", encoding="utf-8")
    write(tmp_path, "private/notes.pdf", "x")

    rules = {f.rule for f in validate(tmp_path, schema, exclude=["private"])}

    assert "untyped-binary" not in rules


# -- reporting ----------------------------------------------------------------


def test_text_report_groups_by_severity(tmp_path, schema):
    write(tmp_path, f"{PEOPLE}/Jane Doe.md", "---\ntype: person\n---\n")

    text = as_text(validate(tmp_path, schema))

    assert "ERROR" in text
    assert "missing-required-field" in text


def test_text_report_says_so_when_clean():
    assert "no findings" in as_text([]).lower()


def test_json_report_is_machine_readable(tmp_path, schema):
    write(tmp_path, f"{PEOPLE}/Jane Doe.md", "---\ntype: person\n---\n")

    payload = json.loads(as_json(validate(tmp_path, schema)))

    assert payload["counts"]["error"] >= 1
    assert payload["findings"][0]["rule"]
    assert payload["findings"][0]["severity"] == Severity.ERROR.value
