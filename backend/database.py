import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras


def get_database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    return url


@contextmanager
def get_cursor():
    """Yields a dict-cursor and commits/closes automatically."""
    conn = psycopg2.connect(get_database_url())
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield cur
        conn.commit()
    finally:
        conn.close()
