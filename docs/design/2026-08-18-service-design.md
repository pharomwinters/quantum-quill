# Service Design

**Date:** 2026-08-18
**Status:** approved, not yet implemented
**Supersedes:** [2026-08-17-application-design.md](2026-08-17-application-design.md)

Companion to [`types.yaml`](../../types.yaml) and
[`Folder-layout.yaml`](../../Folder-layout.yaml). Those define the schema; this
defines the service built to it.

---

## 1. What changed, and why it was cheap

Yesterday's design was a VS Code extension over an LSP server, with files on
every machine replicated by Syncthing. It is superseded.

Three limitations decided it, all structural rather than fixable: an editor
extension **cannot run when the editor is closed**, which rules out recurrence,
reminders and scheduled anything; VS Code has **no mobile presence at all**;
and its UI vocabulary is text, so every list, form and dashboard becomes a
webview — a web app with extra steps.

Mobile turned out not to matter. The capture habit, unchanged for years, is
*email yourself, file it properly later*. Which is the finding that shapes this
design: **a service can read that mailbox.** The existing habit becomes the
capture mechanism, with no new habit and no phone client.

**The pivot cost one commit.** Both discarded architectures were discarded
before implementation, because the schema was the artifact and the schema did
not move. That is the method working, not failing.

---

## 2. Decisions locked

| Decision | Choice | Why |
|---|---|---|
| Shape | **Always-on service** on the homeserver | Recurrence, reminders and email ingest are impossible without a process that outlives the client |
| Reachability | **Cloudflare Tunnel** | No inbound port, no admin, no VPN driver — the work machine allows installs but not admin |
| Auth | **Cloudflare Access** in front | No login screen to build; the app verifies `Cf-Access-Jwt-Assertion` |
| Source of truth | **Postgres** | Turns ~12 of 28 validation rules from detection into prevention |
| Durability | **Continuous projection** to the Johnny Decimal tree | Keeps plain-text durability without paying for it in query power |
| Projected filenames | **Slugs** (`paint-line.md`) | So a future Obsidian reader resolves `related: [paint-line]` natively |
| DDL | **Hand-written, cross-checked** against `types.yaml` by test | Idiomatic SQL, standard migrations, drift unshippable |
| UI | **Server-rendered**, editor component only on `/edit` | Least code for the most working surface |
| Language | **TypeScript** | One language; the Python validator is superseded |
| Sensitive categories | **LAN only** | `31 Identity & Vital`, `34 Insurance & Medical`, `36 Legal & Correspondence` never traverse the tunnel |

### Why plain-text durability survived a database

The principle, from an earlier design in this project:

> *"notes stay plain markdown + YAML frontmatter + wikilinks. A broken build
> degrades rendering, never readability."*

A database costs that, and "export later" is weaker than it sounds — the
exporter gets written at the moment you are already leaving, by someone
motivated to be done rather than careful.

The projector resolves it. Postgres is authoritative and enforces; a job
renders every change to markdown in the JD tree. The export path is not a
future project, it runs on every write, so it is proven continuously.

---

## 3. Architecture

```
   browser  (home · work · anywhere)          browser  (LAN only)
      |   https://vault.<domain>                 |  https://vault.lan
      v                                          |
   Cloudflare  -- Access policy                  |
      |   tunnel, no inbound port                |
      v                                          v
   homeserver -- docker compose
      |
      +-- app         Hono · server-rendered HTML · TWO listeners
      +-- postgres    SOURCE OF TRUTH
      +-- projector   JD tree on every commit; git commit daily
      +-- scheduler   recurrence · reminders · retention
      +-- ingest      IMAP poll -> 06 Inbox
```

**Two listeners, deliberately.** cloudflared forwards to localhost, so the app
cannot distinguish tunnel traffic from LAN traffic by source address. The
tunnel listener and the LAN listener are separate ports, and sensitive
categories are simply not routed on the tunnel listener. Enforcement by
topology rather than by a conditional someone can get wrong later.

---

## 4. Data model

Supertype/subtype. This is what makes polymorphic, multi-valued links work.

```sql
record        id PK · type FK · title · body · created · updated · archived_on
document      id FK->record · doc_type FK · doc_date · file · revision · ...
person        id FK->record · role · email[] · phone[] · met · ...
task          id FK->record · state FK · priority FK · due · completed · ...
              (one table per core type, 14 in total)

link          source FK->record · field · target FK->record
              UNIQUE (source, field, target)

vocabulary    name · value          <- SEEDED FROM types.yaml
```

Three consequences:

- **`link` as one table** handles both awkward cases in the schema at once:
  `to: [organization, person]` is polymorphic, and `list[link]` is
  multi-valued. Both are rows.
- **Inverses become a query**, not a maintained structure —
  `SELECT source FROM link WHERE target = $1 AND field = 'attended'`. The edge
  index disappears entirely, along with any possibility of it drifting.
- **Vocabulary tables are seeded from `types.yaml`.** Adding a `doc_type` stays
  a one-line edit to the YAML; the foreign key enforces it. The schema file
  remains where vocabularies live.

### The DDL cross-check

A test asserts the live schema and `types.yaml` agree in both directions: a
column with no field fails, a field with no column fails, an enum whose values
differ fails. The same discipline as the rule registry's
declared-equals-implemented test, applied one layer down.

---

## 5. What the database enforces

Of 28 declared rules:

