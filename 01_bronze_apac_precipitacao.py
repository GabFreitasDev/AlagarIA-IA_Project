# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze — Precipitação Acumulada APAC (via landing zone)
# MAGIC
# MAGIC Arquitetura atual: como o Databricks Community Edition bloqueia
# MAGIC chamadas HTTP de saída para a API da APAC, a chamada à API é
# MAGIC feita LOCALMENTE (script Python rodado no computador de um dos
# MAGIC integrantes), e o JSON resultante é enviado manualmente para a
# MAGIC landing zone deste Volume. Este notebook não faz nenhuma chamada
# MAGIC de rede — ele só lê o que já está no Volume.
# MAGIC
# MAGIC Cada arquivo representa o acumulado de UM dia (nomeado
# MAGIC `precipAcum_AAAA-MM-DD.json`, com a data do dia ANTERIOR ao da
# MAGIC coleta, já que a API só devolve o estado atual/24h).
# MAGIC
# MAGIC Este notebook processa apenas arquivos que ainda não foram
# MAGIC gravados na Bronze antes — controla isso através da tabela
# MAGIC `governanca.arquivos_processados`.
# MAGIC
# MAGIC **Responsável:** Gabriel de Freitas  
# MAGIC **Frequência de execução:** diária, após o upload manual do arquivo do dia.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 1 — Importações e parâmetros

# COMMAND ----------

import json
from pyspark.sql import functions as F
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

NOME_FONTE_PRECIP = "apac_api_local"
CODIGO_IBGE_RECIFE = 2611606
CATALOGO = "alerta_alagamento_recife"
SCHEMA_BRONZE = "bronze"

NOME_TABELA_PRECIP = f"{CATALOGO}.{SCHEMA_BRONZE}.apac_precipitacao"
NOME_TABELA_CONTROLE = f"{CATALOGO}.governanca.arquivos_processados"

caminho_landing_precip = f"/Volumes/{CATALOGO}/{SCHEMA_BRONZE}/landing_zone/apac_precipitacao/"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 2 — Descobrir quais arquivos ainda não foram processados
# MAGIC
# MAGIC Lista todos os arquivos `precipAcum*.json` na landing zone e
# MAGIC compara com a tabela de controle. Só os arquivos que ainda não
# MAGIC aparecem lá são processados nesta execução — isso evita
# MAGIC duplicar dados na Bronze se o notebook for rodado mais de uma
# MAGIC vez, ou se houver atraso entre uploads.

# COMMAND ----------

try:
    arquivos_na_landing = dbutils.fs.ls(caminho_landing_precip)
except Exception as e:
    raise RuntimeError(
        f"Não foi possível acessar a landing zone em {caminho_landing_precip}.\n"
        f"Verifique se o caminho existe e se o arquivo já foi enviado.\nErro: {e}"
    )

nomes_na_landing = {
    arquivo.name for arquivo in arquivos_na_landing
    if arquivo.name.startswith("precipAcum") and arquivo.name.endswith(".json")
}

if not nomes_na_landing:
    print(f"Nenhum arquivo precipAcum*.json encontrado em {caminho_landing_precip}.")
    nomes_ja_processados = set()
    nomes_novos = set()
