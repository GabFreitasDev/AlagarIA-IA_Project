from pydantic import BaseModel, Field
from datetime import datetime

class MedicaoEntrada(BaseModel):
    data_medicao: datetime = Field(..., alias="data")
    municipio: str
    rpa: int = Field(..., alias="RPA")
    bairro: str = Field(..., alias="Bairro")
    elevacao_metros: float
    precipitacao_atual: float
    precipitacao_1h: float = Field(..., alias="1_hora")
    precipitacao_6h: float = Field(..., alias="6_horas")
    precipitacao_12h: float = Field(..., alias="12_horas")
    precipitacao_24h: float = Field(..., alias="24_horas")
    altura_mare: float
    status_mare: str
    precipitacao_prevista_24h: float
    prob_alagamento: float
    alagamento_previsto: str
    score_risco: float
    nivel_risco: str

    model_config = {"populate_by_name": True}

class MedicaoResposta(MedicaoEntrada):
    id: int

    model_config = {"from_attributes": True}