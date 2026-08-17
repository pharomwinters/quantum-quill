---
type: note
related:
  - "[[Vault Core]]"
  - "[[Vault Core Plugin Design]]"
created: 2026-08-03
---

# Vault Core — Plugin Design

> **Status: current.** This is the live project. [[PIM App Design]] v0.3 folds the PIM model *into* this plugin rather than a standalone app — there is one build, not two. The standalone native app (v0.1 and v0.2 of that note) is **cancelled**.
>
> **The phase table below is superseded.** The roadmap now lives in [[PIM App Design]] §11, which merges these phases with the SQLite index work into two parallel tracks. Everything else here — the audit findings, the measured footprint, the compat layer, the Templater teardown, the schema registry, the risks — stands unchanged, and is the detail reference for track A.

Companion to [[Custom Plugin Migration]]. That note decided *whether* to build; this one decides *what* to build.

Working name **Vault Core**, id `vault-core`. API reachable at `app.plugins.plugins['vault-core'].api`.

**Scope locked 2026-07-31.** Ten plugins go: four are **absorbed** (Meta Bind, Templater, Datacore, homepage), five were **retired outright** and are already gone (sheet-plus, html-blocks, mdx-preview, modalforms, dashboards), and **js-engine leaves with Meta Bind** in phase 3 — it has no fences of its own but powers Meta Bind's `inlineJS` actions. **Bases and TaskNotes stay** — they own tables and tasks respectively, and rebuilding either buys nothing.

**25 → 20 already done; 20 → 15 is this project.**

Two of the retirements are abandoned attempts at capabilities the plugin actually delivers — see **Dead-weight audit** below. That's the difference between deleting dead code and finally shipping the feature it was reaching for.

## What the audit changed

Four findings from reading every glue file in the vault, because they move the thesis:

**1. The real duplication is view code, not Templater logic.** Hub bodies are *copied into every instantiated note*. 15 person notes each carry their own ~130-line fork of the Person hub JSX; `_Weekly Note.md`'s blocks are stamped into each weekly note (9 `dc.useCurrentFile()` sites apiece); the `ymd()` date-normalizer exists in 6+ independent copies. And they drift — `Paint Line.md` has a `columns` layout `_Project Hub.md` never got. Fixing a hub bug today means editing 15 files and hoping. `Components.md` + `dc.require` was the right instinct, but it only helps single-instance dashboards (Home, Personal Hub), never the bodies stamped into notes.

**2. js-engine has no fences of its own — but it is not dead weight.** Zero ` ```js-engine ` blocks exist vault-wide, which made it look retirable. It isn't: **Meta Bind delegates its `inlineJS` action to js-engine**, so the vault's `mtask` and `ptask` buttons depend on it transitively. Searching for a plugin's own syntax says nothing about who else calls it.

The consequence is scheduling, not scope: js-engine still leaves, but it **cannot leave in phase 0**. It exits in phase 3 as a side effect of Meta Bind's removal, once the compat layer reinterprets those two `inlineJS` actions natively. Nothing else in the vault can keep it alive.

**3. Templater comes out entirely — and the vault barely notices.** *(Decided 2026-07-31: Templater was the only tool available when the vault was built, not a chosen dependency. It goes.)* Two audit facts make this cheap rather than brave:

- **Templater's tag appears in exactly 21 files** — the templates themselves — plus two documentation notes. **Zero live notes contain a Templater tag.** No person, meeting, project, resource, or journal note has any Templater syntax in it. Uninstalling breaks no content, only the buttons that *invoke* templates.

- **The 26 world-building templates contain no Templater tags either.** `World Entry.md` already treats them as plain markdown it string-patches. They survive as **body sources** the plugin reads directly.

So the removal is bounded to 21 files, all of which are being replaced anyway. See **Templater teardown** below for the facility-by-facility mapping.

**4. Datacore is being used as a Preact host with three filters.** *(Decided 2026-07-31: it goes too.)* A vault-wide sweep of every `dc.*` call returns six functions and four page accessors — and only four query strings, three of which are "all pages", "pages tagged `#task`", and "pages linking to X". Nothing uses the indexer, section/block queries, or embeds. At 350 files a plain metadata scan is **0.7 ms — measured in Obsidian, 2026-08-06** (~2 µs/file, full scan plus grouping by `type`), and the plugin already bundles Preact for `vault-view`, so absorbing it adds **zero dependencies**. See **Absorbing Datacore** below.

Corrected plugin math: not 3 folded in, but **ten out — 25 → 15**. Five had no live artifacts and are already gone; the four absorbed ones happen to be exactly those every dashboard, hub, and creation flow depends on; js-engine falls out with Meta Bind.

## Measured footprint

