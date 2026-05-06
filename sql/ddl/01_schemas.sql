-- Schema layout: `warehouse` for star schema, `staging` for landing CSVs.
-- Re-runnable: drop+create (the loader is idempotent so any state is recoverable).

DROP SCHEMA IF EXISTS warehouse CASCADE;
DROP SCHEMA IF EXISTS staging CASCADE;

CREATE SCHEMA warehouse;
CREATE SCHEMA staging;
