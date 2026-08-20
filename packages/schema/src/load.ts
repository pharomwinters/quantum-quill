// Loads the two schema files. Nothing here interprets them — see model.ts.
//
// The YAML is the specification, so it is read at runtime rather than
// generated into TypeScript: a generated copy is a second source of truth,
// which is the failure this project exists to correct.
//
// The types below are the other half of that bargain, and the half that can
// rot quietly. `parse()` returns whatever the file holds; `read<T>()` casts it.
// So a block the file carries and this file does not declare is invisible —
// unreadable without `as any`, and unnoticed until someone needs it. That is
// not hypothetical: `lifecycle` and `import` were both absent here for the
// whole of phase 1, and `routing.explicit` declared two of its six keys.
//
// Hence TYPES_KEYS / LAYOUT_KEYS / FIELD_ATTRIBUTE_KEYS below: runtime lists,
// proved at compile time to equal the corresponding TypeScript type, and at
// test time to equal what the files actually contain. Both directions, the
// same discipline the DDL cross-check applies one layer down.
//
// Known limit: the check is exact at the top level and for field attributes.
// Nested shapes are typed from the files as measured, and guarded by a weaker
// no-undeclared-keys test rather than proved.

import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'yaml';

/**
 * Resolves to `Declared` when it names exactly the keys in `Keys`, and to
 * `never` otherwise — so a mismatched list fails to assign, and the drift is a
 * compile error rather than a comment that used to be true.
 */
type Exact<Keys extends PropertyKey, Declared extends readonly PropertyKey[]> =
  [Exclude<Keys, Declared[number]>] extends [never]
    ? [Exclude<Declared[number], Keys>] extends [never]
      ? Declared
      : never
    : never;

// -----------------------------------------------------------------------------
//  FIELDS
// -----------------------------------------------------------------------------

/**
 * Everything sayable about a field. Beyond `key`, `type` and `description`,
 * every property here must appear in the file's own `field_attributes` block —
 * which is what FIELD_ATTRIBUTE_KEYS proves.
 */
export type FieldSpec = {
  key: string;
  type: string | string[];
  description?: string;

  /** The author must supply a value. `on-create` warns rather than errors on imports. */
  required?: boolean | 'on-create';
  /** Present means the store always materialises a value; the column is NOT NULL. */
  default?: unknown;
  /** Unique in combination with these fields. An empty list means unique alone. */
  unique_with?: string[];
  immutable?: boolean;
  system?: boolean;
  /** The closed vocabulary an `enum` draws from. */
  of?: string;
  /** The types a `link` may point at. `"*"` means any core type. */
  to?: string | string[];
  /** The reverse edge's name — derived, never written, unique on the TARGET type. */
  inverse?: string;
  /** The link is its own inverse. Only `related`. */
  symmetric?: boolean;
  /** Where the value comes from when it is not authored. */
  derived_from?: string;
};

const FIELD_ATTRIBUTE_KEYS_DECLARED = [
  'required', 'default', 'unique_with', 'immutable', 'system',
  'of', 'to', 'inverse', 'symmetric', 'derived_from',
] as const;

/** The attribute names, minus the three properties that are the field itself. */
export const FIELD_ATTRIBUTE_KEYS: Exact<
  Exclude<keyof FieldSpec, 'key' | 'type' | 'description'>,
  typeof FIELD_ATTRIBUTE_KEYS_DECLARED
> = FIELD_ATTRIBUTE_KEYS_DECLARED;

export type Provenance = 'derived' | 'confirmed' | 'provisional';

export type TypeSpec = {
  id: string;
  name: string;
  kind: string;
  subtype: string | null;
  provenance: Provenance;
  evidence: string;
  description: string;
  fields?: FieldSpec[];
};

export type VocabularyValue = string | { id: string; name?: string; adds?: FieldSpec[] };

export type VocabularySpec = {
  parent?: string;
  provenance: string;
  closed: boolean;
  multi?: boolean;
  values: VocabularyValue[];
};

// -----------------------------------------------------------------------------
//  ROUTING
// -----------------------------------------------------------------------------

/**
 * A type that routes on something other than a subtype value. `map` turns a
 * field value into a category; `relative_to: container` resolves against
 * another RECORD instead of against Folder-layout.yaml, which is why the
 * router takes the container's folder as an argument rather than a database.
 */
