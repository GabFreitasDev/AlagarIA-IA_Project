# Databricks notebook source
# MAGIC %md
# MAGIC # 07 — Motor de Regressão (Linear + Logística)
# MAGIC
# MAGIC Este notebook treina dois modelos complementares usando a base
# MAGIC histórica fictícia de 180 dias dos 94 bairros de Recife:
# MAGIC
# MAGIC **Modelo 1 — Regressão Linear:**
# MAGIC Prevê a precipitação acumulada das próximas 24h (variável contínua).
# MAGIC Responde: "quanto vai chover amanhã neste bairro?"
# MAGIC
# MAGIC **Modelo 2 — Regressão Logística:**
# MAGIC Prevê a probabilidade de alagamento (variável binária Sim/Não).
# MAGIC Responde: "dado o que prevemos de chuva, este bairro vai alagar?"
# MAGIC
# MAGIC A base fictícia já contém todos os campos necessários para os dois
# MAGIC modelos, incluindo a coluna `alagamento` (Sim/Não) gerada com
# MAGIC padrões climáticos reais do Recife (pico em Abr/Mai/Jun) e
# MAGIC susceptibilidade por RPA e altitude.
# MAGIC
# MAGIC Os modelos são salvos como .pkl no Volume Gold e carregados pelo
# MAGIC notebook 08 (Lógica Fuzzy) a cada execução operacional.
# MAGIC
# MAGIC ## Divisão de responsabilidades
# MAGIC - **Pessoa 1:** Blocos 2 e 3 — preparação dos dados de treino
# MAGIC - **Pessoa 2:** Blocos 4, 5 e 6 — treino, validação e persistência
# MAGIC
# MAGIC **Frequência:** sob demanda — re-executar só se quiserem
# MAGIC recalibrar os modelos com uma base fictícia atualizada.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 1 — Importações e configuração
# MAGIC
# MAGIC O Databricks já tem scikit-learn instalado nativamente.
# MAGIC Importamos aqui tudo que os dois modelos precisam.

# COMMAND ----------

import sys
sys.path.append("/Workspace/Users/gabriel.fo.br@gmail.com/AlagarIA-IA_Project/utils")

from utils.catalogo import tabela, CATALOGO, SCHEMA_BRONZE, SCHEMA_GOLD, SCHEMA_GOVERNANCA

import json
import pickle
import tempfile
import os
import numpy as np
import pandas as pd

from sklearn.linear_model import RidgeCV, LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    mean_absolute_error, mean_squared_error, r2_score,
    accuracy_score, classification_report,
    confusion_matrix
)
from pyspark.sql import functions as F
from datetime import datetime, timezone

# Caminhos para salvar os modelos no Volume Gold
CAMINHO_MODELOS          = f"/Volumes/{CATALOGO}/{SCHEMA_GOLD}/modelos"
CAMINHO_MODELO_LINEAR    = f"{CAMINHO_MODELOS}/regressao_linear.pkl"
CAMINHO_MODELO_LOGISTICA = f"{CAMINHO_MODELOS}/regressao_logistica.pkl"
CAMINHO_SCALER           = f"{CAMINHO_MODELOS}/scaler.pkl"

# Cria o volume se ele ainda não existir
spark.sql(f"""
    CREATE VOLUME IF NOT EXISTS {CATALOGO}.{SCHEMA_GOLD}.modelos
""")
dbutils.fs.mkdirs(CAMINHO_MODELOS)

# ─────────────────────────────────────────────────────────────────
# PESSOA 1 — PREPARAÇÃO DOS DADOS DE TREINO
# ─────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 2 — Carregar a base histórica fictícia (Pessoa 1)
# MAGIC
# MAGIC Carrega o JSON gerado pelo script `gerar_base_ficticia.py`,
# MAGIC que deve ter sido subido para a landing zone do Volume Bronze.
# MAGIC
# MAGIC A base tem 16.920 registros (94 bairros × 180 dias) com os
# MAGIC campos: data, municipio, RPA, Bairro, elevacao_metros,
# MAGIC precipitacao, ultima_medicao, 1_hora, 6_horas, 12_horas,
# MAGIC 24_horas, altura_mare, status_mare, alagamento.

# COMMAND ----------

CAMINHO_BASE_FICTICIA = (
    f"/Volumes/{CATALOGO}/{SCHEMA_BRONZE}/landing_zone/"
    "historico_ficticio_180dias_recife.json"
)

