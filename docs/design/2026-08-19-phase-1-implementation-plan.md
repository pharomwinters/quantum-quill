# Phase 1 — Implementation Plan

**Date:** 2026-08-19
**Status:** in progress · steps 1-12 done 2026-08-19, step 13 not taken
**Implements:** [2026-08-18-service-design.md](2026-08-18-service-design.md) §8, phase 1

Phase 1 is: **compose stack, numbered SQL migrations, DDL cross-check test
green.** Nothing renders, nothing is created, nothing is ingested. The
deliverable is a schema that a test proves equal to `types.yaml`, and the
machinery that keeps proving it.

The order matters. Once SQL exists beside `types.yaml` with nothing binding
them, `types.yaml` stops being an executable specification and becomes advisory
documentation — which is the exact failure this project was created to correct.
The cross-check is therefore not a nicety at the end of phase 1; it is the
reason phase 1 exists.

---

## 1. Definition of done

```
git clone && cp .env.example .env && docker compose up -d && npm ci && npm test
```

— green, on a machine that has never seen this project, against an **empty**
database. Green means:

| Assertion | Where |
|---|---|
| Every core type has a table; every table has a core type | cross-check |
| Every declared field has a column; every column has a field | cross-check |
| Every closed vocabulary's live rows equal its `types.yaml` values | cross-check |
| Every link field is registered, with its declared targets and cardinality | cross-check |
| Declared inverses match `query.inverses.by_target` | schema meta-test |
| Every subtype routing key resolves to exactly one category | schema meta-test |
| Each validation rule claimed as DDL-enforced is actually rejected by the DDL | constraint tests |
| Migrations apply from scratch, are idempotent, and detect edited history | runner tests |

### In scope

Workspace skeleton · compose stack · migration runner · the DDL · vocabulary
and link-field seeding from YAML · the cross-check · constraint tests · Kysely
type generation · CI.

### Not in scope

No HTTP surface beyond a health endpoint, no records, no routing computation,
no projector, no triggers for cross-row rules, no state machines, no import. If
a decision can be deferred without the DDL becoming wrong, it is deferred.

---

## 2. What was verified before writing this

The DDL shapes below were built on PostgreSQL 16 and each constraint was made
to fire. This plan is not proposing untested SQL.

| # | Case | Result |
|---|---|---|
| 1 | `STORED` generated column as the referencing side of a composite FK | works, and enforces |
| 2 | `gross` on a `deed` (`subtype-field-on-wrong-subtype`) | rejected by CHECK |
| 3 | `gross` on a `paystub` | accepted |
| 4 | Money amount without currency | rejected by CHECK |
| 5 | `document.attaches_to` → `project` | accepted |
| 6 | `document.attaches_to` → `person` (not a declared target) | rejected by FK to `link_field` |
| 7 | Second value on a single-valued link field | rejected by partial unique index |
| 8 | Link to a non-existent record | rejected by FK to `record` |
| 9 | Link to an existing record of the wrong type | rejected by composite FK to `record(id, type)` |
| 10 | `doc_type` outside the vocabulary | rejected by FK to `vocabulary` |
| 11 | Deleting a record that is a link target | rejected by `ON DELETE RESTRICT` |
| 12 | `id` that is not kebab-case | rejected by CHECK |

Two checks were also run against the current YAML, and both pass **today**:

- All 65 subtype routing keys resolve to exactly one category in
  `Folder-layout.yaml`. The only unclaimed keys are `project` and `area`, which
  route explicitly, as declared.
- The inverse names declared by fields match `query.inverses.by_target`
  exactly, on all nine targets.

Phase 1 turns both into tests that start green, so the next edit to either file
cannot quietly break them.

---

## 3. Three schema questions the DDL forced open — settled

The DDL is not where the schema gets edited, so these were settled in
`types.yaml` first, before a line of SQL exists to be wrong. All three landed
on 2026-08-19; both files still parse, all 65 routing keys still resolve, and
the inverse registry still matches.

### 3.1 `body` is a column with no field — **added**

`conventions.body` described it, `query.indexes` full-text indexed it, and the
service design's data model had it, but `universal:` did not declare it. A
`record.body` column would have failed the cross-check on day one.

