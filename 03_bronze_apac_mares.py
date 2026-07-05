# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze — Tábua de Marés APAC (via landing zone)
# MAGIC
# MAGIC Mesma arquitetura do notebook de precipitação: a chamada à API é
# MAGIC feita LOCALMENTE (script Python no computador de um dos
# MAGIC integrantes, pedindo explicitamente a data do dia anterior), e o
# MAGIC JSON resultante é enviado manualmente para a landing zone deste
# MAGIC Volume. Este notebook não faz nenhuma chamada de rede.
# MAGIC
# MAGIC Cada arquivo representa a tábua de maré de UM dia (nomeado
# MAGIC `mare_AAAA-MM-DD.json`).
# MAGIC
# MAGIC Processa apenas arquivos que ainda não foram gravados na Bronze
# MAGIC antes, controlando isso pela tabela `governanca.arquivos_processados`
# MAGIC — a mesma tabela de controle usada pelo notebook de precipitação,
# MAGIC distinguindo as fontes pela coluna `fonte`.
# MAGIC
# MAGIC **Responsável:** Gabriel de Freitas   
# MAGIC **Frequência de execução:** diária, após o upload manual do arquivo do dia.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 1 — Importações e parâmetros

# COMMAND ----------

import json
from pyspark.sql import functions as F
from datetime import datetime, timezone

NOME_FONTE_MARE = "apac_mare_api_local"
CATALOGO = "alerta_alagamento_recife"
SCHEMA_BRONZE = "bronze"

NOME_TABELA_MARE = f"{CATALOGO}.{SCHEMA_BRONZE}.apac_mares"
NOME_TABELA_CONTROLE = f"{CATALOGO}.governanca.arquivos_processados"

caminho_landing_mare = f"/Volumes/{CATALOGO}/{SCHEMA_BRONZE}/landing_zone/apac_mare/"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 2 — Descobrir quais arquivos ainda não foram processados

# COMMAND ----------

try:
    arquivos_na_landing = dbutils.fs.ls(caminho_landing_mare)
except Exception as e:
    raise RuntimeError(
        f"Não foi possível acessar a landing zone em {caminho_landing_mare}.\n"
        f"Verifique se o caminho existe e se o arquivo já foi enviado.\nErro: {e}"
    )

nomes_na_landing = {
    arquivo.name for arquivo in arquivos_na_landing
    if arquivo.name.startswith("mare") and arquivo.name.endswith(".json")
}

if not nomes_na_landing:
    print(f"Nenhum arquivo mare_*.json encontrado em {caminho_landing_mare}.")
    nomes_ja_processados = set()
    nomes_novos = set()