else:
    # Cria a tabela de controle se ainda não existir, para a primeira
    # execução não falhar por falta da tabela.
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {NOME_TABELA_CONTROLE} (
            nome_arquivo STRING,
            fonte STRING,
            processado_em TIMESTAMP
        )
    """)

    df_controle = spark.table(NOME_TABELA_CONTROLE).filter(F.col("fonte") == NOME_FONTE_PRECIP)
    nomes_ja_processados = {
        linha["nome_arquivo"] for linha in df_controle.select("nome_arquivo").collect()
    }

    # O arquivo do dia atual é reenviado/atualizado várias vezes ao longo do dia (execuções às 3h, 11h e 19h), sempre com o MESMO nome — mas o conteúdo pode mudar entre uma execução e outra. Por isso ele nunca pode ser tratado como "definitivamente processado": precisa ser reprocessado em toda execução do dia, mesmo já constando na tabela de controle de uma rodada anterior (ex.: a das 3h).
    # O nome do arquivo carrega a data do dia ANTERIOR ao da coleta, então o arquivo "do dia atual" é o que tem a data de ontem, calculada no  fuso horário de Recife (evita erro de virada de dia perto da meia-noite).
    data_referencia_arquivo_atual = (
        datetime.now(ZoneInfo("America/Recife")) - timedelta(days=1)
    ).strftime("%Y-%m-%d")
    nome_arquivo_dia_atual = f"precipAcum_{data_referencia_arquivo_atual}.json"

    nomes_novos = nomes_na_landing - nomes_ja_processados
    ja_estava_novo = nome_arquivo_dia_atual in nomes_novos
    if nome_arquivo_dia_atual in nomes_na_landing:
        nomes_novos = nomes_novos | {nome_arquivo_dia_atual}

    print(f"Arquivos na landing zone: {len(nomes_na_landing)}")
    print(f"Já processados anteriormente: {len(nomes_ja_processados)}")
    if nome_arquivo_dia_atual in nomes_novos and not ja_estava_novo:
        print(f" Reprocessando arquivo do dia atual (pode ter sido atualizado): {nome_arquivo_dia_atual}")
    print(f"Novos/a reprocessar nesta execução: {len(nomes_novos)}")
    for nome in sorted(nomes_novos):
        print(f"  - {nome}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 3 — Leitura e validação de schema dos arquivos novos
# MAGIC
# MAGIC Lê cada arquivo novo, junta tudo em uma lista única, e valida se
# MAGIC os campos esperados estão presentes ANTES de gravar qualquer
# MAGIC coisa na Bronze — se a API mudou o formato em algum dia
# MAGIC específico, o pipeline para aqui, de forma visível.

# COMMAND ----------

CAMPOS_ESPERADOS_PRECIP = {
    "municipio", "codigo_municipio", "estacao", "latitude", "longitude",
    "bacia", "codigo_estacao", "data_hora_ultima_leitura",
    "ultima_medicao", "1_hora", "6_horas",
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


dados_precip_consolidados = []
arquivos_lidos_com_sucesso = []

for nome_arquivo in sorted(nomes_novos):
    caminho_completo = caminho_landing_precip + nome_arquivo
    try:
        conteudo_json = dbutils.fs.head(caminho_completo, 1024 * 1024 * 10)
        dados_arquivo = json.loads(conteudo_json)

        if isinstance(dados_arquivo, list):
            dados_precip_consolidados.extend(dados_arquivo)
        else:
            dados_precip_consolidados.append(dados_arquivo)

        arquivos_lidos_com_sucesso.append(nome_arquivo)

    except Exception as e:
        # Um arquivo corrompido não deve impedir o processamento dos
        # outros arquivos novos — registra o problema e continua.
        print(f"[ALERTA] Falha ao ler {nome_arquivo}, pulando este arquivo: {e}")

if dados_precip_consolidados:
    validar_schema(dados_precip_consolidados, CAMPOS_ESPERADOS_PRECIP, NOME_FONTE_PRECIP)
    print(f"✓ Schema validado — {len(dados_precip_consolidados)} registro(s) de "
          f"{len(arquivos_lidos_com_sucesso)} arquivo(s) novo(s).")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 4 — Transformação mínima e filtro de Recife

# COMMAND ----------

if dados_precip_consolidados:
    # Normalizar tipos dos campos numéricos antes de criar o DataFrame
    # A API retorna tipos mistos (int/float/str) para os mesmos campos
    def normalizar_numerico(valor):
        """Converte qualquer valor numérico para float, mantendo None como None."""
        if valor is None:
            return None
        try:
            return float(valor)
        except (ValueError, TypeError):
            return None
    
    campos_numericos = [
        "ultima_medicao", "1_hora", "3_horas", "6_horas",
        "12_horas", "24_horas", "48_horas", "72_horas",
        "96_horas", "120_horas"
    ]
    
    for registro in dados_precip_consolidados:
        for campo in campos_numericos:
            if campo in registro:
                registro[campo] = normalizar_numerico(registro[campo])
    
    from pyspark.sql.types import StructType, StructField, StringType, IntegerType, FloatType
    
    schema = StructType([
        StructField("municipio", StringType(), True),
        StructField("codigo_municipio", IntegerType(), True),
        StructField("estacao", StringType(), True),
        StructField("latitude", FloatType(), True),
        StructField("longitude", FloatType(), True),
        StructField("bacia", StringType(), True),
        StructField("codigo_estacao", StringType(), True),
        StructField("data_hora_ultima_leitura", StringType(), True),
        StructField("precipitacao", FloatType(), True),
        StructField("ultima_medicao", FloatType(), True),
        StructField("1_hora", FloatType(), True),
        StructField("3_horas", FloatType(), True),
        StructField("6_horas", FloatType(), True),
        StructField("12_horas", FloatType(), True),
        StructField("24_horas", FloatType(), True),
        StructField("48_horas", FloatType(), True),
        StructField("72_horas", FloatType(), True),
        StructField("96_horas", FloatType(), True),
        StructField("120_horas", FloatType(), True),
    ])
    
    df_bronze_precip = spark.createDataFrame(dados_precip_consolidados, schema=schema)

    df_bronze_precip = df_bronze_precip.filter(
        F.col("codigo_municipio") == CODIGO_IBGE_RECIFE
    )

    print(f"✓ {df_bronze_precip.count()} registro(s) de Recife confirmados.")
else:
    df_bronze_precip = None
    print("Nada novo para processar nesta execução.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bloco 5 — Metadados de auditoria e gravação na Bronze

# COMMAND ----------

data_execucao = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")

if df_bronze_precip is not None:
    df_bronze_precip = (
        df_bronze_precip
        .withColumn("_ingerido_em", F.current_timestamp())
        .withColumn("_fonte", F.lit(NOME_FONTE_PRECIP))
        .withColumn("_data_execucao", F.lit(data_execucao))
    )

    (
        df_bronze_precip.write
        .format("delta")
        .mode("append")
        .partitionBy("_data_execucao")
        .option("mergeSchema", "true")
        .saveAsTable(f"{CATALOGO}.{SCHEMA_BRONZE}.apac_precipitacao_recife")
    )

    spark.sql(f"""
        COMMENT ON TABLE {CATALOGO}.{SCHEMA_BRONZE}.apac_precipitacao_recife IS
        'Precipitação acumulada por estação da APAC (1h/6h/24h/...), dado cru
        sem transformação. Fonte: api.apac.pe.gov.br/api.php/precipitacao_acumulada.
        Ingestão manual via script local + upload na landing zone (API bloqueada
        para chamadas de datacenter). Particionado por _data_execucao.'
    """)

    print(f"OK — {df_bronze_precip.count()} registros gravados em "f"{CATALOGO}.{SCHEMA_BRONZE}.apac_precipitacao_recife")
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
# MAGIC
# MAGIC Só registra como "processado" os arquivos que de fato foram
# MAGIC lidos com sucesso (Bloco 3) — se um arquivo falhou na leitura,
# MAGIC ele NÃO entra aqui, e será tentado novamente na próxima execução.

# COMMAND ----------

if arquivos_lidos_com_sucesso:
    df_controle_novo = spark.createDataFrame([
        {
            "nome_arquivo": nome,
            "fonte": NOME_FONTE_PRECIP,
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
    "notebook": "01_bronze_apac_precipitacao",
    "timestamp_execucao": datetime.now(timezone.utc).isoformat(),
    "sucesso": resultado["sucesso"],
    "tentativas": resultado["tentativas"],
    "erro": resultado["erro"] if resultado["erro"] is not None else "",
    "linhas_gravadas": df_bronze_precip.count() if df_bronze_precip is not None else 0,
}])

(
    log_execucao.write
    .format("delta")
    .mode("append")
    .saveAsTable(f"{CATALOGO}.governanca.log_ingestao")
)
