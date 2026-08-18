# Application Design

**Date:** 2026-08-17
**Status:** SUPERSEDED by [2026-08-18-service-design.md](2026-08-18-service-design.md).
The editor-extension architecture was replaced by an always-on service. Kept
for the reasoning it records — the schema and `core` decisions still hold.

Companion to [`types.yaml`](../../types.yaml) and
[`Folder-layout.yaml`](../../Folder-layout.yaml). Those define the schema; this
defines the program built to it.

---

## 1. What this is

A typed personal information manager. Records are markdown files whose
frontmatter is validated data and whose body is prose. The schema was written
first, on purpose — the previous attempt grew application-first and ended up
with a taxonomy shaped by whatever the tools happened to do.

That ordering has a consequence worth stating plainly: **most of what an
application would normally decide is already decided.** Types, fields,
vocabularies, where every record goes, what is queryable, which state changes
are legal, and what counts as invalid at three severities. What the schema is
silent on is how a person touches any of it. That silence is this document.

---

## 2. Decisions locked

| Decision | Choice | Why |
|---|---|---|
| Editor | **VS Code extension** | Already installed on both machines; a `.vsix` needs no admin; markdown editing is solved by an editor already liked rather than being the largest and least satisfying part of a bespoke app |
| Protocol | **LSP** | Diagnostics, completion, navigation, references and rename are protocol features rather than bespoke code |
| Language | **TypeScript throughout** | Distribution: VS Code ships a Node runtime, so a `.vsix` is self-contained. A Python server needs Python on a locked-down work machine |
| Storage | **Local files on every machine** | The validator already operates on a local directory |
| Sync | **Syncthing, supervised by the app** | Portable binary, no admin, no VPN, traverses NAT via its own relays |
| Homeserver role | **A sync peer, not an application host** | Nothing is exposed to the internet, which no-VPN would otherwise force |
| Schema location | **Inside the vault**, at `00-09 System/02 Schema/` | The layout declared that category for exactly this; the tree becomes self-describing |
| Package manager | **npm workspaces** | Node 24 / npm 11 are present; pnpm is not, and needs no adding |

### Why the homeserver runs nothing

The work machine permits installs but not admin, which rules out a VPN client
(WireGuard and Tailscale both need a driver on Windows). The usual consequence
is that the homeserver must be publicly reachable, with authentication as the
only thing protecting personal documents.

Syncthing avoids the dilemma entirely: it does its own NAT traversal and
discovery, needs no admin, and never requires an open inbound port. The
homeserver becomes a peer that happens to always be on.

---

## 3. Architecture

```
       VS Code  (home PC · work PC — no admin required)
          │
          ├── quantum-quill extension        TypeScript, deliberately thin
          │      creation forms · tree views · status bar
          │
          └── LSP over stdio
                 │
          language server                    vscode-languageserver
                 │
          core                               schema · index · rules
                 │
          local file tree  ←──── Syncthing (supervised binary)
                                        │
                                 homeserver — a peer, not a server
```

**The extension holds no schema knowledge.** Every question about types,
fields, vocabularies, routing or validity is answered by the server. This is
what keeps a second language from becoming a second source of truth.

---

## 4. Packages

```
quantum-quill/
  types.yaml                    the schema — language-neutral, unchanged
  Folder-layout.yaml
  docs/design/
  package.json                  npm workspace root
  packages/
    core/       @quantum-quill/core     schema, parse, index, rules, validate
    server/     @quantum-quill/server   LSP over core
    client/     quantum-quill           the extension (.vsix)
```

`core` exposes a CLI binary (`qq check`, `qq validate`) so the validator stays
usable outside the editor — in a git hook, or on the homeserver.

---

## 5. What LSP gives us

The mapping is close to one-to-one, which is the argument for the protocol:

| Already built | Becomes |
|---|---|
| `Finding` with rule, severity, target, message | `Diagnostic` — squiggles, Problems panel |
| Closed vocabularies | Completion on `doc_type:`, `state:`, `relationship:` |
| Forward link index | Go-to-definition — ctrl-click a link field |
| **Inverse** index | Find-all-references — every meeting a person attended |
| Permanent slug ids | Rename that updates every referrer |
| Schema `fields` + `adds` | A creation form, from the schema, with no per-type code |
| Routing table | The form knows where to write the file |
| Rule quick fixes | Code actions — insert a missing field, correct a value |

### The scope that could not be checked, can be

`illegal-transition` and `id-changed` needed `Scope.MUTATION` — a before *and*
an after — which a filesystem scan cannot supply. `textDocument/didChange`
supplies exactly that. Changing `status: active` to `status: done` on a project
raises the transition check live; editing an `id:` warns immediately that ids
are immutable.

Two rules that a scan could only declare become rules an editor can enforce.

---

## 6. Validation strategy

Full corpus revalidation per keystroke does not scale, even where it is fast
today. Three tiers, matching the three scopes:

