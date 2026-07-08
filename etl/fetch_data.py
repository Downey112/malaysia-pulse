"""
Malaysia Pulse — ETL script.

Pulls state-level CPI, CPI inflation, fuel price, and quarterly labour force
data from the official data.gov.my Open API and upserts it into Postgres
using the long-format schema in schema.sql.

IMPORTANT: run explore_api.py first and check the printed field names
against DATE_FIELD / STATE_FIELD below before trusting this on new datasets.
The data.gov.my API is public and needs no auth key.

Usage:
    pip install -r requirements.txt
    export DATABASE_URL="postgresql://user:password@host:5432/dbname"
    python fetch_data.py
"""

import os
import sys
import time
from datetime import date, datetime
from typing import Any

import psycopg2
import psycopg2.extras
import requests

BASE_URL = "https://api.data.gov.my/data-catalogue"
REQUEST_TIMEOUT = 30

# Per-dataset config. `date_field` and `state_field` come from running
# explore_api.py first. `state_field=None` means the dataset is
# national-level only (we tag it as state_code='malaysia').
DATASET_CONFIG: dict[str, dict[str, Any]] = {
    "cpi_state": {"date_field": "date", "state_field": "state"},
    "cpi_state_inflation": {"date_field": "date", "state_field": "state"},
    "fuelprice": {"date_field": "date", "state_field": None},
    "lfs_qtr_state": {"date_field": "date", "state_field": "state"},
}

# Columns that are dimensions/metadata, never metrics, even though some
# (like 'division') are strings that get folded into the metric name.
NON_METRIC_KEYS = {"date", "state"}


MAX_RETRIES = 4
SINGLE_REQUEST_LIMIT = 200_000  # generously above any single dataset's real row count


def fetch_all_rows(dataset_id: str) -> list[dict[str, Any]]:
    """
    Fetch a dataset in one request with a large `limit`.

    IMPORTANT: api.data.gov.my's documented API only supports `id` and `limit`
    as query parameters — there is no documented `offset`/page parameter. An
    earlier version of this script assumed standard offset pagination, which
    was never actually supported by this API: sending an unrecognized offset
    value gets silently ignored, so a naive "keep incrementing offset" loop
    just re-fetches the same data forever and never terminates. Don't
    reintroduce offset-based looping here without first confirming (by
    testing directly against the API) that it's actually supported.
    """
    url = f"{BASE_URL}?id={dataset_id}&limit={SINGLE_REQUEST_LIMIT}"

    rows = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            rows = resp.json()
            break
        except requests.RequestException as e:
            wait = min(2 ** attempt, 15)  # capped backoff: 2s,4s,8s,15s
            print(
                f"    ...attempt {attempt}/{MAX_RETRIES} failed ({e}); retrying in {wait}s",
                flush=True,
            )
            if attempt == MAX_RETRIES:
                raise
            time.sleep(wait)

    rows = rows or []
    print(f"    ...fetched {len(rows)} rows in a single request", flush=True)

    if len(rows) == SINGLE_REQUEST_LIMIT:
        print(
            f"    WARNING: row count exactly equals SINGLE_REQUEST_LIMIT "
            f"({SINGLE_REQUEST_LIMIT}) — this dataset may be larger than expected "
            f"and truncated. Increase SINGLE_REQUEST_LIMIT and re-run, or confirm "
            f"the real total row count some other way before trusting this data.",
            flush=True,
        )

    return rows


def parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(str(value), fmt).date()
        except ValueError:
            continue
    return None


def normalize_state(raw: str) -> str:
    return raw.strip().lower().replace(" ", "_")


def rows_to_facts(
    dataset_id: str, raw_rows: list[dict[str, Any]], date_field: str, state_field: str | None
) -> list[tuple]:
    """
    Flatten each raw row into one or more (dataset_id, state_code, obs_date,
    metric, value, unit) tuples. Any string columns besides date/state are
    treated as dimension tags and folded into the metric name (e.g. a
    'division' column with value 'food' turns numeric column 'index' into
    metric 'index_food'). Any numeric columns become their own metric row.
    """
    facts = []
    for row in raw_rows:
        obs_date = parse_date(row.get(date_field))
        if obs_date is None:
            continue

        state_code = normalize_state(row[state_field]) if state_field and row.get(state_field) else "malaysia"

        dimension_tags = []
        numeric_cols = {}
        for key, value in row.items():
            if key in NON_METRIC_KEYS or key == date_field or key == state_field:
                continue
            if isinstance(value, (int, float)) and value is not None:
                numeric_cols[key] = value
            elif isinstance(value, str) and value:
                dimension_tags.append(normalize_state(value))

        suffix = ("_" + "_".join(dimension_tags)) if dimension_tags else ""
        for metric_name, value in numeric_cols.items():
            facts.append((dataset_id, state_code, obs_date, f"{metric_name}{suffix}", value, None))

    return facts


def upsert_facts(conn, facts: list[tuple]) -> None:
    if not facts:
        return
    sql = """
        INSERT INTO fact_indicator (dataset_id, state_code, obs_date, metric, value, unit)
        VALUES %s
        ON CONFLICT (dataset_id, state_code, obs_date, metric)
        DO UPDATE SET value = EXCLUDED.value, loaded_at = now()
    """
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(cur, sql, facts, page_size=500)
    conn.commit()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        choices=list(DATASET_CONFIG.keys()),
        help="Run only this dataset (recommended when invoking via an agent/CLI wrapper, "
        "so each call finishes quickly instead of one long run covering all four).",
    )
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        sys.exit("Set DATABASE_URL before running, e.g.\n"
                  "  export DATABASE_URL='postgresql://user:pass@host:5432/dbname'")

    datasets_to_run = {args.dataset: DATASET_CONFIG[args.dataset]} if args.dataset else DATASET_CONFIG

    conn = psycopg2.connect(database_url)
    total_facts = 0

    for dataset_id, cfg in datasets_to_run.items():
        print(f"Fetching {dataset_id} ...", flush=True)
        raw_rows = fetch_all_rows(dataset_id)
        print(f"  {len(raw_rows)} raw rows", flush=True)

        facts = rows_to_facts(dataset_id, raw_rows, cfg["date_field"], cfg["state_field"])
        print(f"  {len(facts)} fact rows to upsert", flush=True)

        upsert_facts(conn, facts)
        total_facts += len(facts)
        print(f"  upserted.\n", flush=True)

    conn.close()
    print(f"\nDone. {total_facts} fact rows upserted across {len(datasets_to_run)} dataset(s).", flush=True)


if __name__ == "__main__":
    main()
