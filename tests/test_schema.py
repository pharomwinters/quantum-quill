from vault.model import Severity
from vault.schema import Schema


def test_loads_every_core_type(schema_dir):
    schema = Schema.load(schema_dir)

    assert len(schema.types) == 14
    assert schema.types["person"].name == "Person"


def test_reads_declared_rules_with_their_severity(schema_dir):
    schema = Schema.load(schema_dir)

    assert schema.rules["missing-required-field"] is Severity.ERROR
    assert schema.rules["person-without-relationship"] is Severity.WARN
    assert schema.rules["orphan"] is Severity.INFO


def test_required_fields_combine_universal_and_type_level(schema_dir):
    schema = Schema.load(schema_dir)

    assert schema.required("meeting") == {"id", "type", "created", "date", "attended"}


def test_title_is_derived_so_never_required(schema_dir):
    schema = Schema.load(schema_dir)

    assert "title" not in schema.required("note")


def test_exposes_closed_vocabularies_including_subtypes(schema_dir):
    schema = Schema.load(schema_dir)

    assert "paystub" in schema.vocabulary("doc_type")
    assert "work" in schema.vocabulary("scope")
    assert schema.subtype_field("document") == "doc_type"
    assert schema.subtype_field("person") is None


def test_routes_each_subtype_value_to_exactly_one_folder(schema_dir):
    schema = Schema.load(schema_dir)

    assert schema.route("paystub") == "income-employment"
    assert schema.route("person") == "people"
    assert schema.route("weekly") == "journal"


def test_knows_which_link_fields_a_type_has(schema_dir):
    schema = Schema.load(schema_dir)

    assert schema.link_fields("meeting") == {"attended": ["person"], "related": ["*"]}