| Trigger | Runs | Cost |
|---|---|---|
| change, immediate | RECORD rules on that document | one record |
| change, with previous state | MUTATION rules | one record |
| change, debounced ~300 ms | incremental index update, then CORPUS rules | edges in the changed document |
| external write (watcher) | re-parse — this is how Syncthing's changes arrive | one record |
| explicit command | SCHEMA rules (`check`) | both YAML files |

**Incremental index update** means removing a document's edges and re-adding
them, rather than rebuilding. The index is declared derived and disposable, so
a wrong index is always recoverable by rebuilding.

---

## 7. Creation

The floor for the first usable version: **creating a record must be easier than
the old setup.** Hand-writing frontmatter is worse than what came before, and
until creation works the schema stays theoretical — which matters because
[roughly half of it is marked provisional](../../types.yaml) and only real use
will test it.

Flow:

1. Command palette → pick a type (14) → pick a subtype where the type has one
2. A form generated from `fields`, plus whatever the subtype `adds`
3. Required fields enforced; closed vocabularies as dropdowns; link fields as
   pickers over the index
4. Destination resolved from the routing table — including container-relative
   routing for `attaches_to` and `world-entry`
5. `id` minted by slugifying the title, with collision handling
6. Written, opened, cursor in the body

No per-type code anywhere in that list. Adding a type to `types.yaml` adds a
creation form.

---

## 8. Sync

Syncthing ships as a supervised child process: the extension spawns the binary,
writes its configuration, and drives it through its REST API. The user never
sees Syncthing's own interface.

Until that is built (phase 5), configure Syncthing by hand once per machine.
Nothing else in the design depends on it.

**Conflicts.** Syncthing writes `*.sync-conflict-*` files rather than losing
data. The extension surfaces them; `duplicate-id` already catches the failure
that actually matters — two machines minting the same record.

---

## 9. Porting from Python

2,103 lines across 3 commits exist in Python. The port is mechanical because
the design, not the code, was the work.

**Ports directly:** the rule registry keyed by id; the four scopes; the
declared-equals-implemented meta-test; the forward-and-inverse index; the
three-tier validation strategy; the separation of schema-check rules into their
own registry.

**Ports mechanically:** 104 tests, pytest to vitest.

**Improves in the move:** Python's `parse.py` records no line numbers, so
findings carry a path but no position and cannot attach a squiggle. The `yaml`
npm package exposes source ranges on every node. That task disappears.

**Method:** port test-first, file by file, keeping the Python on a branch until
the TypeScript suite is green and reports the same findings against the same
real material. Then delete it.

---

## 10. Phases

Each phase ends with something usable.

| Phase | Deliverable | Why it is here |
|---|---|---|
| **1** | Workspace, `core` ported, 104 tests green, `qq` CLI | Parity before anything new |
| **2** | LSP server + extension: diagnostics with real positions | The rules become visible where the work happens |
| **3** | **Creation** — schema-driven forms, routing, id minting | The floor. Without it the schema stays theoretical |
| **4** | Navigation — completion, ctrl-click, references, rename | The index earns its keep |
| **5** | Actions — code-action quick fixes, transitions, archive, supersede | Lifecycle rules become operations |
| **6** | Syncthing supervision; conflict surfacing | Until now, configured by hand |
| **7** | Views — tree view over saved queries | The query contract becomes visible |

Phase 3 is the one that matters. Phases 1 and 2 are groundwork; 4 onward are
improvements to something already working.

---

## 11. Risks

| Risk | Mitigation |
|---|---|
| **Half the schema is provisional** and phase 3 starts testing it | Expected, not a failure. `first-instance-of-provisional` already fires on the first record of a provisional type. Budget for schema churn after phase 3 |
| Two languages become two sources of truth | The extension holds no schema knowledge; every judgment comes from the server |
| Sync conflicts are a new failure mode | `duplicate-id` catches the important one; conflict files surfaced in phase 6 |
| Rewriting working, tested code | 2,103 lines, 3 commits, ported test-first against a passing suite. The cost only grows from here |
| VS Code lock-in | Accepted. The files are plain markdown and the CLI works without an editor, so the data is never trapped |
| No phone access | Accepted. A read-only API on the homeserver remains possible later |

---

## 12. Open questions

Recorded rather than guessed at.

1. **`resource-status`** — carried over from `types.yaml`. Three real resources
   carry a status the type has no field for. Decide on first real use of a
   `plan` resource.
2. **Type migrations** — `--import` applies field derivations but not type
   remapping (`daily` → `journal` + `period`, `polity` → `world-entry`,
   `A3` → `document`/`analysis`). Deferred deliberately; ~41 of the 57 errors
   against real material are this.
3. **Where the working tree lives on each machine** — the Syncthing folder
   path. Needs deciding before phase 6, irrelevant before it.
