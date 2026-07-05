from pydantic import BaseModel


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
