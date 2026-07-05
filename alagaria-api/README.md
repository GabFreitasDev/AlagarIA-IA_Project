## Fonte dos Dados

A fonte unica da API e o JSON Gold gerado pelo pipeline Databricks:

```text
risco_bairros_atual.json
```

Esse arquivo e produzido pelo notebook `08_logica_fuzzy.py`, depois que o
pipeline Bronze/Silver/Gold consolida chuva, mare, elevacao e modelos de IA
por bairro. A API nao consulta APAC, Open-Meteo ou outras fontes externas em
tempo de requisicao; ela apenas entrega o Gold em um contrato HTTP estavel.

## Como rodar

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

No Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

## Endpoints principais

### Risco por bairro (JSON Gold)

Este e o endpoint principal para o frontend:

```http
GET /risk/bairros
```

Ele le o arquivo configurado em `GOLD_RISK_JSON_PATH`, gerado pelo notebook
`08_logica_fuzzy.py` como `risco_bairros_atual.json`, e devolve uma resposta
normalizada para consumo do front.

Exemplo:

```json
{
  "city": "Recife",
  "generated_at": "2026-07-05 14:00:00",
  "source_updated_at": "2026-07-05T17:05:30+00:00",
  "neighborhoods_count": 94,
  "neighborhoods": [
    {
      "data": "2026-07-05 14:00:00",
      "municipio": "Recife",
      "bairro": "Boa Viagem",
      "rpa": 6,
      "elevacao_metros": 4.2,
      "precipitacao_atual": 12.4,
      "chuva_1h": 1.2,
      "chuva_6h": 8.5,
      "chuva_12h": 10.0,
      "chuva_24h": 12.4,
      "altura_mare": 1.8,
      "status_mare": "enchente",
      "precipitacao_prevista_24h": 35.7,
      "prob_alagamento": 0.42,
      "alagamento_previsto": "Nao",
      "score_risco": 0.4,
      "nivel_risco": "moderado"
    }
  ],
  "source": "Databricks Gold",
  "model": "gold_fuzzy_regression_v1"
}
```

Para detalhe de um bairro:

```http
GET /risk/bairros/Boa%20Viagem
```

Para inspecionar o JSON original, sem normalizacao:

```http
GET /risk/raw
```

Configuracao local:

```bash
copy .env.example .env
```

Depois ajuste `GOLD_RISK_JSON_PATH` para o arquivo exportado pelo pipeline. Em
desenvolvimento local, o caminho padrao e:

```text
data/risco_bairros_atual.json
```

### Health check

```http
GET /health
```

Resposta esperada:

```json
{
  "status": "ok",
  "app": "Recife Flood API",
  "version": "0.1.0"
}
```

## Contrato para o frontend

O frontend deve consumir o snapshot Gold normalizado:

```js
const response = await fetch("http://localhost:8000/risk/bairros");
const data = await response.json();

console.log(data.generated_at);
console.log(data.neighborhoods_count);
console.log(data.neighborhoods);
```

Campos importantes:

- `generated_at`: timestamp mais recente encontrado nos registros do Gold.
- `neighborhoods_count`: quantidade de bairros retornados; esperado: 94.
- `neighborhoods`: lista de bairros com risco, chuva, mare e previsoes.
- `neighborhoods[].bairro`: nome do bairro.
- `neighborhoods[].score_risco`: score numerico do motor fuzzy.
- `neighborhoods[].nivel_risco`: `baixo`, `moderado`, `alto` ou `critico`.
- `neighborhoods[].precipitacao_prevista_24h`: previsao de chuva em 24h.

