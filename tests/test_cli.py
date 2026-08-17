from vault.cli import main


def write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_check_passes_on_the_shipped_schema(schema_dir, capsys):
    code = main(["check", "--schema", str(schema_dir)])

    assert code == 0
    assert "no findings" in capsys.readouterr().out.lower()


def test_validate_exits_nonzero_when_errors_are_found(tmp_path, schema_dir, capsys):
    write(tmp_path, "50-59C Contacts/51 People/Jane.md", "---\ntype: person\n---\n")

    code = main(["validate", str(tmp_path), "--schema", str(schema_dir)])

    assert code == 1
    assert "missing-required-field" in capsys.readouterr().out


def test_validate_exits_zero_on_a_clean_tree(tmp_path, schema_dir):
    code = main(["validate", str(tmp_path), "--schema", str(schema_dir)])

    assert code == 0


def test_severity_filter_hides_warnings(tmp_path, schema_dir, capsys):
    write(tmp_path, "50-59C Contacts/51 People/Jane.md",
          "---\ntype: person\nid: jane\ncreated: 2026-08-17\n"
          "relationship: [colleague]\nrelated: ''\n---\n")

    main(["validate", str(tmp_path), "--schema", str(schema_dir),
          "--severity", "error"])

    assert "empty-field-normally-filled" not in capsys.readouterr().out


def test_rule_filter_shows_only_that_rule(tmp_path, schema_dir, capsys):
    write(tmp_path, "50-59C Contacts/51 People/Jane.md", "---\ntype: person\n---\n")

    main(["validate", str(tmp_path), "--schema", str(schema_dir),
          "--rule", "missing-required-field"])

    out = capsys.readouterr().out
    assert "missing-required-field" in out
    assert "person-without-relationship" not in out
