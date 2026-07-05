from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db_session
from app.schemas import GoldRiskIngestionRecord, GoldRiskIngestionResponse
from app.services.gold_risk_repository import ingest_gold_risk_records

router = APIRouter(tags=["ingestion"])


@router.post("/ingestao", response_model=GoldRiskIngestionResponse)
def ingest_gold_risk_snapshot(
    records: list[GoldRiskIngestionRecord],
    db: Session = Depends(get_db_session),
):
    return ingest_gold_risk_records(records, db)
