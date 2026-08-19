// The derived model: what types.yaml says the database must look like.
//
// Nothing here talks to Postgres. The cross-check compares this model against
// a live schema; these tests compare it against Folder-layout.yaml and against
// types.yaml's own declared contracts. Both directions of drift are caught
// because both sides are derived independently and then set-compared.

import {
  isLink,
  loadLayout,
  loadTypes,
  targets,
  valueAdds,
  valueId,
  type FieldSpec,
  type Layout,
  type Types,
} from './load.ts';

/**
 * Field type to SQL type. Kept as data rather than as a switch buried in the
 * cross-check, so there is one place to argue with when a mapping is wrong.
 *
 * `money` and `link` are absent deliberately: money is two columns and a link
 * is a row, so neither is a single mapping. `slug` is `text` plus the id CHECK.
 */
export const SQL_TYPE: Readonly<Record<string, string>> = Object.freeze({
  slug: 'text',
  text: 'text',
  longtext: 'text',
  date: 'date',
  datetime: 'timestamptz',
  number: 'numeric',
  bool: 'boolean',
  enum: 'text',
  file: 'text',
  folder: 'text',
});

export type Column = {
  table: string;
  name: string;
  sqlType: string;
  notNull: boolean;
  /** The declared field this column comes from. `money` yields two. */
  field: string;
  /** Set when the column is an enum: the vocabulary its FK points at. */
  vocabulary?: string;
  unique?: boolean;
  /** Set for subtype `adds`: the subtype values that may carry this column. */
  guard?: { field: string; values: string[] };
};

export type Junction = {
  /** Multi-valued closed vocabularies: an array cannot carry a foreign key. */
  name: string;
  table: string;
  field: string;
  vocabulary: string;
};

export type Table = { name: string; type: string; columns: Column[] };

export type LinkField = {
  sourceType: string;
  field: string;
  targets: string[];
  multi: boolean;
  inverse: string;
  required: boolean;
  /** Set when the link is declared by a subtype value rather than by the type. */
  guard?: { field: string; value: string };
};

export type RoutingKey = { key: string; type: string; via: 'subtype' | 'type' };

export type Model = {
  types: Types;
  layout: Layout;
  coreTypes: string[];
  /** Vocabulary name to its closed value list. */
  vocabularies: Map<string, string[]>;
  /** One table per core type, plus `record` for the universal fields. */
  tables: Map<string, Table>;
  junctions: Junction[];
  linkFields: LinkField[];
  /** Every link field expanded across its declared targets — the `link_field` rows. */
  linkFieldRows: Array<{ sourceType: string; field: string; targetType: string; multi: boolean; inverse: string }>;
  /** Inverse names a target type receives, derived from what fields declare. */
  inversesByTarget: Map<string, Set<string>>;
  /** Subtype value (or type id) to the type that routes on it. */
  routingKeys: RoutingKey[];
  /** Routing key to the categories in Folder-layout.yaml claiming it. */
  layoutClaims: Map<string, string[]>;
};

const LIST = /^list\[(.+)\]$/;

/**
 * Core type ids are kebab-case slugs; SQL identifiers are not. One rule, not a
 * lookup table, and it touches exactly one type today (`world-entry`).
 */
export function tableName(typeId: string): string {
  return typeId.replaceAll('-', '_');
}

function elementOf(type: string): string | null {
  const m = LIST.exec(type);
  return m?.[1] ?? null;
}

function columnsFor(
  table: string,
  fields: readonly FieldSpec[],
  guard?: { field: string; values: string[] },
): { columns: Column[]; junctions: Junction[] } {
  const columns: Column[] = [];
  const junctions: Junction[] = [];

  for (const f of fields) {
    if (isLink(f)) {
      // Links are rows in `link`. A union of link|text keeps a text column for
      // the half that is not a link yet — see person.organization.
      if (Array.isArray(f.type) && f.type.includes('text')) {
        columns.push({
          table,
          name: `${f.key}_text`,
          sqlType: 'text',
          notNull: false,
          field: f.key,
          ...(guard ? { guard } : {}),
        });
      }
      continue;
    }

    const type = f.type as string;
    const notNull = f.required === true;
    const element = elementOf(type);

    if (element === 'enum') {
      junctions.push({
        name: `${table}_${f.key}`,
        table,
        field: f.key,
        vocabulary: required(f.of, `${table}.${f.key} is an enum with no of:`),
      });
      continue;
    }

    if (element !== null) {
      columns.push({
        table,
        name: f.key,
        sqlType: `${required(SQL_TYPE[element], `no SQL type for ${element}`)}[]`,
        notNull,
        field: f.key,
        ...(guard ? { guard } : {}),
      });
      continue;
    }

    if (type === 'money') {
      // "Decimal amount plus a currency code" is two values, paired by CHECK.
      // The amount keeps the field's own name — `gross`, not `gross_amount` —
      // so the common column reads as the field and only the currency is a suffix.
      for (const [name, sql] of [[f.key, 'numeric(14,2)'], [`${f.key}_currency`, 'char(3)']] as const) {
        columns.push({ table, name, sqlType: sql, notNull, field: f.key, ...(guard ? { guard } : {}) });
      }
      continue;
    }

    columns.push({
      table,
      name: f.key,
      sqlType: required(SQL_TYPE[type], `no SQL type for ${type} (${table}.${f.key})`),
      notNull,
      field: f.key,
      ...(type === 'enum' ? { vocabulary: required(f.of, `${table}.${f.key} is an enum with no of:`) } : {}),
      ...(f.unique ? { unique: true } : {}),
      ...(guard ? { guard } : {}),
    });
  }

  return { columns, junctions };
}

