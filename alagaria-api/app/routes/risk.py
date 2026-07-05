from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db_session
from app.schemas import GoldRiskSnapshot, NeighborhoodRisk
from app.services.gold_risk_repository import (
    get_gold_risk_snapshot,
    get_neighborhood_history,
    get_neighborhood_risk,
    get_raw_gold_risk_records,
)

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("/bairros", response_model=GoldRiskSnapshot)
def list_neighborhood_risks():
    return get_gold_risk_snapshot()


@router.get("/bairros/{bairro}/historico", response_model=list[NeighborhoodRisk])
def get_neighborhood_risk_history(
    bairro: str,
    limit: int = 24,
    db: Session = Depends(get_db_session),
):
    return get_neighborhood_history(bairro, db, limit)


@router.get("/bairros/{bairro}", response_model=NeighborhoodRisk)
def get_neighborhood_risk_detail(bairro: str):
    return get_neighborhood_risk(bairro)


@router.get("/raw")
def get_raw_gold_risk():
    return get_raw_gold_risk_records()
