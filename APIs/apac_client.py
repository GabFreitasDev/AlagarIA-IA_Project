"""
-----------------------------------------------------------------
                RODANDO LOCALMENTE PELO TERMINAL!!
-----------------------------------------------------------------

Módulo de ingestão: API da APAC (precipitação acumulada em tempo real).

Diferença em relação à versão anterior:
1. Esta API NÃO tem parâmetro de intervalo de datas — ela só devolve o
   estado atual das estações (1h/6h/24h acumulado até agora). Por isso,
   não existe "buscar histórico" aqui; isso é responsabilidade do
   notebook que consome a Open-Meteo, que é uma fonte diferente.
2. Adicionado retry com backoff exponencial: timeout de conexão é um
   evento ESPERADO para uma API pública estadual sem SLA, não uma
   exceção rara. O código precisa tentar novamente antes de desistir,
   em vez de falhar na primeira tentativa.
"""

import requests
import time
from datetime import datetime, timezone

APAC_API_URL = "https://api.apac.pe.gov.br/api.php/precipitacao_acumulada"


def fetch_apac_data(
    municipio: str = "Recife",
    timeout_seconds: int = 15,
    max_tentativas: int = 3,
) -> dict:
    """
    Faz a chamada HTTP para a API da APAC, com retry automático.

    Parâmetros:
        municipio: filtro aplicado já na própria chamada à API (mais
                   eficiente do que buscar tudo e filtrar depois no Spark).
        timeout_seconds: tempo máximo de espera POR TENTATIVA. Reduzido
                   de 30 para 15s: se a API não respondeu em 15s, é mais
                   eficiente desistir e tentar de novo do que ficar
                   esperando os 30s completos a cada vez.
        max_tentativas: quantas vezes tentar antes de desistir de vez.

    Retorna:
        dict com sucesso/dados/erro/tentativas, no mesmo padrão usado
        pelos outros clientes (openmeteo_client.py, dhn_client.py).
    """
    timestamp_busca = datetime.now(timezone.utc).isoformat()
    parametros = {"municipio": municipio}

    ultimo_erro = None

    for tentativa in range(1, max_tentativas + 1):
        try:
            resposta = requests.get(
                APAC_API_URL,
                params=parametros,
                timeout=timeout_seconds,
            )
            resposta.raise_for_status()

            return {
                "sucesso": True,
                "dados": resposta.json(),
                "timestamp_busca": timestamp_busca,
                "status_code": resposta.status_code,
                "erro": None,
                "tentativas": tentativa,
            }

        except requests.exceptions.RequestException as e:
            ultimo_erro = str(e)
            print(f"[tentativa {tentativa}/{max_tentativas}] falhou: {ultimo_erro}")

            # Backoff exponencial: espera 2s, depois 4s, depois 8s...
            # Dá tempo para uma instabilidade momentânea do servidor se
            # resolver, em vez de martelar a API sem intervalo.
            if tentativa < max_tentativas:
                time.sleep(2 ** tentativa)

    # Todas as tentativas falharam — devolve erro estruturado.
    # Não lançamos exceção: quem chama esta função decide o que fazer
    # (ex: não escrever nada na Bronze nesta execução, mas registrar
    # o log de falha e seguir adiante sem quebrar o Job).
    return {
        "sucesso": False,
        "dados": None,
        "timestamp_busca": timestamp_busca,
        "status_code": None,
        "erro": ultimo_erro,
        "tentativas": max_tentativas,
    }