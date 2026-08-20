# Phase 2 — Implementation Plan

**Date:** 2026-08-20
**Status:** in progress · step 1 done 2026-08-20
**Implements:** [2026-08-18-service-design.md](2026-08-18-service-design.md) §8, phase 2
**Follows:** [2026-08-19-phase-1-implementation-plan.md](2026-08-19-phase-1-implementation-plan.md)

Phase 2 is: **the rules Postgres cannot enforce with a constraint, the router,
and the import derivations.** Still nothing renders and nothing is created —
phase 3 owns that. The deliverable is that 23 of the 28 validation rules are
either enforced or accounted for by a mechanism that exists, and the five that
remain belong to phases that have not started.

Phase 1 ended with a schema a test proves equal to `types.yaml`. Phase 2 ends
with *behaviour* proved equal to `types.yaml` — the state machines, the guards
and the routing table interpreted from the YAML rather than transcribed out of
it. Transcription is the failure mode: a hard-coded transition is a second
source of truth that no cross-check can see.

---

## 0. One correction to the phase boundary, before anything else

`CLAUDE.md` describes phase 2 as "`core` in TypeScript — the rules Postgres
cannot enforce". `packages/db/test/constraints.test.ts` marks three rules
`phase 2: trigger`, and a trigger is SQL. Both are right about the work and the
short description is misleading about where it lives.

**Phase 2 writes migrations as well as TypeScript.** Migrations `0008`–`0010`
carry the triggers; `packages/core` carries everything a trigger cannot express
— warnings, transitions, effects, derivations, routes. The split is not
stylistic:

> A rule goes in the database when it must hold for **every** writer, and in
> `core` when it must be **reported** rather than refused.

The importer (phase 8) writes 88 records by script, and the projector (phase 4)
writes nothing but reads everything. An ERROR-severity invariant enforced only
in `core` is an invariant the importer can walk straight through.

---

## 1. Definition of done

`npm test` green, and the rule register in `constraints.test.ts` reads:

| Fate | Count | Mechanism | Phase |
|---|---|---|---|
| DDL constraints | 7 | `PRIMARY KEY`, `FOREIGN KEY`, `NOT NULL`, `date`, `CHECK` | 1 |
| Dissolved | 4 | No folders to be wrong about; typed columns | 1 |
| Triggers | 4 | Deferred constraint triggers, seeded from `types.yaml` | **2** |
| `core`, blocking | 2 | The state machine interpreter | **2** |
| `core`, advisory | 6 | The rule registry | **2** |
| Later phases | 5 | 1 in phase 3, 2 in phase 4, 2 in phase 5 | — |

7 + 4 + 4 + 2 + 6 + 5 = 28. **Phase 2 closes 12.**

Green also means:

| Assertion | Where |
|---|---|
| Every rule is enforced, implemented, or has a phase entry — and every entry is real | `constraints.test.ts` (extended, not replaced) |
| Every declared state machine has an interpreter path; every state a machine names is in that field's vocabulary | `core/test/lifecycle.test.ts` |
| Every effect verb appearing in `lifecycle` is implemented, and every implemented verb appears | `core/test/registry.test.ts` |
| Every guard is evaluable, and uses no query operator `core` has not implemented | `core/test/guards.test.ts` |
| Every one of the 65 routing keys produces a path; the four explicit shapes and `9N` archiving do too | `core/test/route.test.ts` |
| Each of the 6 import derivations produces the declared field from the declared source | `core/test/import.test.ts` |
| The three required links and the four subtype-guarded links are refused by the database | `constraints.test.ts` |

### In scope

`packages/core` · migrations `0008`–`0010` · the router · the machine
interpreter · the guard evaluator · the 6 advisory rules · the import
derivations · the four loose ends in §2.

### Not in scope

No HTTP surface beyond the health endpoint in §2.4, no create/view/edit, no
projector, no real import run, no saved views. If a decision can be deferred
without `core` becoming wrong, it is deferred.

---

## 2. Loose ends from phase 1 — the first four steps

These come first, and not out of tidiness. The first one blocks every other
line of phase 2, and the other three get cheaper the earlier they are done.

### 2.1 The loader does not declare half of what phase 2 reads — **blocking** · done

