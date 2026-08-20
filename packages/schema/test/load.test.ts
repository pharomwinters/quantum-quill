// The TypeScript view of the schema files equals the schema files.
//
// This is the cross-check's problem one layer up. `read<T>()` casts whatever
// YAML holds into the declared type, so a block the file carries and load.ts
// does not declare parses fine, types as nothing, and goes unnoticed — which
// is exactly what happened to `lifecycle`, `import` and four of the six keys
// on `routing.explicit` for the whole of phase 1.
//
// The key lists in load.ts are proved against the TYPES at compile time. These
// tests prove the same lists against the FILES. Neither half is sufficient
// alone: the compile-time proof says the list matches what we declare, and
// these say what we declare matches what exists.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  loadTypes, loadLayout, valueAdds,
  TYPES_KEYS, LAYOUT_KEYS, FIELD_ATTRIBUTE_KEYS,
  type FieldSpec,
} from '../src/index.ts';

const types = loadTypes();
const layout = loadLayout();

const sorted = (v: readonly string[]): string[] => [...v].sort();

test('every top-level block of types.yaml is declared, and every declared block exists', () => {
  assert.deepEqual(sorted(Object.keys(types)), sorted(TYPES_KEYS));
});

test('every top-level block of Folder-layout.yaml is declared, and every declared block exists', () => {
  assert.deepEqual(sorted(Object.keys(layout)), sorted(LAYOUT_KEYS));
});

test('FieldSpec carries exactly the attributes field_attributes declares', () => {
  assert.deepEqual(sorted(Object.keys(types.field_attributes)), sorted(FIELD_ATTRIBUTE_KEYS));
});

/** Universal fields, type fields, and the fields a subtype value contributes. */
function everyField(): FieldSpec[] {
  const adds = Object.values(types.vocabularies).flatMap((v) => v.values.flatMap(valueAdds));
  return [...types.universal, ...types.types.flatMap((t) => t.fields ?? []), ...adds];
}

/**
 * Field attributes the file uses and `field_attributes` does not declare.
 *
 * Same two rules as packages/db/test/exemptions.ts: an entry that no longer
 * matches anything FAILS, and adding one is a schema conversation rather than
 * a fix. Empty is the intended steady state.
 */
const UNDECLARED_ATTRIBUTES: ReadonlyArray<{ attribute: string; on: string; reason: string }> = [
  {
    attribute: 'sensitive',
    on: 'resource_type=software-license adds license_key',
    reason:
      'Sensitivity is folder-scoped everywhere else: the layout marks CATEGORIES ' +
      'sensitive (31, 34, 36), `sensitive-not-scanned` excludes those folders from ' +
      'the text index, and the design binds them to a LAN-only listener. This is the ' +
      'only field-level use, and `software-license` routes to 38 Purchases, ' +
      'Warranties & Licenses, which is not sensitive — so the attribute claims a ' +
      'protection no mechanism delivers. Declare it, drop it, or make the category ' +
      'sensitive. Not guessed at here.',
  },
];

test('no field uses an attribute that field_attributes does not declare', () => {
  const declared = new Set<string>([...FIELD_ATTRIBUTE_KEYS, 'key', 'type', 'description']);
  const found = new Set<string>();
  for (const f of everyField()) {
    for (const k of Object.keys(f)) if (!declared.has(k)) found.add(k);
  }

  const registered = new Set(UNDECLARED_ATTRIBUTES.map((e) => e.attribute));
  assert.deepEqual(
    [...found].filter((a) => !registered.has(a)),
    [],
    'a field attribute nothing declares and nothing accounts for',
  );
  assert.deepEqual(
    [...registered].filter((a) => !found.has(a)),
    [],
    'a registered exemption that no longer matches anything — delete it',
  );
});

// The blocks phase 2 reads. The top-level check above cannot see inside them,
// and these are the shapes the interpreter, the router and the importer are
// about to be written against.
const NESTED: Array<{ what: string; rows: () => object[]; keys: string[] }> = [
  {
    what: 'lifecycle.machines',
    rows: () => types.lifecycle.machines,
    keys: ['type', 'field', 'provenance', 'evidence', 'initial', 'terminal',
           'transitions', 'snapshots', 'archive', 'note'],
  },
  {
    what: 'lifecycle.machines[].transitions',
    rows: () => types.lifecycle.machines.flatMap((m) => m.transitions),
    keys: ['from', 'to', 'requires', 'requires_index', 'guards', 'effects', 'note'],
  },
  {
    what: 'transition guards',
    rows: () => types.lifecycle.machines.flatMap((m) => m.transitions.flatMap((t) => t.guards ?? [])),
    keys: ['check', 'severity', 'message', 'note'],
  },
  {
    what: 'routing.explicit',
    rows: () => types.routing.explicit,
    keys: ['type', 'routes_by', 'map', 'when', 'relative_to', 'rule'],
  },
  {
    what: 'import.derived',
    rows: () => types.import.derived,
    keys: ['field', 'source', 'covers', 'note'],
  },
  {
    what: 'open_questions',
    rows: () => types.open_questions,
    keys: ['id', 'raised', 'question', 'evidence', 'why_unresolved', 'unblocks', 'decide_by'],
  },
];

for (const { what, rows, keys } of NESTED) {
  test(`${what} uses no key load.ts does not declare`, () => {
    const declared = new Set(keys);
    const seen = new Set<string>();
    const all = rows();
    assert.ok(all.length > 0, `${what} matched nothing — the walk is wrong, not the file`);
    for (const row of all) {
      for (const k of Object.keys(row)) if (!declared.has(k)) seen.add(k);
    }
    assert.deepEqual([...seen], [], `${what} carries a key load.ts cannot see`);
  });
}

test('every guard severity is one the interpreter will have to distinguish', () => {
  const severities = new Set(
    types.lifecycle.machines.flatMap((m) => m.transitions.flatMap((t) => (t.guards ?? []).map((g) => g.severity))),
  );
  assert.deepEqual(sorted([...severities]), ['error', 'warn']);
});
