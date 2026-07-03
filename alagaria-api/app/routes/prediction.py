from fastapi import APIRouter

from app.schemas import FloodRiskResponse
from app.services.apac_client import get_rain_by_intervals
from app.services.flood_predictor import predict_flood_risk

router = APIRouter(prefix="/predict", tags=["prediction"])


@router.get("/recife", response_model=FloodRiskResponse)
async def predict_recife_flood_risk():
    summaries = await get_rain_by_intervals(city="Recife", intervals=[1, 3, 6, 12, 24])
    return predict_flood_risk(city="Recife", summaries=summaries)
