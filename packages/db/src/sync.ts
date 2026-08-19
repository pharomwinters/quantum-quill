// Seeds `vocabulary` and `link_field` from types.yaml.
//
// Not a migration, deliberately. Adding a doc_type has to stay a one-line edit
// to the YAML; a migration per vocabulary value would make that false. A new
// VOCABULARY still needs a migration, because it needs a column and a foreign
// key — which is correct, since that is a schema change.

import { buildModel, type Model } from '@quantum-quill/schema';
import type { Client } from 'pg';

export type SyncReport = {
  vocabulary: { inserted: number; extra: string[] };
  linkFields: { written: number; extra: string[] };
  pruned: number;
};

export async function sync(
  client: Client,
  options: { model?: Model; prune?: boolean } = {},
): Promise<SyncReport> {
  const model = options.model ?? buildModel();

  const values = [...model.vocabularies].flatMap(([name, list]) =>
    list.map((value) => ({ name, value })),
  );
  const inserted = await client.query(
    `INSERT INTO vocabulary (name, value)
     SELECT * FROM unnest($1::text[], $2::text[])
     ON CONFLICT DO NOTHING`,
    [values.map((v) => v.name), values.map((v) => v.value)],
  );

  const rows = model.linkFieldRows;
  const written = await client.query(
    `INSERT INTO link_field (source_type, field, target_type, multi, inverse)
     SELECT * FROM unnest($1::text[], $2::text[], $3::text[], $4::boolean[], $5::text[])
     ON CONFLICT (source_type, field, target_type)
     DO UPDATE SET multi = excluded.multi, inverse = excluded.inverse`,
    [
      rows.map((r) => r.sourceType),
      rows.map((r) => r.field),
      rows.map((r) => r.targetType),
      rows.map((r) => r.multi),
      rows.map((r) => r.inverse),
    ],
  );

  const declared = new Set(values.map((v) => `${v.name}\t${v.value}`));
  const live = await client.query<{ name: string; value: string }>(
    'SELECT name, value FROM vocabulary',
  );
  const extraValues = live.rows
    .filter((r) => !declared.has(`${r.name}\t${r.value}`))
    .map((r) => `${r.name}\t${r.value}`);

  const declaredLinks = new Set(rows.map((r) => `${r.sourceType}\t${r.field}\t${r.targetType}`));
  const liveLinks = await client.query<{ source_type: string; field: string; target_type: string }>(
    'SELECT source_type, field, target_type FROM link_field',
  );
  const extraLinks = liveLinks.rows
    .filter((r) => !declaredLinks.has(`${r.source_type}\t${r.field}\t${r.target_type}`))
    .map((r) => `${r.source_type}\t${r.field}\t${r.target_type}`);

  // Deleting a value something still references is refused by the foreign key,
  // which is the correct answer: that is a data migration, not a sync.
  let pruned = 0;
  if (options.prune === true) {
    for (const entry of extraValues) {
      const [name, value] = entry.split('\t');
      const result = await client.query('DELETE FROM vocabulary WHERE name = $1 AND value = $2', [
        name,
        value,
      ]);
      pruned += result.rowCount ?? 0;
    }
    for (const entry of extraLinks) {
      const [source, field, target] = entry.split('\t');
      const result = await client.query(
        'DELETE FROM link_field WHERE source_type = $1 AND field = $2 AND target_type = $3',
        [source, field, target],
      );
      pruned += result.rowCount ?? 0;
    }
  }

  return {
    vocabulary: { inserted: inserted.rowCount ?? 0, extra: extraValues },
    linkFields: { written: written.rowCount ?? 0, extra: extraLinks },
    pruned,
  };
}
