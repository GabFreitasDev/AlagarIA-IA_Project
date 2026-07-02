"""
----------------------------------------------------------------
                RODANDO LOCALMENTE PELO TERMINAL!!
----------------------------------------------------------------

Módulo de ingestão: API da APAC (tábua de marés).

Correção de nomenclatura importante: esta fonte NÃO é do DHN/Marinha.
É a mesma API da APAC usada na precipitação (api.apac.pe.gov.br),
só que um endpoint diferente dela: /api.php/mare em vez de
/api.php/precipitacao_acumulada.

O parâmetro confirmado por teste manual (navegador/Postman) é `codigo`
(código IBGE do município), e não `municipio` (texto) como na
precipitação, nem `estacao` como havia sido assumido antes de testar.
APIs diferentes do mesmo provedor às vezes usam convenções de
parâmetro diferentes entre si, então vale sempre confirmar testando,
como foi feito aqui.
"""

import requests
import time
from datetime import datetime, timezone, date

APAC_MARE_API_URL = "https://api.apac.pe.gov.br/api.php/mare"

def fetch_apac_mare(
    codigo: int = 2611606,
    data: str = None,
    timeout_seconds: int = 20,
    max_tentativas: int = 3,
) -> dict:
    """
    Busca a tábua de marés da APAC para um município e data, com
    retry automático em caso de instabilidade de rede.

    Parâmetros:
        codigo: código IBGE do município (default: Recife).
        data: data no formato "AAAA-MM-DD". Se None, a
                          função usa a data de HOJE automaticamente,
                          calculada no momento da chamada (não no
                          momento em que o módulo foi importado —
                          por isso o cálculo fica dentro do corpo da
                          função, e não como valor default direto na
                          assinatura).
        timeout_seconds: tempo máximo de espera POR TENTATIVA.
        max_tentativas: quantas vezes tentar antes de desistir de vez.

    Retorna:
        dict com sucesso/dados/erro/tentativas — mesmo formato usado
        por fetch_apac_data (precipitação), para que o notebook trate
        as duas fontes da mesma maneira.
    """
    # Se nenhuma data foi passada, usa hoje. Calculado AQUI (em tempo
    # de execução), não como default na assinatura — um default
    # calculado na assinatura seria fixado uma única vez, no momento
    # em que o módulo é importado, e não seria atualizado nas
    # chamadas seguintes na mesma sessão do notebook.
    if data is None:
        data = date.today().isoformat()

    timestamp_busca = datetime.now(timezone.utc).isoformat()

    parametros = {"codigo": codigo, "data": data}

    ultimo_erro = None

    for tentativa in range(1, max_tentativas + 1):
        try:
            resposta = requests.get(
                APAC_MARE_API_URL,
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

            if tentativa < max_tentativas:
                time.sleep(2 ** tentativa)

    return {
        "sucesso": False,
        "dados": None,
        "timestamp_busca": timestamp_busca,
        "status_code": None,
        "erro": ultimo_erro,
        "tentativas": max_tentativas,
    }