| Thing | Count | Where |
|---|---|---|
| Inline `` `BUTTON[...]` `` call sites | ~35 live | Home, Team Directory, Paint Line, Empire, 15 people, 3 dailies, 12 meetings |
| Hidden ` ```meta-bind-button ` blocks | ~88 across 45 files | baked into note bodies |
| Distinct button-id sets | **6** | `d-*`, `mtask`, `pm-*`, `p*`, `wentry`, home/team |
| Templater templates | 21 (+26 world bodies) | `3-Resource/3.1-Templates/` |
| Notes carrying forked hub JSX | ~22 | people, weeklies, dailies, project + world hubs |

The 6-distinct-id-sets number is the important one: note migration is deterministic, not case-by-case.

## Dead-weight audit

Ten plugins leave. Five were pure deletion — verified zero live artifacts, nothing to migrate — and are **already uninstalled as of 2026-07-31**, taking the vault from 25 to 20 before a line of code was written.

| Plugin | Verified state | Action |
|---|---|---|
| `html-blocks` | **0** ` ```html-block ` fences | ✅ removed |
| `modalforms` | **0** ` ```modal-form ` fences; stock + 2 prototype schemas in its own config | ✅ removed — **schemas kept**, see below |
| `dashboards` | **0** ` ```dashboard ` fences | ✅ removed; study the source on GitHub rather than hosting it |
| `sheet-plus` | superseded by Excel | ✅ removed |
| `mdx-preview` | 4 `.mdx` files, all experiments | ✅ removed — files still need converting, see below |
| `js-engine` | 0 fences of its own, **but Meta Bind's `inlineJS` depends on it** | **stays until phase 3** — leaves with Meta Bind |
| `obsidian-meta-bind-plugin` | ~88 blocks, ~35 call sites | **absorbed** — compat layer, then migrate |
| `templater-obsidian` | 21 templates, 0 live notes | **absorbed** — registry + commands |
| `datacore` | 6 functions, 4 accessors | **absorbed** — query layer + Preact views |
| `homepage` | one setting | **absorbed** — ~10 lines in `onLayoutReady` |

**Current state: 20 installed. Four absorbed plus js-engine remain to go → 15.**

The js-engine entry is the useful lesson in this table: a plugin with no syntax of its own can still be load-bearing. Grepping for `​```js-engine` proved only that *nothing calls it directly* — Meta Bind calls it on the vault's behalf. Worth remembering before pulling anything else on a zero-usage argument alone.

### The two failed experiments were real requirements

This is the part worth taking seriously. `html-blocks` and `modalforms` weren't clutter — they were attempts at capabilities the vault genuinely wanted and neither plugin could deliver:

**`html-blocks` → live dashboards.** It failed for a structural reason, documented in `CLAUDE.md`: each block is Shadow-DOM-scoped with an isolated `<script>`, so it can't reach `dc.useQuery`, Bases, or `this.file`. It could render *anything* and *know* nothing — useless for a dashboard, which is by definition vault-aware. That is precisely the gap `vault-view` + `ViewHost` closes: full vault access, real reactivity, theme-native styling. Its documented dark-mode wart (the white ring the wrapper injects, needing a CSS-snippet override that was never written) becomes moot along with it.

**`modalforms` → Notion-like structured entry.** Its config still holds two hand-authored schemas, `person` and `project-hub`, and they encode a requirement the vault has *never* met. Every template today prompts for a **title only**, then stamps `role`, `organization`, `email`, `phone` as empty strings to be filled in later by hand. The `person` form asked for all of them up front — and did something more:

```json
{ "name": "Company", "condition": { "dependencyName": "Position", "type": "isSet" } },
{ "name": "Email",   "condition": { "dependencyName": "Company",  "type": "isSet" } }
```

**Conditional fields** — show Company only once Position is set, Email only once Company is. That's a genuine design idea, prototyped and then stranded because wiring modalforms to Templater was more work than it was worth.

The schema registry makes it nearly free, because the registry *already* declares each type's fields. See **Typed creation forms** below. The two stranded form definitions become the first two entries; the `account-form` / `transaction-form` definitions belong to the retired plain-text accounting system and are discarded with it.

### `.mdx` disposition

Removing `mdx-preview` orphans four files. They split cleanly:

| File | Fate |
|---|---|
| `Templater Fence Recipe (walkthrough).mdx` | **convert to `.md`** — the historical record of why templates were built that way |
| `Datacore Query Idiom (walkthrough).mdx` | **convert to `.md`** — same, for the query layer |
| `MDX Prototype.mdx` | delete — a capability test |
| `MDX Annotations Test.mdx` | delete — a capability test |

Converting is worth doing regardless: `.mdx` isn't markdown, so those two notes are invisible to search, backlinks, and every `@page` query today. As `.md` they finally join the vault they document.

### One kept plugin whose rationale narrows

`markdown-columns` stays, but its justification shrinks. `CLAUDE.md` keeps it because "Datacore's HTML-wrapper columns break code-fence execution." Once views render inside the plugin, columns are just flexbox in a component — that reason is gone. What remains is narrower and still valid: it's the only way to put two ` ```base ` blocks side by side, and Bases is staying. If hub tables ever move into views, `markdown-columns` becomes removable too. **25 → 14**, eventually.

## Design principle — one stable seam

> **Migrate note bodies once, to a seam that never has to change again. Everything behind the seam is code.**