`packages/schema/src/load.ts` types `Types` with `meta`, `field_types`,
`universal`, `routing`, `types`, `vocabularies`, `query`, `validation`,
`open_questions`. The YAML also carries `lifecycle` and `import`, and the parse
returns them — they are simply not on the type. Reading a state machine today
requires `as any`.

`routing.explicit` is worse than absent, because it is declared *wrong*:

```ts
explicit: Array<{ type: string; routes_by: string }>
```

The four real entries carry `map`, `when`, `relative_to` and `rule`. A router
written against this type would typecheck while silently ignoring
container-relative routing.

This is the same defect the cross-check exists to catch, one layer up: the
TypeScript view of `types.yaml` has drifted from `types.yaml`, and nothing
fails when it does. Phase 2 cannot be written type-safely on top of it, and
every `as any` is a place the drift goes unnoticed.

**Step:** type `lifecycle` and `import`, widen `routing.explicit`, and add the
same shape of assertion the loader already earns elsewhere — parsing a key the
type does not declare should be visible, not silent.

### 2.2 §5 of the service design is now measurably wrong

It says *"~12 become constraints"*. Phase 1 measured **7**, and
`constraints.test.ts:279` pins that number. Plan §13 question 5 asked for the
correction and it was not made. Its "Need triggers | 3" also becomes **4** once
§4 of this plan lands, and "Stay app rules | ~9" becomes **13**.

Fold in the documentation fix phase 1 recorded and did not take: `query.indexes`
says *"all 18 link fields"*. There are **19** — 18 excluding `related`. The
model says so; pick a reading and write it.

### 2.3 The `pg_dump` script was funded and never committed

§12 of the phase 1 plan: *"Phase 1 should at least commit the `pg_dump` script,
so the thing being rehearsed exists."* It does not exist. Design §9 defers the
*rehearsal* to before phase 8; it does not defer the script.

Phase 2 is the last comfortable moment — from phase 3 the database starts
holding records that are not reproducible from a migration.

### 2.4 Step 13: `/healthz` on two listeners

Phase 1 marked this optional and cuttable, and it was cut. The reasoning for
doing it early has not weakened:

> The design's LAN-only guarantee is enforced by topology, and topology is far
> cheaper to establish before there are routes than to retrofit under them.

`31 Identity & Vital`, `34 Insurance & Medical` and `36 Legal &
Correspondence` are LAN-only, and cloudflared forwards to localhost — so source
address cannot distinguish tunnel from LAN, and a conditional cannot do this
job. Two binds, ~30 lines, before phase 3 puts routes on top.

---

## 3. Three schema questions the interpreter forces open — settle these first

The DDL was not where the schema got edited, and neither is `core`. These are
edits to `types.yaml`, taken before the interpreter exists to be wrong.

### 3.1 Guards are English prose, and the interpreter cannot execute prose

Four guards and one `requires_index` are the entire population:

| Machine | Check, as written today |
|---|---|
| `project` → `done` | `"tasks where state in [open, in-progress, blocked] is empty"` |
| `area` → `closed` | `"projects where status == active is empty"` |
| `world` → `done`/`cancelled` | `"entries is empty"` |
| `document` → `superseded` | `requires_index: "superseded_by is not empty"` |

Every one traverses a declared inverse — `tasks`, `projects`, `entries`,
`superseded_by` are all in `query.inverses.by_target`. So the guards are
already queries; they are just written as sentences.

Two ways to close it:

**(a) Hand-implement each guard in TypeScript, keyed by machine and
transition,** with a meta-test asserting every declared guard has an
implementation and every implementation a guard. The prose stays documentation.

**(b) Express each `check:` as a query-contract tree,** which `query.shape` and
`query.operators` already define, and evaluate it.

**Recommend (b).** The query contract exists precisely so that "the query layer
is defined by the schema rather than by whatever the first app happened to
implement", and a guard hand-written in TypeScript is that failure in
miniature. Four guards is a small, closed corpus to make the contract real
against.

The cost is honest and should be stated: **(b) pulls a query evaluator forward
out of phase 5.** The mitigation is to implement only the operators these five
checks use — `eq`, `in`, `is`, and edge traversal — and let a meta-test fail if
a guard ever uses an operator `core` has not implemented. Phase 5 then widens
one evaluator instead of meeting one already in production.

