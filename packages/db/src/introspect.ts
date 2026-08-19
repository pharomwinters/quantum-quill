// Reads the live schema back out of Postgres.
//
// Deliberately dumb: it reports what is there and interprets nothing. All the
// judgement lives in the cross-check, so that the thing being compared and the
// thing doing the comparing cannot quietly agree with each other.

import type { Client } from 'pg';

export type LiveColumn = {
  table: string;
  name: string;
  /** `format_type` output: text, date, timestamp with time zone, numeric(14,2)... */
  sqlType: string;
  notNull: boolean;
  generated: boolean;
  /** For generated columns: the expression, e.g. `'core_type'::text`. */
  generationExpression: string | null;
};

export type LiveCheck = { table: string; name: string; definition: string };
export type LiveForeignKey = { table: string; name: string; definition: string };
export type LiveIndex = { table: string; name: string; definition: string; columns: string[] };

export type LiveSchema = {
  tables: string[];
  columns: LiveColumn[];
  checks: LiveCheck[];
  foreignKeys: LiveForeignKey[];
  indexes: LiveIndex[];
  vocabulary: Array<{ name: string; value: string }>;
  linkFields: Array<{
    sourceType: string;
    field: string;
    targetType: string;
    multi: boolean;
    inverse: string;
  }>;
};

export async function introspect(client: Client): Promise<LiveSchema> {
  const tables = await client.query<{ table_name: string }>(
    `SELECT table_name FROM information_schema.tables
     WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
     ORDER BY table_name`,
  );

  const columns = await client.query<{
    table: string;
    name: string;
    sql_type: string;
    not_null: boolean;
    generated: boolean;
    generation_expression: string | null;
  }>(
    `SELECT c.relname                                   AS table,
            a.attname                                   AS name,
            format_type(a.atttypid, a.atttypmod)        AS sql_type,
            a.attnotnull                                AS not_null,
            a.attgenerated <> ''                        AS generated,
            pg_get_expr(d.adbin, d.adrelid)             AS generation_expression
       FROM pg_attribute a
       JOIN pg_class c     ON c.oid = a.attrelid
       JOIN pg_namespace n ON n.oid = c.relnamespace
       LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
      WHERE n.nspname = 'public' AND c.relkind = 'r'
        AND a.attnum > 0 AND NOT a.attisdropped
      ORDER BY c.relname, a.attnum`,
  );

  const constraints = await client.query<{
    table: string;
    name: string;
    kind: string;
    definition: string;
  }>(
    `SELECT c.relname AS table, con.conname AS name, con.contype AS kind,
            pg_get_constraintdef(con.oid) AS definition
       FROM pg_constraint con
       JOIN pg_class c     ON c.oid = con.conrelid
       JOIN pg_namespace n ON n.oid = c.relnamespace
      WHERE n.nspname = 'public' AND con.contype IN ('c', 'f')
      ORDER BY c.relname, con.conname`,
  );

  const indexes = await client.query<{
    table: string;
    name: string;
    definition: string;
    columns: string[];
  }>(
    `SELECT c.relname AS table, i.relname AS name,
            pg_get_indexdef(x.indexrelid) AS definition,
            array_remove(array_agg(a.attname ORDER BY a.attnum), NULL) AS columns
       FROM pg_index x
       JOIN pg_class c     ON c.oid = x.indrelid
       JOIN pg_class i     ON i.oid = x.indexrelid
       JOIN pg_namespace n ON n.oid = c.relnamespace
       LEFT JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = ANY (x.indkey)
      WHERE n.nspname = 'public'
      GROUP BY c.relname, i.relname, x.indexrelid
      ORDER BY c.relname, i.relname`,
  );

  const vocabulary = await client.query<{ name: string; value: string }>(
    'SELECT name, value FROM vocabulary ORDER BY name, value',
  );

  const linkFields = await client.query<{
    source_type: string;
    field: string;
    target_type: string;
    multi: boolean;
    inverse: string;
  }>('SELECT source_type, field, target_type, multi, inverse FROM link_field');

  return {
    tables: tables.rows.map((r) => r.table_name),
    columns: columns.rows.map((r) => ({
      table: r.table,
      name: r.name,
      sqlType: r.sql_type,
      notNull: r.not_null,
      generated: r.generated,
      generationExpression: r.generated ? r.generation_expression : null,
    })),
    checks: constraints.rows
      .filter((r) => r.kind === 'c')
      .map((r) => ({ table: r.table, name: r.name, definition: r.definition })),
    foreignKeys: constraints.rows
      .filter((r) => r.kind === 'f')
      .map((r) => ({ table: r.table, name: r.name, definition: r.definition })),
    indexes: indexes.rows.map((r) => ({
      table: r.table,
      name: r.name,
      definition: r.definition,
      columns: r.columns,
    })),
    vocabulary: vocabulary.rows,
    linkFields: linkFields.rows.map((r) => ({
      sourceType: r.source_type,
      field: r.field,
      targetType: r.target_type,
      multi: r.multi,
      inverse: r.inverse,
    })),
  };
}

/**
 * The model spells SQL types the way the DDL does; Postgres spells them its own
 * way. One alias map, here rather than in the schema package, because this is a
 * Postgres detail and not something types.yaml should know about.
 */
const ALIASES: Readonly<Record<string, string>> = Object.freeze({
  timestamptz: 'timestamp with time zone',
  'char(3)': 'character(3)',
  bool: 'boolean',
});

export function canonicalType(sqlType: string): string {
  return ALIASES[sqlType] ?? sqlType;
}

/** String literals inside a constraint or index definition, in order. */
export function literals(definition: string): string[] {
  return [...definition.matchAll(/'((?:[^']|'')*)'/g)].map((m) =>
    (m[1] as string).replaceAll("''", "'"),
  );
}
