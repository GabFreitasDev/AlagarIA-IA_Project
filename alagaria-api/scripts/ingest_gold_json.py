from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_API_URL = "http://127.0.0.1:8000/ingestao"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Envia um arquivo JSON Gold para o endpoint de ingestao da alagaria-api.",
    )
    parser.add_argument(
        "json_path",
        type=Path,
        help="Caminho do arquivo risco_bairros_atual.json ou equivalente.",
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_API_URL,
        help=f"Endpoint de ingestao. Padrao: {DEFAULT_API_URL}",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    json_path = args.json_path.resolve()

    if not json_path.exists():
        print(f"Arquivo nao encontrado: {json_path}", file=sys.stderr)
        return 1

    try:
        payload = json.loads(json_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        print(f"JSON invalido em {json_path}: {exc}", file=sys.stderr)
        return 1

    if not isinstance(payload, list):
        print("JSON Gold invalido: esperado um array de bairros.", file=sys.stderr)
        return 1

    request = urllib.request.Request(
        args.url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        print(f"API retornou HTTP {exc.code}: {error_body}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"Nao foi possivel conectar em {args.url}: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(response_payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
