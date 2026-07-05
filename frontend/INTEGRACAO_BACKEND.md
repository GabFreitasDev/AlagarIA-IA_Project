# Integração Frontend ↔ Backend — AlagarIA

Este documento descreve a integração feita no frontend para consumir o motor
de IA (regressão linear + lógica fuzzy) via backend, substituindo os dados
mockados usados na Sprint 1.

## O que mudou

Antes, `MapView.jsx` calculava o status de cada bairro localmente com uma
regra determinística (`code % 7`, `code % 5`, `code % 3`). Isso foi removido.
Agora o status vem de um único lugar: os dados retornados pelo backend.

## Contrato de API esperado

```
GET {VITE_API_BASE_URL}/risco/bairros
```

Resposta esperada — uma lista com um objeto por bairro, no mesmo formato do
arquivo `risco_bairros_atual.json` exportado pelo notebook
`08_logica_fuzzy.py` (Bloco 6):

```json
[
  {
    "data": "2026-07-04 03:34:22",
    "municipio": "Recife",
    "RPA": 3,
    "Bairro": "Aflitos",
    "elevacao_metros": 6.0,
    "precipitacao_atual": 0.0,
    "1_hora": 0.0,
    "6_horas": 0.017,
    "12_horas": 0.017,
    "24_horas": 0.017,
    "altura_mare": 2.14,
    "status_mare": "Alta",
    "precipitacao_prevista_24h": 32.25,
    "prob_alagamento": 0.1077,
    "alagamento_previsto": "Não",
    "score_risco": 0.4251,
    "nivel_risco": "moderado"
  }
]
```

**Este endpoint (`/risco/bairros`) ainda não existe no backend inspecionado**
(`alagaria-api`). O backend hoje só expõe `/predict/recife`, que é a baseline
antiga (`rule_based_baseline_v1`, cidade inteira, sem granularidade por
bairro). É necessário que o time de backend:

1. Carregue o `risco_bairros_atual.json` (ou consulte o banco onde ele for
   persistido) dentro da API;
2. Exponha esse conteúdo em `GET /risco/bairros`, no formato acima;
3. Garanta CORS liberado para a origem do frontend (`http://localhost:5173`
   já está na lista padrão em `app/config.py`).

Se o path final for outro, basta editar uma única constante:
`src/config/api.js` → `ENDPOINTS.riscoBairros`.

## Arquivos criados/alterados

| Arquivo | O que faz |
|---|---|
| `src/config/api.js` | URL base da API, endpoint, intervalo de polling e timeout — tudo centralizado. |
| `src/services/riscoService.js` | Busca os dados no backend (com timeout de 8s); em caso de falha de rede, timeout ou formato inválido, cai para `riscoBairrosFallback.json` sem quebrar a tela. |
| `src/data/riscoBairrosFallback.json` | Cópia do `risco_bairros_atual.json` fornecido, usada como dado de contingência (não é mais um mock sintético — é uma exportação real do pipeline). |
| `src/utils/riscoStatus.js` | Converte `nivel_risco` (baixo/moderado/alto/critico) para o `status` visual (normal/atencao/alerta/emergencia) e centraliza cores/labels. |
| `src/utils/bairroMatcher.js` | Casa os nomes de bairro do GeoJSON do mapa com os nomes retornados pela API (ver seção abaixo). |
| `src/hooks/useRiscoBairros.js` | Hook React: busca os dados ao montar, atualiza a cada 5 min (polling), expõe `carregando`/`origem`/`erro`. |
| `src/components/MapView.jsx` | Trocado o `getMockData(code % n)` por consulta ao mapa de risco real. |
| `src/components/Layout.jsx` | Painel lateral agora exibe campos reais (chuva prevista 24h, probabilidade de alagamento, maré, alagamento previsto). Adicionado aviso de status da conexão com o backend. |
| `src/App.jsx` | Conecta o hook `useRiscoBairros` ao `MapView` e ao `Layout`. |
| `.env.example` | Documenta a variável `VITE_API_BASE_URL`. |

## Por que existe um "matcher" de nomes de bairro

O GeoJSON do mapa (`bairros-do-recife.json`) e o JSON do backend não usam
exatamente a mesma grafia para todos os 94 bairros. Exemplos encontrados:

- `"Água Fria"` (mapa) vs `"Agua Fria"` (backend) — diferença de acentuação;
- `"Sítio dos Pintos - São Brás"` (mapa) vs `"Sitio Dos Pintos"` (backend) —
  nome abreviado;
- `"Cohab - Ibura de Cima"` (mapa) vs `"Cohab"` (backend) — idem.

Comparar as strings diretamente faria alguns bairros nunca serem
encontrados e ficarem cinza ("sem dado") por engano. `bairroMatcher.js`
resolve isso em 3 passos: normalização (remove acento/caixa), correspondência
por prefixo, e por fim uma tabela `ALIASES_BAIRRO` explícita para os dois
casos residuais que não se resolvem nem por prefixo. Essa tabela deve ser
revisada se a lista de bairros do backend mudar.

## Estados de carregamento e falha

A barra logo abaixo do cabeçalho mostra três estados possíveis:

- **Azul** — carregando dados do backend (primeira carga);
- **Verde** — conectado, com horário da última atualização;
- **Âmbar** — backend indisponível; o mapa continua funcional exibindo o
  `riscoBairrosFallback.json` (modo de contingência), e o motivo do erro é
  mostrado para facilitar o diagnóstico.

O mapa **nunca fica vazio**: se a API falhar, o fallback garante que a
demonstração e o uso continuem possíveis.

## O que ainda depende do backend (pendências conhecidas)

1. **Endpoint `/risco/bairros`** — descrito acima, é o bloqueador principal.
2. **Histórico por bairro (gráfico de 24h)** — hoje o backend só gera um
   *snapshot* atual (roda 3x/dia: 03h, 11h, 19h), sem série temporal por
   bairro. O gráfico (`HistoricoChart`) continua usando uma simulação
   ancorada no score real (`gerarHistorico24h`), documentada em `App.jsx`.
   Quando existir algo como `GET /risco/bairros/{bairro}/historico`, essa
   função mock deve ser substituída por uma chamada real.
3. **Novos níveis de risco possíveis no futuro** — o mapeamento em
   `riscoStatus.js` já cobre os 4 níveis usados pelo motor fuzzy
   (baixo/moderado/alto/critico → normal/atencao/alerta/emergencia). Qualquer
   nível desconhecido cai automaticamente em "sem-dado" (cinza) em vez de
   quebrar a aplicação.

## Como rodar localmente

```bash
cp .env.example .env.local
# ajuste VITE_API_BASE_URL se o backend não estiver em localhost:8000
npm install
npm run dev
```

Sem um backend rodando em `/risco/bairros`, o frontend funciona normalmente
em modo de contingência (dados de `riscoBairrosFallback.json`), com o aviso
âmbar visível.