`body: longtext` is now a universal field. The omission had a cause and not a
reason: in a file-based vault the body was whatever the frontmatter was not, so
nothing had to declare it. A store that is not a file has to give it somewhere
to live. All three fields in the text index class — `title`, `body`, `tags` —
are now declared fields, which they were not before.

### 3.2 `folder` is guaranteed queryable but is not a field — **question opened**

`query.indexes` exact-indexes `folder` and `lifecycle.archive` preserves `jd`,
yet neither is declared on any type, because both are **derived**: routing
computes them from `type`, the subtype value and `attaches_to`.

No column in phase 1. `open_questions.folder-storage` now records the choice —
stored derived column, or a view computed on read — with what makes it hard
(container-relative routes resolve against another *record*, so the computed
form has to join) and who decides: phase 4, which has to write the real path
anyway. This is the `resource-status` treatment: record the question, do not
invent a way to close it.

### 3.3 `created` and `updated` were `date` — **widened to `datetime`**

Both are now `datetime`, mapping to `timestamptz`. A file-based vault was
written by hand a few times a day; a service writes whenever it is asked to,
and `date` cannot order two records made the same afternoon.

Two consequences recorded alongside the change:

- **`archived_on` and `task.completed` deliberately stay `date`.** Nothing asks
  when in the day a task was finished, and 24 real tasks already carry a
  date-only `completedDate`. Reality outranks consistency-for-its-own-sake.
- **`import.derived` for `meeting.date` is now a truncation, not a copy** —
  taken in the vault's local zone, or a meeting written up late in the evening
  lands on tomorrow. The rule now says so.

### Also, minor

`query.indexes` says *"all 18 link fields"*. There are 19, or 18 excluding
`related`. One number should change; either reading is defensible. Left as a
documentation fix, not a blocker.

---

## 4. Repository layout

```
package.json                 npm workspaces root; scripts delegate down
tsconfig.base.json
compose.yaml
.env.example
.github/workflows/ci.yml

packages/
  schema/                    the YAML, loaded and typed
    src/load.ts              parse types.yaml + Folder-layout.yaml
    src/model.ts             the derived model: tables, columns, vocabularies,
                             link fields, routing keys
    test/inverses.test.ts    declared inverses == query.inverses.by_target
    test/routing.test.ts     every routing key resolves to exactly one category

  db/
    migrations/0001_*.sql … numbered, forward-only
    src/migrate.ts           the runner
    src/sync.ts              seed vocabulary + link_field from types.yaml
    src/schema.d.ts          generated Kysely types (committed)
    test/migrate.test.ts     apply, re-apply, checksum drift
    test/crosscheck.test.ts  ** the load-bearing test **
    test/constraints.test.ts one case per DDL-enforced validation rule
    test/exemptions.ts       the exemption register
```

`packages/core` is deliberately absent — that is phase 2. `packages/app` is
phase 3, apart from the optional health endpoint in §11.

**Toolchain:** Node 22 LTS, TypeScript, `node:test` as the runner (no test
framework dependency), Kysely for phase 2 onward, `pg` as the driver. No ORM,
no migration library — the DDL is hand-written by decision, and a library that
generates or reverses it would take that back.

Tests run TypeScript through **Node's own type stripping**
(`--experimental-strip-types`), so there is no build step and no transpiler:
`tsc` only ever typechecks. A compile step between the schema and the tests
that check it is one more place for the two to disagree. The cost is that
source must be erasable-syntax-only — no TS enums, no parameter properties —
which `erasableSyntaxOnly` enforces at typecheck time.

---

## 5. Data model decisions

