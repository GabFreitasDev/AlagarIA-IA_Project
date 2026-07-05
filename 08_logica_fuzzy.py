# Databricks notebook source
# MAGIC %md
# MAGIC # 08 — Motor de Lógica Fuzzy (Score de Risco por Bairro)
# MAGIC
# MAGIC Este notebook é o motor operacional do AlagarIA. Roda 3x ao dia
# MAGIC (03h, 11h, 19h) logo após o notebook 05 (Gold), e produz o JSON
# MAGIC final de risco que o backend consome.
# MAGIC
# MAGIC ## O que ele faz em sequência:
# MAGIC 1. Carrega os modelos treinados pelo notebook 07
# MAGIC 2. Usa a Regressão Linear para prever a precipitação das 24h seguintes
# MAGIC 3. Usa a Regressão Logística para estimar a probabilidade de alagamento
# MAGIC 4. Aplica a Lógica Fuzzy para classificar o nível de risco
# MAGIC    (baixo / moderado / alto / crítico)
# MAGIC 5. Gera o JSON final `risco_bairros_atual.json` com 94 registros
# MAGIC
# MAGIC ## Divisão de responsabilidades
# MAGIC - **Pessoa 3:** Bloco 3 — funções de pertinência fuzzy
# MAGIC - **Pessoa 4:** Bloco 4 — regras de inferência e defuzzificação
# MAGIC - **Pessoa 5:** Blocos 2, 5 e 6 — integração, predição e exportação
# MAGIC
# MAGIC **Frequência:** 3x/dia (03h, 11h, 19h) — Job encadeado após notebook 05.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 1 — Importações e configuração

# COMMAND ----------

import sys
sys.path.append("/Workspace/Users/gabriel.fo.br@gmail.com/AlagarIA-IA_Project/utils")

from utils.catalogo import tabela, CATALOGO, SCHEMA_GOLD, SCHEMA_SILVER, SCHEMA_GOVERNANCA

import json
import pickle
import numpy as np
import pandas as pd
import tempfile
import os

from pyspark.sql import functions as F
from datetime import datetime, timezone

CAMINHO_MODELOS       = f"/Volumes/{CATALOGO}/{SCHEMA_GOLD}/modelos"
CAMINHO_MODELO_LINEAR = f"{CAMINHO_MODELOS}/regressao_linear.pkl"
CAMINHO_MODELO_LOGISTICA = f"{CAMINHO_MODELOS}/regressao_logistica.pkl"
CAMINHO_SCALER        = f"{CAMINHO_MODELOS}/scaler.pkl"
CAMINHO_JSON_RISCO    = f"/Volumes/{CATALOGO}/{SCHEMA_GOLD}/exportacoes/risco_bairros_atual.json"

# ─────────────────────────────────────────────────────────────────
# PESSOA 5 — INTEGRAÇÃO: CARREGA DADOS E MODELOS
# ─────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 2 — Carregar dados atuais e modelos treinados (Pessoa 5)
# MAGIC
# MAGIC Carrega o snapshot mais recente por bairro (gerado pelo notebook 05)
# MAGIC e os modelos treinados pelo notebook 07.

# COMMAND ----------

def carregar_pickle_do_volume(caminho_volume: str):
    """
    Carrega um arquivo .pkl do Volume do Databricks.
    Volumes suportam leitura direta via Python open().
    """
    with open(caminho_volume, 'rb') as f:
        obj = pickle.load(f)
    return obj


print("Carregando dados atuais da Silver...")
df_silver = spark.table(tabela(SCHEMA_SILVER, "dados_por_bairro"))

# Pega o registro mais recente de cada bairro (mesmo padrão do notebook 05)
from pyspark.sql.window import Window
janela = Window.partitionBy("Bairro").orderBy(F.col("data").desc())
df_atual = (
    df_silver
    .withColumn("_ordem", F.row_number().over(janela))
    .filter(F.col("_ordem") == 1)
    .drop("_ordem")
)
pdf_atual = df_atual.toPandas()
print(f"✓ {len(pdf_atual)} bairros carregados.")

print("Carregando modelos treinados...")
modelo_linear = carregar_pickle_do_volume(CAMINHO_MODELO_LINEAR)
print("✓ Modelo Linear carregado.")

try:
    modelo_logistica = carregar_pickle_do_volume(CAMINHO_MODELO_LOGISTICA)
    scaler           = carregar_pickle_do_volume(CAMINHO_SCALER)
    tem_logistica    = True
    print("✓ Modelo Logístico + Scaler carregados.")
except Exception as e:
    print(f"[AVISO] Modelo Logístico não encontrado: {e}")
    print("  Execute o notebook 07 com a base fictícia para treinar o Modelo 2.")
    tem_logistica = False

