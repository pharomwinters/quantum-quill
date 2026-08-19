-- A journal date identifies an entry only once you know which kind it is.
--
-- `journal.date` was UNIQUE outright, which made a Monday daily and a weekly
-- anchored on that same Monday mutually exclusive — every week of the year.
-- types.yaml now declares `unique_with: [period]`; this follows it.

ALTER TABLE journal DROP CONSTRAINT journal_date_key;
ALTER TABLE journal ADD CONSTRAINT journal_period_date_key UNIQUE (period, date);
