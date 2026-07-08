from datetime import date

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from database import get_cursor
from schemas import IndicatorPoint, LatestIndicator, StateComparisonPoint, StateOut

app = FastAPI(
    title="Malaysia Pulse API",
    description="State-level CPI, fuel price, and labour force indicators for Malaysia.",
    version="0.1.0",
)

# Tighten this to your deployed frontend origin before going to production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/states", response_model=list[StateOut])
def list_states():
    with get_cursor() as cur:
        cur.execute("SELECT state_code, state_name FROM dim_state ORDER BY state_name")
        return cur.fetchall()


@app.get("/datasets")
def list_datasets():
    with get_cursor() as cur:
        cur.execute("SELECT DISTINCT dataset_id FROM fact_indicator ORDER BY dataset_id")
        return [row["dataset_id"] for row in cur.fetchall()]


@app.get("/metrics")
def list_metrics(dataset_id: str = Query(...)):
    with get_cursor() as cur:
        cur.execute(
            "SELECT DISTINCT metric FROM fact_indicator WHERE dataset_id = %s ORDER BY metric",
            (dataset_id,),
        )
        return [row["metric"] for row in cur.fetchall()]


@app.get("/indicators", response_model=list[IndicatorPoint])
def get_indicators(
    dataset_id: str = Query(...),
    metric: str = Query(...),
    state_code: str = Query("malaysia"),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
):
    """Time series for one metric in one state, with prev-period value for
    computing month-over-month / quarter-over-quarter change client-side."""
    conditions = ["dataset_id = %s", "metric = %s", "state_code = %s"]
    params: list = [dataset_id, metric, state_code]

    if date_from:
        conditions.append("obs_date >= %s")
        params.append(date_from)
    if date_to:
        conditions.append("obs_date <= %s")
        params.append(date_to)

    sql = f"""
        SELECT state_code, obs_date, metric, value, prev_value, prev_date
        FROM v_indicator_timeseries
        WHERE {' AND '.join(conditions)}
        ORDER BY obs_date
    """
    with get_cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="No data for that dataset/metric/state combination")
    return rows


@app.get("/latest", response_model=list[LatestIndicator])
def get_latest(dataset_id: str | None = Query(None), state_code: str | None = Query(None)):
    conditions, params = [], []
    if dataset_id:
        conditions.append("dataset_id = %s")
        params.append(dataset_id)
    if state_code:
        conditions.append("state_code = %s")
        params.append(state_code)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT * FROM v_latest_indicator {where_clause} ORDER BY dataset_id, state_code, metric"

    with get_cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


@app.get("/compare", response_model=list[StateComparisonPoint])
def compare_states(dataset_id: str = Query(...), metric: str = Query(...)):
    """Latest value of a metric across every state — powers the state
    comparison view on the dashboard."""
    sql = """
        SELECT v.state_code, d.state_name, v.value, v.obs_date
        FROM v_latest_indicator v
        JOIN dim_state d ON d.state_code = v.state_code
        WHERE v.dataset_id = %s AND v.metric = %s AND v.state_code != 'malaysia'
        ORDER BY v.value DESC NULLS LAST
    """
    with get_cursor() as cur:
        cur.execute(sql, (dataset_id, metric))
        rows = cur.fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="No data for that dataset/metric combination")
    return rows