# ─────────────────────────────────────────────────────────────────
# PESSOA 3 — FUNÇÕES DE PERTINÊNCIA FUZZY
# ─────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 3 — Funções de pertinência fuzzy (Pessoa 3)
# MAGIC
# MAGIC Define como cada variável de entrada é convertida em graus de
# MAGIC pertinência (valores entre 0 e 1) para os conjuntos fuzzy.
# MAGIC
# MAGIC Cada função recebe um valor numérico e devolve um dicionário
# MAGIC com o grau de pertinência de cada conjunto linguístico.
# MAGIC
# MAGIC Os limiares foram definidos com base na realidade climática
# MAGIC de Recife e no histórico de alagamentos da cidade.

# COMMAND ----------

def pertinencia_chuva(p24h: float) -> dict:
    """
    Converte precipitação prevista em 24h (mm) para graus de pertinência.

    Limiares baseados em registros históricos de Recife:
    - Até 10mm: sem impacto significativo
    - 10-40mm: chuva moderada, vigilância
    - 30-80mm: chuva forte, risco de alagamentos pontuais
    - Acima de 60mm: chuva muito forte, alto risco
    """
    p = max(0.0, float(p24h))

    # Pertinência "baixa": plena até 10mm, zero a partir de 30mm
    baixa = max(0.0, min(1.0, (30 - p) / 20)) if p <= 30 else 0.0

    # Pertinência "moderada": pico entre 20-40mm
    if p <= 10:
        moderada = 0.0
    elif p <= 30:
        moderada = (p - 10) / 20
    elif p <= 50:
        moderada = (50 - p) / 20
    else:
        moderada = 0.0

    # Pertinência "forte": cresce a partir de 30mm, plena acima de 70mm
    if p <= 30:
        forte = 0.0
    elif p <= 70:
        forte = (p - 30) / 40
    else:
        forte = 1.0

    # Pertinência "extrema": só acima de 60mm, plena acima de 120mm
    # (eventos extremos como os que causam desastres em Recife)
    if p <= 60:
        extrema = 0.0
    elif p <= 120:
        extrema = (p - 60) / 60
    else:
        extrema = 1.0

    return {"baixa": baixa, "moderada": moderada, "forte": forte, "extrema": extrema}


def pertinencia_mare(altura: float) -> dict:
    """
    Converte altura da maré (metros) em graus de pertinência.

    Limiares baseados nas tábuas de maré do Porto do Recife:
    - Maré baixa: < 0.8m
    - Maré média: 0.6m - 1.6m
    - Maré alta: > 1.4m
    Maré alta + chuva = efeito de represamento (água não escoa)
    """
    h = max(0.0, float(altura))

    baixa = max(0.0, min(1.0, (1.0 - h) / 0.7)) if h <= 1.0 else 0.0

    if h <= 0.5:
        media = 0.0
    elif h <= 1.0:
        media = (h - 0.5) / 0.5
    elif h <= 1.5:
        media = (1.5 - h) / 0.5
    else:
        media = 0.0

    alta = max(0.0, min(1.0, (h - 1.2) / 0.6)) if h >= 1.2 else 0.0

    return {"baixa": baixa, "media": media, "alta": alta}


def pertinencia_altitude(elev: float) -> dict:
    """
    Converte altitude do bairro (metros) em graus de pertinência.

    Bairros baixos de Recife (< 5m) são os mais vulneráveis a
    alagamentos — estão no nível do lençol freático e próximos
    dos rios Capibaribe e Beberibe.
    """
    e = max(0.0, float(elev))

    # Bairro baixo: até 5m é totalmente baixo, zero acima de 15m
    baixa = max(0.0, min(1.0, (15 - e) / 10)) if e <= 15 else 0.0

    # Bairro médio: entre 5m e 30m
    if e <= 5:
        media = 0.0
    elif e <= 15:
        media = (e - 5) / 10
    elif e <= 30:
        media = (30 - e) / 15
    else:
        media = 0.0

    # Bairro alto: acima de 20m, seguro acima de 40m
    alta = max(0.0, min(1.0, (e - 20) / 20)) if e >= 20 else 0.0

    return {"baixa": baixa, "media": media, "alta": alta}


print("✓ Funções de pertinência definidas.")
print("  Teste rápido com 50mm de chuva:", pertinencia_chuva(50))
print("  Teste rápido com maré 1.8m:", pertinencia_mare(1.8))
print("  Teste rápido com altitude 4m:", pertinencia_altitude(4))

# ─────────────────────────────────────────────────────────────────
# PESSOA 4 — REGRAS DE INFERÊNCIA E DEFUZZIFICAÇÃO
# ─────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 4 — Regras fuzzy e defuzzificação (Pessoa 4)
# MAGIC
# MAGIC Define as regras de inferência (SE... ENTÃO...) que combinam
# MAGIC as pertinências das 3 variáveis para calcular o risco.
# MAGIC
# MAGIC Método de defuzzificação: centroide (centro de massa).
# MAGIC Devolve score numérico [0, 1] e nível linguístico de risco.

