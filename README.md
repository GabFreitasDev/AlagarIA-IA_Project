# AlagarIA - Sistema Inteligente de Alertas de Alagamento

Projeto da disciplina de Inteligencia Artificial do curso de Engenharia da
Computacao.

AlagarIA monitora chuva, mare e altitude dos 94 bairros de Recife e usa modelos
de IA encadeados com logica fuzzy para calcular o nivel de risco de alagamento
por bairro.

## Fluxo Principal

```text
Databricks / notebooks
  -> 07_regressao_linear.py treina os modelos
  -> 08_logica_fuzzy.py gera o JSON Gold de risco
  -> POST /ingestao envia o Gold para a API
  -> Postgres guarda snapshots e historico
  -> GET /risk/bairros entrega o snapshot atual
  -> frontend exibe mapa, painel e historico
```

A API nao consulta APAC nem fontes externas diretamente. Ela serve dados Gold ja
processados.

## Estrutura

```text
.
|-- 00_setup_catalog.ipynb
|-- 01_bronze_apac_precipitacao.py
|-- 02_bronze_altitude_ElevationAPI.ipynb
|-- 03_bronze_apac_mares.py
|-- 04_bronze_to_silver.py
|-- 05_silver_to_gold.py
|-- 07_regressao_linear.py
|-- 08_logica_fuzzy.py
|-- APIs/
|-- utils/
|-- alagaria-api/
`-- frontend/
```

## Como Rodar Localmente

Use tres terminais: um para Postgres, um para API e um para frontend.

### 1. Subir O Postgres

Abra o Docker Desktop e espere o engine iniciar. Depois rode:

```powershell
docker run --name pg_alagaria `
  -e POSTGRES_PASSWORD=senha `
  -e POSTGRES_DB=recife_gis `
  -p 5432:5432 `
  -d postgres:16
```

Nas proximas execucoes:

```powershell
docker start pg_alagaria
```

Para conferir:

```powershell
docker ps
```

### 2. Subir A API

```powershell
cd C:\Users\lucas\AlagarIA-IA_Project\alagaria-api

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

No arquivo `alagaria-api/.env`, deixe:

```env
DATABASE_URL=postgresql://postgres:senha@localhost:5432/recife_gis
GOLD_RISK_JSON_PATH=data/risco_bairros_atual.json
```

Suba a API:

```powershell
uvicorn app.main:app --reload
```

Ela ficara em:

```text
http://127.0.0.1:8000
```

### 3. Carregar Dados Gold No Banco

Se o banco estiver vazio, o endpoint `/risk/bairros` retorna `503`. Para fazer
uma carga local com um JSON Gold:

```powershell
cd C:\Users\lucas\AlagarIA-IA_Project\alagaria-api
.\.venv\Scripts\python.exe scripts\ingest_gold_json.py C:\Users\lucas\Downloads\risco_bairros_atual.json
```

Para usar o fallback versionado do frontend como carga de desenvolvimento:

```powershell
.\.venv\Scripts\python.exe scripts\ingest_gold_json.py ..\frontend\src\data\riscoBairrosFallback.json
```

Depois confira:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/risk/bairros
```

### 4. Subir O Frontend

Use Node `20.19+`.

```powershell
cd C:\Users\lucas\AlagarIA-IA_Project\frontend

npm install
copy .env.example .env.local
npm run dev
```

No `frontend/.env.local`:

```env
VITE_API_BASE_URL=http://localhost:8000
```

Abra:

```text
http://127.0.0.1:5173
```

O frontend busca `/risk/bairros` automaticamente e atualiza a cada 5 minutos.
Se a API estiver indisponivel, ele usa `frontend/src/data/riscoBairrosFallback.json`.

## Endpoints Da API

### Health

```http
GET /health
```

### Ingestao Do Gold

```http
POST /ingestao
```

Recebe o array cru do Gold, no formato gerado pelo `08_logica_fuzzy.py`, e grava
os registros no Postgres. Duplicados sao ignorados por bairro e data.

### Snapshot Para O Frontend

```http
GET /risk/bairros
```

Retorna o snapshot mais recente normalizado para consumo do frontend:

```json
{
  "city": "Recife",
  "generated_at": "2026-07-05T22:02:50+00:00",
  "source_updated_at": "2026-07-05T22:02:50+00:00",
  "neighborhoods_count": 94,
  "source": "PostgreSQL",
  "model": "gold_fuzzy_regression_v1",
  "neighborhoods": [
    {
      "data": "2026-07-05T22:02:50+00:00",
      "municipio": "Recife",
      "bairro": "Aflitos",
      "rpa": 3,
      "score_risco": 0.4439,
      "nivel_risco": "moderado"
    }
  ]
}
```

### Detalhe E Historico

```http
GET /risk/bairros/{bairro}
GET /risk/bairros/{bairro}/historico
```

### Gold Cru

```http
GET /risk/raw
```

Retorna o snapshot mais recente no formato mais proximo do JSON Gold original
(`Bairro`, `RPA`, `1_hora`, `6_horas`, etc.).

## Atualizacao Dos Dados

O frontend nao e atualizado manualmente. Ele sempre consulta a API. Para
atualizar os dados exibidos:

```text
novo JSON Gold
  -> POST /ingestao
  -> Postgres
  -> GET /risk/bairros
  -> frontend