export type ExplicitRoute = {
  type: string;
  routes_by: string;
  /** Only `project`, which maps a scope onto a category. */
  map?: Record<string, string>;
  /** A condition on when the override applies. Only `document`, on `attaches_to`. */
  when?: string;
  /** `container` means the destination is inside another record's folder. */
  relative_to?: string;
  rule?: string;
};

export type Routing = {
  derived_from_layout: { types: string[]; rule: string };
  explicit: ExplicitRoute[];
};

// -----------------------------------------------------------------------------
//  LIFECYCLE
// -----------------------------------------------------------------------------

/**
 * Either a bare verb (`archive`) or a single-key mapping carrying its argument
 * (`{ stamp: completed }`, `{ preserve: [id, jd] }`). The set of verbs is not a
 * closed vocabulary in the file, and inventing one to serve the interpreter is
 * what the method forbids — phase 2 closes it with a registry meta-test instead.
 */
export type Effect = string | Record<string, string | string[]>;

/** A condition that blocks a transition (`error`) or merely reports it (`warn`). */
export type Guard = {
  check: string;
  severity: 'warn' | 'error';
  message: string;
  note?: string;
};

export type Transition = {
  from: string | string[];
  to: string | string[];
  /** Fields that must be set for the transition to complete. */
  requires?: string[];
  /** A requirement on the INDEX rather than on the record — an inbound edge. */
  requires_index?: string;
  guards?: Guard[];
  effects?: Effect[];
  note?: string;
};

export type Machine = {
  type: string;
  field: string;
  provenance: Provenance;
  evidence: string;
  initial: string;
  terminal: string[];
  transitions: Transition[];
  /** Only `document`: a record with `snapshot_of` set follows its parent. */
  snapshots?: { rule: string };
  /** Only `task`, which is archived in batches rather than individually. */
  archive?: string;
  note?: string;
};

export type Lifecycle = {
  principle: string;
  archive: {
    applies_to: string;
    trigger: string;
    effects: Effect[];
    rules: string[];
    reversible: boolean;
    unarchive: string;
  };
  machines: Machine[];
  stateless: { types: string[]; rule: string; system_note: string };
};

// -----------------------------------------------------------------------------
//  QUERY
// -----------------------------------------------------------------------------

export type IndexClass = {
  class: string;
  fields: string[] | string;
  /** Names VOCABULARIES, not fields. Field names are not unique across types. */
  subtype_vocabularies?: string[];
  bidirectional?: boolean;
  excludes?: string;
  note?: string;
};

export type Query = {
  form: string;
  form_note: string;
  shape: Record<string, string>;
  example: string;
  operators: {
    logical: string[];
    equality: string[];
    ordering: string[];
    text: string[];
    presence: string[];
    edge: string[];
  };
  values: { self: string; today: string };
  indexes: IndexClass[];
  inverses: {
    storage: string;
    rule: string;
    read_only: boolean;
    uniqueness: string;
    by_target: Record<string, string[]>;
  };
  excluded: Array<{ subject: string; rationale: string }>;
};

// -----------------------------------------------------------------------------
//  IMPORT
// -----------------------------------------------------------------------------

/** A required field the import computes rather than reads. `covers` is measured. */
export type Derivation = {
  field: string;
  source: string;
  covers: number;
  note?: string;
};

export type Import = {
  derived: Derivation[];
  manual: {
    description: string;
    fields: Array<{ field: string; count: number; severity: 'error' | 'warn' }>;
  };
  binary_survey: {
    measured: string;
    corpus: number;
    method: string;
    findings: Array<{ defect: string; count: number; fix: string }>;
    confirmed_correct: { values: string[]; note: string };
  };
  conforms_already: { types: string[]; note: string };
};

// -----------------------------------------------------------------------------
//  THE FILES
// -----------------------------------------------------------------------------

export type OpenQuestion = {
  id: string;
  raised: string;
  question: string;
  evidence: string;
  why_unresolved: string;
  unblocks: string;
  decide_by: string;
};

