def validar_schema(registros: list, campos_esperados: set, nome_fonte: str):
    """Governança: barra a ingestão se a API mudar de formato sem aviso (não é API documentada)."""
    if not registros:
        raise ValueError(f"[{nome_fonte}] resposta vazia da API — verificar disponibilidade do serviço")
    faltantes = campos_esperados - set(registros[0].keys())
    if faltantes:
        raise ValueError(f"[{nome_fonte}] campos ausentes na resposta: {faltantes}. A API pode ter mudado.")

def validar_intervalo(df, coluna: str, minimo: float, maximo: float):
    """Lança erro se algum valor estiver fora do intervalo esperado. Para a pipeline em vez de propagar dado ruim."""
    fora_do_intervalo = df.filter(f"{coluna} < {minimo} OR {coluna} > {maximo}").count()
    if fora_do_intervalo > 0:
        raise ValueError(f"{fora_do_intervalo} linhas com '{coluna}' fora de [{minimo}, {maximo}]")

def validar_nulos(df, colunas: list):
    """Garante que colunas críticas não tenham nulos antes de avançar de camada."""
    for col in colunas:
        n_nulos = df.filter(df[col].isNull()).count()
        if n_nulos > 0:
            raise ValueError(f"Coluna '{col}' tem {n_nulos} valores nulos")

def log_execucao(spark, catalogo: str, schema_governanca: str, notebook: str, linhas: int, status: str = "sucesso", observacao: str = ""):
    """Registra a execução na tabela de auditoria — rastreabilidade do pipeline para o relatório final."""
    spark.sql(f"""
        INSERT INTO {catalogo}.{schema_governanca}.log_execucoes
        VALUES ('{notebook}', current_timestamp(), {linhas}, '{status}', '{observacao}')
    """)