### 3.2 `requires_index` is a fifth shape saying the same thing

`document` → `superseded` uses `requires_index:` where the other machines use
`requires:`, because the requirement is on the *inbound* index rather than on a
field of the record. Under (b) that distinction disappears — an edge traversal
in the inverse direction is just a query — and `requires_index` can either
fold into `requires:` or stay as a deliberate signal to a human reader.

Settle it as part of 3.1. Do not leave two spellings whose difference stops
being real.

### 3.3 `document.status` is optional, and its machine declares an initial state

`doc_status` is `required=false`, so a document may exist with no status at
all. The machine declares `initial: active`. Those two facts do not compose:

- If NULL **means** `active`, then `illegal-transition` has to treat NULL as
  `active` on every comparison, and `active` becomes unrepresentable-as-absent.
- If NULL means **stateless-until-set**, then the first write of a status is
  not a transition and the machine does not govern it.

`document` is the only machine on an optional field; the other four are on
required ones. Evidence available: **zero document records**. This is thin
enough that the honest move may be `open_questions`, on the `resource-status`
pattern — but unlike `resource-status`, this one **blocks step 12**, so it
cannot simply be recorded and left. Decide it, or decide that documents have no
machine until a real one has a status.

---

## 4. The mechanism that answers questions 3 and 4 of the phase 1 plan

Phase 1 §13 left two questions and predicted "the same mechanism answers both".
It does, and it also covers two of the three cross-row triggers.

**Question 3 — required links.** `group.members`, `meeting.attended` and
`world-entry.appears_in` are declared `required: true` and none can be
`NOT NULL`, because a link is a row in `link`, not a column.

**Question 4 — link-typed subtype `adds`.** Four fields are contributed by a
subtype value rather than by the type:

| Field | Only legal when |
|---|---|
| `document.carrier` | `doc_type = 'insurance-policy'` |
| `document.vendor` | `doc_type = 'service-record'` |
| `document.issued_by` | `doc_type = 'certificate'` |
| `resource.plan_for` | `resource_type = 'plan'` |

`subtype-field-on-wrong-subtype` is a CHECK for scalar `adds` and cannot reach
these, because the CHECK is on the subtype table and the value is in `link`.

### The shape

Both are **registry-driven triggers**, seeded from `types.yaml` exactly as
`link_field` already is (D2, D8). The alternative — hand-written SQL per field
— makes "adding a link field is a YAML edit" false, which is the same promise
D8 protects for vocabularies.

- **`0008`** adds `link_field.required boolean NOT NULL`, already computed by
  the model as `LinkField.required`, and one **deferred** constraint trigger
  function that asserts a source record has at least one `link` row for each of
  its required fields. Deferred `INITIALLY DEFERRED` so the natural write order
  — insert the record, insert its links, commit — works inside one transaction.
- **`0009`** adds a `link_guard(source_type, field, guard_field, guard_value)`
  registry and **two immediate** triggers: one on `link`, checking the source
  row's guard column; one on the guarded table, checking existing links when
  the guard column changes. Both directions, or a `doc_type` edited after the
  fact leaves an orphaned `carrier`.

The cross-check gains the same treatment it already gives `link_field`: the
live registry must equal the model, in both directions, and the phase 1
finding about A5/A6 applies — pair each with a test that **drifts the live
table inside a transaction** and asserts the comparison notices, or the check
agrees with itself by construction and cannot fail.

### The three cross-row triggers, in `0010`

Two of the three are the *same shape* as a required link — a state value
requires a link to exist:

| Rule | Condition |
|---|---|
| `blocked-task-without-blocker` | `task.state = 'blocked'` requires ≥1 `blocked_by` link |
| `superseded-without-successor` | `document.status = 'superseded'` requires ≥1 **inbound** `supersedes` link |

Both deferred, for the same write-ordering reason. Note the direction on the
second: the check is against the index, not the record — you cannot mark a
document superseded by nothing.

The third is a forbid rather than a require, and needs both edges:

| Rule | Condition |
|---|---|
| `area-closed-with-active-projects` | `area.status = 'closed'` forbids any project linked by `serves` with `status = 'active'` |

