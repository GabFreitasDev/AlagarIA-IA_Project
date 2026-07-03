from fastapi import APIRouter, Query

from app.schemas import RainByInterval, RainSummary
from app.services.apac_client import fetch_apac_layer, get_rain_by_intervals, get_rain_summary

router = APIRouter(prefix="/rain", tags=["rain"])


@router.get("/raw/{hours}")
async def get_raw_apac_layer(hours: int):
    return await fetch_apac_layer(hours)


@router.get("/recife/{hours}", response_model=RainSummary)
async def get_recife_rain_by_interval(hours: int):
    return await get_rain_summary(hours=hours, city="Recife")


@router.get("/recife", response_model=RainByInterval)
async def get_recife_rain(
    intervals: str = Query(default="1,3,6,12,24", description="Intervalos em horas separados por vírgula. Ex.: 1,3,6,12,24")
):
    selected_intervals = [int(value.strip()) for value in intervals.split(",") if value.strip()]
    summaries = await get_rain_by_intervals(city="Recife", intervals=selected_intervals)

    return RainByInterval(
        city="Recife",
        intervals=summaries,
    )
