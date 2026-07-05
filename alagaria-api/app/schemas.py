from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    app: str
    version: str


class NeighborhoodRisk(BaseModel):
    data: str | None = None
    municipio: str = "Recife"
    bairro: str
    rpa: int | None = None
    elevacao_metros: float | None = None
    precipitacao_atual: float | None = None
    chuva_1h: float | None = None
    chuva_6h: float | None = None
    chuva_12h: float | None = None
    chuva_24h: float | None = None
    altura_mare: float | None = None
    status_mare: str | None = None
    precipitacao_prevista_24h: float | None = None
    prob_alagamento: float | None = None
    alagamento_previsto: str | None = None
    score_risco: float
    nivel_risco: str


class GoldRiskSnapshot(BaseModel):
    city: str = "Recife"
    generated_at: str | None = None
    source_updated_at: str | None = None
    neighborhoods_count: int
    neighborhoods: list[NeighborhoodRisk]
    source: str = "Databricks Gold"
    model: str = "gold_fuzzy_regression_v1"


class GoldRiskIngestionRecord(BaseModel):
    data: datetime
    municipio: str = "Recife"
    rpa: int | None = Field(default=None, alias="RPA")
    bairro: str = Field(alias="Bairro")
    elevacao_metros: float | None = None
    precipitacao_atual: float | None = None
    chuva_1h: float | None = Field(default=None, alias="1_hora")
    chuva_6h: float | None = Field(default=None, alias="6_horas")
    chuva_12h: float | None = Field(default=None, alias="12_horas")
    chuva_24h: float | None = Field(default=None, alias="24_horas")
    altura_mare: float | None = None
    status_mare: str | None = None
    precipitacao_prevista_24h: float | None = None
    prob_alagamento: float | None = None
    alagamento_previsto: str | None = None
    score_risco: float = 0.0
    nivel_risco: str = "desconhecido"

    model_config = ConfigDict(populate_by_name=True)


class GoldRiskIngestionResponse(BaseModel):
    inserted: int
    ignored_duplicates: int
    received: int
    message: str
