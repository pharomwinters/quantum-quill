-- The query contract's index classes, made real.
--
-- types.yaml -> query.indexes declares what MUST be fast. Anything omitted
-- there is a scan and may not be relied on, so this file is exactly as long as
-- that declaration and no longer.
--
-- The `folder` exact-class field has no column yet: it is derived, and whether
-- it is stored or computed is open_questions.folder-storage, for phase 4.

-- exact ---------------------------------------------------------------------
CREATE INDEX record_type_idx        ON record (type);
CREATE INDEX project_status_idx     ON project (status);
CREATE INDEX project_scope_idx      ON project (scope);
CREATE INDEX area_status_idx        ON area (status);
CREATE INDEX document_status_idx    ON document (status);
CREATE INDEX world_status_idx       ON world (status);
CREATE INDEX task_state_idx         ON task (state);
CREATE INDEX task_priority_idx      ON task (priority);

-- exact, subtypes: every closed vocabulary is exact-indexed. That is what
-- closing it buys.
CREATE INDEX document_doc_type_idx     ON document (doc_type);
CREATE INDEX resource_resource_type_idx ON resource (resource_type);
CREATE INDEX note_note_type_idx        ON note (note_type);
CREATE INDEX journal_period_idx        ON journal (period);
CREATE INDEX world_entry_entry_type_idx ON world_entry (entry_type);
CREATE INDEX system_system_type_idx    ON system (system_type);

-- range ---------------------------------------------------------------------
CREATE INDEX record_created_idx     ON record (created);
CREATE INDEX record_updated_idx     ON record (updated);
CREATE INDEX document_doc_date_idx  ON document (doc_date);
CREATE INDEX journal_date_idx       ON journal (date);
CREATE INDEX meeting_date_idx       ON meeting (date);
CREATE INDEX task_due_idx           ON task (due);
CREATE INDEX task_scheduled_idx     ON task (scheduled);
CREATE INDEX project_start_idx      ON project ("start");
CREATE INDEX project_end_idx        ON project ("end");
CREATE INDEX person_met_idx         ON person (met);
CREATE INDEX document_coverage_start_idx ON document (coverage_start);
CREATE INDEX document_coverage_end_idx   ON document (coverage_end);
CREATE INDEX document_expires_idx        ON document (expires);
CREATE INDEX document_valid_until_idx    ON document (valid_until);
CREATE INDEX journal_week_start_idx      ON journal (week_start);
CREATE INDEX journal_week_end_idx        ON journal (week_end);
CREATE INDEX document_filed_on_idx       ON document (filed_on);
CREATE INDEX document_tax_year_idx       ON document (tax_year);
CREATE INDEX document_amount_idx         ON document (amount);
CREATE INDEX document_gross_idx          ON document (gross);
CREATE INDEX document_net_idx            ON document (net);

-- text ----------------------------------------------------------------------
-- Full-text over title and body together, and a GIN index over tags.
--
-- The layout's `sensitive-not-scanned` rule says records in sensitive folders
-- are indexed by metadata alone and their bodies are never read. That cannot
-- be enforced here yet, because a record has no folder until routing exists —
-- see the note at the top of this file. Phase 4 owns it.
CREATE INDEX record_fulltext_idx ON record
  USING gin (to_tsvector('english', coalesce(title, '') || ' ' || body));
CREATE INDEX record_tags_idx ON record USING gin (tags);
