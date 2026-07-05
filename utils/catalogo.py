CATALOGO = "alerta_alagamento_recife"
SCHEMA_BRONZE = "bronze"
SCHEMA_SILVER = "silver"
SCHEMA_GOLD = "gold"
SCHEMA_GOVERNANCA = "governanca"
CODIGO_IBGE_RECIFE = 2611606

def tabela(schema: str, nome: str) -> str:
    """Monta o caminho completo catalogo.schema.tabela, evitando hardcode espalhado pelos notebooks."""
    return f"{CATALOGO}.{schema}.{nome}"