Every note that carries behavior today carries an *implementation* — JSX, YAML button definitions, Bases filters. The plugin's job is to replace those with a **name**:

````markdown
```vault-view
view: person-hub
```

```vault-button
preset: person-hub
```
````

Two lines instead of 130. After that migration, the person hub can be rewritten, restyled, or re-architected forever without a single note being touched. This is why the fence migration should happen *early* even if the first implementation behind it is a straight port — the value is in owning the seam, not in the first version of the view.

*(An earlier draft split this: hub views in the plugin, single-instance dashboards left on Datacore. With Datacore also being absorbed — see below — that split collapses. **One rendering system.** Copied-into-notes views still go first, because they're where the pain is; single-instance dashboards follow in phase 5.)*

## Architecture

Three layers, strictly one-directional. The core layer has no Obsidian UI imports and is unit-testable outside Obsidian.

```
src/
  core/                    ← pure, testable, no UI
    dates.ts               ymd, isoWeek, weekBounds, parseDailyName, normalizeDate
    schema.ts              the note-type registry            ★ keystone
    bodies.ts              markdown body builders (meeting skeleton, A3, hub)
    canvas.ts              .canvas JSON builder (from A3 Canvas.md)
  vault/                   ← thin Obsidian file ops
    files.ts               ensureFolder, createNote, stampFrontmatter, renameSafe
    query.ts               pages, tasks, backlinks, byType, isReal  → replaces Datacore
    tasknotes.ts           TaskNotes bridge (openTaskCreationModal)
  ui/
    prompts.ts             promptText(), suggest()   → replaces tp.system.*
    ViewHost.tsx           MarkdownRenderChild + reactive re-render
    views/                 person-hub, project-hub, world-hub, daily, weekly
    dashboards/            home, team-directory, personal-hub
    components/            Card, StatStrip, BarChart, LinkList, InternalLink,
                           Button, ButtonRow, ProgressBar, FileCards, OfficeIcon
  blocks/
    vaultView.ts           ```vault-view  processor
    vaultButton.ts         ```vault-button processor
    legacyCompat.ts        renders Meta Bind syntax when Meta Bind is off
  commands.ts              generated from schema.ts
  migrate.ts               legacy-block migration command (dry-run + apply)
  doctor.ts                frontmatter/schema validation command
  api.ts                   public surface — dashboards + ad-hoc scripting
  settings.ts              folder paths, date format, feature flags
  main.ts
```

### The schema registry (keystone)

Everything else derives from this table — commands, buttons, creation, views, validation. It is the single place the vault's magic strings live (today they're scattered across Meta Bind's `data.json`, 21 templates, and every Datacore block).

```ts
type Ctx = { hub?: TFile; today: string; title: string };

interface NoteType {
  id: string;                                  // frontmatter `type`
  label: string;                               // "Meeting"
  icon: string;                                // "🤝"
  prompt: string;                              // "Meeting title"
  folder: (c: Ctx) => string;                  // context-dependent destination
  fields?: Field[];                            // user-entered, drives the creation form
  frontmatter: (c: Ctx) => Record<string, unknown>;   // computed/system fields
  body?: (c: Ctx) => string;
  view?: string;                               // default vault-view for this type
}

interface Field {
  key: string;                                 // frontmatter key
  label: string;
  type: 'text' | 'textarea' | 'date' | 'number' | 'toggle' | 'select' | 'note';
  required?: boolean;
  options?: string[];                          // select
  folder?: string;                             // note-picker scope
  showIf?: (draft: Draft) => boolean;          // conditional field
}
```

The context-dependence is what kills the six helper templates. One `meeting` entry covers all three of today's meeting templates:

```ts
{
  id: 'meeting', label: 'Meeting', icon: '🤝', prompt: 'Meeting title',
  folder: c => c.hub && isProject(c.hub) ? sub(c.hub, 'Meetings') : S.meetings,
  frontmatter: c => ({
    type: 'meeting',
    related:  c.hub && isProject(c.hub) ? link(c.hub) : '',
    attended: c.hub && isPerson(c.hub)  ? [link(c.hub)] : '',
    result: '', created: c.today,
  }),
  body: bodies.meeting,          // one skeleton, not three escaped copies
}
```

`create(typeId, ctx)` is then the only creation path in the codebase. No string-escaped fences, no `${fence}` recipe, no re-parsing hazard — the body is produced by a function and written with `vault.create`.

Registry entries: `note`, `meeting`, `person`, `resource`, `a3`, `project`, `world`, `weekly` — plus the 26 world-entry kinds, which keep their existing markdown files as **body sources** (read + frontmatter-patched, exactly as `World Entry.md` does today, but typed and in one place).

### Typed creation forms

This is what `modalforms` was reached for, delivered from the registry that already exists.

Today every creation flow prompts for a **title** and nothing else — `Person.md` stamps `role`, `organization`, `email`, `phone` as empty strings you fill in by hand afterwards. Since `fields` declares those anyway, the same declaration renders a form:

```ts
{
  id: 'person', label: 'Person', icon: '👤', prompt: 'First Name-Last Name',
  folder: () => S.people,
  fields: [
    { key: 'role',         label: 'Role',         type: 'text' },
    { key: 'organization', label: 'Organization', type: 'text',
      showIf: d => !!d.role },                                    // ← conditional
    { key: 'email',        label: 'Email',        type: 'text',
      showIf: d => !!d.organization },
    { key: 'phone',        label: 'Phone',        type: 'text' },
    { key: 'met',          label: 'First met',    type: 'date' },
  ],
  frontmatter: c => ({ type: 'person', related: '', created: c.today }),
}
```

`create()` renders whatever `fields` declares as a single modal — one dialog instead of a title prompt followed by manual frontmatter editing — and the `showIf` chain reproduces the exact cascade the stranded `person` form prototyped (Organization appears once Role is set, Email once Organization is). One `<CreateForm>` component serves every type; adding a field to any note type is a one-line registry edit that updates the form, the frontmatter, and the Doctor's validation rules simultaneously.

**Deliberately optional.** A type with no `fields` falls back to the title-only prompt, so `note` and `meeting` stay as fast as they are now. Richness where it pays (`person`, `project`), speed where it doesn't.

### The two block processors

**` ```vault-button `** — replaces `BUTTON[...]` *and* its hidden companion block. One visible fence, nothing hidden.

````yaml
```vault-button
preset: project-hub          # named row defined in code — preferred
```

```vault-button
buttons:                     # or explicit, for one-offs
  - { label: "Today", icon: "📅", action: { command: "daily-notes" } }
  - { label: "New Note", icon: "📝", style: primary, action: { create: note } }
```
````

Actions: `{create: <typeId>}` (context = the note the block sits in), `{command: <id>}`, `{open: "[[Note]]"}`, `{task: {...}}` (TaskNotes modal prefill), `{run: <fnName>}` (registered plugin function, e.g. `complete-project`, `build-a3-canvas`).

Presets — `project-hub`, `person-hub`, `world-hub`, `meeting`, `daily-nav`, `home-create`, `home-tasks` — map 1:1 onto the 6 measured id-sets. Because they're names, changing a hub's button row later is a code edit, never a 15-note edit.

**Design win worth naming:** `Components.md` documents that a Datacore button *cannot* safely dispatch `runTemplaterFile` — orchestrators run in active-file context and can spill output into the current note. That single limitation is the only reason Meta Bind still exists. The plugin has no such hazard: `create()` takes an explicit target folder and never writes to the active file. The blocker dissolves rather than being worked around.

**` ```vault-view `** — named views, resolved at render.

````yaml
```vault-view
view: project-hub            # explicit
```

```vault-view
```                          # empty → view inferred from the note's `type`
````

Views live in `ui/views/` as Preact components receiving `{ file, app, api }`.

### Rendering & reactivity

**Preact + JSX, bundled** (~3 KB). Chosen deliberately: Datacore already renders Preact, so the existing JSX ports nearly verbatim — `dc.useQuery(...)` → `api.query.*`, `<dc.List>` → `<LinkList>`, `dc.useState` → `useState`, styles unchanged. The port is mechanical, which is what makes moving ~1,400 lines of view and dashboard code realistic — and it's the same decision that lets Datacore be absorbed for free in phase 5.

```ts
this.registerMarkdownCodeBlockProcessor('vault-view', (src, el, ctx) =>
  ctx.addChild(new ViewHost(this, el, src, ctx.sourcePath)));
```

`ViewHost extends MarkdownRenderChild`:
- `ctx.sourcePath` → `TFile` (this is the reliable `dc.useCurrentFile()` equivalent)
- `onload` → render; `registerEvent(metadataCache.on('changed'|'resolved'))` → debounced re-render
- `onunload` → `render(null, el)` to unmount

That's the whole reactivity story — roughly 50 lines, and it replaces the reason Datacore was load-bearing.

**Queries without Datacore.** `metadataCache.getBacklinksForFile(file)` where available, falling back to iterating `metadataCache.resolvedLinks` — the exact technique `Project Complete.md:14` already uses, and it catches frontmatter links (`related:`, `projects:`, `attended:`, `appears_in:`), so `linksto` semantics are preserved. At 350 files this is free. Task detection reuses the existing tag check (`cache.tags` + `frontmatter.tags`).

*Caveat:* `getBacklinksForFile` isn't in the public typings. The `resolvedLinks` fallback is fully public, so it degrades safely.

### Commands

Generated from the registry, so every creation flow is palette-searchable and hotkey-bindable — something Meta Bind buttons never offered.

`Vault Core: New {Note, Meeting, Person, Resource, A3, Project, World Entry}` · `Open this week` · `Complete project` · `Build A3 canvas` · `Migrate legacy blocks…` · `Doctor — validate frontmatter`

### Public API

```ts
api = { create, dates, query, canvas, bodies, prompt, suggest }
```

**Dropped from the original plan: the Templater-shim bridge.** Phase 2 of the migration plan had templates calling `app.plugins.plugins['vault-core'].api.*` so the core could be built with the existing UI intact. That was the right instinct when Templater was staying — but if Templater is leaving regardless, rewriting 21 templates into API shims is throwaway work on files scheduled for deletion. Build the commands directly instead; a command is ~5 lines on top of `create()` and is testable the moment it exists.

The API still earns its place, just not as a bridge. Until phase 5 the three Datacore dashboards call it for their buttons; afterwards it's the seam the plugin's own views build on, and the entry point for any ad-hoc scripting later.

## What each existing piece becomes

| Today | After |
|---|---|
| 5 Meta Bind global button templates (`data.json`) | `home-create` / `home-tasks` presets |
| ~88 hidden `meta-bind-button` blocks | deleted — presets live in code |
| `Note/Meeting/Person/Resource/A3.md` (stamp-and-rename) | registry entries + commands |
| `Project Note/Meeting/Resource/A3.md`, `Person Note/Meeting.md` | **deleted** — context-dependent registry fields |
| `Project.md`, `World.md`, `Weekly.md` (orchestrators) | commands (folder trees move to `core/`) |
| `Project Complete.md` | `run: complete-project` |
| `A3 Canvas.md` | `core/canvas.ts` + `run: build-a3-canvas` |
| `_Project Hub.md`, `_World Hub.md`, `Person.md` bodies, `_Weekly Note.md`, `Daily.md` | `vault-view` + `vault-button` fences |
| 26 world-building templates | kept as **body sources**, read by the plugin |
| `Components.md` (Datacore lib) | ports to `ui/components/` — same components, now typed and imported normally |
| `Home.md`, `Team Directory.md`, `Personal Hub.md` blocks | `vault-view` fences → `ui/dashboards/` |
| `Home.canvas` (6 duplicated blocks) | same treatment as `Home.md` — easy to overlook |
| Bases blocks in hubs | **stay as-is** — Bases is core, leave it alone |
| `homepage` plugin | ~10 lines in `onLayoutReady` |
| `templater-obsidian` | **uninstalled** — see teardown above |
| `datacore` | **uninstalled** — see absorption above |
| `modalforms` (2 stranded schemas) | `fields` on the registry + `<CreateForm>` — the requirement ships, the plugin doesn't |
| `html-blocks` | `vault-view` — same goal, with vault access it never had |
| 2 `.mdx` walkthroughs | convert to `.md` (finally searchable/linkable) |
| `mtask` / `ptask` `inlineJS` bodies | native `{task:{…}}` action — no JS engine needed |
| `js-engine` | uninstalled in phase 3, once `inlineJS` has no callers |
| 2 `.mdx` prototypes, `sheet-plus`, `dashboards` | ✅ already deleted / uninstalled |

Bases staying is deliberate: it's a first-party feature, the blocks are ~15 lines, and rewriting sortable tables buys nothing. The plugin owns *behavior and composed views*; Bases owns *tables*.

## Templater teardown

Every Templater facility the vault actually uses, and what replaces it. Nothing here is exotic — most are one Obsidian API call.

| Templater | Replacement | Notes |
|---|---|---|
| `tp.system.prompt(label, dflt, throwOnCancel)` | `ui/prompts.ts → promptText()` | Obsidian `Modal` + text input; returns `null` on cancel |
| `tp.system.suggester(labels, values, …)` | `ui/prompts.ts → suggest<T>()` | `FuzzySuggestModal`, typed |
| `tp.date.now('YYYY-MM-DD')` | `core/dates.ts → ymd()` | already needed for the 6 duplicated copies |
| `tp.file.create_new(body, name, open, folder)` | `vault/files.ts → createNote()` | `vault.create` + `workspace.getLeaf().openFile` |
| `tp.file.find_tfile(basename)` | `metadataCache.getFirstLinkpathDest()` | or direct path lookup |
| `tp.file.path(true)` / active file | `workspace.getActiveFile()` / `ctx.sourcePath` | `sourcePath` is the reliable one inside blocks |
| `tp.file.cursor` | `editor.setCursor()` after open | only `Person.md` uses it |
| `tp.hooks.on_all_templates_executed` | **gone — not replaced** | see below |
| `app.fileManager.processFrontMatter` | *keep* | Obsidian core, not Templater |
| `app.fileManager.renameFile` | *keep* | Obsidian core; still used for archiving |

Two whole idioms disappear rather than getting ported, which is where the real cleanup is:

**Stamp-and-rename dies.** It exists only because Templater creates an untitled file *first*, then needs a hook to stamp frontmatter and rename afterward. The plugin builds the final content and writes it at the final path in a single `vault.create()`. No hook, no two-phase creation, and no race between the rename and the frontmatter stamp.

**The `${fence}` escaping recipe dies.** `Template Authoring.md` documents it as "the easy-to-break part" — one template literal, never close it early, split `<% %>` tokens so `create_new` doesn't re-parse them. All of that is an artifact of building markdown inside a string that Templater will re-evaluate. In TypeScript, bodies are ordinary functions returning ordinary strings; nothing re-parses them. The three-rule hazard list becomes irrelevant.

Config to clean up when Templater goes: `templater-obsidian/data.json` lists three template hotkeys, one of which (`create_folder.md`) points at a file that no longer exists.

`Template Authoring.md` and `Templater Fence Recipe (walkthrough).mdx` become historical documents — worth keeping as a record of why the vault was built the way it was, not as live guidance.

## htm Absorbing Datacore

*(Decided 2026-07-31: Datacore is used as a Preact host with three simple queries. Both are things the plugin already has to provide.)*

### The complete surface in use

A vault-wide audit of every `dc.*` call turns up **six functions and four page accessors** — nothing more:

| API | Replacement |
|---|---|
| `dc.useQuery("@page")` | `query.pages()` — `vault.getMarkdownFiles()` + `metadataCache.getFileCache()` |
| `dc.useQuery("@page and #task")` | `query.tasks()` — tag check already written in `Project Complete.md` |
| `dc.useQuery('… linksto([[X]])')` | `query.backlinks(file)` — already in the design for hub views |
| `dc.useQuery("@file")` | *not a query* — used only as a re-render subscription; becomes `ViewHost`'s existing event wiring |
| `dc.useCurrentFile()` | `ctx.sourcePath` → `TFile` |
| `dc.useState` | Preact's `useState` — literally the same hook |
| `<dc.List rows renderer />` | `<LinkList>` — ~15 lines |
| `dc.require` / `dc.headerLink` / `dc.fileLink` | ordinary ESM `import` |
| `p.value(k)`, `p.$path`, `p.$name` | frontmatter / `file.path` / `file.basename` |
| `p.$link` | `<InternalLink>` — see below |

**Nothing in the vault uses what Datacore is actually for.** No `dc.embed`, no `@section`/`@block`/`@list` queries, no list-item or sub-file indexing, no query expressions beyond the three above, no sortable/groupable table components. The indexer — Datacore's whole reason to exist — is carrying three filters over 350 files. A plain scan is **0.7 ms** at this size (measured 2026-08-06 by the phase-1 smoke view); the index is solving a problem this vault does not have. Even a hub rendering six blocks pays ~4 ms total, and the scan stays imperceptible at ten times the vault.

### Why this is a durability win, not just a plugin-count win

**Datacore is alpha and not in the community store** — it's a BRAT/manual install. Home, Team Directory, Personal Hub, every project and person hub, every daily and weekly note render through it. That is the single largest fragility in the current architecture: an unreleased plugin holding up every dashboard in the vault. Absorbing it removes that dependency entirely.

It also costs **zero new dependencies** — the plugin already bundles Preact for `vault-view`. The rendering infrastructure exists either way; this is reusing it rather than adding to it.

And it retires an entire category of accumulated scar tissue. Every item on `Components.md`'s **Gotchas** list is a Datacore artifact:

| Gotcha | Why it stops existing |
|---|---|
| Never name a local `h` (shadows the JSX factory) | esbuild's automatic JSX runtime + real module scope |
| `dc.require` needs a *codeblock* reference, not a note link | ordinary `import` |
| Keep one block under `## Library` | there is no library note |
| Don't save the library as `.js` (Sync skips non-markdown) | code lives outside the vault |
| Vault-relative `<img src>` won't resolve | one `getResourcePath()` helper, written once |
| Hooks must run at the top of a component | still true — but it's Preact's rule, and TS/ESLint enforces it |
| Don't rebuild `runTemplaterFile` in a custom button | already resolved by the Templater teardown |

Seven documented traps, each one discovered the hard way, all of which simply cease to apply.

### The one non-trivial port

`p.$link` renders a working Obsidian internal link. The replacement is a small `<InternalLink>` component emitting `<a class="internal-link" data-href="…">`, which Obsidian's global click handler picks up; hover-preview needs the `hover-link` workspace trigger fired on mouseover. Perhaps 25 lines, written once, used by every view. Everything else in the port is mechanical.

`FileCards` is the easiest case despite being the largest component — it already reads `app.vault.getFiles()` directly and uses `dc.useQuery("@file")` purely as a change subscription, so it carries **no** Datacore semantics at all.

### What is genuinely lost

**Iteration speed on dashboards.** Editing a `datacorejsx` block in-note gives instant feedback with no toolchain. In the plugin it's esbuild watch + Hot Reload — around a second, but it needs the dev machine. This lands hardest on `Home.md` and `Personal Hub.md`, the two notes most likely to get tweaked on impulse, and it means no dashboard edits from the work machine.

Two things soften it: **Bases** already covers ad-hoc tabular queries natively, with no code at all; and the `html-blocks` plugin remains for self-contained one-off widgets. The gap is specifically *vault-aware exploratory JSX*, which in practice is a rare need once the dashboards are stable.

**Casualties to accept:** `MDX Prototype.mdx`, `MDX Annotations Test.mdx`, and `Datacore Query Idiom (walkthrough).mdx` are experiments built on `dc.useQuery`; they stop rendering. `Available Commands for Datacore.md` becomes a historical reference. None are load-bearing.

**Also worth noting:** `Home.canvas` embeds six copies of Home's Datacore blocks as canvas text nodes — another fork site, and one that's easy to forget. It needs the same treatment as the note it mirrors.

## Migration strategy

**The compat layer doesn't replicate the old syntax — it reinterprets it.** This is the move that lets both plugins leave on the same day without touching a note.

Ship `legacyCompat.ts`: a markdown post-processor that reads Meta Bind's *own* syntax — the `` `BUTTON[id]` `` code span and the ` ```meta-bind-button ` fence — and renders it with the plugin's button engine. It activates **only** when Meta Bind is disabled (`!app.plugins.enabledPlugins.has('obsidian-meta-bind-plugin')`), so the two never fight.

The key part: when it encounters a `runTemplaterFile` or `templaterCreateNote` action, it does **not** call Templater. It looks the template path up in a fixed table and dispatches the native equivalent:

```ts
const REINTERPRET: Record<string, LegacyAction> = {
  'Person Meeting.md':   { create: 'meeting',  ctx: 'active' },
  'Person Note.md':      { create: 'note',     ctx: 'active' },
  'Project Note.md':     { create: 'note',     ctx: 'active' },
  'Project Meeting.md':  { create: 'meeting',  ctx: 'active' },
  'Project Resource.md': { create: 'resource', ctx: 'active' },
  'Project A3.md':       { create: 'a3',       ctx: 'active' },
  'Project Complete.md': { run: 'complete-project' },
  'World Entry.md':      { run: 'new-world-entry' },
  'A3 Canvas.md':        { run: 'build-a3-canvas' },
  'Weekly.md':           { run: 'open-this-week' },
  'World.md':            { create: 'world' },
  'Project.md':          { create: 'project' },
  // + the 4 templaterCreateNote globals from Meta Bind's data.json
};
```

**Twelve live template paths, verified by audit** — that's the entire surface. (`Account.md` / `Transaction.md` / `Account Transaction.md` also appear, but only inside archived design docs for the retired accounting system; they resolve to nothing and need no entry.)

**`inlineJS` gets the same treatment — which is what frees js-engine.** The compat layer must handle all three legacy action types, not just the Templater pair:

| Legacy action | Compat handling |
|---|---|
| `command` | native passthrough — `app.commands.executeCommandById` |
| `runTemplaterFile` / `templaterCreateNote` | reinterpret via the table above |
| `inlineJS` | reinterpret via body-shape match — **no JS executed** |

Only two `inlineJS` actions exist in the vault, `mtask` and `ptask`, and both do the same thing: open TaskNotes' creation modal with `projects` prefilled (`mtask` additionally appends the meeting's `related:` project). Both collapse to one native action:

