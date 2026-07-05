from sqlalchemy import Column, DateTime, Float, Integer, String, UniqueConstraint

from app.database import Base


class NeighborhoodRiskMeasurement(Base):
    __tablename__ = "historico_bairros"
    __table_args__ = (
        UniqueConstraint("bairro", "data_medicao", name="uq_historico_bairros_bairro_data"),
    )

    id = Column(Integer, primary_key=True, index=True)

    data_medicao = Column(DateTime(timezone=True), index=True, nullable=False)
    municipio = Column(String, default="Recife", nullable=False)
    rpa = Column(Integer, index=True)
    bairro = Column(String, index=True, nullable=False)

    elevacao_metros = Column(Float)
    precipitacao_atual = Column(Float)
    chuva_1h = Column(Float)
    chuva_6h = Column(Float)
    chuva_12h = Column(Float)
    chuva_24h = Column(Float)
    altura_mare = Column(Float)
    status_mare = Column(String)

    precipitacao_prevista_24h = Column(Float)
    prob_alagamento = Column(Float)
    alagamento_previsto = Column(String)
    score_risco = Column(Float, nullable=False, default=0.0)
    nivel_risco = Column(String, nullable=False, default="desconhecido")