| # | Decision | Choice | Why |
|---|---|---|---|
| D1 | Vocabularies | One `vocabulary(name, value)` table + a `STORED` generated companion column per enum column | As the design sketches it. Verified: a generated column works as the referencing side of a composite FK. Adding a `doc_type` stays a one-line YAML edit with no DDL |
| D2 | Links | All 19 link fields as rows in `link`, with a `link_field` registry seeded from YAML | Uniform. Polymorphic targets, multi-valued fields and both directions of traversal all fall out. Costs `NOT NULL` on required links — see §6.2 |
| D3 | Subtype `adds` | Nullable columns on the parent table, guarded by CHECK | `CHECK (doc_type = 'paystub' OR gross_amount IS NULL)`, exactly as the design predicts |
| D4 | Money | Two columns, `<field>_amount numeric(14,2)` + `<field>_currency char(3)`, paired by CHECK | "Decimal amount plus a currency code" is two values; a composite type would fight every query builder |
| D5 | `list[text]` | `text[]` | No closure to enforce, so no junction earns its keep |
| D6 | `list[enum]` | Junction table (`person_relationship`) | Multi-valued *and* closed. An array cannot carry a foreign key |
| D7 | `person.organization` (union) | `link` rows, plus an `organization_text` column | The union is temporary by design — text until an organization record exists |
| D8 | Seeding | A sync command reading `types.yaml`, not a migration | A migration per vocabulary value would make "one-line YAML edit" false |
| D9 | Identifiers | Reserved words quoted: `"start"`, `"end"`, `"case"` | SQL's reserved list is a tool artifact. The old-tool rule applies: the schema wins |
| D10 | Down migrations | None | Forward-only. Recovery is restore-from-dump and re-apply, which §9 of the design already funds nightly |

### The shape, in SQL

```sql
CREATE TABLE vocabulary (
  name  text NOT NULL,
  value text NOT NULL,
  PRIMARY KEY (name, value)
);

CREATE TABLE record (
  id          text PRIMARY KEY CHECK (id ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
  type        text NOT NULL,
  type_vocab  text NOT NULL GENERATED ALWAYS AS ('core_type') STORED,
  title       text,
  body        text NOT NULL DEFAULT '',
  created     timestamptz NOT NULL,
  updated     timestamptz,
  archived_on date,
  tags        text[] NOT NULL DEFAULT '{}',
  FOREIGN KEY (type_vocab, type) REFERENCES vocabulary(name, value),
  UNIQUE (id, type)                              -- the handle every subtype and link uses
);

CREATE TABLE project (
  id     text PRIMARY KEY REFERENCES record(id) ON DELETE CASCADE,
  type   text NOT NULL DEFAULT 'project' CHECK (type = 'project'),
  status text NOT NULL,
  status_vocab text NOT NULL GENERATED ALWAYS AS ('project_status') STORED,
  scope  text NOT NULL,
  scope_vocab  text NOT NULL GENERATED ALWAYS AS ('scope') STORED,
  "start" date, "end" date, result text,
  FOREIGN KEY (id, type)             REFERENCES record(id, type) ON DELETE CASCADE,
  FOREIGN KEY (status_vocab, status) REFERENCES vocabulary(name, value),
  FOREIGN KEY (scope_vocab, scope)   REFERENCES vocabulary(name, value)
);
```

The `type` column pinned by `DEFAULT … CHECK` is what makes `record(id, type)`
usable as the subtype's own foreign key: a `task` row can only ever attach to a
record whose type is `task`. It costs one redundant column per table and buys
supertype/subtype integrity with no trigger.

### Links

```sql
CREATE TABLE link_field (                        -- SEEDED FROM types.yaml
  source_type text NOT NULL,
  field       text NOT NULL,
  target_type text NOT NULL,
  multi       boolean NOT NULL,
  inverse     text NOT NULL,
  PRIMARY KEY (source_type, field, target_type)
);

CREATE TABLE link (
  source text NOT NULL, source_type text NOT NULL,
  field  text NOT NULL,
  target text NOT NULL, target_type text NOT NULL,
  PRIMARY KEY (source, field, target),
  FOREIGN KEY (source, source_type) REFERENCES record(id, type) ON DELETE CASCADE,
  FOREIGN KEY (target, target_type) REFERENCES record(id, type) ON DELETE RESTRICT,
  FOREIGN KEY (source_type, field, target_type)
    REFERENCES link_field(source_type, field, target_type)
);

CREATE INDEX link_target_field ON link (target, field);   -- the inverse direction

CREATE UNIQUE INDEX link_single_valued ON link (source, field)
  WHERE field IN ('attaches_to','issuer','supersedes','snapshot_of','organization',
                  'source','appears_in','carrier','vendor','issued_by','plan_for');
```

Three things this buys that the design's §5 table does not count:

- **`to: [organization, person]` is enforced.** A link whose target type is not
  declared for that field has no row in `link_field` to point at.
