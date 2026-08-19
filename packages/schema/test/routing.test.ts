// The routing table is Folder-layout.yaml read in reverse: types never name
// folders, categories name subtype VALUES. So every routing key must resolve
// to exactly one category. Zero matches routes a record nowhere; two is the
// ambiguity that has happened before — `report` collided between 05 and 39.
//
// This is a schema defect either way, not a record defect, which is why it is
// checked here and not at write time.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildModel } from '../src/model.ts';

const model = buildModel();

test('every routing key resolves to exactly one category', () => {
  const unresolved: string[] = [];
  for (const { key, type } of model.routingKeys) {
    const claims = model.layoutClaims.get(key) ?? [];
    if (claims.length !== 1) {
      unresolved.push(`${key} (${type}) -> ${claims.length === 0 ? 'nothing' : claims.join(', ')}`);
    }
  }
  assert.deepEqual(unresolved, []);
});

test('no category claims a key that no type routes on', () => {
  const routable = new Set(model.routingKeys.map((r) => r.key));
  const explicit = new Set(model.types.routing.explicit.map((e) => e.type));
  const orphaned: string[] = [];
  for (const [key, claims] of model.layoutClaims) {
    // `*` is the inbox, which accepts anything. Explicitly-routed types are
    // claimed by name rather than by a subtype value.
    if (key === '*' || routable.has(key) || explicit.has(key)) continue;
    orphaned.push(`${key} claimed by ${claims.join(', ')}`);
  }
  assert.deepEqual(orphaned, []);
});

test('every explicitly-routed type is a core type and is not derived from the layout', () => {
  const derived = new Set(model.types.routing.derived_from_layout.types);
  for (const rule of model.types.routing.explicit) {
    assert.ok(model.coreTypes.includes(rule.type), `${rule.type} is not a core type`);
    if (rule.type === 'document') continue; // routes by doc_type until attaches_to is set
    assert.ok(!derived.has(rule.type), `${rule.type} is routed both explicitly and by the layout`);
  }
});

test('every core type routes somehow', () => {
  const routed = new Set([
    ...model.types.routing.derived_from_layout.types,
    ...model.types.routing.explicit.map((e) => e.type),
  ]);
  for (const type of model.coreTypes) {
    assert.ok(routed.has(type), `\`${type}\` has no routing rule`);
  }
});

test('archive category 9N mirrors area N0-N9', () => {
  // Computable, so no lookup table — but the areas it computes over have to exist.
  const archives = model.layout.areas.find((a) => a.id === 'archives');
  assert.ok(archives, 'no archives area');
  const archived = new Set((archives.categories ?? []).map((c) => c.jd));
  for (const area of model.layout.areas) {
    if (area.id === 'archives' || area.zone !== 'typed') continue;
    const n = area.jd.slice(0, 1);
    if (n === '0') continue; // 00-09 has no archive counterpart, by design
    assert.ok(archived.has(`9${n}`), `area ${area.jd} has no archive category 9${n}`);
  }
});