else:
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {NOME_TABELA_CONTROLE} (
            nome_arquivo STRING,
            fonte STRING,
            processado_em TIMESTAMP
        )
    """)

    df_controle = spark.table(NOME_TABELA_CONTROLE).filter(F.col("fonte") == NOME_FONTE_MARE)
    nomes_ja_processados = {
        linha["nome_arquivo"] for linha in df_controle.select("nome_arquivo").collect()
    }

    nomes_novos = nomes_na_landing - nomes_ja_processados

    print(f"Arquivos na landing zone: {len(nomes_na_landing)}")
    print(f"Já processados anteriormente: {len(nomes_ja_processados)}")
    print(f"Novos a processar nesta execução: {len(nomes_novos)}")
    for nome in sorted(nomes_novos):
        print(f"  - {nome}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 3 — Leitura e validação de schema dos arquivos novos
# MAGIC
# MAGIC Lê cada arquivo novo, junta tudo em uma lista única, e valida se os campos esperados estão presentes ANTES de gravar qualquer coisa na Bronze — se a API mudou o formato em algum dia específico, o pipeline para aqui, de forma visível.

# COMMAND ----------

CAMPOS_ESPERADOS_MARE = {
    "municipio", "codigo_municipio", "praia", "id_praia", "latitude", "longitude", "data", "dia_semana", "altura", "status", "ponto_referencia",
}


def validar_schema(dados: list, campos_esperados: set, nome_fonte: str) -> None:
    if not dados:
        raise RuntimeError(f"[{nome_fonte}] nenhum dado para validar.")
    campos_recebidos = set(dados[0].keys())
    campos_faltando = campos_esperados - campos_recebidos
    if campos_faltando:
        raise RuntimeError(
            f"[{nome_fonte}] schema mudou — campos ausentes: {campos_faltando}. "
            f"Pipeline interrompido para evitar gravar dado incompleto."
        )


dados_mare_consolidados = []
arquivos_lidos_com_sucesso = []

for nome_arquivo in sorted(nomes_novos):
    caminho_completo = caminho_landing_mare + nome_arquivo
    try:
        conteudo_json = dbutils.fs.head(caminho_completo, 1024 * 1024 * 10)
        dados_arquivo = json.loads(conteudo_json)

        if isinstance(dados_arquivo, list):
            dados_mare_consolidados.extend(dados_arquivo)
        else:
            dados_mare_consolidados.append(dados_arquivo)

        arquivos_lidos_com_sucesso.append(nome_arquivo)

    except Exception as e:
        print(f"[ALERTA] Falha ao ler {nome_arquivo}, pulando este arquivo: {e}")

if dados_mare_consolidados:
    validar_schema(dados_mare_consolidados, CAMPOS_ESPERADOS_MARE, NOME_FONTE_MARE)
    print(f"✓ Schema validado — {len(dados_mare_consolidados)} registro(s) de "
          f"{len(arquivos_lidos_com_sucesso)} arquivo(s) novo(s).")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 4 — Transformação mínima (estruturação como DataFrame)
# MAGIC
# MAGIC Diferente da precipitação, aqui não há filtro adicional a
# MAGIC aplicar — a chamada já foi feita para o código IBGE de Recife
# MAGIC especificamente, no próprio script local.

# COMMAND ----------

if dados_mare_consolidados:
    # Normalizar campos numéricos para float para evitar erro de tipo misto
    for record in dados_mare_consolidados:
        if 'altura' in record and isinstance(record['altura'], int):
            record['altura'] = float(record['altura'])
        if 'latitude' in record and isinstance(record['latitude'], int):
            record['latitude'] = float(record['latitude'])
        if 'longitude' in record and isinstance(record['longitude'], int):
            record['longitude'] = float(record['longitude'])
    
    df_bronze_mare = spark.createDataFrame(dados_mare_consolidados)
    print(f"✓ {df_bronze_mare.count()} registro(s) de maré carregados.")
else:
    df_bronze_mare = None
    print("Nada novo para processar nesta execução.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 5 — Metadados de auditoria e gravação na Bronze

# COMMAND ----------

data_execucao = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")

if df_bronze_mare is not None:
    df_bronze_mare = (
        df_bronze_mare
        .withColumn("_ingerido_em", F.current_timestamp())
        .withColumn("_fonte", F.lit(NOME_FONTE_MARE))
        .withColumn("_data_execucao", F.lit(data_execucao))
    )

    (
        df_bronze_mare.write
        .format("delta")
        .mode("append")
        .partitionBy("_data_execucao")
        .option("mergeSchema", "true")
        .saveAsTable(f"{CATALOGO}.{SCHEMA_BRONZE}.apac_mare_recife")
    )

    spark.sql(f"""
        COMMENT ON TABLE {CATALOGO}.{SCHEMA_BRONZE}.apac_mare_recife IS
        'Tábua de marés da APAC para Recife, dado cru sem transformação.
        Fonte: api.apac.pe.gov.br/api.php/mare. Ingestão manual via script
        local + upload na landing zone (API bloqueada para chamadas de
        datacenter). Particionado por _data_execucao.'
    """)

    print(f"OK — {df_bronze_mare.count()} registros gravados em "f"{CATALOGO}.{SCHEMA_BRONZE}.apac_mare_recife")
    resultado = {
        "sucesso": True,
        "tentativas": 1,
        "erro": None
    }
else:
    print("Nenhum registro gravado nesta execução.")
    resultado = {
        "sucesso": True,
        "tentativas": 1,
        "erro": None
    }

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 6 — Atualizar a tabela de controle de arquivos processados

# COMMAND ----------

if arquivos_lidos_com_sucesso:
    df_controle_novo = spark.createDataFrame([
        {
            "nome_arquivo": nome,
            "fonte": NOME_FONTE_MARE,
            "processado_em": datetime.now(timezone.utc),
        }
        for nome in arquivos_lidos_com_sucesso
    ])

    (
        df_controle_novo.write
        .format("delta")
        .mode("append")
        .saveAsTable(NOME_TABELA_CONTROLE)
    )

    print(f"✓ {len(arquivos_lidos_com_sucesso)} arquivo(s) marcado(s) como processado(s).")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 7 — Log de auditoria da execução

# COMMAND ----------

log_execucao = spark.createDataFrame([{
    "notebook": "03_bronze_apac_mares",
    "timestamp_execucao": datetime.now(timezone.utc).isoformat(),
    "sucesso": resultado["sucesso"],
    "tentativas": resultado["tentativas"],
    "erro": resultado["erro"] if resultado["erro"] is not None else "",
    "linhas_gravadas": df_bronze_mare.count() if df_bronze_mare is not None else 0,
}])

(
    log_execucao.write
    .format("delta")
    .mode("append")
    .saveAsTable(f"{CATALOGO}.governanca.log_ingestao")
)