- **Cardinality is enforced.** Eleven single-valued link fields, one partial
  unique index. The predicate is generated from `types.yaml`, and the
  cross-check asserts the live predicate's field list equals the declared
  single-valued set — so the drift is caught by a test rather than prevented by
  cleverness.
- **`serves` is declared twice** — by `project` (→ `area`, inverse `projects`)
  and by `document` (→ `area`, inverse `documents`). Keying `link_field` on
  `(source_type, field, target_type)` handles that without either shadowing the
  other.

`related` is symmetric and stored once. Reading it means unioning both
directions, which is what `link_target_field` is for.

---

## 6. What the database will actually enforce

The design's §5 says ~12 of 28 rules become constraints. Measured against the
model above, phase 1 delivers this:

| Rule | Mechanism | Phase |
|---|---|---|
| `duplicate-id` | `PRIMARY KEY` | 1 |
| `value-outside-closed-vocabulary` | FK → `vocabulary` | 1 |
| `unresolvable-link` | FK → `record(id, type)` | 1 |
| `malformed-date` | `date` column type | 1 |
| `missing-required-field` | `NOT NULL` — **scalar fields only** | 1, partly |
| `subtype-field-on-wrong-subtype` | `CHECK` — **scalar `adds` only** | 1, partly |
| `id-changed` | `BEFORE UPDATE` trigger, one, on `record` | 1 |
| `wrong-folder`, `container-id-mismatch`, `organization-as-text`, `empty-field-normally-filled` | dissolve | — |
| `blocked-task-without-blocker`, `area-closed-with-active-projects`, `superseded-without-successor` | triggers | 2 |
| `world-entry-without-world` | required *link* — see below | 2 |
| `illegal-transition`, `transition-requirement-unmet` | state machines | 2 |
| the 7 remaining warns, the 4 infos | app rules | 2 and 5 |

**Two honest corrections to §5 of the design.**

1. **Five rules become constraints outright and two partly — not twelve.** The
   gap is D2: with links as rows, every rule about a link's *presence* is
   cross-row and needs a trigger or app code. `group.members`,
   `meeting.attended` and `world-entry.appears_in` are all declared `required`
   and none of them can be `NOT NULL`. That is a real cost of the uniform link
   table, and it is worth paying — but it should be written down rather than
   discovered in phase 2.

2. **The database enforces things the rule list never named**: link target
   types, link cardinality, subtype/supertype agreement, referential integrity
   on delete. Counting only the declared rules undersells it.

The recommendation is not to change the model — it is to correct §5's table
after phase 1 measures it, and let the count be evidence rather than an
estimate. That is the same move the provenance markers make everywhere else.

`constraints.test.ts` is what makes this table true rather than claimed: one
case per row marked phase 1, each asserting a rejection, each named by its rule
id from `types.yaml`. Plus a meta-test — every rule id the test file names must
exist in `types.yaml` `validation:`, and every rule id in `types.yaml` must be
either covered or explicitly listed as deferred. Declared equals implemented,
one layer down, exactly as the retired validator did it.

---

## 7. Migrations

```
0001_vocabulary.sql     vocabulary, link_field
0002_record.sql         record, the id-immutability trigger
0003_types.sql          14 subtype tables, junctions, subtype-guard CHECKs
0004_link.sql           link, its indexes, the single-valued predicate
0005_indexes.sql        the query contract's exact / range / text index classes
```

Splitting on concern, not on size. `0003` is the large one and stays one file
because the 14 tables are one decision.

**Runner contract** (`packages/db/src/migrate.ts`, no dependencies beyond `pg`):

- `schema_migrations(version int PRIMARY KEY, name, checksum, applied_at, duration_ms)`
- Session advisory lock for the whole run, so two containers starting together cannot race
- One transaction per file; a failure rolls that file back and stops
- Checksum recorded on apply and re-verified on every run — **editing an applied
  migration is a hard failure**, not a warning
- Forward-only, per D10
- `npm run db:migrate`, `npm run db:status`

---

## 8. Seeding, and why it is not a migration

`npm run db:sync` reads `types.yaml` and upserts:

- `vocabulary` — 16 vocabularies, 135 values
- `link_field` — 19 link fields expanded across their declared targets: 219
  rows, of which 196 are `related` alone, because its `to: "*"` is 14 source
  types × 14 target types. Special-casing it would save 196 rows of nothing and
  cost the uniformity that makes A6 a set comparison

