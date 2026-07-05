# Databricks notebook source
# MAGIC %md
# MAGIC # Gold — Snapshot mais recente por bairro, exportado como JSON
# MAGIC
# MAGIC Este notebook pega a tabela `silver.dados_por_bairro` (que
# MAGIC acumula histórico ao longo do dia — até 282 linhas: 94 bairros ×
# MAGIC 3 horários de maré) e gera um JSON com APENAS o registro MAIS
# MAGIC RECENTE de cada bairro (94 objetos), no formato:
# MAGIC
# MAGIC ```json
# MAGIC [
# MAGIC   {"data": "...", "municipio": "Recife", "RPA": 6, "Bairro": "Boa Viagem", ...},
# MAGIC   {"data": "...", "municipio": "Recife", "RPA": 6, "Bairro": "Ipsep", ...},
# MAGIC   ...
# MAGIC ]
# MAGIC ```
# MAGIC
# MAGIC O arquivo é sobrescrito a cada execução — sempre reflete o estado
# MAGIC mais atual possível no momento em que este notebook roda.
# MAGIC
# MAGIC **Responsável:** Gabriel de Freitas  
# MAGIC **Frequência de execução:** logo após cada execução do notebook 04
# MAGIC (mesma rotina de 07h/14h/21h).

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 1 — Importações e parâmetros

# COMMAND ----------

import sys
sys.path.append("/Workspace/Users/gabriel.fo.br@gmail.com/AlagarIA-IA_Project/utils")

from utils.catalogo import tabela, CATALOGO, SCHEMA_SILVER, SCHEMA_GOLD, SCHEMA_GOVERNANCA

from pyspark.sql import functions as F
from pyspark.sql.window import Window
from datetime import datetime, timezone

# Caminho do Volume onde o JSON final fica disponível para o backend
# consumir. Ajustar conforme o Volume real já criado no catálogo de vocês.
CAMINHO_GOLD_JSON = f"/Volumes/{CATALOGO}/{SCHEMA_GOLD}/exportacoes/dados_bairros_atual"
NOME_ARQUIVO_FINAL = "dados_bairros_atual.json"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 2 — Carregar a Silver e manter só o registro mais recente por bairro
# MAGIC
# MAGIC Usamos uma window function particionada por `Bairro`, ordenada
# MAGIC por `data` decrescente — isso é a forma correta no Spark de
# MAGIC pegar "a última linha de cada grupo" sem precisar de loop manual
# MAGIC ou de trazer tudo para o driver antes da hora.

# COMMAND ----------

df_silver = spark.table(tabela(SCHEMA_SILVER, "dados_por_bairro"))

janela_por_bairro = Window.partitionBy("Bairro").orderBy(F.col("data").desc())

df_mais_recente = (
    df_silver
    .withColumn("_ordem", F.row_number().over(janela_por_bairro))
    .filter(F.col("_ordem") == 1)
    .drop("_ordem")
)

quantidade = df_mais_recente.count()
print(f"✓ {quantidade} bairro(s) no snapshot mais recente.")

