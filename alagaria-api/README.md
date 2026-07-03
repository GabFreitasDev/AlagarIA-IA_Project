## Fonte dos dados

A API usa o serviço público ArcGIS da APAC:

`https://geoportal.apac.pe.gov.br/server/rest/services/met_monitoramento_chuvas_pe/MapServer`

Camadas usadas:

| Intervalo | Layer |
|---|---:|
| 1h | 0 |
| 3h | 1 |
| 6h | 2 |
| 12h | 3 |
| 24h | 4 |
| 48h | 5 |
| 72h | 6 |

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

### Dados brutos da APAC

```http
GET /rain/raw/{hours}
```

Exemplo:

```http
GET /rain/raw/24
```

Use este endpoint para inspecionar o JSON original da APAC.

### Chuva em Recife por intervalo

```http
GET /rain/recife/{hours}
```

Exemplo:

```http
GET /rain/recife/24
```

### Chuva em Recife para vários intervalos

```http
GET /rain/recife?intervals=1,3,6,12,24
```

### Predição inicial de risco

```http
GET /predict/recife
```

Resposta esperada:

```json
{
  "city": "Recife",
  "flood_probability": 0.4,
  "risk_level": "moderado",
  "risk_score": 40,
  "rain": {
    "1h": 0.0,
    "3h": 32.0,
    "6h": 55.0,
    "12h": 55.0,
    "24h": 60.0
  },
  "explanation": [
    "Chuva acumulada em 3h atingiu 32.0 mm, acima do limiar de 30 mm."
  ],
  "source": "APAC Geoportal",
  "model": "rule_based_baseline_v1"
}
```

## Contrato para o frontend

O frontend só precisa consumir:

```js
const response = await fetch("http://localhost:8000/predict/recife");
const data = await response.json();

console.log(data.flood_probability);
console.log(data.risk_level);
console.log(data.rain);
```

Campos importantes:

- `flood_probability`: número entre 0 e 1.
- `risk_level`: `baixo`, `moderado` ou `alto`.
- `risk_score`: pontuação de 0 a 100.
- `rain`: chuva máxima encontrada por intervalo.
- `explanation`: motivos usados no cálculo.

