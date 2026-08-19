# quantum-quill

A schema for a typed personal information manager, and — eventually — the
service built to it.

The schema came first and the application is being built to it, deliberately,
because the previous attempt grew the other way round and ended up with a
taxonomy shaped by whatever the tools happened to do.

## The schema

| File | Answers |
|---|---|
| [`Folder-layout.yaml`](Folder-layout.yaml) | Where a record lives — Johnny Decimal areas, PARA inside the typed zone, routing, filing rules |
| [`types.yaml`](types.yaml) | What a record is — 14 core types, 130 vocabulary values, lifecycle, the query contract, validation rules |

Folders and records are identified by permanent kebab-case slugs. Johnny Decimal
numbers are *addresses*, not keys, so renumbering, moving and archiving never
break a reference.

### It says how much of itself to trust

Both files carry **provenance markers**. Roughly half the schema is
`provisional` — an informed bet with no real instance behind it — and the files
say which half:

| | derived | confirmed | provisional |
|---|---|---|---|
| types | 7 | 3 | 4 |
| vocabularies | 5 | 2 | 9 |
| state machines | 1 | 0 | 4 |
| folder areas | 3 | 2 | 5 |

`derived` means real material contradicted the design and changed it.
`confirmed` means real material exercised it and it held. `provisional` means
untested — expect it to be wrong in ways nothing in the file can predict.

The schema was tested against 88 real records and 114 real binaries, which
found nine defects in it. That is why the `derived` column is not empty.

## The service

Designed, not yet built. See [`docs/design/`](docs/design/).

An always-on service on a homeserver: **Postgres as the source of truth**, with
a projector that renders every change back out to the Johnny Decimal tree as
markdown, so plain-text durability survives the database rather than being
traded away for it.

Putting the data in Postgres turns roughly twelve of the twenty-eight
validation rules from *detection* into *prevention* — `duplicate-id` becomes a
primary key, `unresolvable-link` a foreign key — and dissolves four more
outright.

| Document | Status |
|---|---|
| [2026-08-19 — Phase 1 implementation plan](docs/design/2026-08-19-phase-1-implementation-plan.md) | proposed |
| [2026-08-18 — Service design](docs/design/2026-08-18-service-design.md) | current |
| [2026-08-17 — Application design](docs/design/2026-08-17-application-design.md) | superseded |

## History

A Python validator implementing all 28 record rules and 14 schema checks was
built, run against real material, and archived once Postgres made most of it
structural. It did its job first: it is what found the nine schema defects.

`New-VaultTree.ps1` builds the folder tree from `Folder-layout.yaml`. It is
superseded in the long run by the projector, but useful for bootstrapping an
empty tree before that exists.
