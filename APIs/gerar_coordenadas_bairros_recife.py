"""
Baixa o GeoJSON oficial dos bairros do Recife (Dados Abertos da Prefeitura),
calcula o centroide de cada polígono e gera um JSON pronto para uso
no notebook de ingestão da Open-Meteo Elevation API.

"""
#%pip install shapely
import json
import requests
from shapely.geometry import shape

#URL oficial — Portal de Dados Abertos da Prefeitura do Recife
GEOJSON_URL = (
    "https://dados.recife.pe.gov.br/dataset/"
    "1702c764-ec7a-4ef0-9861-8acd0e40c819/resource/"
    "5c67ce14-1799-40c4-a37c-9daa04d1761c/download/bairros-do-recife.geojson"
)

# URL alternativa (portal mais antigo)
GEOJSON_URL_ALT = (
    "http://dados.recife.pe.gov.br/dataset/"
    "c1f100f0-f56f-4dd4-9dcc-1aa4da28798a/resource/"
    "e43bee60-9448-4d3d-92ff-2378bc3b5b00/download/bairros.geojson"
)

OUTPUT_FILE = "bairros_recife_coords.json"


def baixar_geojson(url: str) -> dict:
    print(f"Baixando GeoJSON de:\n  {url}")
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def extrair_centroides(geojson: dict) -> list[dict]:
    """
    Itera sobre os features do GeoJSON, calcula o centroide de cada
    polígono/multipolígono e retorna lista de dicts com nome e coords.
    """
    registros = []

    for feature in geojson["features"]:
        props = feature.get("properties", {})

        # O campo do nome pode variar — tentamos as chaves mais comuns
        nome = (
            props.get("EBAIRRNOME")
            or props.get("NOME_BAIRRO")
            or props.get("nome_bairro")
            or props.get("NOME")
            or props.get("nome")
            or props.get("NM_BAIRRO")
            or "Desconhecido"
        )

        geom = shape(feature["geometry"])
        centroide = geom.centroid  # ponto central do polígono

        registros.append({
            "bairro":    nome.strip().title(),
            "latitude":  round(centroide.y, 6),
            "longitude": round(centroide.x, 6),
        })

    return sorted(registros, key=lambda r: r["bairro"])


def main():
    # Tenta a URL principal; cai na alternativa se falhar
    try:
        geojson = baixar_geojson(GEOJSON_URL)
    except Exception as e:
        print(f"URL principal falhou ({e}). Tentando alternativa...")
        geojson = baixar_geojson(GEOJSON_URL_ALT)

    centroides = extrair_centroides(geojson)

    print(f"\n✓ {len(centroides)} bairro(s) processado(s):\n")
    for b in centroides:
        print(f"  {b['bairro']:<30} lat={b['latitude']:>10.6f}  lon={b['longitude']:>11.6f}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(centroides, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Arquivo gerado: {OUTPUT_FILE}")
    print(f"  → {len(centroides)} registros prontos para uso no notebook.")


if __name__ == "__main__":
    main()