/**
 * `unknown` marks a block the file carries that nothing in TypeScript reads
 * yet. It is deliberately not `any`: a consumer must narrow it, and typing it
 * on a guess would be inventing structure no test checks.
 */
export type Types = {
  meta: { name: string; version: number; updated: string };
  provenance_levels: unknown;
  provenance_review: unknown;
  conventions: unknown;
  field_types: Record<string, string>;
  field_attributes: Record<string, string>;
  universal: FieldSpec[];
  routing: Routing;
  containers: { types: string[]; rule: string };
  types: TypeSpec[];
  vocabularies: Record<string, VocabularySpec>;
  stubs: unknown;
  lifecycle: Lifecycle;
  query: Query;
  import: Import;
  validation: { error: string[]; warn: string[]; info: string[] };
  open_questions: OpenQuestion[];
};

const TYPES_KEYS_DECLARED = [
  'meta', 'provenance_levels', 'provenance_review', 'conventions', 'field_types',
  'field_attributes', 'universal', 'routing', 'containers', 'types', 'vocabularies',
  'stubs', 'lifecycle', 'query', 'import', 'validation', 'open_questions',
] as const;

export const TYPES_KEYS: Exact<keyof Types, typeof TYPES_KEYS_DECLARED> = TYPES_KEYS_DECLARED;

export type CategorySpec = {
  id: string;
  jd: string;
  name: string;
  types?: string[];
  sensitive?: boolean;
};

export type AreaSpec = {
  id: string;
  jd: string;
  letter: string;
  name: string;
  zone: 'typed' | 'bulk';
  provenance: string;
  categories?: CategorySpec[];
};

export type Layout = {
  meta: { name: string; version: number; updated: string };
  conventions: unknown;
  zones: Record<string, unknown>;
  rules: Array<{ id: string; statement: string }>;
  areas: AreaSpec[];
  tombstones: unknown;
  excluded: unknown;
};

const LAYOUT_KEYS_DECLARED = [
  'meta', 'conventions', 'zones', 'rules', 'areas', 'tombstones', 'excluded',
] as const;

export const LAYOUT_KEYS: Exact<keyof Layout, typeof LAYOUT_KEYS_DECLARED> = LAYOUT_KEYS_DECLARED;

/** Walk up from this file until the schema files are found. */
function repoRoot(): string {
  let dir = dirname(fileURLToPath(import.meta.url));
  for (let i = 0; i < 8; i++) {
    try {
      readFileSync(join(dir, 'types.yaml'));
      return dir;
    } catch {
      dir = dirname(dir);
    }
  }
  throw new Error('types.yaml not found above ' + fileURLToPath(import.meta.url));
}

export const ROOT = repoRoot();

function read<T>(file: string): T {
  return parse(readFileSync(join(ROOT, file), 'utf8')) as T;
}

export function loadTypes(): Types {
  return read<Types>('types.yaml');
}

export function loadLayout(): Layout {
  return read<Layout>('Folder-layout.yaml');
}

/** A vocabulary value is either a bare string or a mapping with an id. */
export function valueId(v: VocabularyValue): string {
  return typeof v === 'string' ? v : v.id;
}

/** Fields a subtype value adds to its parent type. */
export function valueAdds(v: VocabularyValue): FieldSpec[] {
  return typeof v === 'string' ? [] : (v.adds ?? []);
}

/** The file writes one-or-many wherever a list of one would read as fussy. */
export function asList<T>(v: T | T[]): T[] {
  return Array.isArray(v) ? v : [v];
}

/** `to:` is one target or several; normalise to a list. */
export function targets(f: FieldSpec): string[] {
  return f.to === undefined ? [] : asList(f.to);
}

/** A field is a link if its type is `link`, `list[link]`, or a union containing one. */
export function isLink(f: FieldSpec): boolean {
  if (Array.isArray(f.type)) return f.type.includes('link');
  return f.type === 'link' || f.type === 'list[link]';
}

/**
 * The verb an effect names, whether written bare (`archive`) or as a mapping
 * carrying its argument (`{ stamp: completed }`).
 */
export function effectVerb(e: Effect): string {
  if (typeof e === 'string') return e;
  const [verb] = Object.keys(e);
  if (verb === undefined) throw new Error('effect mapping has no verb: ' + JSON.stringify(e));
  return verb;
}
