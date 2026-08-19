-- One table per core type. Each is identified by, and pinned to, its supertype
-- row: the `type` column is fixed by CHECK and joined to record(id, type), so a
-- subtype row can only ever attach to a record that declares that type.
--
-- Enum columns carry a generated companion naming their vocabulary, which is
-- what lets a single seeded `vocabulary` table foreign-key all of them.
--
-- Subtype `adds` are nullable columns on the parent table guarded by CHECK:
-- `gross` on a deed stops being a finding and becomes a rejected write.

-- ---------------------------------------------------------------- containers

CREATE TABLE project (
  id           text PRIMARY KEY,
  type         text NOT NULL DEFAULT 'project' CHECK (type = 'project'),
  status       text NOT NULL,
  status_vocab text NOT NULL GENERATED ALWAYS AS ('project_status') STORED,
  scope        text NOT NULL,
  scope_vocab  text NOT NULL GENERATED ALWAYS AS ('scope') STORED,
  -- Quoted: START is fine unquoted, END is reserved. Quoting both keeps the
  -- pair symmetrical. The schema keeps the names; SQL's keyword list is a tool
  -- artifact, and the prefix that dodged it was dropped for the same reason.
  "start"      date,
  "end"        date,
  result       text,
  FOREIGN KEY (id, type) REFERENCES record(id, type) ON DELETE CASCADE,
  FOREIGN KEY (status_vocab, status) REFERENCES vocabulary(name, value),
  FOREIGN KEY (scope_vocab, scope)   REFERENCES vocabulary(name, value)
);

CREATE TABLE area (
  id             text PRIMARY KEY,
  type           text NOT NULL DEFAULT 'area' CHECK (type = 'area'),
  status         text NOT NULL,
  status_vocab   text NOT NULL GENERATED ALWAYS AS ('area_status') STORED,
  standard       text NOT NULL,
  review_cadence text,
  review_cadence_vocab text NOT NULL GENERATED ALWAYS AS ('cadence') STORED,
  FOREIGN KEY (id, type) REFERENCES record(id, type) ON DELETE CASCADE,
  FOREIGN KEY (status_vocab, status) REFERENCES vocabulary(name, value),
  FOREIGN KEY (review_cadence_vocab, review_cadence) REFERENCES vocabulary(name, value)
);

COMMENT ON COLUMN area.standard IS
  'What "maintained" means for this area. Required because an area without a '
  'standard is just a folder name.';

CREATE TABLE world (
  id           text PRIMARY KEY,
  type         text NOT NULL DEFAULT 'world' CHECK (type = 'world'),
  status       text NOT NULL,
  status_vocab text NOT NULL GENERATED ALWAYS AS ('project_status') STORED,
  setting      text,
  FOREIGN KEY (id, type) REFERENCES record(id, type) ON DELETE CASCADE,
  FOREIGN KEY (status_vocab, status) REFERENCES vocabulary(name, value)
);

-- ------------------------------------------------------------------ payload