# COMMAND ----------

def calcular_risco_fuzzy(p24h: float, altura_mare: float, elevacao: float) -> dict:
    """
    Motor de inferência fuzzy completo.

    Entrada: valores numéricos das 3 variáveis
    Saída: score [0,1] e nível de risco (baixo/moderado/alto/critico)

    Regras implementadas (base de conhecimento):
    - Bairro baixo + chuva extrema + maré alta → crítico
    - Bairro baixo + chuva forte + maré alta   → alto
    - Bairro baixo + chuva forte + maré média  → alto
    - Bairro médio + chuva extrema             → alto
    - Bairro baixo + chuva moderada + maré alta → moderado
    - Bairro baixo + chuva forte + maré baixa  → moderado
    - Bairro médio + chuva forte               → moderado
    - Bairro alto  + chuva extrema             → moderado
    - Chuva baixa (qualquer bairro)            → baixo
    - Bairro alto  + chuva moderada            → baixo
    """
    pc = pertinencia_chuva(p24h)
    pm = pertinencia_mare(altura_mare)
    pa = pertinencia_altitude(elevacao)

    # Cada regra ativa um nível de risco com um grau de ativação
    # Grau = mínimo das pertinências envolvidas (operador AND fuzzy)
    ativacoes = {
        "critico":  max(
            min(pa["baixa"], pc["extrema"], pm["alta"]),
            min(pa["baixa"], pc["forte"],   pm["alta"]) * 0.8,
        ),
        "alto":     max(
            min(pa["baixa"], pc["forte"],    pm["media"]),
            min(pa["media"], pc["extrema"]),
            min(pa["baixa"], pc["extrema"],  pm["media"]) * 0.9,
        ),
        "moderado": max(
            min(pa["baixa"],  pc["moderada"], pm["alta"]),
            min(pa["baixa"],  pc["forte"],    pm["baixa"]),
            min(pa["media"],  pc["forte"]),
            min(pa["alta"],   pc["extrema"]),
        ),
        "baixo":    max(
            pc["baixa"],
            min(pa["alta"],  pc["moderada"]),
            min(pa["media"], pc["baixa"]),
        ),
    }

    # Centros de cada conjunto de saída (posição no universo [0, 1])
    centros = {"baixo": 0.15, "moderado": 0.40, "alto": 0.70, "critico": 0.92}

    # Defuzzificação pelo centroide: média ponderada dos centros pelos graus
    numerador   = sum(ativacoes[k] * centros[k] for k in ativacoes)
    denominador = sum(ativacoes.values())

    if denominador < 1e-6:
        score = 0.0
    else:
        score = numerador / denominador

    score = round(max(0.0, min(1.0, score)), 4)

    # Classificação linguística final
    if score >= 0.75:
        nivel = "critico"
    elif score >= 0.50:
        nivel = "alto"
    elif score >= 0.25:
        nivel = "moderado"
    else:
        nivel = "baixo"

    return {
        "score": score,
        "nivel": nivel,
        "ativacoes": {k: round(v, 4) for k, v in ativacoes.items()}
    }


# Teste com cenário de alto risco (bairro baixo, muita chuva, maré alta)
teste = calcular_risco_fuzzy(p24h=95, altura_mare=2.1, elevacao=3.0)
print(f"✓ Teste alto risco (95mm, maré 2.1m, alt 3m): score={teste['score']}, nível={teste['nivel']}")

# Teste com cenário de baixo risco (bairro alto, pouca chuva)
teste2 = calcular_risco_fuzzy(p24h=8, altura_mare=0.5, elevacao=40.0)
print(f"✓ Teste baixo risco (8mm, maré 0.5m, alt 40m): score={teste2['score']}, nível={teste2['nivel']}")

# ─────────────────────────────────────────────────────────────────
# PESSOA 5 — INTEGRAÇÃO: PREDIÇÃO E EXPORTAÇÃO DO JSON FINAL
# ─────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 5 — Encadear os modelos e calcular risco por bairro (Pessoa 5)
# MAGIC
# MAGIC Para cada um dos 94 bairros:
# MAGIC 1. Usa a Regressão Linear para prever P24h amanhã
# MAGIC 2. (Se disponível) Usa a Logística para estimar prob. de alagamento
# MAGIC 3. Aplica a Lógica Fuzzy com P24h + maré atual + altitude
# MAGIC 4. Monta o registro final com todos os campos

# COMMAND ----------

FEATURES_LINEAR   = ["1_hora", "6_horas", "12_horas", "24_horas"]
FEATURES_LOGISTICA = ["1_hora", "6_horas", "12_horas", "24_horas",
                       "altura", "elevacao_metros"]

