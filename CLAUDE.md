# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Orient yourself first: there is no code here

This repository is a **specification**, not an application. Seven files: two
schema YAMLs, two design documents, a PowerShell scaffolder, a README and this
file. No `package.json`, no source tree, no tests, no build.

That is the current, intended state — not an incomplete checkout. Two
implementations have already been written and discarded (see **Discarded
architectures**), and both were discarded before the schema moved. Do not go
looking for an implementation, and do not assume one is missing.

## The method, which governs how you should change things

The project exists because a previous attempt grew application-first and ended
up with a taxonomy shaped by whatever the tools happened to do. The correction
is: **define the schema, derive it from real material, then build to it.**

Two consequences bind your work here:

**1. Reality outranks invention, with one exception.** When real material and
the schema disagree:

> Where they differ **for no principled reason, reality wins**. Where reality
> encodes a **workaround for the old tool, the schema wins**.

This is why `outcome` was renamed `result` (reality had it, no reason to
prefer the invention) but `project_start` stayed `start` (the prefix only
existed to dodge a flat frontmatter namespace).

**2. Do not guess.** `types.yaml` has an `open_questions:` block. When evidence
is thin or ambiguous, record the question there with what would resolve it,
rather than inventing a vocabulary to close the gap. There is a live example:
`resource-status`.

## The two schema files

| File | Answers | Structure |
|---|---|---|
| `types.yaml` | What a record **is** | `universal`, `types` (14), `vocabularies`, `lifecycle`, `query`, `import`, `validation`, `open_questions` |
| `Folder-layout.yaml` | Where a record **lives** | `zones`, `rules`, `areas` (10) each with `categories` (60 total) |

Records and folders are identified by permanent kebab-case slugs. Johnny
Decimal numbers are **addresses, not keys** — renumbering, moving and archiving
never break a reference. This is load-bearing; do not propose making the JD
number the identifier.

### The coupling you must understand

**The routing table is `Folder-layout.yaml` read in reverse.** Types never name
folders. Each category declares a `types:` list, and those lists name
**subtype values** (`paystub`, `w2`), not core types. To find where a record
goes, look up its subtype value in the layout.

Consequences when editing:

- **Adding a subtype value to `types.yaml` requires adding it to a category's
  `types:` list**, or it routes nowhere. Every value must resolve to *exactly
  one* category — two categories claiming one key is ambiguous and has happened
  before (`report` collided between `05 Logs & Audits` and `39 Work Products`;
  resolved by renaming the system one to `audit`).
- **Adding a link field requires an `inverse:` name** that is unique on its
  *target* type, not globally. `area` receives four; `organization` receives
  six. The declared list lives in `types.yaml` under `query.inverses.by_target`
  and must match what the fields actually declare.
- **Three types route by something other than a subtype** and declare it under
  `routing.explicit`: `project` (by `scope`), `area` (by its own id), and
  `world-entry` (into its world's folder). `document` additionally overrides to
  container-relative routing whenever `attaches_to` is set.
- Archive category `9N` receives area `N0–N9`. Computable, no lookup table.

### Provenance: know which half to trust

Every type, vocabulary, state machine and folder area carries a marker. Roughly
half the schema is `provisional`.

- `derived` — real material contradicted the design and changed it
- `confirmed` — real material exercised it and it held (weaker than it sounds;
  may only mean nothing pushed hard enough)
- `provisional` — no real instance; an informed bet

State machines are the weakest layer: four of five are provisional, because no
record has ever changed state. Hold provisional definitions loosely and expect
churn once real records exist.

### The invariant that governs folder edits

From `Folder-layout.yaml` → `rules` → `stable-single-valued-partitions`:

> A category may partition only by an attribute that is stable and
> single-valued.

Scope (work/personal/creative) qualifies. Relationship (family/friend/colleague)
does not — people are several at once. **Reach for a field before a new
category.** Encoding a multi-valued attribute in a path forces a false choice at
filing time and makes the obvious query unanswerable.

## Commands

There is no build or test tooling yet. What exists:

```powershell
# Build the folder tree from the layout file (idempotent; -WhatIf to preview)
.\New-VaultTree.ps1 -LayoutFile .\Folder-layout.yaml -Root D:\vault -WhatIf
```

```bash
# Sanity-check both schema files parse
python -c "import yaml; yaml.safe_load(open('types.yaml',encoding='utf-8')); yaml.safe_load(open('Folder-layout.yaml',encoding='utf-8')); print('ok')"
```

Phase 1 (below) introduces the real toolchain: npm workspaces, numbered `.sql`
migrations, and the DDL cross-check test.

## Current architecture (designed, not built)

`docs/design/2026-08-18-service-design.md` is authoritative. In short: an
always-on service on a homeserver, reached through a Cloudflare Tunnel, with
**Postgres as the source of truth** and a **projector** that renders every
change back out to the Johnny Decimal tree as markdown — so plain-text
durability survives the database instead of being traded for it.

Points that are easy to get wrong:

- **Sensitive categories are LAN-only** (`31 Identity & Vital`,
  `34 Insurance & Medical`, `36 Legal & Correspondence`). Enforced by binding
  them to a separate listener, *not* by a conditional — cloudflared forwards to
  localhost, so source address cannot distinguish tunnel from LAN.
- **The projector runs one direction only.** The tree is read-only; edits go
  through the app.
- **Projected filenames are slugs** (`paint-line.md`), so a future Obsidian
  reader resolves `related: [paint-line]` in frontmatter natively. This
  deliberately supersedes `conventions.record_file` in `types.yaml`.
- Putting the data in Postgres turns ~12 of the 28 validation rules from
  detection into prevention and dissolves 4 outright. Only ~9 advisory rules
  need application code.

## Discarded architectures — do not re-propose without new information

| Discarded | Why |
|---|---|
| Obsidian plugin (`Vault Core Plugin Design.md`, deleted) | Built top-down; schema retrofitted to the tools |
| VS Code extension + LSP | An extension cannot run when the editor is closed, so no recurrence, reminders or scheduled anything |
| Files-as-truth + Syncthing | Superseded by Postgres; sync conflicts and a drifting index for no gain |
| Python validator (archived) | ~12 of its rules become database constraints; project moved to TypeScript |

The Python validator is archived at
`D:\quantum-quill-python-validator-2026-08-18.tar.gz` (verified by restore
test). It found nine schema defects before being retired — that work is why the
`derived` markers exist.

## Next step

**Phase 1: the compose stack, numbered SQL migrations, and the DDL cross-check
test.**

The cross-check is the load-bearing piece. It asserts the live Postgres schema
and `types.yaml` agree in both directions — a column with no field fails, a
field with no column fails, an enum whose values differ fails. It is the same
discipline as the retired validator's declared-equals-implemented meta-test,
applied one layer down.

Without it, `types.yaml` quietly degrades from executable specification to
advisory documentation the moment SQL exists alongside it, and the project
drifts back into exactly the failure it was created to correct.

Phase 3 (create, view, edit) is the one that matters for usefulness — it is
where records start going in and the provisional half of the schema finally
gets tested. Phases 1 and 2 are groundwork for it.
