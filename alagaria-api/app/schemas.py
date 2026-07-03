from pydantic import BaseModel, Field
from typing import Any


class HealthResponse(BaseModel):
    status: str = "ok"
    app: str
    version: str


class RainStation(BaseModel):
    station_name: str | None = None
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    rainfall_mm: float | None = None
    raw_attributes: dict[str, Any] = Field(default_factory=dict)


class RainSummary(BaseModel):
    city: str
    accumulated_hours: int
    max_rainfall_mm: float
    avg_rainfall_mm: float | None = None
    stations_count: int
    stations: list[RainStation]
    source: str = "APAC Geoportal"


class RainByInterval(BaseModel):
    city: str
    intervals: dict[str, RainSummary]
    source: str = "APAC Geoportal"


class FloodRiskResponse(BaseModel):
    city: str
    flood_probability: float
    risk_level: str
    risk_score: int
    rain: dict[str, float]
    explanation: list[str]
    source: str = "APAC Geoportal"
    model: str = "rule_based_baseline_v1"