timestamp_atual = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
registros_risco = []

for _, linha in pdf_atual.iterrows():
    # ── Regressão Linear: prevê precipitação das próximas 24h ──
    features_lin = np.array([[
        float(linha.get("1_hora",  0) or 0),
        float(linha.get("6_horas", 0) or 0),
        float(linha.get("12_horas",0) or 0),
        float(linha.get("24_horas",0) or 0),
    ]])
    p24h_prevista = float(max(0, modelo_linear.predict(features_lin)[0]))

    # ── Regressão Logística: probabilidade de alagamento ────────
    if tem_logistica:
        features_log = np.array([[
            float(linha.get("1_hora",  0) or 0),
            float(linha.get("6_horas", 0) or 0),
            float(linha.get("12_horas",0) or 0),
            float(linha.get("24_horas",0) or 0),
            float(linha.get("altura",  1) or 1),
            float(linha.get("elevacao_metros", 10) or 10),
        ]])
        features_log_scaled = scaler.transform(features_log)
        prob_alagamento = float(modelo_logistica.predict_proba(features_log_scaled)[0][1])
        alagamento_previsto = "Sim" if prob_alagamento >= 0.5 else "Não"
    else:
        prob_alagamento = None
        alagamento_previsto = None

    # ── Lógica Fuzzy: score e nível de risco ────────────────────
    resultado_fuzzy = calcular_risco_fuzzy(
        p24h=p24h_prevista,
        altura_mare=float(linha.get("altura", 1.0) or 1.0),
        elevacao=float(linha.get("elevacao_metros", 10.0) or 10.0),
    )

    registros_risco.append({
        # Campos de identificação
        "data": timestamp_atual,
        "municipio": str(linha.get("municipio", "Recife")),
        "RPA": int(linha.get("RPA", 0)),
        "Bairro": str(linha.get("Bairro", "")),

        # Dados observados (do pipeline de dados)
        "elevacao_metros": float(linha.get("elevacao_metros", 0) or 0),
        "precipitacao_atual": float(linha.get("precipitacao", 0) or 0),
        "1_hora": float(linha.get("1_hora", 0) or 0),
        "6_horas": float(linha.get("6_horas", 0) or 0),
        "12_horas": float(linha.get("12_horas", 0) or 0),
        "24_horas": float(linha.get("24_horas", 0) or 0),
        "altura_mare": float(linha.get("altura", 0) or 0),
        "status_mare": str(linha.get("status", "")),

        # Saídas dos modelos de IA
        "precipitacao_prevista_24h": round(p24h_prevista, 2),
        "prob_alagamento": round(prob_alagamento, 4) if prob_alagamento is not None else None,
        "alagamento_previsto": alagamento_previsto,
        "score_risco": resultado_fuzzy["score"],
        "nivel_risco": resultado_fuzzy["nivel"],
    })

print(f"✓ Score de risco calculado para {len(registros_risco)} bairros.")

# Resumo dos níveis de risco calculados
from collections import Counter
niveis = Counter(r["nivel_risco"] for r in registros_risco)
for nivel in ["critico", "alto", "moderado", "baixo"]:
    qtd = niveis.get(nivel, 0)
    barra = "█" * qtd
    print(f"  {nivel:10s}: {qtd:2d} bairros {barra}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 6 — Exportar JSON final de risco (Pessoa 5)
# MAGIC
# MAGIC Salva o JSON com os 94 bairros no Volume Gold, sobrescrevendo
# MAGIC o arquivo anterior. O backend consome este arquivo no mesmo
# MAGIC padrão que já consome o dados_bairros_atual.json.

# COMMAND ----------

dbutils.fs.put(
    CAMINHO_JSON_RISCO,
    json.dumps(registros_risco, ensure_ascii=False, indent=2),
    overwrite=True
)

print(f"OK — JSON de risco exportado: {CAMINHO_JSON_RISCO}")
print(f"  {len(registros_risco)} bairros | timestamp: {timestamp_atual}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 7 — Log de auditoria da execução

# COMMAND ----------

log_execucao = spark.createDataFrame([{
    "notebook": "08_logica_fuzzy",
    "timestamp_execucao": datetime.now(timezone.utc).isoformat(),
    "sucesso": True,
    "bairros_processados": len(registros_risco),
    "nivel_critico": niveis.get("critico", 0),
    "nivel_alto": niveis.get("alto", 0),
    "nivel_moderado": niveis.get("moderado", 0),
    "nivel_baixo": niveis.get("baixo", 0),
    "tem_modelo_logistica": tem_logistica,
}])

(
    log_execucao.write
    .format("delta")
    .mode("append")
    .option("mergeSchema", "true")
    .saveAsTable(tabela(SCHEMA_GOVERNANCA, "log_ingestao_gold"))
)

print("✓ Log de execução registrado.")
