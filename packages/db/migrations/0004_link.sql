-- Every link, in one table.
--
-- `to: [organization, person]` is polymorphic and `list[link]` is
-- multi-valued; both are rows, so both stop being awkward. Inverses become a
-- query rather than a maintained structure — there is no edge index to drift.

CREATE TABLE link (
  source      text NOT NULL,
  source_type text NOT NULL,
  field       text NOT NULL,
  target      text NOT NULL,
  target_type text NOT NULL,

  PRIMARY KEY (source, field, target),

  -- Both ends must exist AND be of the type the field declares. This is what
  -- turns `to:` from documentation into a constraint.
  FOREIGN KEY (source, source_type) REFERENCES record(id, type) ON DELETE CASCADE,
  FOREIGN KEY (target, target_type) REFERENCES record(id, type) ON DELETE RESTRICT,
  FOREIGN KEY (source_type, field, target_type)
    REFERENCES link_field(source_type, field, target_type)
);

COMMENT ON TABLE link IS
  'One row per link. Deleting a record cascades to the links it makes and is '
  'refused while anything still points at it — unresolvable-link, prevented.';

-- The reverse direction. `person.meetings` is this index, read backwards:
-- SELECT source FROM link WHERE target = $1 AND field = ''attended''.
CREATE INDEX link_target_field ON link (target, field);

-- Cardinality. A single-valued link field may appear at most once per source.
-- The predicate is generated from types.yaml and asserted by the cross-check,
-- so a link field added later without updating it fails a test rather than
-- silently accepting a second value.
CREATE UNIQUE INDEX link_single_valued ON link (source, field)
  WHERE field IN (
    'attaches_to', 'issuer', 'supersedes', 'snapshot_of', 'organization',
    'source', 'appears_in', 'carrier', 'vendor', 'issued_by', 'plan_for'
  );