Behaviour:

- **Idempotent.** Re-running changes nothing.
- **Additive by default.** A value present in the database and absent from the
  YAML is reported, not deleted.
- **Deletion is opt-in** (`--prune`) and is allowed to fail: if a record still
  references the value, the foreign key refuses, which is the correct answer.
  Removing a vocabulary value that is in use is a data migration, not a sync.
- Runs on container start (after `db:migrate`) and in CI before the cross-check.

A *new vocabulary* — as opposed to a new value — still needs a migration,
because it needs a column and a foreign key. That is correct: a new vocabulary
is a schema change and should cost one.

---

## 9. The cross-check

`packages/db/test/crosscheck.test.ts`. It builds two models and compares them
in both directions.

**Expected**, from `packages/schema`: table per core type; column per scalar and
array field, with SQL type and nullability derived from `type` and `required`;
vocabulary names and value sets; link fields with targets, cardinality and
inverses; subtype `adds` with the guard predicate each one implies.

**Actual**, from `information_schema` and `pg_catalog`: tables, columns, data
types, nullability, `is_generated`, foreign keys, check constraint definitions
via `pg_get_constraintdef`, index definitions, and the live contents of
`vocabulary` and `link_field`.

| # | Assertion | Failure looks like |
|---|---|---|
| A1 | Table set == core type set | a table with no type, a type with no table |
| A2 | Column set per table == field set | a column with no field, a field with no column |
| A3 | Column SQL type == field type's mapping | `doc_date` stored as `timestamptz`, or `tax_year` as `text` |
| A4 | `NOT NULL` iff `required: true` | a required field left nullable |
| A5 | `vocabulary` rows == YAML values, per name, both directions | a `doc_type` added to SQL but not YAML |
| A6 | `link_field` rows == declared link fields × targets | a link field with no registry row |
| A7 | `link_field.multi` == `list[link]`, and the `link_single_valued` predicate == the single-valued set | a new single-valued field missing from the index |
| A8 | A guard CHECK exists for every scalar `adds` column, naming exactly the subtype values that declare it | `tax_year` guarded for `w2` but not `tax-return` |
| A9 | Every FK to `vocabulary` uses a companion column whose generated expression is that vocabulary's name | `status` pointed at the wrong vocabulary |
| A10 | Range-class and exact-class fields from `query.indexes` have an index | the query contract promising speed nothing delivers |

**Exemptions.** Columns with `is_generated = 'ALWAYS'` and the pinned `type`
column are excluded by *rule*, not by list — the introspection distinguishes
them, so there is nothing to maintain. Everything else lives in
`test/exemptions.ts` as `{ table, column, reason, raised }`. Two rules govern it:

- An exemption that no longer matches anything **fails the test**. A stale
  exemption is how a register turns into a place to hide things.
- Adding one is a schema conversation, not a fix. The register should be
  effectively empty after §3 is settled; `person.organization_text` is the one
  entry currently anticipated, and it disappears when the union does.

**Output** is a diff, not an assertion count: expected-only, actual-only,
mismatched, grouped by table, so a failure names the edit that caused it.

---

## 10. Compose stack

| Service | Image | Notes |
|---|---|---|
| `postgres` | `postgres:18-alpine`, pinned by digest | Named volume. Port published on `127.0.0.1` only. `healthcheck: pg_isready` |
| `migrate` | built from repo | One-shot. `depends_on: postgres healthy`. Runs `db:migrate` then `db:sync`, then exits 0 |
| `app` | built from repo | Phase 3. Present in phase 1 only if §11 step 9 is taken |

`.env.example` is committed and carries no secrets: `POSTGRES_PASSWORD`,
`DATABASE_URL`, `PGPORT`, `LAN_PORT`, `TUNNEL_PORT`. `.gitignore` already
excludes `.env` and already un-excludes `.env.example` — the repo anticipated
this.

**Tests do not touch the dev database.** Each run creates
`vault_test_<pid>`, migrates it, asserts, drops it. That keeps the cross-check
honest about running against a schema built only from the migrations.

---

## 11. Work plan

Each step ends with something you can run.