CREATE TABLE document (
  id             text PRIMARY KEY,
  type           text NOT NULL DEFAULT 'document' CHECK (type = 'document'),
  file           text NOT NULL,
  doc_type       text NOT NULL,
  doc_type_vocab text NOT NULL GENERATED ALWAYS AS ('doc_type') STORED,
  doc_date       date NOT NULL,
  revision       text,
  status         text,
  status_vocab   text NOT NULL GENERATED ALWAYS AS ('doc_status') STORED,

  -- subtype adds ---------------------------------------------------------
  gross           numeric(14,2), gross_currency char(3),   -- paystub
  net             numeric(14,2), net_currency   char(3),   -- paystub
  pay_period      text,                                    -- paystub
  tax_year        numeric,                                 -- w2, tax-return
  jurisdiction    text,                                    -- tax-return
  policy_number   text,                                    -- insurance-policy
  coverage_start  date,                                    -- insurance-policy
  coverage_end    date,                                    -- insurance-policy
  term_start      date,                                    -- lease
  term_end        date,                                    -- lease
  rent            numeric(14,2), rent_currency char(3),    -- lease
  odometer        numeric,                                 -- service-record
  "case"          text,                                    -- filing (reserved word)
  court           text,                                    -- filing
  filed_on        date,                                    -- filing
  target          text,                                    -- resume
  expires         date,                                    -- certificate
  period          text,                                    -- performance-review
  rating          text,                                    -- performance-review
  amount          numeric(14,2), amount_currency char(3),  -- quote
  valid_until     date,                                    -- quote
  product         text,                                    -- software-license
  seats           numeric,                                 -- software-license
  license_key     text,                                    -- software-license

  FOREIGN KEY (id, type) REFERENCES record(id, type) ON DELETE CASCADE,
  FOREIGN KEY (doc_type_vocab, doc_type) REFERENCES vocabulary(name, value),
  FOREIGN KEY (status_vocab, status)     REFERENCES vocabulary(name, value),

  CONSTRAINT document_gross_subtype          CHECK (doc_type = 'paystub' OR gross IS NULL),
  CONSTRAINT document_gross_currency_subtype CHECK (doc_type = 'paystub' OR gross_currency IS NULL),
  CONSTRAINT document_net_subtype            CHECK (doc_type = 'paystub' OR net IS NULL),
  CONSTRAINT document_net_currency_subtype   CHECK (doc_type = 'paystub' OR net_currency IS NULL),
  CONSTRAINT document_pay_period_subtype     CHECK (doc_type = 'paystub' OR pay_period IS NULL),
  CONSTRAINT document_tax_year_subtype       CHECK (doc_type IN ('w2', 'tax-return') OR tax_year IS NULL),
  CONSTRAINT document_jurisdiction_subtype   CHECK (doc_type = 'tax-return' OR jurisdiction IS NULL),
  CONSTRAINT document_policy_number_subtype  CHECK (doc_type = 'insurance-policy' OR policy_number IS NULL),
  CONSTRAINT document_coverage_start_subtype CHECK (doc_type = 'insurance-policy' OR coverage_start IS NULL),
  CONSTRAINT document_coverage_end_subtype   CHECK (doc_type = 'insurance-policy' OR coverage_end IS NULL),
  CONSTRAINT document_term_start_subtype     CHECK (doc_type = 'lease' OR term_start IS NULL),
  CONSTRAINT document_term_end_subtype       CHECK (doc_type = 'lease' OR term_end IS NULL),
  CONSTRAINT document_rent_subtype           CHECK (doc_type = 'lease' OR rent IS NULL),
  CONSTRAINT document_rent_currency_subtype  CHECK (doc_type = 'lease' OR rent_currency IS NULL),
  CONSTRAINT document_odometer_subtype       CHECK (doc_type = 'service-record' OR odometer IS NULL),
  CONSTRAINT document_case_subtype           CHECK (doc_type = 'filing' OR "case" IS NULL),
  CONSTRAINT document_court_subtype          CHECK (doc_type = 'filing' OR court IS NULL),
  CONSTRAINT document_filed_on_subtype       CHECK (doc_type = 'filing' OR filed_on IS NULL),
  CONSTRAINT document_target_subtype         CHECK (doc_type = 'resume' OR target IS NULL),
  CONSTRAINT document_expires_subtype        CHECK (doc_type = 'certificate' OR expires IS NULL),
  CONSTRAINT document_period_subtype         CHECK (doc_type = 'performance-review' OR period IS NULL),
  CONSTRAINT document_rating_subtype         CHECK (doc_type = 'performance-review' OR rating IS NULL),
  CONSTRAINT document_amount_subtype         CHECK (doc_type = 'quote' OR amount IS NULL),
  CONSTRAINT document_amount_currency_subtype CHECK (doc_type = 'quote' OR amount_currency IS NULL),
  CONSTRAINT document_valid_until_subtype    CHECK (doc_type = 'quote' OR valid_until IS NULL),
  CONSTRAINT document_product_subtype        CHECK (doc_type = 'software-license' OR product IS NULL),
  CONSTRAINT document_seats_subtype          CHECK (doc_type = 'software-license' OR seats IS NULL),
  CONSTRAINT document_license_key_subtype    CHECK (doc_type = 'software-license' OR license_key IS NULL),

  -- An amount without a currency is not money.
  CONSTRAINT document_gross_is_money  CHECK ((gross  IS NULL) = (gross_currency  IS NULL)),
  CONSTRAINT document_net_is_money    CHECK ((net    IS NULL) = (net_currency    IS NULL)),
  CONSTRAINT document_rent_is_money   CHECK ((rent   IS NULL) = (rent_currency   IS NULL)),
  CONSTRAINT document_amount_is_money CHECK ((amount IS NULL) = (amount_currency IS NULL))
);

-- ---------------------------------------------------------------- reference

CREATE TABLE resource (
  id                  text PRIMARY KEY,
  type                text NOT NULL DEFAULT 'resource' CHECK (type = 'resource'),
  resource_type       text NOT NULL,
  resource_type_vocab text NOT NULL GENERATED ALWAYS AS ('resource_type') STORED,
  source              text,
  url                 text,
  topic               text[],
  FOREIGN KEY (id, type) REFERENCES record(id, type) ON DELETE CASCADE,
  FOREIGN KEY (resource_type_vocab, resource_type) REFERENCES vocabulary(name, value)
);

-- ------------------------------------------------------------------- people

CREATE TABLE person (
  id    text PRIMARY KEY,
  type  text NOT NULL DEFAULT 'person' CHECK (type = 'person'),
  email text[],
  phone text[],
  -- The union half. A person's employer is a link once the organization has a
  -- record and plain text until then; all 15 real person notes are text, so
  -- demanding a link would block every import.
  organization_text text,
  role  text,
  met   date,
  FOREIGN KEY (id, type) REFERENCES record(id, type) ON DELETE CASCADE
);

