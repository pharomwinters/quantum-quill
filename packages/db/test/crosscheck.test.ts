// THE CROSS-CHECK.
//
// Asserts that the live Postgres schema and types.yaml agree in both
// directions: a column with no field fails, a field with no column fails, an
// enum whose values differ fails.
//
// This is the load-bearing test of phase 1. Without it, types.yaml degrades
// from executable specification to advisory documentation the moment SQL
// exists alongside it, and the project drifts back into exactly the failure it
// was created to correct.
//
// Failures are reported as a diff — expected-only, actual-only — so that a
// failure names the edit that caused it rather than an assertion count.

import { test, after, before } from 'node:test';
import assert from 'node:assert/strict';
import { buildModel, tableName } from '@quantum-quill/schema';
import { canonicalType, introspect, literals, type LiveSchema } from '../src/introspect.ts';
import { scratchDatabase, type Scratch } from './harness.ts';
import { EXEMPTIONS } from './exemptions.ts';

const model = buildModel();

/** Tables that exist for the store rather than for a type. */
const INFRASTRUCTURE = new Set([
  'schema_migrations',
  'vocabulary',
  'link_field',
  'link',
  ...model.junctions.map((j) => j.name),
]);

/** Columns excluded by rule rather than by exemption — see exemptions.ts. */
function isStructural(table: string, column: { name: string; generated: boolean }): boolean {
  if (column.generated) return true;
  if (table === 'record') return false;
  return column.name === 'id' || column.name === 'type';
}

function exempt(table: string, column: string): boolean {
  return EXEMPTIONS.some((e) => e.table === table && e.column === column);
}

let scratch: Scratch;
let live: LiveSchema;

before(async () => {
  scratch = await scratchDatabase();
  live = await introspect(scratch.client);
});

after(async () => {
  await scratch?.drop();
});

// A1 ------------------------------------------------------------------------
test('A1: every core type has a table, and every table has a core type', () => {
  const expected = [...model.tables.values()].map((t) => t.name).sort();
  const actual = live.tables.filter((t) => !INFRASTRUCTURE.has(t)).sort();
  assert.deepEqual(actual, expected);
});

test('A1: every junction the model declares exists', () => {
  for (const junction of model.junctions) {
    assert.ok(live.tables.includes(junction.name), `missing junction table ${junction.name}`);
  }
});

// A2 ------------------------------------------------------------------------
test('A2: every declared field has a column, and every column has a field', () => {
  const problems: string[] = [];

  for (const table of model.tables.values()) {
    const expected = new Set(table.columns.map((c) => c.name));
    const actual = live.columns.filter((c) => c.table === table.name && !isStructural(table.name, c));

    for (const column of actual) {
      if (!expected.has(column.name) && !exempt(table.name, column.name)) {
        problems.push(`${table.name}.${column.name}: column with no field`);
      }
    }
    const present = new Set(actual.map((c) => c.name));
    for (const column of table.columns) {
      if (!present.has(column.name)) problems.push(`${table.name}.${column.name}: field with no column`);
    }
  }

  assert.deepEqual(problems, []);
});

// A3 ------------------------------------------------------------------------
test('A3: every column has the SQL type its field maps to', () => {
  const problems: string[] = [];
  for (const table of model.tables.values()) {
    for (const column of table.columns) {
      const actual = live.columns.find((c) => c.table === table.name && c.name === column.name);
      if (actual === undefined) continue; // A2 reports it
      const want = canonicalType(column.sqlType);
      if (actual.sqlType !== want) {
        problems.push(`${table.name}.${column.name}: expected ${want}, found ${actual.sqlType}`);
      }
    }
  }
  assert.deepEqual(problems, []);
});

// A4 ------------------------------------------------------------------------
test('A4: a column is NOT NULL exactly when its field is required', () => {
  const problems: string[] = [];
  for (const table of model.tables.values()) {
    for (const column of table.columns) {
      const actual = live.columns.find((c) => c.table === table.name && c.name === column.name);
      if (actual === undefined) continue;
      if (actual.notNull !== column.notNull) {
        problems.push(
          `${table.name}.${column.name}: field is ${column.notNull ? 'required' : 'optional'}, ` +
            `column is ${actual.notNull ? 'NOT NULL' : 'nullable'}`,
        );
      }
    }
  }
  assert.deepEqual(problems, []);
});

// A5 and A6 -----------------------------------------------------------------
//
// These two compare seeded tables against the model that seeded them, so on a
// freshly synced database they can only agree. That makes them a real check of
// one thing — that `sync` writes the model faithfully — and NO check at all of
// the thing they appear to check, which is a database whose seed has drifted
// from types.yaml since it was written. That case is the live one: a database
// seeded months ago, a vocabulary edited yesterday, `sync` not yet run.
//
// So each is paired with a test that drifts the live database inside a
// transaction and asserts the comparison notices. A check that cannot fail is
// worse than no check, because it reports safety it is not providing.

type Diff = { missing: string[]; extra: string[] };

