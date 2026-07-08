-- Malaysia Pulse — database schema
-- Design note: open government data sources change field names between
-- datasets (and sometimes between releases of the same dataset). Rather than
-- hardcoding one column per metric, this uses a "long" / tidy fact table:
-- one row per (dataset, state, date, metric, value). Wide views are built on
-- top for the API layer to query. This is a deliberate, common pattern for
-- multi-source pipelines — mention this reasoning in your README/interview,
-- it's a real design decision, not a shortcut.

CREATE TABLE IF NOT EXISTS dim_state (
    state_code   TEXT PRIMARY KEY,       -- e.g. 'selangor', 'w.p._kuala_lumpur'
    state_name   TEXT NOT NULL           -- display name
);

INSERT INTO dim_state (state_code, state_name) VALUES
    ('malaysia', 'Malaysia (national)'),
    ('johor', 'Johor'),
    ('kedah', 'Kedah'),
    ('kelantan', 'Kelantan'),
    ('melaka', 'Melaka'),
    ('negeri_sembilan', 'Negeri Sembilan'),
    ('pahang', 'Pahang'),
    ('pulau_pinang', 'Pulau Pinang'),
    ('perak', 'Perak'),
    ('perlis', 'Perlis'),
    ('selangor', 'Selangor'),
    ('terengganu', 'Terengganu'),
    ('sabah', 'Sabah'),
    ('sarawak', 'Sarawak'),
    ('w.p._kuala_lumpur', 'W.P. Kuala Lumpur'),
    ('w.p._labuan', 'W.P. Labuan'),
    ('w.p._putrajaya', 'W.P. Putrajaya')
ON CONFLICT (state_code) DO NOTHING;

CREATE TABLE IF NOT EXISTS fact_indicator (
    id           BIGSERIAL PRIMARY KEY,
    dataset_id   TEXT NOT NULL,          -- 'cpi_state', 'fuelprice', 'lfs_qtr_state', ...
    state_code   TEXT REFERENCES dim_state(state_code),
    obs_date     DATE NOT NULL,
    metric       TEXT NOT NULL,          -- e.g. 'index', 'ron95', 'u_rate'
    value        NUMERIC,
    unit         TEXT,                   -- e.g. 'MYR', 'percent', 'index_points'
    loaded_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (dataset_id, state_code, obs_date, metric)
);

CREATE INDEX IF NOT EXISTS idx_fact_indicator_lookup
    ON fact_indicator (dataset_id, state_code, obs_date);

CREATE INDEX IF NOT EXISTS idx_fact_indicator_metric
    ON fact_indicator (metric, obs_date);

-- Convenience view: latest value per (dataset, state, metric)
CREATE OR REPLACE VIEW v_latest_indicator AS
SELECT DISTINCT ON (dataset_id, state_code, metric)
    dataset_id, state_code, metric, obs_date, value, unit
FROM fact_indicator
ORDER BY dataset_id, state_code, metric, obs_date DESC;

-- Convenience view: month-over-month / year-over-year friendly time series
CREATE OR REPLACE VIEW v_indicator_timeseries AS
SELECT
    dataset_id,
    state_code,
    metric,
    obs_date,
    value,
    LAG(value) OVER (
        PARTITION BY dataset_id, state_code, metric ORDER BY obs_date
    ) AS prev_value,
    LAG(obs_date) OVER (
        PARTITION BY dataset_id, state_code, metric ORDER BY obs_date
    ) AS prev_date
FROM fact_indicator;
