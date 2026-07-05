# Integracao Frontend <-> Backend - AlagarIA

Este documento descreve como o frontend consome a `alagaria-api`. A API nao consulta fontes externas: ela recebe registros Gold em `POST /ingestao`, grava no banco e serve o snapshot mais recente para a interface.

## Fluxo de dados

```text
Databricks / pipeline Gold
  -> POST /ingestao
  -> Postgres
  -> GET /risk/bairros
  -> frontend
```

Em desenvolvimento, se o banco nao estiver configurado, a API ainda pode usar o arquivo Gold local como fallback (`GOLD_RISK_JSON_PATH`). Para uso continuo, o caminho recomendado e o banco.

## Contrato principal

```http
GET {VITE_API_BASE_URL}/risk/bairros
```

Resposta esperada:

```json
{
  "generated_at": "2026-07-04T03:34:22",
  "source_updated_at": "2026-07-04T03:34:22",
  "source": "PostgreSQL",
  "neighborhoods_count": 1,
  "neighborhoods": [
    {
      "data": "2026-07-04T03:34:22",
      "municipio": "Recife",
      "rpa": 3,
      "bairro": "Aflitos",
      "score_risco": 0.4251,
      "nivel_risco": "moderado"
    }
  ]
}
```

O servico `src/services/riscoService.js` adapta esse envelope para o formato usado internamente pelo mapa. Ele tambem aceita registros no formato bruto do Gold (`Bairro`, `RPA`, `1_hora`, etc.) para manter compatibilidade com o fallback local.

## Historico por bairro

```http
GET {VITE_API_BASE_URL}/risk/bairros/{bairro}/historico
```

Esse endpoint retorna os ultimos registros do bairro no banco. O frontend usa esses dados no grafico lateral. Se o historico ainda nao existir ou o backend falhar, a tela usa uma serie local temporaria ancorada no score atual para nao quebrar a experiencia.

## Variaveis de ambiente

Crie `frontend/.env.local` a partir de `frontend/.env.example`:

```bash
VITE_API_BASE_URL=http://localhost:8000
```

Se a API estiver em outra porta ou host, altere apenas essa variavel.

## Arquivos principais

| Arquivo | Funcao |
|---|---|
| `src/config/api.js` | Centraliza URL base, endpoints, polling e timeout. |
| `src/services/riscoService.js` | Busca snapshot e historico, normaliza payloads e aplica fallback. |
| `src/hooks/useRiscoBairros.js` | Carrega os bairros no primeiro render e atualiza periodicamente. |
| `src/utils/riscoStatus.js` | Converte `nivel_risco` do Gold para os status visuais do mapa. |
| `src/utils/bairroMatcher.js` | Casa nomes do GeoJSON com nomes vindos do Gold/API. |
| `src/data/riscoBairrosFallback.json` | Ultima exportacao Gold conhecida para contingencia local. |

## Como rodar localmente

```bash
cd frontend
npm install
npm run dev
```

Com a API ativa em `http://localhost:8000`, o mapa usa os dados reais. Sem a API, ele continua funcionando em modo de contingencia com o fallback local.
