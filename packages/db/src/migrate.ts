// The migration runner. Forward-only, one transaction per file, checksummed.
//
// No migration library, on purpose: the DDL is hand-written by decision, and a
// library that generates or reverses it takes that back. What is left is small
// enough to read in one sitting, which is the point.

import { createHash } from 'node:crypto';
import { readdirSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import type { Client } from 'pg';

export const MIGRATIONS_DIR = join(dirname(dirname(fileURLToPath(import.meta.url))), 'migrations');

/** Only this lock may apply migrations; two containers starting together queue. */
const LOCK_KEY = 8_374_221_905_461_233n % 2_147_483_647n;

export type Migration = { version: number; name: string; file: string; sql: string; checksum: string };

export type Applied = { version: number; name: string; checksum: string };

const FILENAME = /^(\d{4})_([a-z0-9_]+)\.sql$/;

export function loadMigrations(dir = MIGRATIONS_DIR): Migration[] {
  const migrations = readdirSync(dir)
    .filter((f) => f.endsWith('.sql'))
    .map((file) => {
      const m = FILENAME.exec(file);
      if (m === null) throw new Error(`migration filename must be NNNN_name.sql: ${file}`);
      const sql = readFileSync(join(dir, file), 'utf8');
      return {
        version: Number(m[1]),
        name: m[2] as string,
        file,
        sql,
        checksum: createHash('sha256').update(sql).digest('hex'),
      };
    })
    .sort((a, b) => a.version - b.version);

  migrations.forEach((m, i) => {
    const previous = migrations[i - 1];
    if (previous !== undefined && previous.version === m.version) {
      throw new Error(`duplicate migration version ${m.version}: ${previous.file} and ${m.file}`);
    }
  });
  return migrations;
}

async function ensureLedger(client: Client): Promise<void> {
  await client.query(`
    CREATE TABLE IF NOT EXISTS schema_migrations (
      version     integer PRIMARY KEY,
      name        text        NOT NULL,
      checksum    text        NOT NULL,
      applied_at  timestamptz NOT NULL DEFAULT now(),
      duration_ms integer     NOT NULL
    )
  `);
}

export async function appliedMigrations(client: Client): Promise<Applied[]> {
  await ensureLedger(client);
  const { rows } = await client.query<Applied>(
    'SELECT version, name, checksum FROM schema_migrations ORDER BY version',
  );
  return rows;
}

/**
 * An applied migration whose file has since changed is a hard failure. The
 * database cannot be re-derived from a file that no longer describes it, so
 * the only honest options are a new migration or a restore — never a warning.
 */
export function verifyChecksums(migrations: Migration[], applied: Applied[]): void {
  const byVersion = new Map(migrations.map((m) => [m.version, m]));
  for (const row of applied) {
    const migration = byVersion.get(row.version);
    if (migration === undefined) {
      throw new Error(`migration ${row.version} (${row.name}) is applied but its file is gone`);
    }
    if (migration.checksum !== row.checksum) {
      throw new Error(
        `migration ${migration.file} was edited after it was applied\n` +
          `  applied: ${row.checksum}\n  on disk: ${migration.checksum}\n` +
          `  Write a new migration, or restore and re-apply. Editing history is neither.`,
      );
    }
  }
}

export type MigrateResult = { applied: Migration[]; alreadyApplied: number };

export async function migrate(
  client: Client,
  options: { dir?: string; log?: (message: string) => void } = {},
): Promise<MigrateResult> {
  const log = options.log ?? (() => {});
  const migrations = loadMigrations(options.dir);

  await client.query('SELECT pg_advisory_lock($1)', [LOCK_KEY.toString()]);
  try {
    const applied = await appliedMigrations(client);
    verifyChecksums(migrations, applied);

    const done = new Set(applied.map((a) => a.version));
    const pending = migrations.filter((m) => !done.has(m.version));
    if (pending.length === 0) log(`schema up to date (${applied.length} applied)`);

    for (const migration of pending) {
      const started = process.hrtime.bigint();
      await client.query('BEGIN');
      try {
        await client.query(migration.sql);
        const ms = Number((process.hrtime.bigint() - started) / 1_000_000n);
        await client.query(
          'INSERT INTO schema_migrations (version, name, checksum, duration_ms) VALUES ($1, $2, $3, $4)',
          [migration.version, migration.name, migration.checksum, ms],
        );
        await client.query('COMMIT');
        log(`applied ${migration.file} (${ms}ms)`);
      } catch (error) {
        await client.query('ROLLBACK');
        throw new Error(`${migration.file} failed: ${(error as Error).message}`, { cause: error });
      }
    }
    return { applied: pending, alreadyApplied: applied.length };
  } finally {
    await client.query('SELECT pg_advisory_unlock($1)', [LOCK_KEY.toString()]);
  }
}