| # | Step | Done when |
|---|---|---|
| 1 | ~~Workspace skeleton: root `package.json`, `tsconfig.base.json`, `node:test` wiring~~ | **Done, 2026-08-19.** Node 22 type stripping, so no build step and no test framework |
| 2 | ~~`packages/schema`: loaders, derived model, the two meta-tests~~ | **Done, 2026-08-19.** 10 tests green, and each verified to go red on a deliberate break |
| 3 | ~~**Settle §3** — the `body`, `folder` and `date` questions, as edits to `types.yaml`~~ | **Done, 2026-08-19.** The YAML says what the DDL is about to assume |
| 4 | ~~Compose stack: `postgres` + `migrate`~~ | **Done.** Images pinned by digest. Not run end-to-end: no Docker daemon available where this was built |
| 5 | ~~Migration runner~~ | **Done.** 8 tests: ordering, idempotence, checksum drift, vanished file, bad filename, duplicate version, failed migration rolls back |
| 6 | ~~Migrations `0001`–`0005`~~ | **Done.** Applied clean to an empty database on the first attempt |
| 7 | ~~`db:sync`~~ | **Done.** 135 vocabulary values and 219 `link_field` rows, exactly as predicted; re-run is a no-op |
| 8 | ~~`constraints.test.ts`~~ | **Done.** 20 cases; every phase-1 row of §6 fires, plus the four the rule list never named |
| 9 | ~~`crosscheck.test.ts`~~ | **Done.** Green, and verified to fail on eight deliberate breaks |
| 10 | ~~Kysely codegen → `schema.d.ts`, committed~~ | **Done.** 20 tables; CI regenerates and fails on any diff |
| 11 | ~~CI: GitHub Actions, postgres service, `npm test`~~ | **Done.** Not yet observed green — this branch is its first run |
| 12 | ~~Update `README.md` and `CLAUDE.md`~~ | **Done.** "There is no code here" stopped being true |

**Optional, recommended, ~30 lines — step 13:** stand up the `app` service with
nothing but `/healthz`, bound to **two** listeners. Not because phase 1 needs an
HTTP surface, but because the design's LAN-only guarantee is enforced by
topology, and topology is far cheaper to establish before there are routes than
to retrofit under them. Cuttable without affecting anything else in this plan.

Steps 1–2 and 4–5 are independent and can be worked in either order. Step 3
blocks step 6. Everything else is sequential.

---

## 12. Risks

| Risk | Response |
|---|---|
| The cross-check becomes a test people add exemptions to | Stale exemptions fail. The register is reviewed as a schema change, not as test config |
| A field type maps to more than one reasonable SQL type, and the mapping becomes folklore | The mapping table lives in `packages/schema` as data, and A3 reads it. One place to argue with |
| `0003` is large and hand-written; a typo in one of 14 tables passes review | It cannot pass the cross-check — a mistyped column is a column with no field |
| Phase 3 discovers the DDL is wrong because half the schema is provisional | Expected and budgeted. Forward-only migrations make churn cheap; the cross-check makes it visible |
| Postgres major version drift | Pinned by digest. The only version-sensitive feature used is `STORED` generated columns (12+) |
| Restore has never been rehearsed | §9 of the design defers this to before phase 8. Phase 1 should at least commit the `pg_dump` script, so the thing being rehearsed exists |

---

## 13. Open questions this plan raises

1. ~~**`folder` as a stored column or a computed view**~~ — opened as
   `open_questions.folder-storage` in `types.yaml`. Decide by phase 4.
2. ~~**`created` / `updated` as `date` or `datetime`**~~ — settled: `datetime`.
3. **Required links** (`group.members`, `meeting.attended`,
   `world-entry.appears_in`) — trigger, deferred constraint, or app rule?
   Phase 2 decides; phase 1 only has to not pretend they are enforced.
4. **Link-typed subtype `adds`** (`carrier`, `vendor`, `issued_by`, `plan_for`)
   — `subtype-field-on-wrong-subtype` does not reach them through a CHECK.
   Phase 2, alongside question 3; the same mechanism answers both.
5. **§5 of the service design** should be corrected once phase 1 measures what
   the DDL actually enforces — see §6.

---

## 14. What building it found

The cross-check earned its place on its first run, before it had ever been
deliberately broken: it failed twice against DDL written from the same model it
compares against.

