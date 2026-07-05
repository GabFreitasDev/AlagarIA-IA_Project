from __future__ import annotations

import json
import math
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app.config import get_settings
from app.schemas import GoldRiskSnapshot, NeighborhoodRisk


def _resolve_gold_path() -> Path:
    configured_path = Path(get_settings().gold_risk_json_path)

    if configured_path.is_absolute():
        return configured_path

    current_workdir_path = Path.cwd() / configured_path
    if current_workdir_path.exists():
        return current_workdir_path

    api_root = Path(__file__).resolve().parents[2]
    return api_root / configured_path


def _load_gold_records() -> tuple[list[dict[str, Any]], Path, str | None]:
    gold_path = _resolve_gold_path()

    if not gold_path.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                "JSON Gold de risco nao encontrado. Configure "
                "GOLD_RISK_JSON_PATH apontando para risco_bairros_atual.json."
            ),
        )

    try:
        raw_payload = json.loads(gold_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"JSON Gold invalido: {exc}",
        ) from exc

    if not isinstance(raw_payload, list):
        raise HTTPException(
            status_code=502,
            detail="JSON Gold invalido: esperado um array de bairros.",
        )

    records = [record for record in raw_payload if isinstance(record, dict)]
    source_updated_at = datetime.fromtimestamp(
        gold_path.stat().st_mtime,
        tz=timezone.utc,
    ).isoformat()

    return records, gold_path, source_updated_at


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(number):
        return None

    return number


def _to_int(value: Any) -> int | None:
    number = _to_float(value)
    if number is None:
        return None
    return int(number)


def _to_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _first_present(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return None


def _normalize_record(record: dict[str, Any]) -> NeighborhoodRisk:
    bairro = _to_str(_first_present(record, "Bairro", "bairro"))

    if not bairro:
        raise HTTPException(
            status_code=502,
            detail="JSON Gold invalido: registro sem campo Bairro.",
        )

    return NeighborhoodRisk(
        data=_to_str(record.get("data")),
        municipio=_to_str(record.get("municipio")) or "Recife",
        bairro=bairro,
        rpa=_to_int(_first_present(record, "RPA", "rpa")),
        elevacao_metros=_to_float(record.get("elevacao_metros")),
        precipitacao_atual=_to_float(_first_present(record, "precipitacao_atual", "precipitacao")),
        chuva_1h=_to_float(record.get("1_hora")),
        chuva_6h=_to_float(record.get("6_horas")),
        chuva_12h=_to_float(record.get("12_horas")),
        chuva_24h=_to_float(record.get("24_horas")),
        altura_mare=_to_float(_first_present(record, "altura_mare", "altura")),
        status_mare=_to_str(_first_present(record, "status_mare", "status")),
        precipitacao_prevista_24h=_to_float(record.get("precipitacao_prevista_24h")),
        prob_alagamento=_to_float(record.get("prob_alagamento")),
        alagamento_previsto=_to_str(record.get("alagamento_previsto")),
        score_risco=_to_float(record.get("score_risco")) or 0.0,
        nivel_risco=_to_str(record.get("nivel_risco")) or "desconhecido",
    )


def _normalize_search_text(value: str) -> str:
    without_accents = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(char for char in without_accents if not unicodedata.combining(char))
    return ascii_text.casefold().strip()


def get_gold_risk_snapshot() -> GoldRiskSnapshot:
    records, _, source_updated_at = _load_gold_records()
    neighborhoods = [_normalize_record(record) for record in records]

    generated_at = max(
        (neighborhood.data for neighborhood in neighborhoods if neighborhood.data),
        default=None,
    )

    return GoldRiskSnapshot(
        generated_at=generated_at,
        source_updated_at=source_updated_at,
        neighborhoods_count=len(neighborhoods),
        neighborhoods=neighborhoods,
    )


def get_raw_gold_risk_records() -> list[dict[str, Any]]:
    records, _, _ = _load_gold_records()
    return records


def get_neighborhood_risk(bairro: str) -> NeighborhoodRisk:
    snapshot = get_gold_risk_snapshot()
    requested_bairro = _normalize_search_text(bairro)

    for neighborhood in snapshot.neighborhoods:
        if _normalize_search_text(neighborhood.bairro) == requested_bairro:
            return neighborhood

    raise HTTPException(
        status_code=404,
        detail=f"Bairro nao encontrado no JSON Gold: {bairro}",
    )