assert quantidade == 94, (
    f"Esperado snapshot de 94 bairros, mas encontrado {quantidade}. "
    f"Verifique se a tabela silver.dados_por_bairro está completa antes de exportar."
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 3 — Checagem de qualidade antes de exportar
# MAGIC
# MAGIC Não exportamos um JSON com lacunas sem avisar. Se algum bairro
# MAGIC estiver com `precipitacao` ou `altura` nulos (por exemplo, por
# MAGIC causa de uma RPA sem estação ativa, caso já tratado no notebook
# MAGIC 04), isso é reportado aqui — mas NÃO impede a exportação, porque
# MAGIC o backend ainda precisa do JSON mesmo com dados parciais; só
# MAGIC achamos melhor o time saber que aquilo aconteceu.

# COMMAND ----------

bairros_com_chuva_nula = df_mais_recente.filter(F.col("precipitacao").isNull()).select("Bairro", "RPA").collect()
bairros_com_mare_nula = df_mais_recente.filter(F.col("altura").isNull()).select("Bairro", "RPA").collect()

if bairros_com_chuva_nula:
    print(f"[ALERTA] {len(bairros_com_chuva_nula)} bairro(s) sem dado de chuva nesta exportação:")
    for linha in bairros_com_chuva_nula:
        print(f"  - {linha['Bairro']} (RPA {linha['RPA']})")

if bairros_com_mare_nula:
    print(f"[ALERTA] {len(bairros_com_mare_nula)} bairro(s) sem dado de maré nesta exportação:")
    for linha in bairros_com_mare_nula:
        print(f"  - {linha['Bairro']} (RPA {linha['RPA']})")

if not bairros_com_chuva_nula and not bairros_com_mare_nula:
    print("✓ Nenhuma lacuna de dado encontrada — todos os 94 bairros completos.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 4 — Exportar como um único arquivo JSON
# MAGIC
# MAGIC Por padrão, `df.write.json(...)` no Spark gera um DIRETÓRIO com
# MAGIC vários arquivos-parte (comportamento normal de processamento
# MAGIC distribuído) — não um único `.json` limpo. Como o backend precisa
# MAGIC de um arquivo único e previsível, fazemos duas coisas:
# MAGIC 1. `coalesce(1)` força tudo para uma única partição antes de
# MAGIC    escrever, gerando só um arquivo-parte.
# MAGIC 2. Depois, localizamos esse arquivo-parte e o copiamos/renomeamos
# MAGIC    para o nome final fixo que o backend vai sempre procurar.

# COMMAND ----------

caminho_temporario = CAMINHO_GOLD_JSON + "_tmp"

(
    df_mais_recente
    .coalesce(1)
    .write
    .mode("overwrite")
    .json(caminho_temporario)
)

# Localiza o arquivo-parte gerado pelo Spark (nome começa com "part-")
arquivos_gerados = dbutils.fs.ls(caminho_temporario)
arquivo_parte = [a.path for a in arquivos_gerados if a.name.startswith("part-") and a.name.endswith(".json")]

if not arquivo_parte:
    raise RuntimeError(
        f"Nenhum arquivo part-*.json encontrado em {caminho_temporario} após a escrita. "
        f"Verifique se a exportação ocorreu corretamente."
    )

caminho_final = f"{CAMINHO_GOLD_JSON.rsplit('/', 1)[0]}/{NOME_ARQUIVO_FINAL}"

# Spark grava em formato "JSON lines" (um objeto JSON por linha, sem
# colchetes envolvendo tudo). O backend provavelmente espera um array
# JSON de verdade ([{...}, {...}]), então convertemos aqui.
conteudo_linhas = dbutils.fs.head(arquivo_parte[0], 1024 * 1024 * 20)
linhas_json = [linha for linha in conteudo_linhas.strip().split("\n") if linha.strip()]

import json
registros = [json.loads(linha) for linha in linhas_json]

dbutils.fs.put(caminho_final, json.dumps(registros, ensure_ascii=False, indent=2), overwrite=True)

# Limpa o diretório temporário, já que só precisávamos dele de passagem
dbutils.fs.rm(caminho_temporario, recurse=True)

print(f"OK — JSON final exportado em: {caminho_final}")
print(f"({len(registros)} bairro(s) no arquivo)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 5 — Log de auditoria da execução

# COMMAND ----------

log_execucao = spark.createDataFrame([{
    "notebook": "05_silver_to_gold",
    "timestamp_execucao": datetime.now(timezone.utc).isoformat(),
    "sucesso": True,
    "bairros_exportados": len(registros),
    "bairros_chuva_nula": len(bairros_com_chuva_nula),
    "bairros_mare_nula": len(bairros_com_mare_nula),
    "caminho_arquivo": caminho_final,
}])

(
    log_execucao.write
    .format("delta")
    .mode("append")
    .saveAsTable(tabela(SCHEMA_GOVERNANCA, "log_ingestao_gold"))
)