Triggered on `area` status change **and** on anything that would create the
violating pair from the other side — a project going `active`, or a `serves`
link appearing. `ERROR` severity, per the machine guard: *"a project serving a
closed area is genuinely incoherent — unlike a loose task."*

### The cost, stated

A deferred trigger reports at `COMMIT` with no statement context. **Name every
constraint after its rule id**, so `core` can map the SQLSTATE and constraint
name back to a rule and a record. Phase 1 already asserts constraint names
rather than error text — for a good reason, discovered the hard way — and the
same discipline pays for itself here.

---

## 5. `packages/core`

```
packages/core/
  src/
    index.ts
    route.ts          type + subtype + attaches_to -> folder, jd
    lifecycle.ts      the machine interpreter: transitions, requires, effects
    guards.ts         the query subset the guards need
    rules/            one file per advisory rule, registered by its id
    import/
      derive.ts       the 6 import.derived rules
      slug.ts         slugify(filename)
  test/
    route.test.ts
    lifecycle.test.ts
    guards.test.ts
    rules.test.ts
    import.test.ts
    registry.test.ts  ** declared == implemented **
```

Same toolchain as phase 1: `node:test`, Node type stripping, no build step,
`erasableSyntaxOnly`. `core` depends on `@quantum-quill/schema` and
`@quantum-quill/db`; nothing depends on `core` until phase 3.

### The router

Pure, and deliberately without an opinion on storage — `folder-storage` is an
open question that phase 4 decides, and a router that returns a path commits to
neither answer. Everything it needs, phase 1's model already derives:
`routingKeys` (65) and `layoutClaims`.

Four shapes beyond the layout lookup, all declared in `routing.explicit`:
`project` by `scope` through a map, `area` by its own id, `document` by
`attaches_to` relative to its container, `world-entry` by `appears_in` relative
to its world. The last two resolve against another **record**, so the router
takes the container's folder as an argument rather than reaching for a
database — which is what keeps it pure and what makes the phase 4 question
still answerable either way.

Archive destination is computed, not looked up: category `9N` receives area
`N0–N9`.

### The machine interpreter

Reads `lifecycle.machines` and interprets it. It must not contain a transition
table — five machines, four of them provisional, and phase 3 is expected to
churn them. A hard-coded transition is a YAML edit that silently does nothing.

Effects are the one place the schema has no closed vocabulary: `stamp`,
`move_to`, `preserve`, `keep`, `unblock`, `archive` are free text inside
`lifecycle`. Do **not** invent a `vocabularies:` entry to close it — that is
schema vocabulary invented to serve an implementation. Close it the way the
retired validator closed its own rule registry: a meta-test asserting the set
of effect verbs appearing in the YAML equals the set `core` implements. A new
verb then fails a test instead of being ignored at runtime.

`task` → `done` is the effect worth writing a real test for: it stamps
`completed` **and** unblocks every task listing it in `blocked_by`, which move
to `open` and never straight to `done`. It is also the only `derived` machine —
30 real tasks — so it is the one place a transition test is evidence rather
than a restatement of an assumption.

### The advisory rules

Six, all WARN, all cross-row, none refusable:

`link-to-archived-record` · `finished-project-without-result` ·
`person-without-relationship` (required on create, warned on import) ·
`project-done-with-open-tasks` · `world-archived-with-entries` ·
`terminal-record-not-archived`

Each is a query plus a message. Phase 2 produces them **as data** — rule id,
severity, record, message — and takes no position on when they surface; phase 3
is the consumer and gets to decide. `project-done-with-open-tasks` is
deliberately the same check as the `project` → `done` guard at a different
severity, so guard and rule should share one implementation rather than agree
by coincidence.

### The import derivations

Six derivations and three manual fields, all measured against 88 real records
on 2026-08-17. Phase 2 **builds and unit-tests** them; phase 8 runs them. They
are pure functions over filenames and frontmatter, so fixtures test them
honestly — with one caveat worth naming: a green fixture suite is a weaker
claim than a real run against the corpus, in the same way local green was a
weaker claim than CI in phase 1.

Two carry real subtlety:

- **`meeting.date`** is a *truncation* of `created`, taken in the vault's local
  zone. In UTC, a meeting written up late in the evening moves to tomorrow.
  Where the zone comes from is not declared anywhere — see §8.