```ts
{ task: { projects: ['{{self}}', '{{frontmatter.related}}'] } }   // mtask
{ task: { projects: ['{{self}}'] } }                              // ptask
```

Recognise them by button id and dispatch natively. The compat layer never evaluates JavaScript, which is precisely why **js-engine can be uninstalled the same day** — its only caller stops calling.

The consequence: on the day Phase 3 ships, **Meta Bind, Templater, and js-engine are all uninstalled, and not one note has been edited.** Every baked-in button in all 45 files keeps working, now backed by native commands. The ~35 call sites then migrate to `vault-button` presets whenever convenient — or never, since the compat layer is small and stable enough to keep indefinitely.

This also answers the plan's second open question: it isn't migrate-vs-leave, it's *flip the renderer first, migrate at leisure*.

**Then migrate with a command, not by hand.** `Migrate legacy blocks…` runs in two passes:
1. **Dry run** → writes a report note: files touched, id-sets found, proposed replacements, anything unrecognized.
2. **Apply** → strips hidden blocks, replaces the inline call site with the matching preset fence, and for hub notes swaps the forked JSX for a `vault-view` fence.

Deterministic because there are only 6 id-sets. Using the plugin's own parser (not a one-off script) means the migration is re-runnable and testable.

## Build & dev logistics

