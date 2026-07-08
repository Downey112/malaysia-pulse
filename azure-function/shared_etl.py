"""
Same logic as etl/fetch_data.py, packaged so the Azure Function's
ETLTimerTrigger can import it directly. Kept in sync manually for now —
for a v2 of this project, pull this into a shared installable package.
"""

import os
import time
from datetime import date, datetime
from typing import Any

import psycopg2
import psycopg2.extras
import requests

BASE_URL = "https://api.data.gov.my/data-catalogue"
PAGE_SIZE = 1000
REQUEST_TIMEOUT = 30
REQUEST_PAUSE_SECONDS = 0.3

DATASET_CONFIG: dict[str, dict[str, Any]] = {
    "cpi_state": {"date_field": "date", "state_field": "state"},
    "cpi_state_inflation": {"date_field": "date", "state_field": "state"},
    "fuelprice": {"date_field": "date", "state_field": None},
    "lfs_qtr_state": {"date_field": "date", "state_field": "state"},
}

NON_METRIC_KEYS = {"date", "state"}


def fetch_all_rows(dataset_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        url = f"{BASE_URL}?id={dataset_id}&limit={PAGE_SIZE}&offset={offset}"
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        page = resp.json()
        if not page:
            break
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
        time.sleep(REQUEST_PAUSE_SECONDS)
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


def rows_to_facts(dataset_id, raw_rows, date_field, state_field):
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


def upsert_facts(conn, facts):
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


def run_etl() -> str:
    database_url = os.environ["DATABASE_URL"]  # set as an Azure Function App setting
    conn = psycopg2.connect(database_url)
    total = 0
    summary_lines = []

    for dataset_id, cfg in DATASET_CONFIG.items():
        raw_rows = fetch_all_rows(dataset_id)
        facts = rows_to_facts(dataset_id, raw_rows, cfg["date_field"], cfg["state_field"])
        upsert_facts(conn, facts)
        total += len(facts)
        summary_lines.append(f"{dataset_id}: {len(raw_rows)} raw rows -> {len(facts)} facts")

    conn.close()
    summary = f"Upserted {total} fact rows.\n" + "\n".join(summary_lines)
    return summary