function diff(expected: string[], actual: string[]): Diff {
  const want = new Set(expected);
  const have = new Set(actual);
  return {
    missing: expected.filter((e) => !have.has(e)).sort(),
    extra: actual.filter((a) => !want.has(a)).sort(),
  };
}

const vocabularyKeys = (schema: LiveSchema): string[] =>
  schema.vocabulary.map((v) => `${v.name}=${v.value}`);

const declaredVocabulary = (): string[] =>
  [...model.vocabularies].flatMap(([name, values]) => values.map((value) => `${name}=${value}`));

const linkFieldKey = (r: {
  sourceType: string;
  field: string;
  targetType: string;
  multi: boolean;
  inverse: string;
}): string =>
  `${r.sourceType}.${r.field} -> ${r.targetType} (${r.multi ? 'many' : 'one'}, inverse ${r.inverse})`;

test('A5: the seeded vocabularies equal the ones types.yaml declares', () => {
  assert.deepEqual(diff(declaredVocabulary(), vocabularyKeys(live)), { missing: [], extra: [] });
});

test('A5 can fail: a value in the database that types.yaml does not declare', async () => {
  await scratch.client.query('BEGIN');
  await scratch.client.query(`INSERT INTO vocabulary (name, value) VALUES ('priority', 'urgent')`);
  const drifted = await introspect(scratch.client);
  await scratch.client.query('ROLLBACK');
  assert.deepEqual(diff(declaredVocabulary(), vocabularyKeys(drifted)).extra, ['priority=urgent']);
});

test('A5 can fail: a declared value the database is missing', async () => {
  await scratch.client.query('BEGIN');
  await scratch.client.query(`DELETE FROM vocabulary WHERE name = 'priority' AND value = 'low'`);
  const drifted = await introspect(scratch.client);
  await scratch.client.query('ROLLBACK');
  assert.deepEqual(diff(declaredVocabulary(), vocabularyKeys(drifted)).missing, ['priority=low']);
});

test('A6: link_field holds exactly the declared link fields, with their targets', () => {
  assert.deepEqual(
    diff(model.linkFieldRows.map(linkFieldKey), live.linkFields.map(linkFieldKey)),
    { missing: [], extra: [] },
  );
});

test('A6 can fail: a link field whose cardinality has drifted', async () => {
  await scratch.client.query('BEGIN');
  await scratch.client.query(
    `UPDATE link_field SET multi = NOT multi WHERE source_type = 'task' AND field = 'projects'`,
  );
  const drifted = await introspect(scratch.client);
  await scratch.client.query('ROLLBACK');
  const result = diff(model.linkFieldRows.map(linkFieldKey), drifted.linkFields.map(linkFieldKey));
  assert.deepEqual(result.missing, ['task.projects -> project (many, inverse tasks)']);
  assert.deepEqual(result.extra, ['task.projects -> project (one, inverse tasks)']);
});

// A7 ------------------------------------------------------------------------
test('A7: the single-valued link index covers exactly the single-valued fields', () => {
  const index = live.indexes.find((i) => i.name === 'link_single_valued');
  assert.ok(index, 'link_single_valued index is missing');
  const covered = literals(index.definition).sort();
  const expected = [...new Set(model.linkFields.filter((l) => !l.multi).map((l) => l.field))].sort();
  assert.deepEqual(covered, expected);
});

test('A7: link_field.multi matches what the schema declares', () => {
  const problems: string[] = [];
  for (const row of model.linkFieldRows) {
    const actual = live.linkFields.find(
      (l) => l.sourceType === row.sourceType && l.field === row.field && l.targetType === row.targetType,
    );
    if (actual !== undefined && actual.multi !== row.multi) {
      problems.push(`${row.sourceType}.${row.field}: multi should be ${row.multi}`);
    }
  }
  assert.deepEqual(problems, []);
});

// A8 ------------------------------------------------------------------------
test('A8: every subtype field is guarded by a CHECK naming exactly its subtype values', () => {
  const problems: string[] = [];
  for (const table of model.tables.values()) {
    for (const column of table.columns) {
      if (column.guard === undefined) continue;
      const name = `${table.name}_${column.name}_subtype`;
      const check = live.checks.find((c) => c.table === table.name && c.name === name);
      if (check === undefined) {
        problems.push(`${table.name}.${column.name}: no guard constraint ${name}`);
        continue;
      }
      const named = literals(check.definition).sort();
      const expected = [...column.guard.values].sort();
      if (JSON.stringify(named) !== JSON.stringify(expected)) {
        problems.push(
          `${name}: guards [${named.join(', ')}], should guard [${expected.join(', ')}]`,
        );
      }
    }
  }
  assert.deepEqual(problems, []);
});

