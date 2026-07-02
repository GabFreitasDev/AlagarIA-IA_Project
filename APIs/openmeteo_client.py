"""
Módulo de ingestão: API da Open-Meteo (histórico de chuva).

Usado para alimentar a base que vai treinar o Algoritmo Genético.
Diferente da APAC (tempo real), aqui buscamos um INTERVALO de datas passadas.
"""

import requests
from datetime import datetime, timezone

OPENMETEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# Coordenadas do Recife. Em uma versão futura, isso pode virar uma lista
# de coordenadas (uma por bairro), mas para o MVP da Sprint 1, um ponto
# representativo da cidade já é suficiente para destravar o AG.
LATITUDE_RECIFE = -8.0476
LONGITUDE_RECIFE = -34.8770


def fetch_openmeteo_historico(
    data_inicio: str,
    data_fim: str,
    timeout_seconds: int = 30,
) -> dict:
    """
    Busca a série histórica de precipitação horária para Recife.

    Parâmetros:
        data_inicio: data no formato "AAAA-MM-DD" (ex: "2026-01-01")
        data_fim:    data no formato "AAAA-MM-DD" (ex: "2026-06-01")
        timeout_seconds: tempo máximo de espera pela API

    Retorna:
        dict no mesmo padrão do cliente da APAC (sucesso/dados/erro),
        para que o notebook trate as duas fontes da mesma forma.
    """
    timestamp_busca = datetime.now(timezone.utc).isoformat()

    parametros = {
        "latitude": LATITUDE_RECIFE,
        "longitude": LONGITUDE_RECIFE,
        "start_date": data_inicio,
        "end_date": data_fim,
        "hourly": "precipitation",  # variável que nos interessa: chuva por hora
        "timezone": "America/Recife",
    }

    try:
        resposta = requests.get(
            OPENMETEO_ARCHIVE_URL, params=parametros, timeout=timeout_seconds
        )
        resposta.raise_for_status()

        return {
            "sucesso": True,
            "dados": resposta.json(),
            "timestamp_busca": timestamp_busca,
            "status_code": resposta.status_code,
            "erro": None,
        }

    except requests.exceptions.RequestException as e:
        return {
            "sucesso": False,
            "dados": None,
            "timestamp_busca": timestamp_busca,
            "status_code": None,
            "erro": str(e),
        }
