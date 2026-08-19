-- Closed vocabularies, and the registry of link fields.
--
-- Both are SEEDED FROM types.yaml by `db:sync`, never hand-edited and never
-- populated by a migration: adding a doc_type has to stay a one-line edit to
-- the YAML, and a migration per vocabulary value would make that false.

CREATE TABLE vocabulary (
  name  text NOT NULL,
  value text NOT NULL,
  PRIMARY KEY (name, value)
);

COMMENT ON TABLE vocabulary IS
  'Closed vocabularies from types.yaml. Seeded by db:sync. Every enum column '
  'foreign-keys here through a generated companion column naming its vocabulary.';

-- Which link fields exist, what they may point at, and whether they repeat.
-- Keyed on (source_type, field, target_type) because `serves` is declared
-- twice — by project and by document — with different inverses.
CREATE TABLE link_field (
  source_type  text NOT NULL,
  source_vocab text NOT NULL GENERATED ALWAYS AS ('core_type') STORED,
  field        text NOT NULL,
  target_type  text NOT NULL,
  target_vocab text NOT NULL GENERATED ALWAYS AS ('core_type') STORED,
  multi        boolean NOT NULL,
  inverse      text NOT NULL,
  PRIMARY KEY (source_type, field, target_type),
  FOREIGN KEY (source_vocab, source_type) REFERENCES vocabulary(name, value),
  FOREIGN KEY (target_vocab, target_type) REFERENCES vocabulary(name, value)
);

COMMENT ON TABLE link_field IS
  'The declared link fields from types.yaml, expanded across their targets. '
  'A link row must match one of these, which is how to: [organization, person] '
  'becomes a database constraint rather than a documented intention.';
