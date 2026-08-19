// What the database actually enforces, tested rule by rule.
//
// The service design claims ~12 of 28 validation rules become constraints.
// This file is what makes the claim measurable instead of estimated: every
// rule below is named by its id from types.yaml, and either has a test that
// watches it reject a write, or an entry saying which phase owns it.
//
// The meta-test at the bottom is the point — declared equals implemented, the
// same discipline the retired validator applied to its own rule registry.

import { test, after, before } from 'node:test';
import assert from 'node:assert/strict';
import { buildModel } from '@quantum-quill/schema';
import type { Client } from 'pg';
import { scratchDatabase, type Scratch } from './harness.ts';

const model = buildModel();

/** Rules the DDL enforces today. The value names the mechanism. */
const ENFORCED: Readonly<Record<string, string>> = {
  'duplicate-id': 'PRIMARY KEY on record',
  'value-outside-closed-vocabulary': 'FK to vocabulary through a generated companion',
  'unresolvable-link': 'FK from link to record(id, type)',
  'malformed-date': 'date column type',
  'missing-required-field': 'NOT NULL — scalar fields only',
  'subtype-field-on-wrong-subtype': 'CHECK — scalar adds only',
  'id-changed': 'BEFORE UPDATE trigger on record',
};

/** Rules the DDL does not enforce, and why. Every one must be accounted for. */
const NOT_ENFORCED: Readonly<Record<string, string>> = {
  'wrong-folder': 'dissolves: there are no folders to be wrong about',
  'container-id-mismatch': 'dissolves: no folder to disagree with',
  'organization-as-text': 'dissolves: it is a link row or a text column, never ambiguous',
  'empty-field-normally-filled': 'dissolves: typed columns',

  'world-entry-without-world': 'phase 2: a required LINK is cross-row, so not NOT NULL',
  'blocked-task-without-blocker': 'phase 2: trigger',
  'area-closed-with-active-projects': 'phase 2: trigger',
  'superseded-without-successor': 'phase 2: trigger',
  'illegal-transition': 'phase 2: state machines',
  'transition-requirement-unmet': 'phase 2: state machines',

  'missing-payload': 'phase 4: the projector is what knows whether the binary is there',
  'link-to-archived-record': 'phase 2: advisory',
  'finished-project-without-result': 'phase 2: advisory',
  'person-without-relationship': 'phase 2: advisory, required on create only',
  'project-done-with-open-tasks': 'phase 2: advisory',
  'world-archived-with-entries': 'phase 2: advisory',
  'terminal-record-not-archived': 'phase 2: advisory',
  orphan: 'phase 5: advisory',
  stale: 'phase 5: advisory',
  'untyped-binary': 'phase 4: needs the tree',
  'first-instance-of-provisional': 'phase 3: needs records',
};

let scratch: Scratch;
let db: Client;

before(async () => {
  scratch = await scratchDatabase();
  db = scratch.client;
  await db.query(`INSERT INTO record (id, type) VALUES
    ('paint-line', 'project'), ('acme', 'area'), ('bob', 'person'),
    ('a-deed', 'document'), ('a-paystub', 'document'), ('a-task', 'task')`);
  await db.query(`INSERT INTO project (id, status, scope) VALUES ('paint-line', 'active', 'work')`);
  await db.query(`INSERT INTO document (id, file, doc_type, doc_date) VALUES
    ('a-deed', 'deed.pdf', 'deed', '2026-01-01'),
    ('a-paystub', 'pay.pdf', 'paystub', '2026-01-31')`);
});

after(async () => {
  await scratch?.drop();
});

/** Runs a statement that must fail, and returns why. Rolled back either way. */
async function rejects(sql: string, params: unknown[] = []): Promise<{ code: string; message: string }> {
  await db.query('BEGIN');
  try {
    await db.query(sql, params);
    await db.query('ROLLBACK');
    throw new Error(`expected a rejection, but the write succeeded: ${sql.trim().split('\n')[0]}`);
  } catch (error) {
    const e = error as { code?: string; message: string };
    await db.query('ROLLBACK');
    if (e.code === undefined) throw error;
    return { code: e.code, message: e.message };
  }
}