-- `relationship` is multi-valued AND closed, so it is neither an array (which
-- cannot carry a foreign key) nor a column. People are several things at once —
-- this is the field that earned Contacts a cross-cutting area.
CREATE TABLE person_relationship (
  person      text NOT NULL,
  value       text NOT NULL,
  value_vocab text NOT NULL GENERATED ALWAYS AS ('relationship') STORED,
  PRIMARY KEY (person, value),
  FOREIGN KEY (person) REFERENCES person(id) ON DELETE CASCADE,
  FOREIGN KEY (value_vocab, value) REFERENCES vocabulary(name, value)
);

CREATE TABLE organization (
  id             text PRIMARY KEY,
  type           text NOT NULL DEFAULT 'organization' CHECK (type = 'organization'),
  org_type       text,
  org_type_vocab text NOT NULL GENERATED ALWAYS AS ('org_type') STORED,
  website        text,
  industry       text,
  FOREIGN KEY (id, type) REFERENCES record(id, type) ON DELETE CASCADE,
  FOREIGN KEY (org_type_vocab, org_type) REFERENCES vocabulary(name, value)
);

-- Quoted: GROUP is reserved. Same rule as project."end".
CREATE TABLE "group" (
  id      text PRIMARY KEY,
  type    text NOT NULL DEFAULT 'group' CHECK (type = 'group'),
  purpose text,
  FOREIGN KEY (id, type) REFERENCES record(id, type) ON DELETE CASCADE
);

-- ------------------------------------------------------------------ written

CREATE TABLE note (
  id              text PRIMARY KEY,
  type            text NOT NULL DEFAULT 'note' CHECK (type = 'note'),
  note_type       text NOT NULL,
  note_type_vocab text NOT NULL GENERATED ALWAYS AS ('note_type') STORED,
  FOREIGN KEY (id, type) REFERENCES record(id, type) ON DELETE CASCADE,
  FOREIGN KEY (note_type_vocab, note_type) REFERENCES vocabulary(name, value)
);

CREATE TABLE journal (
  id           text PRIMARY KEY,
  type         text NOT NULL DEFAULT 'journal' CHECK (type = 'journal'),
  period       text NOT NULL,
  period_vocab text NOT NULL GENERATED ALWAYS AS ('period') STORED,
  -- `unique: true` as declared in types.yaml. NOTE: this makes a Monday daily
  -- and a weekly anchored on the same Monday mutually exclusive. Raised as a
  -- finding rather than silently widened to UNIQUE (period, date) — the schema
  -- says what it says, and changing it is a schema decision, not a DDL one.
  date         date NOT NULL UNIQUE,
  week_start   date,
  week_end     date,
  FOREIGN KEY (id, type) REFERENCES record(id, type) ON DELETE CASCADE,
  FOREIGN KEY (period_vocab, period) REFERENCES vocabulary(name, value),
  CONSTRAINT journal_week_start_subtype CHECK (period = 'weekly' OR week_start IS NULL),
  CONSTRAINT journal_week_end_subtype   CHECK (period = 'weekly' OR week_end IS NULL)
);

CREATE TABLE meeting (
  id     text PRIMARY KEY,
  type   text NOT NULL DEFAULT 'meeting' CHECK (type = 'meeting'),
  date   date NOT NULL,
  agenda text,
  result text,
  FOREIGN KEY (id, type) REFERENCES record(id, type) ON DELETE CASCADE
);

CREATE TABLE task (
  id             text PRIMARY KEY,
  type           text NOT NULL DEFAULT 'task' CHECK (type = 'task'),
  state          text NOT NULL,
  state_vocab    text NOT NULL GENERATED ALWAYS AS ('task_state') STORED,
  priority       text,
  priority_vocab text NOT NULL GENERATED ALWAYS AS ('priority') STORED,
  due            date,
  scheduled      date,
  completed      date,
  FOREIGN KEY (id, type) REFERENCES record(id, type) ON DELETE CASCADE,
  FOREIGN KEY (state_vocab, state)       REFERENCES vocabulary(name, value),
  FOREIGN KEY (priority_vocab, priority) REFERENCES vocabulary(name, value)
);

COMMENT ON COLUMN task.completed IS
  'Stamped on the transition into done. Without it "what did I finish last '
  'week" is unanswerable, since updated moves on every edit.';

CREATE TABLE world_entry (
  id               text PRIMARY KEY,
  type             text NOT NULL DEFAULT 'world-entry' CHECK (type = 'world-entry'),
  entry_type       text NOT NULL,
  entry_type_vocab text NOT NULL GENERATED ALWAYS AS ('entry_type') STORED,
  FOREIGN KEY (id, type) REFERENCES record(id, type) ON DELETE CASCADE,
  FOREIGN KEY (entry_type_vocab, entry_type) REFERENCES vocabulary(name, value)
);

-- ------------------------------------------------------------------- system

CREATE TABLE system (
  id                text PRIMARY KEY,
  type              text NOT NULL DEFAULT 'system' CHECK (type = 'system'),
  system_type       text NOT NULL,
  system_type_vocab text NOT NULL GENERATED ALWAYS AS ('system_type') STORED,
  FOREIGN KEY (id, type) REFERENCES record(id, type) ON DELETE CASCADE,
  FOREIGN KEY (system_type_vocab, system_type) REFERENCES vocabulary(name, value)
);
