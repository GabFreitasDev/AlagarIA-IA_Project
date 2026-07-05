# Databricks notebook source
# MAGIC %md
# MAGIC # Silver — Enriquecimento, IDW por RPA e montagem do dataset por bairro
# MAGIC
# MAGIC Este notebook resolve três problemas em sequência:
# MAGIC
# MAGIC 1. **Enriquecimento de RPA**: a API da APAC não informa a qual RPA
# MAGIC    cada estação pertence. Resolvemos isso encontrando o BAIRRO MAIS
# MAGIC    PRÓXIMO de cada estação (por distância geográfica) e usando a
# MAGIC    RPA desse bairro como a RPA da estação.
# MAGIC
# MAGIC 2. **IDW restrito à própria RPA**: cada bairro recebe um valor de
# MAGIC    chuva pela média ponderada por distância (IDW) das estações que
# MAGIC    pertencem à MESMA RPA do bairro — não cruza fronteira de RPA,
# MAGIC    para manter a granularidade administrativa que o projeto usa
# MAGIC    para reportar risco.
# MAGIC
# MAGIC 3. **Maré uniforme**: como a tábua de maré não distingue bairros,
# MAGIC    o mesmo valor de altura/status de maré é aplicado a todos os
# MAGIC    94 bairros — decisão consciente de simplificação para o MVP.
# MAGIC
# MAGIC ## Ciclo de atualização
# MAGIC
# MAGIC A precipitação e a maré são atualizadas TRÊS vezes por dia (08h, 14h, 19h).
# MAGIC Isso significa que o dataset do dia cresce em 3 lotes de 94 linhas.
# MAGIC
# MAGIC **Responsável:** Adenilson Gomes e Gabriel de Freitas  
# MAGIC **Frequência de execução:** 3x ao dia, alinhado aos horários de maré (08h, 14h, 19h)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 1 — Importações e parâmetros

# COMMAND ----------

import sys
sys.path.append("/Workspace/Users/gabriel.fo.br@gmail.com/AlagarIA-IA_Project/utils")

from utils.catalogo import tabela, CATALOGO, SCHEMA_BRONZE, SCHEMA_SILVER, SCHEMA_GOLD, SCHEMA_GOVERNANCA

import numpy as np
import pandas as pd
from pyspark.sql import functions as F
from datetime import datetime, timezone, timedelta

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 2 — Carregar a tabela mestre de bairros (já existe na Bronze)
# MAGIC
# MAGIC A tabela `bronze.open_meteo_elevation`, gerada no notebook 2, já
# MAGIC tem os 94 bairros com `bairro`, `rpa`, `latitude`, `longitude` e
# MAGIC `elevacao_metros` — não precisamos recriar essa base, só consumi-la.

# COMMAND ----------

df_bairros = spark.table(tabela(SCHEMA_BRONZE, "open_meteo_elevation"))

pdf_bairros = df_bairros.select(
    "bairro", "rpa", "latitude", "longitude", "elevacao_metros"
).toPandas()

print(f"✓ {len(pdf_bairros)} bairros carregados (esperado: 94).")
assert len(pdf_bairros) == 94, "Número de bairros divergente do esperado — checar tabela bronze.open_meteo_elevation."

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 3 — Enriquecer estações da APAC com a RPA do bairro mais próximo
# MAGIC
# MAGIC Para cada estação de precipitação, calculamos a distância
# MAGIC euclidiana (em graus — suficiente para a escala de uma cidade como
# MAGIC Recife) até os 94 bairros, e atribuímos a RPA do bairro mais
# MAGIC próximo. Isso roda uma vez por execução, sobre o lote de
# MAGIC estações do dia.

# COMMAND ----------

def encontrar_rpa_mais_proxima(lat_estacao: float, lon_estacao: float, pdf_bairros: pd.DataFrame) -> int:
    """
    Calcula a distância da estação até cada bairro e devolve a RPA
    do bairro mais próximo. Distância euclidiana simples em graus —
    adequada para a escala de Recife (poucos km de extensão), sem
    necessidade de fórmulas de distância geodésica mais complexas.
    """
    distancias = np.sqrt(
        (pdf_bairros["latitude"] - lat_estacao) ** 2
        + (pdf_bairros["longitude"] - lon_estacao) ** 2
    )
    indice_mais_proximo = distancias.idxmin()
    return int(pdf_bairros.loc[indice_mais_proximo, "rpa"])

df_precip_bronze = spark.table(tabela(SCHEMA_BRONZE, "apac_precipitacao_recife"))

data_hoje_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
df_precip_hoje = df_precip_bronze.filter(
    F.col("_data_execucao").startswith(data_hoje_utc)
)

ultima_execucao = df_precip_hoje.agg(F.max("_data_execucao")).collect()[0][0]
df_precip_hoje = df_precip_hoje.filter(F.col("_data_execucao") == ultima_execucao)

if ultima_execucao is None:
    raise RuntimeError(
        "Nenhum dado de precipitação encontrado para ontem na Bronze. "
        "Rode o notebook 01_bronze_apac_precipitacao antes deste."
    )

