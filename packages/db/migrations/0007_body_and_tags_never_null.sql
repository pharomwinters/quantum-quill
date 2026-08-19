-- `body` and `tags` are defaulted, and therefore never absent.
--
-- They were made nullable in 0002 because types.yaml declared neither
-- required, and the DDL is not where the schema gets edited. The schema had no
-- way to say "the author is never asked for this, and a record never lacks
-- it" — that is now `default:`, and this migration follows it.
--
-- An absent body and an empty body are the same thing. A column that can hold
-- both is storing a distinction that does not exist.

UPDATE record SET body = '' WHERE body IS NULL;
UPDATE record SET tags = '{}' WHERE tags IS NULL;

ALTER TABLE record ALTER COLUMN body SET NOT NULL;
ALTER TABLE record ALTER COLUMN tags SET NOT NULL;
