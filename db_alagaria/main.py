from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

# Importando os arquivos que você acabou de criar
import models
import schemas
from database import engine, SessionLocal

# Essa linha diz ao SQLAlchemy para olhar o 'models.py' e criar as tabelas no PostgreSQL.
# ATENÇÃO: Como o banco ainda não está rodando, se tentarmos iniciar a API agora, vai dar erro.
# Nós vamos resolver isso na Fase 5!
models.Base.metadata.create_all(bind=engine)

# Inicializando o FastAPI com documentação automática
app = FastAPI(
    title="API de Alerta de Alagamentos - Recife",
    description="Endpoints para ingestão de dados e consulta do modelo de risco (MVP)",
    version="1.0.0"
)


# Dependência: Abre e fecha a conexão com o banco a cada requisição
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/ingestao", summary="Recebe os dados do Databricks e salva no Postgres")
def receber_dados_databricks(dados: List[schemas.MedicaoEntrada], db: Session = Depends(get_db)):
    novos_registros = []
    ignorados = 0

    for item in dados:
        # Trava de duplicatas (continua igual, checando bairro + hora)
        registro_existente = db.query(models.MedicaoBairro).filter(
            models.MedicaoBairro.bairro == item.bairro,
            models.MedicaoBairro.data_medicao == item.data_medicao
        ).first()

        if registro_existente:
            ignorados += 1
            continue

        # Novos campos adicionados aqui
        novo_registro = models.MedicaoBairro(
            bairro=item.bairro,
            municipio=item.municipio,
            rpa=item.rpa,
            elevacao_metros=item.elevacao_metros,
            data_medicao=item.data_medicao,
            precipitacao_atual=item.precipitacao_atual,
            precipitacao_1h=item.precipitacao_1h,
            precipitacao_6h=item.precipitacao_6h,
            precipitacao_12h=item.precipitacao_12h,
            precipitacao_24h=item.precipitacao_24h,
            altura_mare=item.altura_mare,
            status_mare=item.status_mare,
            precipitacao_prevista_24h=item.precipitacao_prevista_24h,
            prob_alagamento=item.prob_alagamento,
            alagamento_previsto=item.alagamento_previsto,
            score_risco=item.score_risco,
            nivel_risco=item.nivel_risco
        )
        novos_registros.append(novo_registro)

    if novos_registros:
        db.add_all(novos_registros)
        db.commit()

    return {
        "mensagem": f"{len(novos_registros)} novas medições salvas com sucesso!",
        "duplicadas_ignoradas": ignorados
    }

@app.get("/historico/{nome_bairro}", response_model=List[schemas.MedicaoResposta],
         summary="Retorna o histórico de um bairro")
def obter_historico_bairro(nome_bairro: str, db: Session = Depends(get_db)):
    # Busca no banco filtrando pelo bairro (ilike ignora maiúsculas/minúsculas)
    historico = db.query(models.MedicaoBairro) \
        .filter(models.MedicaoBairro.bairro.ilike(nome_bairro)) \
        .order_by(models.MedicaoBairro.data_medicao.desc()) \
        .limit(24).all()  # Retorna as últimas 24 medições para o gráfico

    if not historico:
        raise HTTPException(status_code=404, detail=f"Nenhum histórico encontrado para o bairro '{nome_bairro}'")

    return historico