# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze — Histórico de Precipitação (Open-Meteo Archive)
# MAGIC
# MAGIC Ingestão da série histórica de precipitação horária via API da
# MAGIC Open-Meteo (endpoint `/v1/archive`), usando reanálise ERA5 com
# MAGIC cobertura global sem dados faltantes.
# MAGIC
# MAGIC ## Por que essa fonte existe
# MAGIC
# MAGIC A API da APAC só devolve o estado ATUAL das estações — não tem
# MAGIC endpoint de histórico navegável. Para alimentar o motor de
# MAGIC **Regressão Linear** (que precisa de uma série histórica para
# MAGIC aprender o padrão de chuva ao longo dos dias e prever o dia atual),
# MAGIC usamos a Open-Meteo como fonte histórica complementar.
# MAGIC
# MAGIC ## Modos de execução
# MAGIC
# MAGIC - **carga_inicial**: busca os últimos N dias de uma vez (configurável
# MAGIC   via widget). Rodar UMA VEZ para popular a base de treino.
# MAGIC - **incremental**: busca só o dia anterior. Rodar DIARIAMENTE para
# MAGIC   manter a série atualizada sem reprocessar o histórico inteiro.
# MAGIC
# MAGIC ## Diferença de formato em relação à APAC
# MAGIC
# MAGIC A Open-Meteo devolve dados no formato "colunar":
# MAGIC `{"hourly": {"time": [...], "precipitation": [...]}}`
# MAGIC — dois arrays paralelos, não uma lista de objetos. O notebook
# MAGIC converte para lista de objetos antes de gravar como Delta Table.
# MAGIC
# MAGIC **Responsável:** Pessoa B
# MAGIC **Frequência de execução:** diária (modo incremental), após carga inicial.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 1 — Importações e parâmetros

# COMMAND ----------

import sys
sys.path.append("/Workspace/Users/gabriel.fo.br@gmail.com/AlagarIA-IA_Project/utils")
sys.path.append("/Workspace/Users/gabriel.fo.br@gmail.com/AlagarIA-IA_Project/APIs")

import importlib
import openmeteo_client
importlib.reload(openmeteo_client)
from openmeteo_client import fetch_openmeteo_historico

from utils.catalogo import tabela, CATALOGO, SCHEMA_BRONZE, SCHEMA_GOVERNANCA

from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, FloatType
from datetime import datetime, timezone, date, timedelta

# Widget para escolher o modo sem precisar editar o código.
# Na PRIMEIRA execução: escolher "carga_inicial" e configurar DIAS_HISTORICO.
# Nas execuções DIÁRIAS seguintes (via Job agendado): deixar "incremental".
dbutils.widgets.dropdown("MODO_EXECUCAO", "incremental", ["carga_inicial", "incremental"])
dbutils.widgets.text("DIAS_HISTORICO", "180", "Dias de histórico (só carga_inicial)")

modo_execucao = dbutils.widgets.get("MODO_EXECUCAO")
dias_historico = int(dbutils.widgets.get("DIAS_HISTORICO"))

data_execucao = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 2 — Definir o intervalo de datas a buscar
# MAGIC
# MAGIC Carga inicial: busca um intervalo longo (ex: 180 dias) para já
# MAGIC ter volume suficiente para a regressão linear treinar desde o
# MAGIC início do projeto.
# MAGIC
# MAGIC Incremental: busca só o dia anterior (ontem), que já tem as 24h
# MAGIC completas consolidadas — o dia atual ainda está em andamento e
# MAGIC os valores seriam parciais.

# COMMAND ----------

if modo_execucao == "carga_inicial":
    data_fim = date.today() - timedelta(days=1)
    data_inicio = data_fim - timedelta(days=dias_historico)
    print(f"Modo: CARGA INICIAL | {dias_historico} dias | {data_inicio} → {data_fim}")