```

Localmente, rode o script de ingestao com o JSON novo. Em producao, o notebook
`08_logica_fuzzy.py` deve publicar automaticamente para a API.

## Databricks

### Configuracao Inicial

Importe os notebooks/scripts para o Workspace do Databricks e execute
`00_setup_catalog.ipynb`. Ele cria o catalogo, schemas e volumes usados pelo
pipeline.

Se o caminho do Workspace mudar, ajuste os `sys.path.append(...)` dos notebooks
para apontar para a pasta correta do projeto no Databricks.

### Ordem Do Pipeline

```text
00_setup_catalog.ipynb       (uma vez)
02_bronze_altitude_ElevationAPI.ipynb (uma vez)
07_regressao_linear.py       (treino/recalibracao dos modelos)

01_bronze_apac_precipitacao.py
03_bronze_apac_mares.py
04_bronze_to_silver.py
05_silver_to_gold.py
08_logica_fuzzy.py
```

O `08_logica_fuzzy.py` gera automaticamente:

```text
/Volumes/{CATALOGO}/{SCHEMA_GOLD}/exportacoes/risco_bairros_atual.json
```

Ele tambem pode publicar o snapshot na API se a variavel de ambiente estiver
configurada:

```text
ALAGARIA_API_INGESTION_URL=https://sua-api/ingestao
```

No Databricks, nao use `localhost` para apontar para sua maquina local. Ali,
`localhost` e o proprio cluster. A API precisa estar em um host acessivel pelo
cluster, como um servidor, cloud, endpoint interno ou tunnel temporario.

## Modelos De IA

O `07_regressao_linear.py` treina:

- regressao Ridge calibrada para prever precipitacao das proximas 24h;
- regressao logistica para probabilidade de alagamento;
- scaler usado pela logistica.

O `08_logica_fuzzy.py` carrega os modelos, calcula o score fuzzy e gera o JSON
Gold final.

Depois de calibrar modelos, execute no Databricks:

```text
1. 07_regressao_linear.py
2. 08_logica_fuzzy.py
```

## Limitacoes Conhecidas

- O Databricks Community Edition pode bloquear chamadas HTTP de saida para a
  APAC. Nesse caso, a coleta APAC deve ser feita localmente e enviada para a
  landing zone.
- A base de treino ainda usa dados ficticios com padroes climaticos realistas,
  nao uma serie historica oficial de alagamentos.
- A mare e aplicada de forma uniforme por bairro; uma versao futura pode
  ponderar por proximidade com mar, rios e canais.

## Troubleshooting

### Docker Nao Conecta

Abra o Docker Desktop e espere iniciar. Depois teste:

```powershell
docker version
```

### API Retorna 503 Em `/risk/bairros`

O banco esta vazio ou `DATABASE_URL` nao foi configurado. Ingerir um JSON Gold:

```powershell
cd C:\Users\lucas\AlagarIA-IA_Project\alagaria-api
.\.venv\Scripts\python.exe scripts\ingest_gold_json.py C:\Users\lucas\Downloads\risco_bairros_atual.json
```

### Frontend Mostra Modo De Contingencia

Confirme que a API responde:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/risk/bairros
```

Depois recarregue:

```text
http://127.0.0.1:5173
```

### Vite Nao Abre

Confirme Node `20.19+`:

```powershell
node --version
```

Rode novamente:

```powershell
cd C:\Users\lucas\AlagarIA-IA_Project\frontend
npm run dev
```
