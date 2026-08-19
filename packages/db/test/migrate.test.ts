// The runner: applies once, is idempotent, and refuses edited history.

import { test, after, before } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { appliedMigrations, loadMigrations, migrate, verifyChecksums } from '../src/migrate.ts';
import { scratchDatabase, type Scratch } from './harness.ts';

let scratch: Scratch;

before(async () => {
  // Not seeded: this file is about the runner, not the vocabularies.
  scratch = await scratchDatabase({ seed: false });
});

after(async () => {
  await scratch?.drop();
});

test('every migration filename is NNNN_name.sql, and versions are unique', () => {
  const migrations = loadMigrations();
  assert.ok(migrations.length > 0);
  const versions = migrations.map((m) => m.version);
  assert.deepEqual([...versions].sort((a, b) => a - b), versions, 'migrations are not in version order');
  assert.equal(new Set(versions).size, versions.length);
});

test('the ledger records every migration that ran', async () => {
  const applied = await appliedMigrations(scratch.client);
  assert.deepEqual(
    applied.map((a) => a.version),
    loadMigrations().map((m) => m.version),
  );
});

test('re-running applies nothing', async () => {
  const result = await migrate(scratch.client);
  assert.deepEqual(result.applied, []);
  assert.equal(result.alreadyApplied, loadMigrations().length);
});

test('a migration edited after it was applied is a hard failure', () => {
  const migrations = loadMigrations();
  const first = migrations[0];
  assert.ok(first);
  const applied = [{ version: first.version, name: first.name, checksum: 'a-different-checksum' }];
  assert.throws(
    () => verifyChecksums(migrations, applied),
    /was edited after it was applied/,
  );
});

test('an applied migration whose file has vanished is a hard failure', () => {
  assert.throws(
    () => verifyChecksums([], [{ version: 1, name: 'gone', checksum: 'x' }]),
    /is applied but its file is gone/,
  );
});

test('a badly named migration file is refused', () => {
  const dir = mkdtempSync(join(tmpdir(), 'qq-migrations-'));
  try {
    writeFileSync(join(dir, 'add_a_thing.sql'), 'SELECT 1');
    assert.throws(() => loadMigrations(dir), /must be NNNN_name\.sql/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('two migrations claiming the same version are refused', () => {
  const dir = mkdtempSync(join(tmpdir(), 'qq-migrations-'));
  try {
    writeFileSync(join(dir, '0001_one.sql'), 'SELECT 1');
    writeFileSync(join(dir, '0001_two.sql'), 'SELECT 2');
    assert.throws(() => loadMigrations(dir), /duplicate migration version/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('a failing migration leaves nothing behind', async () => {
  const dir = mkdtempSync(join(tmpdir(), 'qq-migrations-'));
  try {
    writeFileSync(
      join(dir, '0001_half_valid.sql'),
      'CREATE TABLE should_not_survive (x int);\nTHIS IS NOT SQL;',
    );
    const fresh = await scratchDatabase({ migrate: false });
    try {
      await assert.rejects(() => migrate(fresh.client, { dir }), /0001_half_valid\.sql failed/);
      const survivors = await fresh.client.query(
        `SELECT 1 FROM information_schema.tables WHERE table_name = 'should_not_survive'`,
      );
      assert.equal(survivors.rowCount, 0, 'a failed migration was not rolled back');
    } finally {
      await fresh.drop();
    }
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
