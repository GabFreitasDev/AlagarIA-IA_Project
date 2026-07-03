from __future__ import annotations

import math
from typing import Any

import httpx
from fastapi import HTTPException

from app.config import get_settings
from app.schemas import RainStation, RainSummary


LAYER_BY_HOURS = {
    1: 0,
    3: 1,
    6: 2,
    12: 3,
    24: 4,
    48: 5,
    72: 6,
}

RECIFE_BBOX = {
    "min_lat": -8.20,
    "max_lat": -7.90,
    "min_lon": -35.05,
    "max_lon": -34.80,
}

CITY_FIELD_CANDIDATES = [
    "municipio",
    "município",
    "cidade",
    "city",
    "nome_municipio",
    "nm_municipio",
    "nome_mun",
    "nm_mun",
]

STATION_FIELD_CANDIDATES = [
    "posto",
    "estacao",
    "estação",
    "nome",
    "nome_posto",
    "nome_estacao",
    "nome_estação",
]

RAINFALL_FIELD_HINTS = [
    "chuva",
    "precipitacao",
    "precipitação",
    "acumulado",
    "valor",
    "mm",
]

IGNORED_NUMERIC_FIELD_HINTS = [
    "objectid",
    "id",
    "codigo",
    "código",
    "cod",
    "data",
    "date",
    "hora",
    "time",
    "latitude",
    "longitude",
    "lat",
    "lon",
    "x",
    "y",
]


async def fetch_apac_layer(hours: int) -> dict[str, Any]:
    if hours not in LAYER_BY_HOURS:
        raise HTTPException(
            status_code=400,
            detail=f"Intervalo inválido. Use um destes: {list(LAYER_BY_HOURS.keys())}",
        )

    settings = get_settings()
    layer_id = LAYER_BY_HOURS[hours]
    url = f"{settings.apac_base_url}/{layer_id}/query"

    params = {
        "f": "json",
        "where": "1=1",
        "outFields": "*",
        "returnGeometry": "true",
        "resultRecordCount": 1000,
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Erro ao consultar dados da APAC: {exc}",
        ) from exc

    if "error" in payload:
        raise HTTPException(
            status_code=502,
            detail=f"APAC retornou erro: {payload['error']}",
        )

    return payload


def _normalize_key(key: str) -> str:
    return key.strip().lower()


def _get_first_matching_attr(attributes: dict[str, Any], candidates: list[str]) -> Any:
    normalized = {_normalize_key(k): v for k, v in attributes.items()}
    for candidate in candidates:
        value = normalized.get(_normalize_key(candidate))
        if value not in (None, ""):
            return value
    return None


def _extract_coordinates(feature: dict[str, Any]) -> tuple[float | None, float | None]:
    geometry = feature.get("geometry") or {}
    x = geometry.get("x")
    y = geometry.get("y")

    if isinstance(x, (int, float)) and isinstance(y, (int, float)):
        return float(y), float(x)

    attributes = feature.get("attributes") or {}
    lat = _get_first_matching_attr(attributes, ["latitude", "lat"])
    lon = _get_first_matching_attr(attributes, ["longitude", "lon", "lng"])

    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
        return float(lat), float(lon)

    return None, None


def _is_inside_recife_bbox(latitude: float | None, longitude: float | None) -> bool:
    if latitude is None or longitude is None:
        return False

    return (
        RECIFE_BBOX["min_lat"] <= latitude <= RECIFE_BBOX["max_lat"]
        and RECIFE_BBOX["min_lon"] <= longitude <= RECIFE_BBOX["max_lon"]
    )


def _is_recife_feature(feature: dict[str, Any], city: str) -> bool:
    attributes = feature.get("attributes") or {}
    city_value = _get_first_matching_attr(attributes, CITY_FIELD_CANDIDATES)

    if isinstance(city_value, str) and city.lower() in city_value.lower():
        return True

    latitude, longitude = _extract_coordinates(feature)
    if city.lower() == "recife":
        return _is_inside_recife_bbox(latitude, longitude)

    return False


def _extract_rainfall_mm(attributes: dict[str, Any]) -> float | None:
    numeric_values: list[tuple[str, float]] = []

    for key, value in attributes.items():
        if isinstance(value, bool):
            continue

        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            normalized_key = _normalize_key(key)
            numeric_values.append((normalized_key, float(value)))

    if not numeric_values:
        return None

    hinted_values = [
        value
        for key, value in numeric_values
        if any(hint in key for hint in RAINFALL_FIELD_HINTS)
    ]

    if hinted_values:
        return max(hinted_values)

    filtered_values = [
        value
        for key, value in numeric_values
        if not any(hint in key for hint in IGNORED_NUMERIC_FIELD_HINTS)
    ]

    if filtered_values:
        return max(filtered_values)

    return None


def _feature_to_station(feature: dict[str, Any]) -> RainStation:
    attributes = feature.get("attributes") or {}
    latitude, longitude = _extract_coordinates(feature)

    return RainStation(
        station_name=_get_first_matching_attr(attributes, STATION_FIELD_CANDIDATES),
        city=_get_first_matching_attr(attributes, CITY_FIELD_CANDIDATES),
        latitude=latitude,
        longitude=longitude,
        rainfall_mm=_extract_rainfall_mm(attributes),
        raw_attributes=attributes,
    )


def parse_rain_summary(payload: dict[str, Any], hours: int, city: str = "Recife") -> RainSummary:
    features = payload.get("features") or []

    city_features = [feature for feature in features if _is_recife_feature(feature, city)]

    if not city_features:
        city_features = features

    stations = [_feature_to_station(feature) for feature in city_features]
    rainfall_values = [station.rainfall_mm for station in stations if station.rainfall_mm is not None]

    max_rainfall = max(rainfall_values) if rainfall_values else 0.0
    avg_rainfall = sum(rainfall_values) / len(rainfall_values) if rainfall_values else None

    return RainSummary(
        city=city,
        accumulated_hours=hours,
        max_rainfall_mm=round(float(max_rainfall), 2),
        avg_rainfall_mm=round(float(avg_rainfall), 2) if avg_rainfall is not None else None,
        stations_count=len(stations),
        stations=stations,
    )


async def get_rain_summary(hours: int, city: str = "Recife") -> RainSummary:
    payload = await fetch_apac_layer(hours)
    return parse_rain_summary(payload=payload, hours=hours, city=city)


async def get_rain_by_intervals(city: str = "Recife", intervals: list[int] | None = None) -> dict[str, RainSummary]:
    intervals = intervals or [1, 3, 6, 12, 24, 48, 72]
    summaries: dict[str, RainSummary] = {}

    for hours in intervals:
        summaries[f"{hours}h"] = await get_rain_summary(hours=hours, city=city)

    return summaries
