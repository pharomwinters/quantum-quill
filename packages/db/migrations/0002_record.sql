-- The supertype. Every record of every type is a row here first.

CREATE TABLE record (
  id          text PRIMARY KEY,
  type        text NOT NULL,
  type_vocab  text NOT NULL GENERATED ALWAYS AS ('core_type') STORED,
  title       text,
  -- Nullable, because types.yaml declares neither `body` nor `tags` required.
  -- The DEFAULT means you get an empty one without asking; it does not mean the
  -- column may never be null, which would be a schema claim and belongs there.
  body        text DEFAULT '',
  created     timestamptz NOT NULL DEFAULT now(),
  updated     timestamptz,
  archived_on date,
  tags        text[] DEFAULT '{}',

  -- Permanent, lowercase, ASCII, shell-safe. `conventions.id_format`.
  CONSTRAINT record_id_is_a_slug CHECK (id ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
  FOREIGN KEY (type_vocab, type) REFERENCES vocabulary(name, value),

  -- The handle every subtype table and every link row points at. It is what
  -- lets a foreign key say "a task row attaches only to a record of type task"
  -- and "attaches_to points only at a project, area or world".
  UNIQUE (id, type)
);

COMMENT ON COLUMN record.body IS
  'Everything below the frontmatter. Never parsed for data; an empty body is valid.';
COMMENT ON COLUMN record.archived_on IS
  'Null means live. Deliberately separate from any type''s status: archiving is '
  'about location and attention, status is domain state.';

-- `id` is immutable. A changed id is corruption, not an edit — every inbound
-- link is a slug, so letting one move would break references silently.
CREATE FUNCTION record_id_is_immutable() RETURNS trigger
  LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'id is immutable: % cannot become %', OLD.id, NEW.id
    USING ERRCODE = 'restrict_violation';
END;
$$;

CREATE TRIGGER record_id_immutable
  BEFORE UPDATE OF id ON record
  FOR EACH ROW WHEN (OLD.id IS DISTINCT FROM NEW.id)
  EXECUTE FUNCTION record_id_is_immutable();

-- `updated` is system-stamped, so the database stamps it. Hand-editing it is
-- not forbidden so much as pointless: the next write overwrites it.
CREATE FUNCTION record_stamp_updated() RETURNS trigger
  LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated := now();
  RETURN NEW;
END;
$$;

CREATE TRIGGER record_updated_stamp
  BEFORE UPDATE ON record
  FOR EACH ROW EXECUTE FUNCTION record_stamp_updated();