- Repo **outside the vault** (e.g. `C:\dev\vault-core`) — node_modules must never enter OneDrive/Sync.
- esbuild → `G:\vault\.obsidian\plugins\vault-core\main.js`, watch mode in dev; `jsx: 'automatic'`, `jsxImportSource: 'preact'`.
- Hot Reload plugin (pjeby) + a `.hotreload` marker in the plugin folder for live iteration.
- TypeScript `strict`, `obsidian` typings, Vitest on `core/` (dates, schema, bodies, canvas JSON — all pure).
- **Sync:** enable *installed community plugins* in Obsidian Sync so `main.js` + `manifest.json` reach the work machine. Only the built artifact syncs.
- **OneDrive:** rebuilds churn `main.js` on every save — pause OneDrive during dev sessions if it gets noisy.

## Capabilities this unlocks (not possible today)

- **Typed creation forms** — one modal with the right fields per type, conditional fields included. Two years of empty `role:`/`organization:` strings waiting to be backfilled, solved at the point of creation. This is `modalforms`' unmet goal, delivered from a registry that had to exist anyway.
- **Doctor** — validate every note against the registry: wrong `type` for its folder, missing required fields, unresolved `related:`/`appears_in:` links, orphaned hubs. A typed schema makes this ~80 lines; today it's impossible.
- **Hotkeys for everything** — creation flows are commands, not buttons.
- **Hub views that improve retroactively** — fix the person header once, all 15 update.
- **Real tests** on date math, ISO weeks, and the `.canvas` builder.