pdf_estacoes = df_precip_hoje.select(
    "estacao", "latitude", "longitude",
    "1_hora", "6_horas", "12_horas", "24_horas",
    "ultima_medicao", "precipitacao",
).toPandas()

pdf_estacoes["rpa"] = pdf_estacoes.apply(
    lambda linha: encontrar_rpa_mais_proxima(linha["latitude"], linha["longitude"], pdf_bairros),
    axis=1,
)

print(f"✓ {len(pdf_estacoes)} estação(ões) enriquecida(s) com RPA.")
print(pdf_estacoes[["estacao", "rpa"]].drop_duplicates().to_string(index=False))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 4 — IDW(Inverse Distance Weighted) restrito à própria RPA
# MAGIC
# MAGIC Para cada bairro, calculamos o valor de chuva como a média
# MAGIC ponderada por distância (peso = 1/distância²) usando SOMENTE as
# MAGIC estações que pertencem à MESMA RPA do bairro. Se uma RPA não tiver
# MAGIC nenhuma estação própria, os bairros dela ficam sem valor nesta
# MAGIC execução — registramos isso como alerta, não como erro fatal,
# MAGIC porque pode ser temporário (estação fora do ar naquele dia).

# COMMAND ----------

CAMPOS_CHUVA = ["1_hora", "6_horas", "12_horas", "24_horas", "ultima_medicao", "precipitacao"]


def idw_interpolar_rpa(lat_bairro: float, lon_bairro: float, estacoes_da_rpa: pd.DataFrame, coluna_valor: str, potencia: int = 2) -> float:
    """
    Interpolação IDW simples, restrita a um subconjunto de estações
    (as que já foram filtradas para pertencer à mesma RPA do bairro).
    Peso = 1 / distância^potencia. Evita divisão por zero substituindo
    distância 0 por um valor mínimo.
    """
    distancias = np.sqrt(
        (estacoes_da_rpa["latitude"] - lat_bairro) ** 2
        + (estacoes_da_rpa["longitude"] - lon_bairro) ** 2
    )
    distancias = distancias.replace(0, 1e-6)
    pesos = 1 / (distancias ** potencia)
    return float(np.sum(pesos * estacoes_da_rpa[coluna_valor]) / np.sum(pesos))


resultados_chuva = []
rpas_sem_estacao = set()

for _, bairro in pdf_bairros.iterrows():
    estacoes_da_rpa = pdf_estacoes[pdf_estacoes["rpa"] == bairro["rpa"]]

    if estacoes_da_rpa.empty:
        rpas_sem_estacao.add(bairro["rpa"])
        valores = {campo: None for campo in CAMPOS_CHUVA}
    else:
        valores = {
            campo: idw_interpolar_rpa(bairro["latitude"], bairro["longitude"], estacoes_da_rpa, campo)
            for campo in CAMPOS_CHUVA
        }

    resultados_chuva.append({
        "bairro": bairro["bairro"],
        "rpa": bairro["rpa"],
        **valores,
    })

pdf_chuva_por_bairro = pd.DataFrame(resultados_chuva)

if rpas_sem_estacao:
    print(f"[ALERTA] RPA(s) sem nenhuma estação ativa nesta execução: {sorted(rpas_sem_estacao)}. "
          f"Bairros dessas RPAs ficaram com chuva nula nesta execução.")

