from vault.parse import read_record


def write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_splits_frontmatter_from_body(tmp_path):
    path = write(
        tmp_path,
        "Jane Doe.md",
        "---\ntype: person\nrole: Engineer\n---\n\nMet at the plant.\n",
    )

    record = read_record(path)

    assert record.frontmatter == {"type": "person", "role": "Engineer"}
    assert record.body.strip() == "Met at the plant."


def test_title_comes_from_the_filename(tmp_path):
    path = write(tmp_path, "Jane Doe.md", "---\ntype: person\n---\n")

    assert read_record(path).title == "Jane Doe"


def test_file_without_frontmatter_has_none(tmp_path):
    path = write(tmp_path, "Scratch.md", "just some prose\n")

    record = read_record(path)

    assert record.frontmatter == {}
    assert record.body.strip() == "just some prose"


def test_reads_frontmatter_with_windows_line_endings(tmp_path):
    path = tmp_path / "Note.md"
    path.write_bytes(b"---\r\ntype: note\r\n---\r\n\r\nbody\r\n")

    assert read_record(path).frontmatter == {"type": "note"}


def test_malformed_yaml_yields_empty_frontmatter_not_a_crash(tmp_path):
    path = write(tmp_path, "Broken.md", "---\ntype: [unclosed\n---\n\nbody\n")

    record = read_record(path)

    assert record.frontmatter == {}
    assert record.malformed is True