- **`journal.date`** parses two filename patterns: `YYYY-MM-DD-[W]WW-DDD` for
  dailies and `YYYY-Www` for weeklies. Migration `0006` exists precisely so a
  daily and a weekly can share a Monday, so the parser and the constraint are
  two halves of one decision.

---

## 6. Work plan

Each step ends with something you can run.

| # | Step | Done when |
|---|---|---|
| 1 | **§2.1** — type `lifecycle`, `import` and the real `routing.explicit`; remove every `as any` | `npm run typecheck` green with the machines and derivations reachable as typed data |
| 2 | **§2.2** — correct design §5 from the measured register; fix 18 → 19 link fields | The doc matches `constraints.test.ts`; the counts test still pins it |
| 3 | **§2.3** — commit the `pg_dump` / restore script | Dumps the compose database and restores it into a scratch one |
| 4 | **§2.4** — `app` with `/healthz`, two listeners | Both answer; the LAN-only one is a separate bind, not a conditional |
| 5 | **§3** — settle the guard representation and `document.status`, as edits to `types.yaml` | Both files parse; all 10 phase-1 meta-tests still green |
| 6 | `packages/core` skeleton + `registry.test.ts`, **red** | It names all 28 rules and fails on the 12 phase 2 owes |
| 7 | The router | All 65 keys, the 4 explicit shapes, `9N` archiving, container-relative both ways |
| 8 | `0008` — `link_field.required` + the deferred required-link trigger | The 3 required links are refused; the rule moves in the register |
| 9 | `0009` — `link_guard` + the subtype-guard triggers, both directions | `carrier` on a non-policy refused, and refused again if `doc_type` is edited away |
| 10 | `0010` — the three cross-row triggers | Each refuses; all three move in the register |
| 11 | The guard evaluator | The 4 guards and the `requires_index` evaluate against real rows |
| 12 | The machine interpreter | `illegal-transition` and `transition-requirement-unmet` refuse; `task` → `done` unblocks dependents |
| 13 | The 6 advisory rules | Each fires on a constructed case **and stays quiet otherwise** |
| 14 | The import derivations, against fixtures | All 6 derive the declared field from the declared source |
| 15 | CI, `README.md`, `CLAUDE.md` | `core` in the test glob; the docs describe what exists |

Step 1 blocks everything. Step 5 blocks 11 and 12. Steps 8–10 share the
registry-and-trigger pattern, so 8 is the expensive one and 9–10 are cheap
after it. Steps 2–4 are independent of the rest and of each other.

**Every trigger and every rule must be watched failing before it is trusted.**
Phase 1's A5/A6 finding is the precedent: two cross-checks that could not fail,
green for a reason that had nothing to do with correctness.

---

## 7. Risks

| Risk | Response |
|---|---|
| The guard decision drags a query evaluator forward from phase 5 | Implement only the operators the five checks use. A meta-test fails if a guard reaches for one that is not there |
| Deferred triggers report at `COMMIT` with no statement context | Every constraint named after its rule id; `core` maps back. Phase 1 already asserts constraint names rather than messages |
| Four of five machines are provisional; phase 3 churns them | The interpreter reads the YAML. Churn is a YAML edit — unless someone hard-codes a transition, which is the actual risk |
| Import derivations cannot meet the real corpus until phase 8 | Fixtures built from the measured counts in `import.derived`. State plainly that green here is a weaker claim than a real run |
| The trigger registries agree with the model by construction | Each paired with a drift test inside a transaction, exactly as A5/A6 were repaired |
| `core` grows into an application layer, and phase 3 inherits a private API | `core` returns data — rules produce findings, the router returns a path, the interpreter returns a transition result. Nothing in it renders, prompts or decides |
| Postgres version drift, again | Unchanged: pinned by digest, and CI remains the authority for anything version-sensitive |

---

## 8. Open questions this plan raises

1. **The vault's local timezone is not declared anywhere.** `import.derived`
   requires `meeting.date` in "the vault's local zone", and neither schema file
   says what it is. Configuration (`.env`) or schema (`types.yaml meta`)?
   Blocks step 14, and only for 14 records.
