// A scratch database per test file: created, migrated, dropped.
//
// Tests never touch the dev database. Building the schema only from the
// migrations is what keeps the cross-check honest — a hand-patched dev database
// would let a missing migration pass.

import { Client } from 'pg';
import { migrate } from '../src/migrate.ts';
import { sync } from '../src/sync.ts';
import { withDatabase } from '../src/connect.ts';

const BASE = process.env['DATABASE_URL'] ?? 'postgres://postgres@localhost:5432/postgres';

let counter = 0;

export type Scratch = { client: Client; name: string; drop: () => Promise<void> };

/**
 * A fresh database with every migration applied and the vocabularies seeded.
 * `migrate: false` gives an empty one, for testing the runner itself.
 */
export async function scratchDatabase(
  options: { seed?: boolean; migrate?: boolean } = {},
): Promise<Scratch> {
  const name = `vault_test_${process.pid}_${counter++}`;
  const admin = new Client({ connectionString: withDatabase(BASE, 'postgres') });
  await admin.connect();
  await admin.query(`DROP DATABASE IF EXISTS ${name}`);
  await admin.query(`CREATE DATABASE ${name}`);
  await admin.end();

  const client = new Client({ connectionString: withDatabase(BASE, name) });
  await client.connect();
  if (options.migrate !== false) {
    await migrate(client);
    if (options.seed !== false) await sync(client);
  }

  return {
    client,
    name,
    drop: async () => {
      await client.end();
      const cleanup = new Client({ connectionString: withDatabase(BASE, 'postgres') });
      await cleanup.connect();
      await cleanup.query(`DROP DATABASE IF EXISTS ${name}`);
      await cleanup.end();
    },
  };
}
