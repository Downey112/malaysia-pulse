import logging
import sys
import os

import azure.functions as func

# Make shared_etl.py (one level up) importable
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared_etl import run_etl  # noqa: E402


def main(mytimer: func.TimerRequest) -> None:
    if mytimer.past_due:
        logging.warning("Timer trigger is running late.")

    logging.info("Malaysia Pulse ETL run starting.")
    try:
        summary = run_etl()
        logging.info(summary)
    except Exception:
        logging.exception("ETL run failed.")
        raise
