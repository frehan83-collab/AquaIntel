-- TimescaleDB bootstrap for AquaIntel production.
--
-- Creates the extension. Hypertable conversion is deliberately NOT automated
-- here: it requires a real time column per table and a correct chunk interval,
-- and a wrong conversion silently degrades query plans. The current state is
-- reported by `python scripts/verify_production_truth.py` (extension present,
-- N hypertables) so "not yet converted" is a visible gap, never a false claim.
--
-- To convert a table once it has a proper timestamp column, e.g.:
--   SELECT create_hypertable('lice_records', 'fetched_at',
--          chunk_time_interval => INTERVAL '30 days',
--          migrate_data => true);
--   SELECT add_retention_policy('lice_records', INTERVAL '5 years');

CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Helpful for the freshness queries in core/market/freshness_monitor.py.
CREATE INDEX IF NOT EXISTS ix_lice_records_fetched_at ON lice_records (fetched_at);
CREATE INDEX IF NOT EXISTS ix_chlorophyll_fetched_at ON chlorophyll_readings (fetched_at);
