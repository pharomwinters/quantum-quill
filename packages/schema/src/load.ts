// Loads the two schema files. Nothing here interprets them — see model.ts.
//
// The YAML is the specification, so it is read at runtime rather than
// generated into TypeScript: a generated copy is a second source of truth,
// which is the failure this project exists to correct.

import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'yaml';

export type FieldSpec = {
  key: string;
  type: string | string[];
  of?: string;
  to?: string | string[];
  inverse?: string;
  required?: boolean | 'on-create';
  unique?: boolean;
  immutable?: boolean;
  system?: boolean;
  description?: string;
};

export type TypeSpec = {
  id: string;
  name: string;
  kind: string;
  subtype: string | null;
  provenance: 'derived' | 'confirmed' | 'provisional';
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

export type Types = {
  meta: { name: string; version: number; updated: string };
  field_types: Record<string, string>;
  universal: FieldSpec[];
  routing: {
    derived_from_layout: { types: string[]; rule: string };
    explicit: Array<{ type: string; routes_by: string }>;
  };
  types: TypeSpec[];
  vocabularies: Record<string, VocabularySpec>;
  query: {
    indexes: Array<{ class: string; fields: string[] | string; subtypes?: string[] }>;
    inverses: { by_target: Record<string, string[]> };
  };
  validation: { error: string[]; warn: string[]; info: string[] };
  open_questions: Array<{ id: string; question: string }>;
};

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
  zones: Record<string, unknown>;
  rules: Array<{ id: string; statement: string }>;
  areas: AreaSpec[];
};

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

/** `to:` is one target or several; normalise to a list. */
export function targets(f: FieldSpec): string[] {
  if (f.to === undefined) return [];
  return typeof f.to === 'string' ? [f.to] : f.to;
}

/** A field is a link if its type is `link`, `list[link]`, or a union containing one. */
export function isLink(f: FieldSpec): boolean {
  if (Array.isArray(f.type)) return f.type.includes('link');
  return f.type === 'link' || f.type === 'list[link]';
}