## Risks

| Risk | Mitigation |
|---|---|
| Rewriting ~1,400 lines of working JSX (hubs + dashboards) | Preact means near-verbatim port; one view at a time behind the stable fence, and phase 5 reuses everything phase 4 built |
| **Everything now depends on one plugin I maintain** | Real, and the honest answer is that the *content* is unaffected: notes stay plain markdown + YAML frontmatter + wikilinks. A broken build degrades rendering, never readability — every note remains editable in any editor. This is why the vault's data model was worth keeping boring |
| Dashboard tweaks now need the toolchain | Accepted cost of absorbing Datacore. Bases covers ad-hoc tables with no code; `html-blocks` covers self-contained widgets |
| `getBacklinksForFile` is semi-public | `resolvedLinks` fallback (already proven in `Project Complete.md`) |
| Obsidian API churn | Core layer is UI-free and unaffected; surface area is small |
| Two-machine drift | Only the built artifact syncs; source is single-machine |
| Losing ad-hoc template *insertion* with Templater | Audit shows none in use: `folder_templates`, `file_templates`, `startup_templates` are all empty, and the 3 hotkeys are orchestrators becoming commands. If plain insertion is ever wanted, Obsidian's **core Templates plugin** covers it with no third party |
| Scope creep into Bases / TaskNotes | Explicit non-goals — the mapping table above is the boundary. Bases owns tables, TaskNotes owns tasks |

