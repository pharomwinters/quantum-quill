// Intentional divergences between types.yaml and the live schema.
//
// Two rules govern this file:
//
//   1. An exemption that no longer matches anything FAILS the cross-check. A
//      stale exemption is how a register turns into a place to hide things.
//   2. Adding one is a schema conversation, not a fix. If a column has no
//      field, the usual answer is that the field is missing from types.yaml.
//
// Structural columns are NOT exemptions and are not listed here — they are
// excluded by rule, because the introspection can tell them apart:
//
//   * generated columns (`*_vocab`), identified by attgenerated
//   * `id` and the pinned `type` discriminator on subtype tables
//   * infrastructure tables, which have no core type by construction
//
// It is currently empty, which is the intended steady state.

export type Exemption = {
  table: string;
  column: string;
  reason: string;
  raised: string;
};

export const EXEMPTIONS: readonly Exemption[] = [];
