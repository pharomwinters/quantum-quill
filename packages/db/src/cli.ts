#!/usr/bin/env node
// migrate | sync | status | migrate-and-sync

import { appliedMigrations, loadMigrations, migrate } from './migrate.ts';
import { connect } from './connect.ts';
import { sync } from './sync.ts';

const command = process.argv[2] ?? 'status';
const prune = process.argv.includes('--prune');
const log = (message: string): void => {
  console.log(message);
};

const client = await connect();
try {
  switch (command) {
    case 'migrate':
      await migrate(client, { log });
      break;

    case 'sync': {
      const report = await sync(client, { prune });
      log(`vocabulary: ${report.vocabulary.inserted} inserted`);
      log(`link_field: ${report.linkFields.written} written`);
      for (const extra of [...report.vocabulary.extra, ...report.linkFields.extra]) {
        log(`  in the database but not in types.yaml: ${extra.replaceAll('\t', ' ')}`);
      }
      if (prune) log(`pruned: ${report.pruned}`);
      break;
    }

    case 'migrate-and-sync': {
      await migrate(client, { log });
      const report = await sync(client);
      log(
        `vocabulary: ${report.vocabulary.inserted} inserted, ` +
          `link_field: ${report.linkFields.written} written`,
      );
      break;
    }

    case 'status': {
      const applied = await appliedMigrations(client);
      const all = loadMigrations();
      const done = new Set(applied.map((a) => a.version));
      for (const m of all) log(`${done.has(m.version) ? 'applied' : 'PENDING'}  ${m.file}`);
      log(`${applied.length}/${all.length} applied`);
      break;
    }

    default:
      console.error(`unknown command: ${command}`);
      process.exitCode = 2;
  }
} finally {
  await client.end();
}