print("Carregando base histórica fictícia...")
conteudo = dbutils.fs.head(CAMINHO_BASE_FICTICIA, 1024 * 1024 * 50)  # até 50MB
registros = json.loads(conteudo)
pdf = pd.DataFrame(registros)
pdf["data"] = pd.to_datetime(pdf["data"]).dt.date.astype(str)

print(f"✓ {len(pdf):,} registros carregados.")
print(f"  Bairros: {pdf['Bairro'].nunique()} | Dias: {pdf['data'].nunique()}")
print(f"  Alagamentos: {(pdf['alagamento'] == 'Sim').sum():,} Sim / "
      f"{(pdf['alagamento'] == 'Não').sum():,} Não")
print(f"  Colunas: {list(pdf.columns)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 3 — Preparar features e targets (Pessoa 1)
# MAGIC
# MAGIC **Modelo 1 — Regressão Linear:**
# MAGIC Features: acumulados de chuva do dia atual (1h, 6h, 12h, 24h).
# MAGIC Target: precipitação acumulada de 24h do dia SEGUINTE.
# MAGIC O modelo aprende: "dado o que choveu hoje, quanto choverá amanhã?"
# MAGIC A autocorrelação temporal (dias chuvosos tendem a continuar chuvosos)
# MAGIC é o padrão que a regressão linear consegue capturar.
# MAGIC
# MAGIC **Modelo 2 — Regressão Logística:**
# MAGIC Features: acumulados de chuva + altura da maré + elevação do bairro.
# MAGIC Target: coluna `alagamento` (1 = Sim, 0 = Não).
# MAGIC O modelo aprende: "dado o volume de chuva, maré e altitude,
# MAGIC qual a probabilidade de alagamento neste bairro?"

# COMMAND ----------

# ── MODELO 1: Regressão Linear ────────────────────────────────────

# Ordena por bairro e data — obrigatório para o shift temporal funcionar
pdf_ord = pdf.sort_values(["Bairro", "data"]).reset_index(drop=True)

# Target: precipitação do DIA SEGUINTE (shift de -1 dentro de cada bairro)
# Este é o núcleo da previsão temporal: X = hoje, y = amanhã
pdf_ord["target_24h_amanha"] = (
    pdf_ord.groupby("Bairro")["24_horas"].shift(-1)
)

# O último dia de cada bairro não tem "amanhã" — removemos essas linhas
pdf_modelo1 = pdf_ord.dropna(subset=["target_24h_amanha"]).copy()

pdf_modelo1["data_ts"] = pd.to_datetime(pdf_modelo1["data"])
pdf_modelo1["mes"] = pdf_modelo1["data_ts"].dt.month
pdf_modelo1["dia_ano"] = pdf_modelo1["data_ts"].dt.dayofyear
pdf_modelo1["dia_ano_sin"] = np.sin(2 * np.pi * pdf_modelo1["dia_ano"] / 365.25)
pdf_modelo1["dia_ano_cos"] = np.cos(2 * np.pi * pdf_modelo1["dia_ano"] / 365.25)

FEATURES_LINEAR = [
    "1_hora",
    "6_horas",
    "12_horas",
    "24_horas",
    "mes",
    "dia_ano_sin",
    "dia_ano_cos",
    "altura_mare",
    "elevacao_metros",
    "RPA",
]
for coluna in FEATURES_LINEAR:
    pdf_modelo1[coluna] = pd.to_numeric(pdf_modelo1[coluna], errors="coerce")

X_linear = pdf_modelo1[FEATURES_LINEAR].fillna(0).values
y_linear = pdf_modelo1["target_24h_amanha"].values

print(f"✓ Dataset Modelo 1 (Linear):")
print(f"  {len(X_linear):,} amostras | {len(FEATURES_LINEAR)} features")
print(f"  Features: {FEATURES_LINEAR}")
print(f"  Target: precipitação 24h do dia seguinte")
print(f"  Média do target: {y_linear.mean():.2f}mm | Máx: {y_linear.max():.1f}mm")

# ── MODELO 2: Regressão Logística ────────────────────────────────

# A base fictícia tem altura_mare como float — usamos diretamente
# sem precisar de encoding, pois já é numérica
pdf_modelo2 = pdf.dropna(subset=["alagamento"]).copy()
pdf_modelo2["target_alagamento"] = (pdf_modelo2["alagamento"] == "Sim").astype(int)

FEATURES_LOGISTICA = ["1_hora", "6_horas", "12_horas", "24_horas",
                       "altura_mare", "elevacao_metros"]

X_logistica = pdf_modelo2[FEATURES_LOGISTICA].fillna(0).values
y_logistica = pdf_modelo2["target_alagamento"].values

print(f"\n✓ Dataset Modelo 2 (Logística):")
print(f"  {len(X_logistica):,} amostras | {len(FEATURES_LOGISTICA)} features")
print(f"  Features: {FEATURES_LOGISTICA}")
print(f"  Target: alagamento (1=Sim / 0=Não)")
print(f"  Balanceamento: {y_logistica.sum():,} Sim ({y_logistica.mean()*100:.1f}%) "
      f"/ {(1-y_logistica).sum():,} Não")

# ─────────────────────────────────────────────────────────────────
# PESSOA 2 — TREINO, VALIDAÇÃO E PERSISTÊNCIA
# ─────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 4 — Treinar Modelo 1: Regressão Linear (Pessoa 2)
# MAGIC
# MAGIC Divide 80% treino / 20% teste, treina e avalia.
# MAGIC
# MAGIC **RMSE** (Root Mean Squared Error): erro médio da previsão em mm.
# MAGIC Um RMSE de 15mm significa que o modelo erra em média 15mm na
# MAGIC previsão de chuva do dia seguinte — aceitável para um MVP.
# MAGIC
# MAGIC **R²**: proporção da variância explicada pelo modelo. Valor entre
# MAGIC 0 e 1; mais próximo de 1 é melhor. Para dados climáticos com alta
# MAGIC variabilidade, R² entre 0.3 e 0.6 já é razoável.

# COMMAND ----------

datas_unicas = np.array(sorted(pdf_modelo1["data"].unique()))
indice_corte = int(len(datas_unicas) * 0.8)
datas_treino = set(datas_unicas[:indice_corte])
mascara_treino_linear = pdf_modelo1["data"].isin(datas_treino)

X_train_l = pdf_modelo1.loc[mascara_treino_linear, FEATURES_LINEAR].fillna(0).values
X_test_l = pdf_modelo1.loc[~mascara_treino_linear, FEATURES_LINEAR].fillna(0).values
y_train_l = pdf_modelo1.loc[mascara_treino_linear, "target_24h_amanha"].values
y_test_l = pdf_modelo1.loc[~mascara_treino_linear, "target_24h_amanha"].values

modelo_linear = Pipeline(steps=[
    ("scaler", StandardScaler()),
    ("ridge", RidgeCV(alphas=np.logspace(-3, 3, 13))),
])
modelo_linear.fit(X_train_l, y_train_l)

y_pred_l = modelo_linear.predict(X_test_l)
y_pred_l = np.clip(y_pred_l, 0, None)  # precipitação não pode ser negativa

rmse = float(np.sqrt(mean_squared_error(y_test_l, y_pred_l)))
mae  = float(mean_absolute_error(y_test_l, y_pred_l))
r2   = float(r2_score(y_test_l, y_pred_l))
baseline_persistencia = np.clip(X_test_l[:, FEATURES_LINEAR.index("24_horas")], 0, None)
rmse_baseline = float(np.sqrt(mean_squared_error(y_test_l, baseline_persistencia)))
ganho_rmse_vs_baseline = float((rmse_baseline - rmse) / rmse_baseline) if rmse_baseline else 0.0
alpha_ridge = float(modelo_linear.named_steps["ridge"].alpha_)

print("── Modelo 1: Regressão Linear ──────────────────────────────")
print(f"  RMSE : {rmse:.2f} mm  (erro médio na previsão de amanhã)")
print(f"  R²   : {r2:.4f}     (variância explicada pelo modelo)")
print(f"  Coeficientes por feature:")
print(f"  MAE  : {mae:.2f} mm")
print(f"  Baseline persistencia RMSE: {rmse_baseline:.2f} mm")
print(f"  Ganho vs baseline       : {ganho_rmse_vs_baseline*100:.1f}%")
print(f"  Ridge alpha escolhido   : {alpha_ridge:.4f}")
print(f"  Split temporal          : treino ate {datas_unicas[indice_corte-1]} | teste desde {datas_unicas[indice_corte]}")
for feat, coef in zip(FEATURES_LINEAR, modelo_linear.named_steps["ridge"].coef_):
    print(f"    {feat:16s}: {coef:+.4f}")
print(f"  Intercepto: {modelo_linear.named_steps['ridge'].intercept_:+.4f}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 5 — Treinar Modelo 2: Regressão Logística (Pessoa 2)
# MAGIC
# MAGIC Divide com estratificação (garante a mesma proporção Sim/Não
# MAGIC em treino e teste). Normaliza as features com StandardScaler
# MAGIC antes do treino — a logística é sensível à escala das variáveis.
# MAGIC
# MAGIC `class_weight="balanced"` compensa o desbalanceamento natural
# MAGIC entre dias com e sem alagamento (há mais dias sem alagamento).
# MAGIC
# MAGIC **Acurácia**: % de previsões corretas.
# MAGIC **Precisão**: dos que o modelo disse "vai alagar", quantos realmente alagaram.
# MAGIC **Recall**: dos que realmente alagaram, quantos o modelo identificou.

# COMMAND ----------

X_train_log, X_test_log, y_train_log, y_test_log = train_test_split(
    X_logistica, y_logistica, test_size=0.2, random_state=42,
    stratify=y_logistica
)

# StandardScaler: normaliza cada feature para média 0 e desvio 1
# O scaler é treinado APENAS no conjunto de treino (fit_transform)
# e aplicado sem re-treinar no teste (transform) — evita data leakage
scaler = StandardScaler()
X_train_log_scaled = scaler.fit_transform(X_train_log)
X_test_log_scaled  = scaler.transform(X_test_log)

modelo_logistica = LogisticRegression(
    max_iter=1000,
    class_weight="balanced",
    random_state=42
)
modelo_logistica.fit(X_train_log_scaled, y_train_log)

y_pred_log = modelo_logistica.predict(X_test_log_scaled)
acuracia   = float(accuracy_score(y_test_log, y_pred_log))
cm         = confusion_matrix(y_test_log, y_pred_log)

print("── Modelo 2: Regressão Logística ───────────────────────────")
print(f"  Acurácia: {acuracia:.4f} ({acuracia*100:.1f}%)")
print(f"  Matriz de confusão:")
print(f"    Previu Não / Real Não (acerto): {cm[0][0]:5d}")
print(f"    Previu Sim / Real Não (falso alarme): {cm[0][1]:5d}")
print(f"    Previu Não / Real Sim (alagamento perdido): {cm[1][0]:5d}")
print(f"    Previu Sim / Real Sim (acerto): {cm[1][1]:5d}")
print()
print(classification_report(y_test_log, y_pred_log, target_names=["Não", "Sim"]))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 6 — Salvar modelos no Volume Gold (Pessoa 2)
# MAGIC
# MAGIC Salva os 3 artefatos como .pkl no Volume Gold:
# MAGIC - `regressao_linear.pkl` — modelo de previsão de chuva
# MAGIC - `regressao_logistica.pkl` — modelo de previsão de alagamento
# MAGIC - `scaler.pkl` — normalizador das features da logística
# MAGIC   (obrigatório salvar junto: o notebook 08 precisa do mesmo
# MAGIC   scaler que foi treinado aqui para normalizar os dados de entrada)

# COMMAND ----------

def salvar_pickle_no_volume(objeto, caminho_volume: str, nome: str):
    """
    Salva um objeto Python como .pkl no Volume do Databricks.
    Volumes suportam escrita direta via Python open().
    """
    with open(caminho_volume, 'wb') as f:
        pickle.dump(objeto, f)
    print(f"✓ {nome} → {caminho_volume}")


salvar_pickle_no_volume(modelo_linear,    CAMINHO_MODELO_LINEAR,    "Modelo Linear")
salvar_pickle_no_volume(modelo_logistica, CAMINHO_MODELO_LOGISTICA, "Modelo Logístico")
salvar_pickle_no_volume(scaler,           CAMINHO_SCALER,           "Scaler")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 7 — Log de auditoria do treino

# COMMAND ----------

log_treino = spark.createDataFrame([{
    "notebook": "07_regressao_linear",
    "timestamp_execucao": datetime.now(timezone.utc).isoformat(),
    "sucesso": True,
    "fonte_historico": "base_ficticia",
    "rmse_linear": rmse,
    "mae_linear": mae,
    "r2_linear": r2,
    "rmse_baseline_persistencia": rmse_baseline,
    "ganho_rmse_vs_baseline": ganho_rmse_vs_baseline,
    "alpha_ridge": alpha_ridge,
    "acuracia_logistica": acuracia,
    "amostras_treino_linear": int(len(X_train_l)),
    "amostras_treino_logistica": int(len(X_train_log)),
}])

(
    log_treino.write
    .format("delta")
    .mode("append")
    .option("mergeSchema", "true")
    .saveAsTable(tabela(SCHEMA_GOVERNANCA, "log_treino_modelos"))
)

print("✓ Log de treino registrado.")
