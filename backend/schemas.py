from datetime import date

from pydantic import BaseModel


class StateOut(BaseModel):
    state_code: str
    state_name: str


class IndicatorPoint(BaseModel):
    state_code: str
    obs_date: date
    metric: str
    value: float | None
    prev_value: float | None = None
    prev_date: date | None = None


class LatestIndicator(BaseModel):
    dataset_id: str
    state_code: str
    metric: str
    obs_date: date
    value: float | None
    unit: str | None = None


class StateComparisonPoint(BaseModel):
    state_code: str
    state_name: str
    value: float | None
    obs_date: date | None
