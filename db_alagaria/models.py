from sqlalchemy import Column, Integer, String, Float, DateTime
from database import Base


class MedicaoBairro(Base):
    __tablename__ = "historico_bairros"

    # Chave primária
    id = Column(Integer, primary_key=True, index=True)

    # Informações do local
    bairro = Column(String, index=True)
    municipio = Column(String)
    rpa = Column(Integer)
    elevacao_metros = Column(Float)

    # Data da medição
    data_medicao = Column(DateTime, index=True)

    # Dados climáticos / Maré
    precipitacao_atual = Column(Float)
    precipitacao_1h = Column(Float)
    precipitacao_6h = Column(Float)
    precipitacao_12h = Column(Float)
    precipitacao_24h = Column(Float)
    altura_mare = Column(Float)
    status_mare = Column(String)

    # Previsões e IA
    precipitacao_prevista_24h = Column(Float)
    prob_alagamento = Column(Float)
    alagamento_previsto = Column(String)
    score_risco = Column(Float)
    nivel_risco = Column(String)