## Answers to the plan's open questions

**Commit, or stop at "it works today"?** — Commit, but for the corrected reason. "Kill copy-pasted Templater logic" is worth maybe a weekend. The forking view layer is the load-bearing argument: `Paint Line.md` has *already* diverged from its template, and every new person note forks the hub again. That gets monotonically worse and has no fix inside the current architecture.

**Migrate existing notes' buttons, or only templates going forward?** — Neither, in that order. Ship the compat shim first so removing Meta Bind requires no note edits at all, then migrate with the built-in command when convenient. Leaving notes on legacy syntax permanently is the one option to reject — it makes Meta Bind unremovable and defeats the project.

**Ever migrate Templater flows into commands?** — **Decided: yes, completely, and early.** Not phase 5 — phase 3, alongside Meta Bind. Six of the 21 templates vanish outright into registry context-fields, the orchestrators become commands, and the 26 world-building templates stay as content the plugin reads. Templater was the only tool available when the vault was built; it was never chosen on merit, and the audit shows the cost of removing it is bounded to 21 files that are being replaced anyway.

## Revised phases

| Phase | Deliverable | Payoff |
|---|---|---|
| **0** | ✅ **Done** — five dead plugins uninstalled (25 → 20); 2 `.mdx` walkthroughs converted to `.md` (2026-08-07) | free — verified zero live artifacts |
| **1** | Toolchain, empty plugin, Hot Reload | de-risk setup |
| **2** | `core/` + `vault/` + `ui/prompts.ts` + **every creation command** | Templater's entire job, reimplemented — and hotkey-able for the first time |
| **3** | `vault-button` + presets + **reinterpreting compat layer** (incl. `inlineJS`) | 🚩 **Meta Bind, Templater *and* js-engine uninstalled — zero notes edited** |
| **4** | `vault-view` + port hub views; migration command | **the actual payoff** — forking ends |
| **5** | Port the 3 dashboards + `Home.canvas`; absorb `homepage` | 🚩 **Datacore uninstalled** — 25 → 15, one render system |
| **6** | Delete the 21 templates; Doctor, settings tab, tests | capabilities that never existed |

Three deliberate departures from the original plan's ordering:

- **Templater dies in phase 3, not phase 5.** Once creation commands exist (phase 2) and the compat layer reinterprets the baked-in buttons (phase 3), Templater has no remaining caller. Holding it longer would mean maintaining 21 dead template files for no reason.
- **Buttons before views, but views are the point.** Buttons are the easier proof and the thing that unblocks the first two uninstalls; the view seam in phase 4 is why the project is worth doing at all.
- **Datacore last, and almost for free.** Phase 4 has already built the query layer, the component library, and `ViewHost` — everything the dashboards need. Phase 5 is mostly moving JSX between files, which is why the third uninstall costs so little.

Phase 6's template deletion is bookkeeping — by then nothing has called those files for three phases.

**Each phase ends with the vault fully working.** Nothing here is a flag day: phases 0–2 add capability without removing any, phase 3 swaps two renderers behind a compat layer, and phases 4–5 migrate note bodies that keep rendering the whole time.

---

*Footnote:* `templater-obsidian/data.json` lists `3-Resource/3.1-Templates/create_folder.md` as an enabled template hotkey, but that file no longer exists — a dead binding to clean up whenever Templater is touched.