print(f"✓ Chuva calculada por IDW para {len(pdf_chuva_por_bairro)} bairros.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 5 — Selecionar maré por proximidade de horário (mesma para todos os bairros)
# MAGIC
# MAGIC O JSON de maré contém múltiplos registros ao longo do dia
# MAGIC anterior (ex: 08h, 14h, 19h), para múltiplas praias de Recife.
# MAGIC
# MAGIC A lógica deste bloco:
# MAGIC 1. Calcula a diferença em minutos entre o horário de CADA registro
# MAGIC    de maré e o horário ATUAL de execução do notebook.
# MAGIC 2. Identifica o horário mais próximo (menor diferença absoluta).
# MAGIC 3. Filtra todos os registros desse horário (pode haver mais de um,
# MAGIC    pois múltiplas praias têm leituras no mesmo horário).
# MAGIC 4. Calcula a MÉDIA SIMPLES de `altura` entre todas as praias
# MAGIC    desse grupo — e o STATUS mais frequente entre elas.
# MAGIC
# MAGIC Resultado: um único par (altura, status) aplicado igualmente
# MAGIC a todos os 94 bairros nesta execução.

# COMMAND ----------

from datetime import datetime, timezone

df_mare_bronze = spark.table(tabela(SCHEMA_BRONZE, "apac_mare_recife"))

# Pega todos os registros de maré ingeridos hoje (o arquivo do dia
# anterior, carregado pelo notebook 03 pela manhã, antes das execuções)
df_mare_hoje = df_mare_bronze.filter(F.col("_data_execucao").startswith(data_hoje_utc))

if df_mare_hoje.count() == 0:
    raise RuntimeError(
        "Nenhum dado de maré encontrado para hoje na Bronze. "
        "Rode o notebook 03_bronze_apac_mares antes deste."
    )

# Converte para Pandas para trabalhar com diferença de horários em Python
# (mais simples e legível do que fazer isso em Spark para 20-30 registros)
pdf_mare = df_mare_bronze.select("data", "altura", "status").toPandas()

# Campo "data" no JSON vem como "YYYY-MM-DD HH:MM:SS" — converte para datetime
pdf_mare["data_dt"] = pd.to_datetime(pdf_mare["data"], format="%Y-%m-%d %H:%M:%S")

# Horário atual de execução (só HH:MM:SS, sem data)
# O JSON sempre é do dia ANTERIOR, então não comparamos datas —
# só o horário dentro do dia. Isso garante que "07:00 hoje" bate
# corretamente com "03:23 de ontem" e não com "21:55 de ontem".
agora = datetime.now(timezone.utc)
agora_segundos = agora.hour * 3600 + agora.minute * 60 + agora.second
pdf_mare["segundos_no_dia"] = (
    pdf_mare["data_dt"].dt.hour * 3600
    + pdf_mare["data_dt"].dt.minute * 60
    + pdf_mare["data_dt"].dt.second
)
pdf_mare["diff_segundos"] = (pdf_mare["segundos_no_dia"] - agora_segundos).abs()

# Identifica o horário mais próximo
menor_diff = pdf_mare["diff_segundos"].min()

# Tolerância de 5 minutos (300s): considera como "mesmo horário" registros
# que estejam a no máximo 5 minutos de diferença entre si no grupo mais
# próximo. Isso agrupa praias medidas quase simultaneamente (ex: 15:46 e 15:50)
grupo_mais_proximo = pdf_mare[pdf_mare["diff_segundos"] <= menor_diff + 300]

# Média simples de altura entre todas as praias do grupo
altura_mare_atual = round(float(grupo_mais_proximo["altura"].mean()), 2)

# Status mais frequente entre as praias do grupo (moda)
# Se houver empate, pega o primeiro em ordem alfabética para ser determinístico
status_mare_atual = grupo_mais_proximo["status"].mode().sort_values().iloc[0]

horario_referencia = grupo_mais_proximo["data_dt"].iloc[0].strftime("%H:%M")
print(f"✓ Maré desta execução (horário de referência: {horario_referencia}, "
      f"{len(grupo_mais_proximo)} praia(s) no grupo):")
print(f"  altura média = {altura_mare_atual}m | status = {status_mare_atual}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 6 — Montar as 94 linhas do esquema final e gravar
# MAGIC
# MAGIC Monta o registro final por bairro, no esquema acordado com o
# MAGIC backend e o motor de IA. Cada execução (08h/14h/20h) ADICIONA 94
# MAGIC novas linhas — não sobrescreve — para que, ao final do dia, o
# MAGIC dataset tenha 282 linhas (94 bairros × 3 horários de maré).

# COMMAND ----------

CODIGO_MUNICIPIO_RECIFE = "Recife"
timestamp_atual = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

pdf_bairros_completo = pdf_bairros.merge(pdf_chuva_por_bairro[["bairro"] + CAMPOS_CHUVA], on="bairro", how="left")

registros_finais = []
for _, linha in pdf_bairros_completo.iterrows():
    registros_finais.append({
        "data": timestamp_atual,
        "municipio": CODIGO_MUNICIPIO_RECIFE,
        "RPA": int(linha["rpa"]),
        "Bairro": linha["bairro"],
        "elevacao_metros": float(linha["elevacao_metros"]) if linha["elevacao_metros"] is not None else None,
        "precipitacao": linha["precipitacao"],
        "ultima_medicao": linha["ultima_medicao"],
        "1_hora": linha["1_hora"],
        "6_horas": linha["6_horas"],
        "12_horas": linha["12_horas"],
        "24_horas": linha["24_horas"],
        "altura": float(altura_mare_atual) if altura_mare_atual is not None else None,
        "status": status_mare_atual,
    })

df_silver_bairros = spark.createDataFrame(registros_finais)

(
    df_silver_bairros.write
    .format("delta")
    .mode("append")
    .saveAsTable(tabela(SCHEMA_SILVER, "dados_por_bairro"))
)

print(f"OK — {len(registros_finais)} registro(s) gravado(s) em {tabela(SCHEMA_SILVER, 'dados_por_bairro')} "
      f"(timestamp: {timestamp_atual}).")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 7 — Log de auditoria da execução

# COMMAND ----------

log_execucao = spark.createDataFrame([{
    "notebook": "04_bronze_to_silver",
    "timestamp_execucao": datetime.now(timezone.utc).isoformat(),
    "sucesso": True,
    "rpas_sem_estacao": str(sorted(rpas_sem_estacao)) if rpas_sem_estacao else "",
    "linhas_gravadas": len(registros_finais),
}])

(
    log_execucao.write
    .format("delta")
    .mode("append")
    .saveAsTable(tabela(SCHEMA_GOVERNANCA, "log_ingestao_silver"))
)