2. **`area` routes by its own id, which must be a category id in area 20–29.**
   Nothing enforces that a future `area` record has a home. Core rule, a
   foreign key to a seeded `category` table, or unchecked until phase 4 builds
   the tree? The seeded-registry pattern from §4 would cover it cheaply.
3. **When do advisory rules run?** On write, on read, or as a sweep. Phase 2
   only has to emit them as data; phase 3 is the consumer and should decide
   with a UI in front of it.
4. **`folder-storage` remains open, as designed.** The router being pure keeps
   both answers available. Still phase 4's call — it has to write the real path
   anyway.

---

## 9. What step 1 found

**The drift was twice as wide as §2.1 described.** §2.1 named `lifecycle`,
`import` and `routing.explicit`. Measured, `Types` declared **8 of the 18**
top-level blocks in `types.yaml` and `Layout` **4 of the 7** in
`Folder-layout.yaml`. Also absent: `provenance_levels`, `provenance_review`,
`conventions`, `field_attributes`, `containers`, `stubs` — and, on the layout
side, `conventions`, `tombstones`, `excluded`. `open_questions` was typed with
2 of its 7 keys and `query.indexes` with 3 of its 6.

Nothing was wrong with any of it, which is the point: a cast cannot fail, so
none of it was ever going to surface on its own.

### How it is held now

`TYPES_KEYS`, `LAYOUT_KEYS` and `FIELD_ATTRIBUTE_KEYS` are runtime lists,
checked in both directions:

- **At compile time**, against the TypeScript type. An `Exact<>` helper
  resolves to `never` when the list and the type disagree, so the assignment
  fails to compile — proved by adding a key to `Types` alone, to the list
  alone, and by shortening `LAYOUT_KEYS`.
- **At test time**, against the file. `packages/schema/test/load.test.ts`
  compares each list to `Object.keys()` of the parsed YAML — proved by adding
  a block to `types.yaml`, removing `stubs`, and removing `tombstones` from the
  layout.

Neither half is sufficient alone. The compile-time proof says the list matches
what we declare; the test says what we declare matches what exists.

`FieldSpec` gets a stronger version of the same check, because the file
declares its own field-attribute vocabulary: `field_attributes` has 10 entries,
and `FieldSpec` must carry exactly those beyond `key`, `type` and
`description`. That is not a hand-copied expectation — it is the schema
checking itself, and it caught `symmetric` and `derived_from` missing from the
type.

Nested shapes are guarded more weakly: a no-undeclared-keys test over the six
collections phase 2 reads (`machines`, `transitions`, `guards`,
`routing.explicit`, `import.derived`, `open_questions`). It catches the file
gaining a key, which is the drift that actually happened, but it is a second
hand-derivation rather than a proof. Stated so it is not mistaken for one.

All eleven deliberate breaks were watched failing before any of this was
trusted.

### A schema question step 1 raised — for §3

The attribute check went red on its first run, on a real defect:

> `resource_type: software-license` adds
> `{ key: license_key, type: text, sensitive: true }`, and `field_attributes`
> declares no `sensitive` attribute.

Sensitivity is **folder-scoped everywhere else in the project**: the layout
marks *categories* sensitive (`31`, `34`, `36`), `sensitive-not-scanned`
excludes those folders from the text index, and the service design binds them
to a LAN-only listener. This is the only field-level use in either file, and
`software-license` routes to **`38 Purchases, Warranties & Licenses`, which is
not sensitive** — so the attribute claims a protection no mechanism delivers.

Three ways out, none taken here: declare `sensitive` as a field attribute and
give it a mechanism; drop it as a stray; or mark the category sensitive and let
the existing folder-scoped machinery cover it. It is recorded as a registered
exemption in `load.test.ts`, under the same two rules as
`packages/db/test/exemptions.ts` — an entry that stops matching anything fails
the suite, so it cannot quietly become permanent.

**This wants an `open_questions` entry in `types.yaml`**, which is a schema
edit and therefore step 5's business, not step 1's.

### Caveats

- Verified against **PostgreSQL 16**, not the 18 that compose and CI pin. Step
  1 touches no SQL, so the exposure is small — but phase 1 §14 established that
  CI is the authority for anything version-sensitive, and that has not changed.
- Full suite: **71 tests green**, up from 60.