| Found | Verdict |
|---|---|
| `record.body` and `record.tags` were `NOT NULL DEFAULT ''` | The DDL had invented a requirement. `types.yaml` declares neither field required, so the columns are nullable now. See the open question below |
| A10 demanded an index on `document.gross_currency` and `document.period` | A bug in the check, not the DDL. It matched guarantees by bare field name; `period` is both the journal subtype vocabulary and a plain text field on a performance-review, and a money field's currency column is not the quantity the range guarantee is about |

Three more surfaced while writing the tests.

**A5 and A6 could not fail.** They compare the seeded `vocabulary` and
`link_field` tables against the model that seeded them, so on a freshly synced
database they agree by construction. The case they appear to cover — a database
seeded months ago, a vocabulary edited yesterday, `sync` not yet run — was
untested. Both are now paired with a test that drifts the live database inside
a transaction and asserts the comparison notices.

**`journal.date` is declared `unique: true`, and that forbids something real.**
A daily entry for a Monday and a weekly anchored on that same Monday cannot
coexist, because both are journals and both carry that date. The DDL implements
what is declared and says so in a comment; widening it to `UNIQUE (period, date)`
would be a schema decision made in SQL, which is the move this whole
arrangement exists to prevent.

**The query contract identifies fields by bare name, and names are not unique.**
`period` is the case that bit. `status`, `date` and `result` are also declared
on more than one type, but there the meaning is genuinely shared. A future
reader of `query.indexes` cannot tell the two situations apart.

### Open question this raises

`body` and `tags` want to be nullable in the schema and never-null in storage.
`required` means *the author must supply it*, which is not true of either; but
an empty body is `''` and an absent tag list is `{}`, and a third state that
means the same thing as one of the other two is worth nothing. The schema has
no way to say "defaulted, never null" — which would be a new field attribute
(`default:`), and inventing schema vocabulary is exactly what the method
forbids doing on a hunch. Left as it stands, flagged rather than guessed at.

### What CI found that local testing could not

The first CI run failed one test of 58: `a record that something links to
cannot be deleted` expected SQLSTATE `23503` and got `23001`.

**Postgres 18 reports an `ON DELETE RESTRICT` refusal as `restrict_violation`
(23001); 17 and earlier report `foreign_key_violation` (23503).** The DDL was
right and the database was doing its job — the test was asserting a Postgres
version. It now asserts class 23 and the constraint name, which is what the
rule is actually about.

The real defect was upstream of the test: **everything was verified against
PostgreSQL 16, while compose and CI pin 18.** Pinning by digest was supposed to
stop exactly this, and then the verification happened somewhere else. Postgres
18 is not installable in the environment this was built in, so until that
changes, CI is the authority for anything version-sensitive and local green is
a weaker claim than it looks.

Chasing it surfaced a quieter bug. Adding A11 made the index assertions fail
with nonsense — `enforces [,, d, e, i, p, t, y, {, }]` — because `attname` is
of SQL type `name`, `array_agg` over it produces `name[]`, and node-postgres
does not parse `name[]`: it hands back the raw `"{id}"` string. A10 had been
calling `.includes()` on that string, so it was substring-matching rather than
testing membership, and would have accepted an index on `doc_date` as
satisfying a guarantee about `date`. Fixed by casting to `text`.

### The three findings, resolved

| Finding | Resolution |
|---|---|
| `body` and `tags` want to be nullable in the schema and never-null in storage | New field attribute **`default:`**. It says what `required` could not: the author is never asked, and a record never lacks one. `0007` restores `NOT NULL`, and A11 asserts a declared default is a real one |
| `journal.date` was `unique: true`, forbidding a Monday daily beside a weekly anchored on that Monday | New field attribute **`unique_with: [period]`**, and migration `0006`. A11 now asserts declared uniqueness is enforced and nothing else is — so this can no longer drift either way |
| `query.indexes.subtypes` reads as field names but means vocabularies | Renamed to **`subtype_vocabularies:`**. The values never changed; the key now says what the list is, and the cross-check special case became a stated rule |

Two of the three closed by adding a field attribute rather than by bending the
DDL. That is the arrangement working: the schema gained the vocabulary to say
something true that it previously could not say, and the SQL followed.