// The seven ------------------------------------------------------------------

test('duplicate-id: a second record with the same id is rejected', async () => {
  const { code } = await rejects(`INSERT INTO record (id, type) VALUES ('bob', 'person')`);
  assert.equal(code, '23505'); // unique_violation
});

test('value-outside-closed-vocabulary: an invented type is rejected', async () => {
  const { code } = await rejects(`INSERT INTO record (id, type) VALUES ('x', 'invented')`);
  assert.equal(code, '23503'); // foreign_key_violation
});

test('value-outside-closed-vocabulary: an invented doc_type is rejected', async () => {
  const { code } = await rejects(`UPDATE document SET doc_type = 'invented' WHERE id = 'a-deed'`);
  assert.equal(code, '23503');
});

test('unresolvable-link: a link to a record that does not exist is rejected', async () => {
  const { code } = await rejects(
    `INSERT INTO link VALUES ('a-deed', 'document', 'attaches_to', 'ghost', 'project')`,
  );
  assert.equal(code, '23503');
});

test('malformed-date: a date that is not one is rejected', async () => {
  const { code } = await rejects(`UPDATE document SET doc_date = '2026-13-45' WHERE id = 'a-deed'`);
  assert.equal(code, '22008'); // datetime_field_overflow
});

test('missing-required-field: an area with no standard is rejected', async () => {
  const { code } = await rejects(
    `INSERT INTO area (id, status) VALUES ('acme', 'active')`,
  );
  assert.equal(code, '23502'); // not_null_violation
});

test('subtype-field-on-wrong-subtype: gross on a deed is rejected', async () => {
  const { code, message } = await rejects(
    `UPDATE document SET gross = 100, gross_currency = 'GBP' WHERE id = 'a-deed'`,
  );
  assert.equal(code, '23514'); // check_violation
  // Both the amount guard and the currency guard forbid this write; Postgres
  // reports whichever it evaluates first, so assert the family, not the name.
  assert.match(message, /document_gross(_currency)?_subtype/);
});

test('subtype-field-on-wrong-subtype: a lone paystub field on a deed is rejected', async () => {
  // pay_period is guarded by exactly one constraint, so the name is determinate.
  const { code, message } = await rejects(
    `UPDATE document SET pay_period = 'monthly' WHERE id = 'a-deed'`,
  );
  assert.equal(code, '23514');
  assert.match(message, /document_pay_period_subtype/);
});

test('subtype-field-on-wrong-subtype: the same field on a paystub is accepted', async () => {
  await db.query('BEGIN');
  await db.query(`UPDATE document SET gross = 100, gross_currency = 'GBP' WHERE id = 'a-paystub'`);
  await db.query('ROLLBACK');
});

test('id-changed: an id cannot be edited', async () => {
  const { code, message } = await rejects(`UPDATE record SET id = 'robert' WHERE id = 'bob'`);
  assert.equal(code, '23001'); // restrict_violation
  assert.match(message, /id is immutable/);
});

// What the rule list never named --------------------------------------------

test('a link may not point at a type the field does not declare', async () => {
  // document.attaches_to declares project, area and world. Not person.
  const { code } = await rejects(
    `INSERT INTO link VALUES ('a-deed', 'document', 'attaches_to', 'bob', 'person')`,
  );
  assert.equal(code, '23503');
});

test('a link may not point at an existing record of the wrong type', async () => {
  const { code } = await rejects(
    `INSERT INTO link VALUES ('a-deed', 'document', 'attaches_to', 'bob', 'project')`,
  );
  assert.equal(code, '23503');
});