else:
    data_fim = date.today() - timedelta(days=1)
    data_inicio = data_fim
    print(f"Modo: INCREMENTAL | buscando {data_inicio} (ontem)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 3 — Chamada à API Open-Meteo
# MAGIC
# MAGIC A Open-Meteo Archive não exige chave de API e é gratuita para
# MAGIC uso não comercial (até 10.000 chamadas/dia). Diferente da APAC,
# MAGIC esta API funciona a partir do cluster Databricks (não tem bloqueio
# MAGIC de rede para datacenters — confirmar antes de rodar se ainda não
# MAGIC testado no ambiente de vocês).

# COMMAND ----------

resultado = fetch_openmeteo_historico(
    data_inicio=data_inicio.isoformat(),
    data_fim=data_fim.isoformat(),
)

if not resultado["sucesso"]:
    raise RuntimeError(
        f"Falha na chamada à API Open-Meteo: {resultado['erro']}\n"
        f"Verifique a conectividade de rede do cluster com archive-api.open-meteo.com"
    )

print(f"✓ API respondeu com status {resultado['status_code']} em {resultado['timestamp_busca']}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 4 — Converter formato colunar → lista de registros
# MAGIC
# MAGIC A Open-Meteo devolve dois arrays paralelos:
# MAGIC `{"time": ["2026-01-01T00:00", ...], "precipitation": [0.0, ...]}`
# MAGIC
# MAGIC Convertemos para uma lista de objetos (mesmo padrão da APAC),
# MAGIC para que a leitura Spark fique uniforme entre as duas fontes.
# MAGIC
# MAGIC Também validamos que os dois arrays têm o mesmo comprimento —
# MAGIC se não tiverem, os dados estão corrompidos e não devemos gravar.

# COMMAND ----------

dados_horarios = resultado["dados"]["hourly"]

timestamps = dados_horarios["time"]
precipitacoes = dados_horarios["precipitation"]

if len(timestamps) != len(precipitacoes):
    raise RuntimeError(
        f"Arrays de tamanhos diferentes na resposta da API: "
        f"time={len(timestamps)}, precipitation={len(precipitacoes)}. "
        f"Dado corrompido — abortando ingestão."
    )

registros = [
    {
        "timestamp_hora": t,
        "precipitacao_mm": float(p) if p is not None else None,
    }
    for t, p in zip(timestamps, precipitacoes)
]

print(f"✓ {len(registros)} registros horários convertidos "
      f"({data_inicio} → {data_fim}).")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 5 — Criar DataFrame Spark com schema explícito e gravar na Bronze
# MAGIC
# MAGIC Schema explícito (não inferido) para evitar o mesmo problema de
# MAGIC LongType vs DoubleType que ocorreu com a APAC. Aqui o risco é
# MAGIC menor (só dois campos), mas o padrão de schema explícito é mais
# MAGIC robusto e consistente com o notebook 01.

# COMMAND ----------

schema_historico = StructType([
    StructField("timestamp_hora", StringType(), False),
    StructField("precipitacao_mm", FloatType(), True),
])

df_bronze_historico = spark.createDataFrame(registros, schema=schema_historico)

df_bronze_historico = (
    df_bronze_historico
    .withColumn("_ingerido_em", F.current_timestamp())
    .withColumn("_fonte", F.lit("open_meteo_archive"))
    .withColumn("_modo_execucao", F.lit(modo_execucao))
    .withColumn("_data_execucao", F.lit(data_execucao))
    # Extrai só a data do timestamp para facilitar filtros e particionamento
    .withColumn("_data_referencia", F.to_date(F.col("timestamp_hora")))
)

# Grava com partitionBy data_referencia: permite leituras eficientes
# por período (ex: "me dê os últimos 30 dias") sem escanear tudo.
# Modo "append" tanto na carga inicial quanto no incremental — o
# histórico deve ser acumulativo, nunca sobrescrito.
(
    df_bronze_historico.write
    .format("delta")
    .mode("append")
    .partitionBy("_data_referencia")
    .option("mergeSchema", "true")
    .saveAsTable(tabela(SCHEMA_BRONZE, "openmeteo_historico_precipitacao"))
)

spark.sql(f"""
    COMMENT ON TABLE {tabela(SCHEMA_BRONZE, 'openmeteo_historico_precipitacao')} IS
    'Série histórica de precipitação horária (mm) para Recife, via Open-Meteo
    Archive API (reanálise ERA5, resolução 9km, sem dados faltantes). Usada
    como base de treino para o motor de Regressão Linear do projeto AlagarIA.
    Coordenadas: lat=-8.0476, lon=-34.8770 (ponto representativo de Recife).
    Particionado por _data_referencia. Fonte: archive-api.open-meteo.com'
""")

total_gravado = df_bronze_historico.count()
print(f"OK — {total_gravado} registros gravados em "
      f"{tabela(SCHEMA_BRONZE, 'openmeteo_historico_precipitacao')}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 6 — Log de auditoria da execução

# COMMAND ----------

log_execucao = spark.createDataFrame([{
    "notebook": "06_bronze_openmeteo_historico",
    "timestamp_execucao": datetime.now(timezone.utc).isoformat(),
    "sucesso": resultado["sucesso"],
    "tentativas": 1,
    "erro": resultado["erro"] if resultado["erro"] is not None else "",
    "linhas_gravadas": total_gravado,
}])

(
    log_execucao.write
    .format("delta")
    .mode("append")
    .saveAsTable(tabela(SCHEMA_GOVERNANCA, "log_ingestao"))
)

