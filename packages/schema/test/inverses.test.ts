// query.inverses.by_target is a declared list. The fields themselves declare
// inverse names independently. This test asserts the two agree, in both
// directions — the retired validator's declared-equals-implemented discipline,
// applied to the one contract types.yaml makes with itself.
//
// An inverse name must be unique on its TARGET type, not globally: `area`
// receives four, two of which come from the same source type.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildModel } from '../src/model.ts';

const model = buildModel();
const stated = model.types.query.inverses.by_target;

test('every target with inverses is declared in the query contract', () => {
  const declared = [...model.inversesByTarget.keys()].sort();
  const contract = Object.keys(stated).sort();
  assert.deepEqual(declared, contract);
});

test('the inverse names each target receives match the contract exactly', () => {
  for (const [target, names] of model.inversesByTarget) {
    assert.deepEqual(
      [...names].sort(),
      [...(stated[target] ?? [])].sort(),
      `inverses received by \`${target}\``,
    );
  }
});

test('inverse names are unique on their target', () => {
  const perTarget = new Map<string, string[]>();
  for (const lf of model.linkFields) {
    for (const target of lf.targets) {
      const names = perTarget.get(target);
      if (names === undefined) perTarget.set(target, [`${lf.inverse}`]);
      else names.push(lf.inverse);
    }
  }
  for (const [target, names] of perTarget) {
    const duplicates = names.filter((n, i) => names.indexOf(n) !== i);
    assert.deepEqual(duplicates, [], `\`${target}\` receives a repeated inverse name`);
  }
});

test('every link field declares an inverse and at least one target', () => {
  for (const lf of model.linkFields) {
    assert.ok(lf.inverse, `${lf.sourceType}.${lf.field} has no inverse`);
    assert.ok(lf.targets.length > 0, `${lf.sourceType}.${lf.field} has no to:`);
  }
});

test('every link target is a core type, or the wildcard', () => {
  const known = new Set([...model.coreTypes, '*']);
  for (const lf of model.linkFields) {
    for (const target of lf.targets) {
      assert.ok(known.has(target), `${lf.sourceType}.${lf.field} points at unknown type \`${target}\``);
    }
  }
});
