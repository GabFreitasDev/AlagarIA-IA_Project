"""
Encapsula a chamada HTTP à Open-Meteo Elevation API com retry e backoff.

Endpoint:
    GET https://api.open-meteo.com/v1/elevation
        ?latitude=<lat1,lat2,...>
        &longitude=<lon1,lon2,...>
"""

import time
import requests

# configuração 

BASE_URL      = "https://api.open-meteo.com/v1/elevation"
MAX_TENTATIVAS = 3
BACKOFF_BASE   = 2.0   # segundos de espera: 2s, 4s, 8s 
TIMEOUT        = 10    # segundos por requisição

# função pública 


def fetch_elevation_data(
    latitudes: list[float],
    longitudes: list[float],
) -> dict:
    """
    Consulta a Open-Meteo Elevation API para uma lista de coordenadas.
    Parâmetros:
    latitudes  : lista de latitudes  (WGS84, graus decimais)
    longitudes : lista de longitudes (WGS84, graus decimais)

    """
    if len(latitudes) != len(longitudes):
        return {
            "sucesso":    False,
            "dados":      None,
            "tentativas": 0,
            "erro":       (
                f"Listas de tamanhos diferentes: "
                f"{len(latitudes)} lat(s) vs {len(longitudes)} lon(s)."
            ),
        }

    if len(latitudes) > 100:
        return {
            "sucesso":    False,
            "dados":      None,
            "tentativas": 0,
            "erro":       (
                f"A API aceita no máximo 100 pares de coordenadas por chamada; "
                f"foram fornecidos {len(latitudes)}."
            ),
        }

    params = {
        "latitude":  ",".join(str(lat) for lat in latitudes),
        "longitude": ",".join(str(lon) for lon in longitudes),
    }

    ultimo_erro: str | None = None

    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            response = requests.get(BASE_URL, params=params, timeout=TIMEOUT)

            # A API devolve HTTP 400 com JSON de erro para parâmetros inválidos
            if response.status_code == 400:
                payload = response.json()
                ultimo_erro = payload.get("reason", "Erro 400 sem detalhe.")
                # Erro de parâmetro: não adianta tentar de novo
                break

            response.raise_for_status()

            payload = response.json()

            # Defesa extra: a chave "elevation" deve existir
            if "elevation" not in payload:
                ultimo_erro = (
                    f"Resposta inesperada da API (sem campo 'elevation'): "
                    f"{list(payload.keys())}"
                )
                # Pode ser instabilidade transitória — vale tentar de novo
                raise ValueError(ultimo_erro)

            return {
                "sucesso":    True,
                "dados":      payload,
                "tentativas": tentativa,
                "erro":       None,
            }

        except (requests.exceptions.RequestException, ValueError) as exc:
            ultimo_erro = str(exc)
            print(
                f"[elevation_client] Tentativa {tentativa}/{MAX_TENTATIVAS} falhou: "
                f"{ultimo_erro}"
            )
            if tentativa < MAX_TENTATIVAS:
                espera = BACKOFF_BASE ** tentativa
                print(f"[elevation_client] Aguardando {espera:.0f}s antes de tentar novamente...")
                time.sleep(espera)

    return {
        "sucesso":    False,
        "dados":      None,
        "tentativas": MAX_TENTATIVAS,
        "erro":       ultimo_erro,
    }