test('a single-valued link field may not be given a second value', async () => {
  await db.query('BEGIN');
  await db.query(`INSERT INTO link VALUES ('a-deed', 'document', 'attaches_to', 'paint-line', 'project')`);
  let code = '';
  try {
    await db.query(`INSERT INTO link VALUES ('a-deed', 'document', 'attaches_to', 'acme', 'area')`);
  } catch (error) {
    code = (error as { code: string }).code;
  }
  await db.query('ROLLBACK');
  assert.equal(code, '23505');
});

test('a multi-valued link field may be given several values', async () => {
  await db.query('BEGIN');
  await db.query(`INSERT INTO link VALUES ('a-deed', 'document', 'party', 'bob', 'person')`);
  await db.query(`INSERT INTO record (id, type) VALUES ('carol', 'person')`);
  await db.query(`INSERT INTO link VALUES ('a-deed', 'document', 'party', 'carol', 'person')`);
  await db.query('ROLLBACK');
});

test('a record that something links to cannot be deleted', async () => {
  await db.query('BEGIN');
  await db.query(`INSERT INTO link VALUES ('a-deed', 'document', 'attaches_to', 'paint-line', 'project')`);
  let code = '';
  try {
    await db.query(`DELETE FROM record WHERE id = 'paint-line'`);
  } catch (error) {
    code = (error as { code: string }).code;
  }
  await db.query('ROLLBACK');
  assert.equal(code, '23503');
});

test('a subtype row cannot attach to a record of another type', async () => {
  const { code } = await rejects(`INSERT INTO task (id, state) VALUES ('bob', 'open')`);
  assert.equal(code, '23503');
});

test('deleting a record removes its subtype row and its links', async () => {
  await db.query('BEGIN');
  await db.query(`INSERT INTO link VALUES ('a-deed', 'document', 'party', 'bob', 'person')`);
  await db.query(`DELETE FROM record WHERE id = 'a-deed'`);
  const document = await db.query(`SELECT 1 FROM document WHERE id = 'a-deed'`);
  const links = await db.query(`SELECT 1 FROM link WHERE source = 'a-deed'`);
  await db.query('ROLLBACK');
  assert.equal(document.rowCount, 0);
  assert.equal(links.rowCount, 0);
});

test('an id that is not a slug is rejected', async () => {
  const { code } = await rejects(`INSERT INTO record (id, type) VALUES ('Not A Slug', 'person')`);
  assert.equal(code, '23514');
});

test('money is an amount and a currency, or neither', async () => {
  const { code, message } = await rejects(
    `UPDATE document SET gross = 100 WHERE id = 'a-paystub'`,
  );
  assert.equal(code, '23514');
  assert.match(message, /document_gross_is_money/);
});

// Declared equals implemented ------------------------------------------------

test('every validation rule is either enforced here or accounted for', () => {
  const declared = [
    ...model.types.validation.error,
    ...model.types.validation.warn,
    ...model.types.validation.info,
  ];
  const accounted = new Set([...Object.keys(ENFORCED), ...Object.keys(NOT_ENFORCED)]);
  const unaccounted = declared.filter((rule) => !accounted.has(rule));
  assert.deepEqual(unaccounted, [], 'a rule in types.yaml that this file says nothing about');
});

test('every rule this file names exists in types.yaml', () => {
  const declared = new Set([
    ...model.types.validation.error,
    ...model.types.validation.warn,
    ...model.types.validation.info,
  ]);
  const invented = [...Object.keys(ENFORCED), ...Object.keys(NOT_ENFORCED)].filter(
    (rule) => !declared.has(rule),
  );
  assert.deepEqual(invented, [], 'a rule this file claims to cover that the schema does not declare');
});

test('the counts the service design quotes are what phase 1 actually delivers', () => {
  const declared =
    model.types.validation.error.length +
    model.types.validation.warn.length +
    model.types.validation.info.length;
  assert.equal(declared, 28, 'types.yaml no longer declares 28 rules — update the design doc');
  assert.equal(Object.keys(ENFORCED).length, 7);
  assert.equal(
    Object.values(NOT_ENFORCED).filter((why) => why.startsWith('dissolves')).length,
    4,
  );
});
