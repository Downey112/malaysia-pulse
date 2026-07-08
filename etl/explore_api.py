"""
Run this FIRST, before writing any schema or ETL logic.

Open data APIs rarely match their documentation exactly. This script hits
each dataset we plan to use and prints the raw JSON shape so you know the
real field names before you design tables around them.

Usage:
    pip install requests
    python explore_api.py
"""

import json
import requests

BASE_URL = "https://api.data.gov.my/data-catalogue"

# Datasets confirmed to exist on data.gov.my for this project.
# state-level CPI + inflation, weekly fuel prices, quarterly labour force by state.
DATASET_IDS = [
    "cpi_state",
    "cpi_state_inflation",
    "fuelprice",
    "lfs_qtr_state",
]


def explore(dataset_id: str, limit: int = 3) -> None:
    url = f"{BASE_URL}?id={dataset_id}&limit={limit}"
    print(f"\n{'=' * 60}\nDataset: {dataset_id}\nURL: {url}\n{'=' * 60}")
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"  Request failed: {e}")
        return

    if not data:
        print("  Empty response.")
        return

    print(f"  Records returned: {len(data)}")
    print("  Sample record:")
    print(json.dumps(data[0], indent=2, default=str))

    if len(data) > 1:
        keys_row0 = set(data[0].keys())
        keys_row1 = set(data[1].keys())
        if keys_row0 != keys_row1:
            print("  WARNING: field names differ between rows in the same response.")
            print(f"    Only in row 0: {keys_row0 - keys_row1}")
            print(f"    Only in row 1: {keys_row1 - keys_row0}")


if __name__ == "__main__":
    for ds_id in DATASET_IDS:
        explore(ds_id)

    print(
        "\nNext step: compare the printed field names against etl/schema.sql "
        "and etl/fetch_data.py, and adjust the METRIC_COLUMNS mapping in "
        "fetch_data.py if any names differ from what's assumed there."
    )
