# vault

A schema for a typed personal information manager, and the validator that enforces it.

The schema came first and the application is being built to it — deliberately, because
the previous attempt grew the other way round and ended up with a taxonomy shaped by
whatever the tools happened to do.

## The two schema files

| File | Answers |
|---|---|
| [`Folder-layout.yaml`](Folder-layout.yaml) | Where a record lives — Johnny Decimal areas, PARA inside the typed zone, routing, filing rules |
| [`types.yaml`](types.yaml) | What a record is — 14 core types, 81 subtype values, lifecycle, the query contract, validation rules |

Folders and records are identified by permanent kebab-case slugs. Johnny Decimal numbers
are *addresses*, not keys, so renumbering, moving and archiving never break a reference.

Both files carry **provenance markers**. Roughly half the schema is `provisional` — an
informed bet with no real instance behind it — and the files say which half:

| | derived | confirmed | provisional |
|---|---|---|---|
| types | 7 | 3 | 4 |
| vocabularies | 5 | 2 | 9 |
| state machines | 1 | 0 | 4 |
| folder areas | 3 | 2 | 5 |

`derived` means real material contradicted the design and changed it. `confirmed` means
real material exercised it and it held. `provisional` means untested.

## The validator

```sh
uv run vault check                     # the two schema files against each other
uv run vault validate <path>           # records against the schema
uv run vault validate <path> --import  # apply declared derivations first
```

Every rule id declared in `types.yaml` has exactly one registered implementation, and a
test asserts the two sets match in both directions — so the validator cannot drift from
the schema it enforces.

## Development

```sh
uv sync
uv run pytest
```