// A9 ------------------------------------------------------------------------
test('A9: every enum column foreign-keys to the vocabulary its field names', () => {
  const problems: string[] = [];
  for (const table of model.tables.values()) {
    for (const column of table.columns) {
      if (column.vocabulary === undefined) continue;

      const companion = live.columns.find(
        (c) => c.table === table.name && c.name === `${column.name}_vocab`,
      );
      if (companion === undefined || !companion.generated) {
        problems.push(`${table.name}.${column.name}: no generated ${column.name}_vocab companion`);
        continue;
      }
      const [named] = literals(companion.generationExpression ?? '');
      if (named !== column.vocabulary) {
        problems.push(
          `${table.name}.${column.name}: companion names \`${named}\`, field declares \`${column.vocabulary}\``,
        );
      }

      const fk = live.foreignKeys.find(
        (f) =>
          f.table === table.name &&
          f.definition.includes(`${column.name}_vocab`) &&
          f.definition.includes('REFERENCES vocabulary'),
      );
      if (fk === undefined) problems.push(`${table.name}.${column.name}: no foreign key to vocabulary`);
    }
  }
  assert.deepEqual(problems, []);
});

// A10 -----------------------------------------------------------------------
test('A10: every field the query contract guarantees is indexed, is indexed', () => {
  const byName = new Set<string>();
  const byVocabulary = new Set<string>();
  for (const index of model.types.query.indexes) {
    if (index.class !== 'exact' && index.class !== 'range') continue;
    for (const field of Array.isArray(index.fields) ? index.fields : []) byName.add(field);
    // `subtype_vocabularies:` names VOCABULARIES, not field names — the key is
    // spelled that way because the two are not interchangeable. `period` is
    // both the journal subtype vocabulary and a plain text field on a
    // performance-review document, and only the first is guaranteed queryable.
    for (const vocabulary of index.subtype_vocabularies ?? []) byVocabulary.add(vocabulary);
  }
  // `folder` is derived and has no column yet — open_questions.folder-storage.
  byName.delete('folder');

  const problems: string[] = [];
  for (const table of model.tables.values()) {
    for (const column of table.columns) {
      // A money field yields an amount and a currency; the guarantee is about
      // the amount. Companion columns are named for their field and are not it.
      const isTheFieldsOwnColumn = column.name === column.field;
      const guaranteed =
        (isTheFieldsOwnColumn && byName.has(column.field)) ||
        (column.vocabulary !== undefined && byVocabulary.has(column.vocabulary));
      if (!guaranteed) continue;

      const indexed = live.indexes.some(
        (i) => i.table === table.name && i.columns.includes(column.name),
      );
      if (!indexed) {
        problems.push(`${table.name}.${column.name} is guaranteed queryable but not indexed`);
      }
    }
  }
  assert.deepEqual(problems, []);
});

test('A10: the full-text and tag indexes the text class promises exist', () => {
  const onRecord = live.indexes.filter((i) => i.table === 'record');
  assert.ok(
    onRecord.some((i) => i.definition.includes('to_tsvector')),
    'no full-text index over title and body',
  );
  assert.ok(
    onRecord.some((i) => i.columns.includes('tags')),
    'no index over tags',
  );
});

// A11 -----------------------------------------------------------------------
test('A11: declared uniqueness is enforced, and nothing else is', () => {
  const structural = (columns: string[]): boolean =>
    columns.every((c) => c === 'id' || c === 'type');

  const problems: string[] = [];
  for (const table of model.tables.values()) {
    const declared = model.uniqueKeys
      .filter((k) => k.table === table.name)
      .map((k) => [...k.columns].sort().join(', '))
      .sort();

    // Primary keys and the record(id, type) handle are structural, not schema
    // claims, so they are excluded by rule rather than by exemption.
    const enforced = live.indexes
      .filter((i) => i.table === table.name && i.definition.includes('CREATE UNIQUE INDEX'))
      .map((i) => [...i.columns].sort())
      .filter((columns) => !structural(columns))
      .map((columns) => columns.join(', '))
      .sort();

    if (JSON.stringify(declared) !== JSON.stringify(enforced)) {
      problems.push(
        `${table.name}: declares unique [${declared.join(' | ')}], enforces [${enforced.join(' | ')}]`,
      );
    }
  }
  assert.deepEqual(problems, []);
});

test('A11: a field with a declared default has one in the database', () => {
  const problems: string[] = [];
  for (const table of model.tables.values()) {
    for (const column of table.columns) {
      if (column.default === undefined) continue;
      const actual = live.columns.find((c) => c.table === table.name && c.name === column.name);
      if (actual?.default == null) {
        problems.push(`${table.name}.${column.name} is declared with a default and has none`);
      }
    }
  }
  assert.deepEqual(problems, []);
});

// The register ---------------------------------------------------------------
test('no exemption is stale', () => {
  const stale = EXEMPTIONS.filter(
    (e) => !live.columns.some((c) => c.table === e.table && c.name === e.column),
  ).map((e) => `${e.table}.${e.column} (raised ${e.raised})`);
  assert.deepEqual(stale, [], 'an exemption that matches nothing is a place to hide things');
});

test('the table-name rule is the only mapping between type ids and tables', () => {
  for (const [type, table] of model.tables) {
    if (type === 'record') continue;
    assert.equal(table.name, tableName(type));
  }
});
