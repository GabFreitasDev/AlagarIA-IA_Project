from __future__ import annotations

import json
import math
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_session_factory, is_database_enabled
from app.models import NeighborhoodRiskMeasurement
from app.schemas import GoldRiskIngestionRecord, GoldRiskIngestionResponse, GoldRiskSnapshot, NeighborhoodRisk


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


def _measurement_to_neighborhood(record: NeighborhoodRiskMeasurement) -> NeighborhoodRisk:
    return NeighborhoodRisk(
        data=record.data_medicao.isoformat() if record.data_medicao else None,
        municipio=record.municipio or "Recife",
        bairro=record.bairro,
        rpa=record.rpa,
        elevacao_metros=record.elevacao_metros,
        precipitacao_atual=record.precipitacao_atual,
        chuva_1h=record.chuva_1h,
        chuva_6h=record.chuva_6h,
        chuva_12h=record.chuva_12h,
        chuva_24h=record.chuva_24h,
        altura_mare=record.altura_mare,
        status_mare=record.status_mare,
        precipitacao_prevista_24h=record.precipitacao_prevista_24h,
        prob_alagamento=record.prob_alagamento,
        alagamento_previsto=record.alagamento_previsto,
        score_risco=record.score_risco or 0.0,
        nivel_risco=record.nivel_risco or "desconhecido",
    )


def _measurement_to_raw_record(record: NeighborhoodRiskMeasurement) -> dict[str, Any]:
    return {
        "data": record.data_medicao.isoformat() if record.data_medicao else None,
        "municipio": record.municipio,
        "RPA": record.rpa,
        "Bairro": record.bairro,
        "elevacao_metros": record.elevacao_metros,
        "precipitacao_atual": record.precipitacao_atual,
        "1_hora": record.chuva_1h,
        "6_horas": record.chuva_6h,
        "12_horas": record.chuva_12h,
        "24_horas": record.chuva_24h,
        "altura_mare": record.altura_mare,
        "status_mare": record.status_mare,
        "precipitacao_prevista_24h": record.precipitacao_prevista_24h,
        "prob_alagamento": record.prob_alagamento,
        "alagamento_previsto": record.alagamento_previsto,
        "score_risco": record.score_risco,
        "nivel_risco": record.nivel_risco,
    }


def _latest_database_snapshot() -> GoldRiskSnapshot:
    session_factory = get_session_factory()
    if session_factory is None:
        raise HTTPException(status_code=503, detail="Banco de dados nao configurado.")

    with session_factory() as db:
        latest_timestamp = db.query(func.max(NeighborhoodRiskMeasurement.data_medicao)).scalar()

        if latest_timestamp is None:
            raise HTTPException(
                status_code=503,
                detail="Banco de dados configurado, mas ainda sem registros de risco.",
            )

        records = (
            db.query(NeighborhoodRiskMeasurement)
            .filter(NeighborhoodRiskMeasurement.data_medicao == latest_timestamp)
            .order_by(NeighborhoodRiskMeasurement.bairro.asc())
            .all()
        )

    neighborhoods = [_measurement_to_neighborhood(record) for record in records]

    return GoldRiskSnapshot(
        generated_at=latest_timestamp.isoformat(),
        source_updated_at=latest_timestamp.isoformat(),
        neighborhoods_count=len(neighborhoods),
        neighborhoods=neighborhoods,
        source="PostgreSQL",
    )


def get_gold_risk_snapshot() -> GoldRiskSnapshot:
    if is_database_enabled():
        return _latest_database_snapshot()

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
    if is_database_enabled():
        session_factory = get_session_factory()
        if session_factory is None:
            raise HTTPException(status_code=503, detail="Banco de dados nao configurado.")

        with session_factory() as db:
            latest_timestamp = db.query(func.max(NeighborhoodRiskMeasurement.data_medicao)).scalar()
            if latest_timestamp is None:
                return []

            records = (
                db.query(NeighborhoodRiskMeasurement)
                .filter(NeighborhoodRiskMeasurement.data_medicao == latest_timestamp)
                .order_by(NeighborhoodRiskMeasurement.bairro.asc())
                .all()
            )

        return [_measurement_to_raw_record(record) for record in records]

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


def ingest_gold_risk_records(
    records: list[GoldRiskIngestionRecord],
    db: Session,
) -> GoldRiskIngestionResponse:
    inserted = 0
    ignored_duplicates = 0

    for item in records:
        existing_record = (
            db.query(NeighborhoodRiskMeasurement)
            .filter(
                NeighborhoodRiskMeasurement.bairro == item.bairro,
                NeighborhoodRiskMeasurement.data_medicao == item.data,
            )
            .first()
        )

        if existing_record:
            ignored_duplicates += 1
            continue

        db.add(
            NeighborhoodRiskMeasurement(
                data_medicao=item.data,
                municipio=item.municipio,
                rpa=item.rpa,
                bairro=item.bairro,
                elevacao_metros=item.elevacao_metros,
                precipitacao_atual=item.precipitacao_atual,
                chuva_1h=item.chuva_1h,
                chuva_6h=item.chuva_6h,
                chuva_12h=item.chuva_12h,
                chuva_24h=item.chuva_24h,
                altura_mare=item.altura_mare,
                status_mare=item.status_mare,
                precipitacao_prevista_24h=item.precipitacao_prevista_24h,
                prob_alagamento=item.prob_alagamento,
                alagamento_previsto=item.alagamento_previsto,
                score_risco=item.score_risco,
                nivel_risco=item.nivel_risco,
            )
        )
        inserted += 1

    if inserted:
        db.commit()

    return GoldRiskIngestionResponse(
        inserted=inserted,
        ignored_duplicates=ignored_duplicates,
        received=len(records),
        message=f"{inserted} registro(s) inserido(s); {ignored_duplicates} duplicado(s) ignorado(s).",
    )


def get_neighborhood_history(bairro: str, db: Session, limit: int = 24) -> list[NeighborhoodRisk]:
    records = (
        db.query(NeighborhoodRiskMeasurement)
        .filter(NeighborhoodRiskMeasurement.bairro.ilike(bairro))
        .order_by(desc(NeighborhoodRiskMeasurement.data_medicao))
        .limit(limit)
        .all()
    )

    if not records:
        raise HTTPException(
            status_code=404,
            detail=f"Nenhum historico encontrado para o bairro '{bairro}'.",
        )

    return [_measurement_to_neighborhood(record) for record in records]