| Fate | Count | Mechanism |
|---|---|---|
| **Become constraints** | ~12 | `PRIMARY KEY`, `FOREIGN KEY`, `NOT NULL`, `date`, `CHECK` |
| **Dissolve entirely** | 4 | `wrong-folder`, `container-id-mismatch` (no folders to be wrong about); `organization-as-text` (it is a link or it is not); `empty-field-normally-filled` (typed columns) |
| **Need triggers** | 3 | `area-closed-with-active-projects`, `superseded-without-successor`, `blocked-task-without-blocker` — all cross-row |
| **Stay app rules** | ~9 | The advisory ones: `stale`, `orphan`, `project-done-with-open-tasks`, `missing-payload` |

`subtype-field-on-wrong-subtype` is the pleasing one:
`CHECK (doc_type = 'paystub' OR gross IS NULL)`. A deed carrying a `gross`
stops being a finding and becomes a rejected write.

---

## 6. The projector

Renders changed records to markdown and writes them into the JD tree.
`Folder-layout.yaml`'s routing table is its specification — including
container-relative routing for `attaches_to`, and archive `9N` mirroring.

- **One direction only.** The tree is read-only; edits go through the app.
  Two-way sync between a database and a filesystem is a genuinely hard problem
  and buys nothing here.
- **Filenames are slugs.** `paint-line.md`, not `Paint Line.md`, so a future
  Obsidian reader resolves `related: [paint-line]` in frontmatter natively —
  its graph and backlinks read frontmatter links. `title` carries the display
  name. This supersedes `conventions.record_file` in `types.yaml`, which was
  written when files were the source of truth.
- **Handles moves** — write the new path, remove the old — and is idempotent,
  with a full re-projection command.
- **git commit every 24 hours**, batching the day's changes. The tree is
  written continuously; only the commit is daily.

---

## 7. Stack

| | | Why |
|---|---|---|
| Hono + JSX | HTTP, server-rendered HTML | Type-safe templates in TypeScript, no template language |
| Kysely | Query builder | Types queries *against* the schema without owning it — correct, since the DDL is hand-written |
| Numbered `.sql` + small runner | Migrations | Fewest moving parts, full SQL control |
| HTMX | Interactivity | Avoids an SPA for lists, filters and forms |
| CodeMirror 6 | Markdown editing | Loads only on `/edit` |
| imapflow | Email capture | The existing habit becomes the capture mechanism |
| Cloudflare Access | Auth | Verify the JWT header; no login to build |

---

## 8. Phases

| Phase | Deliverable |
|---|---|
| **1** | Compose stack, migrations, DDL cross-check test green |
| **2** | `core` ported to TypeScript — rules Postgres cannot enforce, import derivations |
| **3** | **Create, view, edit.** The floor: records go in, the provisional schema starts being tested |
| **4** | Projector + daily git |
| **5** | Lists, filters, saved views over the query contract |
| **6** | Email ingest into `06 Inbox` |
| **7** | Scheduler — recurrence, reminders, retention |
| **8** | Migrate the real material (the deferred type remapping) |

Phase 3 is the one that matters. Everything before it is groundwork; everything
after improves something already working.

---

## 9. Backup and recovery

| What | When | Holds |
|---|---|---|
| `pg_dump`, gzipped, off-box | **nightly** | Everything. The only true restore path |
| Projected tree, git commit | daily | Records only — no link table, no vocabularies, no internal state |

**The tree is not a backup.** It is a readable fallback and a future Obsidian
source. Recovering from it means writing an importer while already in trouble.

Nightly rather than weekly is a deliberate change from what was first proposed:
this database will be single-digit megabytes, so a dump costs seconds and
kilobytes, while a weekly cadence would mean a seven-day loss window on
identity, legal and medical records. Weekly optimises nothing measurable.

Both artifacts contain sensitive categories. Wherever they are stored, they
carry `31`, `34` and `36` with them.

---

## 10. Risks

| Risk | Mitigation |
|---|---|
| **Availability is now a real property** — home internet or power down means no notes, from anywhere | Accepted. The projected tree is readable on the LAN; the future Obsidian companion reading the git repo is the offline answer |
| Cloudflare terminates TLS | Sensitive categories never traverse the tunnel — enforced by binding them to a separate listener, not by a conditional |
| Half the schema is provisional and phase 3 starts testing it | Expected. `first-instance-of-provisional` already fires on the first record of a provisional type. Budget for schema churn after phase 3 |
| Backups are entirely self-managed | Nightly off-box dump; restore rehearsed at least once before phase 8 puts real material in |
| Postgres becomes a single point of failure for readability | The projector, running continuously, is the answer — and it is phase 4, not deferred |

---

## 11. Future, not now

1. **Obsidian companion plugin** reading the projected git repo — offline and
   mobile reading of everything the service holds, using an app that already
   solves both. The slug-filename decision in section 6 exists so this works
   when it arrives.
2. **A read-only API** for anything else that wants the data.

---

## 12. Open questions

1. **`resource-status`** — carried from `types.yaml`. Three real resources
   carry a status the type has no field for. Decide on first real use of a
   `plan` resource.
2. **Type migrations** — `daily` to `journal` + `period`, `polity` to
   `world-entry`, `A3` to `document`/`analysis`. Deferred deliberately; this is
   phase 8 and accounts for most of the errors against real material.
3. **Task management is the thinnest part of the schema** — no recurrence, time
   tracking or contexts, all of which the previous setup had. `as-notes` is the
   reference to study before designing phase 7.