function required<T>(v: T | undefined, message: string): T {
  if (v === undefined) throw new Error(message);
  return v;
}

export function buildModel(types = loadTypes(), layout = loadLayout()): Model {
  const coreTypes = types.types.map((t) => t.id);

  const vocabularies = new Map<string, string[]>();
  for (const [name, spec] of Object.entries(types.vocabularies)) {
    vocabularies.set(name, spec.values.map(valueId));
  }

  const tables = new Map<string, Table>();
  const junctions: Junction[] = [];
  const linkFields: LinkField[] = [];
  const inversesByTarget = new Map<string, Set<string>>();

  const collectLinks = (
    sourceType: string,
    fields: readonly FieldSpec[],
    guard?: { field: string; value: string },
  ): void => {
    for (const f of fields) {
      if (!isLink(f)) continue;
      const to = targets(f);
      linkFields.push({
        sourceType,
        field: f.key,
        targets: to,
        multi: f.type === 'list[link]',
        inverse: required(f.inverse, `link ${sourceType}.${f.key} declares no inverse`),
        required: f.required === true,
        ...(guard ? { guard } : {}),
      });
      for (const target of to) {
        let names = inversesByTarget.get(target);
        if (names === undefined) inversesByTarget.set(target, (names = new Set()));
        names.add(f.inverse as string);
      }
    }
  };

  // `record` carries the universal fields; one table per core type carries the rest.
  const universal = columnsFor('record', types.universal);
  tables.set('record', { name: 'record', type: '*', columns: universal.columns });
  junctions.push(...universal.junctions);
  collectLinks('*', types.universal);

  for (const t of types.types) {
    const built = columnsFor(tableName(t.id), t.fields ?? []);
    tables.set(t.id, { name: tableName(t.id), type: t.id, columns: built.columns });
    junctions.push(...built.junctions);
    collectLinks(t.id, t.fields ?? []);
  }

  // Subtype `adds` land on the parent's table, guarded by the values that declare them.
  // A field added by more than one value — `tax_year` on both w2 and tax-return —
  // is ONE column whose guard names every value, not two columns.
  for (const [name, spec] of Object.entries(types.vocabularies)) {
    const parent = spec.parent;
    if (parent === undefined) continue;
    const table = required(tables.get(parent), `vocabulary ${name} has unknown parent ${parent}`);
    const parentTable = table.name;

    const declaredBy = new Map<string, { field: FieldSpec; values: string[] }>();
    for (const value of spec.values) {
      for (const f of valueAdds(value)) {
        const seen = declaredBy.get(f.key);
        if (seen === undefined) declaredBy.set(f.key, { field: f, values: [valueId(value)] });
        else seen.values.push(valueId(value));
      }
      collectLinks(parent, valueAdds(value), { field: name, value: valueId(value) });
    }

    for (const { field, values } of declaredBy.values()) {
      const built = columnsFor(parentTable, [{ ...field, required: false }], { field: name, values });
      table.columns.push(...built.columns);
      junctions.push(...built.junctions);
    }
  }

  const linkFieldRows = linkFields.flatMap((lf) => {
    const sources = lf.sourceType === '*' ? coreTypes : [lf.sourceType];
    const expanded = lf.targets.flatMap((t) => (t === '*' ? coreTypes : [t]));
    return sources.flatMap((sourceType) =>
      expanded.map((targetType) => ({
        sourceType,
        field: lf.field,
        targetType,
        multi: lf.multi,
        inverse: lf.inverse,
      })),
    );
  });

  // Routing: a subtype value, or a type id where there is no subtype. Three
  // types route on something else entirely and declare it under routing.explicit.
  const derived = new Set(types.routing.derived_from_layout.types);
  const routingKeys: RoutingKey[] = [];
  for (const t of types.types) {
    if (!derived.has(t.id)) continue;
    if (t.subtype === null) {
      routingKeys.push({ key: t.id, type: t.id, via: 'type' });
      continue;
    }
    const values = required(vocabularies.get(t.subtype), `${t.id} has unknown subtype ${t.subtype}`);
    for (const key of values) routingKeys.push({ key, type: t.id, via: 'subtype' });
  }

  const layoutClaims = new Map<string, string[]>();
  for (const area of layout.areas) {
    for (const category of area.categories ?? []) {
      for (const key of category.types ?? []) {
        const claims = layoutClaims.get(key);
        if (claims === undefined) layoutClaims.set(key, [`${category.jd} ${category.id}`]);
        else claims.push(`${category.jd} ${category.id}`);
      }
    }
  }

  return {
    types,
    layout,
    coreTypes,
    vocabularies,
    tables,
    junctions,
    linkFields,
    linkFieldRows,
    inversesByTarget,
    routingKeys,
    layoutClaims,
  };
}
