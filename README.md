# AlagarIA — Sistema Inteligente de Alertas de Alagamento

> Projeto da disciplina de Inteligência Artificial — Engenharia da Computação <br>
> Professor: Fausto Lorenzato <br>
> Alunos: Adenilson Neto, Bruno Alberto, Gabriel de Freitas, Lucas Carneiro e Lucas Rafael <br>
> Recife-PE · 2026

AlagarIA monitora dados de chuva, maré e altitude dos 94 bairros de Recife e utiliza dois motores de IA encadeados — **Regressão Linear + Logística e Lógica Fuzzy** — para calcular e exibir em tempo real o nível de risco de alagamento de cada bairro.

---

## Avaliação do Projeto

### O que foi entregue

| Componente | Status | Observação |
|---|---|---|
| Pipeline de dados (Bronze → Silver → Gold) | ✅ Completo | 6 notebooks Databricks, arquitetura medalhão |
| Ingestão de precipitação (APAC) | ✅ Funcional | Via script local + upload manual (limitação de rede) |
| Ingestão de maré (APAC) | ✅ Funcional | Seleção por proximidade de horário, média entre praias |
| Altitude dos 94 bairros | ✅ Funcional | Open-Meteo Elevation API |
| IDW espacial por RPA | ✅ Funcional | Testado empiricamente |
| Motor de Regressão Linear | ✅ Funcional | Prevê P24h por bairro |
| Motor de Regressão Logística | ✅ Funcional | Prevê probabilidade de alagamento |
| Lógica Fuzzy (3 variáveis, 4 níveis) | ✅ Funcional | Pertinência + regras + defuzzificação por centroide |
| Backend FastAPI | ✅ Funcional | Modo arquivo JSON e modo PostgreSQL |
| Frontend React + Leaflet | ✅ Funcional | Mapa interativo com score por bairro |
| Governança (logs, controle de arquivos, validações) | ✅ Completo | 4 tabelas de auditoria |

### Pontos fortes
- A arquitetura de separação de responsabilidades (dados → IA → backend → frontend) está bem implementada e cada camada tem papel claro.
- O motor de IA é o ponto de maior destaque: dois modelos encadeados com lógica fuzzy de 4 níveis, com funções de pertinência calibradas para a realidade climática do Recife (limiares baseados em sazonalidade real — pico Abr/Mai/Jun).
- O backend tem dois modos de operação (arquivo JSON direto ou PostgreSQL), o que torna o projeto resiliente para demonstração sem infraestrutura de banco.
- A governança de dados (logs de execução, controle de arquivos processados, validação de schema) está além do esperado para um MVP acadêmico.

### Limitação principal documentada
O Databricks Community Edition bloqueia chamadas HTTP de saída para `api.apac.pe.gov.br` (IP governamental bloqueado em firewalls de datacenter — confirmado com diagnóstico TCP em dois ambientes de nuvem diferentes). A ingestão da APAC é feita via script local rodado no computador de um integrante, com posterior upload manual para a landing zone. Isso foi documentado como desvio consciente do roteiro original ("scheduler automático a cada 15 min").

---

## Estrutura do Repositório

```
AlagarIA-IA_Project/
├── 00_setup_catalog.ipynb          # Configuração inicial do catálogo Databricks (roda 1x)
├── 01_bronze_apac_precipitacao.py  # Ingestão de chuva da landing zone
├── 02_bronze_altitude_ElevationAPI.ipynb  # Altitude dos 94 bairros (roda 1x)
├── 03_bronze_apac_mares.py         # Ingestão de maré da landing zone
├── 04_bronze_to_silver.py          # IDW por RPA + seleção de maré por horário
├── 05_silver_to_gold.py            # Snapshot mais recente → JSON para o backend
├── 07_regressao_linear.py          # Treino dos modelos de regressão (roda 1x)
├── 08_logica_fuzzy.py              # Motor operacional: predição + fuzzy → JSON de risco
├── APIs/
│   ├── apac_client.py              # Script local: coleta precipitação da APAC
│   ├── apac_mare_client.py         # Script local: coleta maré da APAC
│   ├── elevation_client.py         # Chamado pelo notebook 02
│   ├── openmeteo_client.py         # Chamado pelo notebook 06 (histórico)
│   ├── bairros_recife_coords.json  # Coordenadas dos 94 bairros
│   └── bairros_rpa.json            # Mapeamento bairro → RPA
├── utils/
│   ├── catalogo.py                 # Constantes e função tabela()
│   └── qualidade.py                # Funções de validação de schema
├── alagaria-api/                   # Backend FastAPI
│   ├── app/
│   │   ├── main.py
│   │   ├── routes/risk.py
│   │   └── services/gold_risk_repository.py
│   ├── .env.example
│   └── requirements.txt
└── frontend/                       # Frontend React + Leaflet
    ├── src/
    │   ├── App.jsx
    │   ├── components/
    │   └── hooks/useRiscoBairros.js
    └── package.json
```

---

## Pré-requisitos

| Componente | Versão mínima |
|---|---|
| Databricks Community Edition | Qualquer (gratuito) |
| Python (scripts locais) | 3.10+ |
| Node.js (frontend) | 18+ |
| pip package: `requests` | Qualquer |

---

## Como Rodar — Passo a Passo

### 1. Configuração inicial do Databricks (uma única vez)

Importe todos os arquivos `.py` e `.ipynb` da raiz do repositório para o seu Workspace no Databricks:

**Catalog → Workspace → Import → selecionar os arquivos**

Depois execute o notebook `00_setup_catalog.ipynb`. Ele cria:
- Catálogo `alerta_alagamento_recife`
- Schemas: `bronze`, `silver`, `gold`, `governanca`
- Volume `landing_zone` dentro do schema `bronze`

> ⚠️ **Atenção:** todos os outros notebooks fazem `sys.path.append` com o caminho do Workspace de Gabriel (`gabriel.fo.br@gmail.com`). Se você estiver rodando em outro usuário, atualize essa linha no Bloco 1 de cada notebook para o seu caminho real antes de executar.

### 2. Altitude dos bairros (uma única vez)

Execute `02_bronze_altitude_ElevationAPI.ipynb`. Ele chama a Open-Meteo Elevation API diretamente do cluster (sem bloqueio de rede) e cria a tabela `bronze.open_meteo_elevation` com os 94 bairros, coordenadas, RPA e altitude.

### 3. Geração da base histórica fictícia (uma única vez)

No seu computador local, gere o arquivo de base histórica que será usado para treinar os modelos:

```bash
# Na pasta raiz do projeto
python APIs/gerar_base_ficticia.py
```

Isso gera `historico_ficticio_180dias_recife.json` (≈ 5MB, 16.920 registros).

Em seguida, faça upload desse arquivo para a landing zone no Databricks:

**Catalog → alerta_alagamento_recife → bronze → Volumes → landing_zone → Upload**

### 4. Treino dos modelos de IA (uma única vez, após o passo 3)

Execute `07_regressao_linear.py`. Ele:
- Carrega a base fictícia da landing zone
- Treina a Regressão Linear (prevê P24h)
- Treina a Regressão Logística (prevê probabilidade de alagamento)
- Salva os 3 artefatos (`.pkl`) no Volume `gold/modelos/`

> O notebook imprime RMSE, R² e acurácia ao final. Guarde esses números para a defesa do projeto.

### 5. Rotina diária de ingestão

A cada dia, **antes das 03h**, rode localmente:

```bash
# Na pasta APIs/
python apac_client.py
python apac_mare_client.py
```

Dois arquivos serão gerados na pasta local:
- `precipAcum_AAAA-MM-DD.json`
- `mare_AAAA-MM-DD.json`

Faça upload de ambos no Databricks:

**Catalog → bronze → Volumes → landing_zone → apac_precipitacao** (para o de chuva)  
**Catalog → bronze → Volumes → landing_zone → apac_mares** (para o de maré)

### 6. Jobs automáticos no Databricks (03h, 11h, 19h)

Configure um Databricks Job com a seguinte sequência de tarefas:

```
01_bronze_apac_precipitacao
        ↓
03_bronze_apac_mares
        ↓
04_bronze_to_silver
        ↓
05_silver_to_gold
        ↓
08_logica_fuzzy
```

Agendamento (cron Quartz, horário de Recife `America/Recife`):

```
0 0 3,11,19 * * ?
```

> **Como configurar:** no Job, clique em "Add trigger" → Scheduled → Custom cron → cole a expressão acima → selecione o timezone `America/Recife`.

O notebook `08_logica_fuzzy.py` gera o arquivo `risco_bairros_atual.json` no Volume Gold ao final de cada execução. Esse é o arquivo que o backend consome.

---

## Backend (FastAPI)

### Instalação

```bash
cd alagaria-api
cp .env.example .env
pip install -r requirements.txt
```

### Configuração do `.env`

```env
# Caminho para o JSON exportado pelo notebook 08
# Use caminho absoluto ou relativo à pasta alagaria-api/
GOLD_RISK_JSON_PATH=data/risco_bairros_atual.json

# Opcional: banco PostgreSQL (se não definido, lê direto do JSON)
DATABASE_URL=
```

### Como apontar para o JSON do Databricks

O backend lê o arquivo `risco_bairros_atual.json` localmente. Você precisa baixar esse arquivo do Volume Gold do Databricks e colocar em `alagaria-api/data/`:

**Catalog → gold → Volumes → exportacoes → risco_bairros_atual.json → Download**

Renomeie se necessário e coloque em `alagaria-api/data/risco_bairros_atual.json`.

> Para automação futura, o script `scripts/ingest_gold_json.py` pode ser configurado para buscar e inserir os dados no PostgreSQL periodicamente.

### Execução

```bash
uvicorn app.main:app --reload --port 8000
```

### Endpoints principais

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/risk/bairros` | Snapshot completo dos 94 bairros com score de risco |
| GET | `/risk/bairros/{bairro}` | Dados de um bairro específico |
| GET | `/risk/bairros/{bairro}/historico` | Histórico de medições do bairro (requer PostgreSQL) |
| GET | `/risk/raw` | JSON Gold bruto sem normalização |
| GET | `/health` | Status da API |

Documentação interativa disponível em `http://localhost:8000/docs`.

---

## Frontend (React + Vite + Leaflet)

### Instalação e execução

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

O frontend estará disponível em `http://localhost:5173`.

### Configuração da API

No arquivo `frontend/.env`, configure a URL do backend:

```env
VITE_API_URL=http://localhost:8000
```

Se o backend não estiver disponível, o frontend usa automaticamente o arquivo fallback em `src/data/riscoBairrosFallback.json` para exibir dados mesmo sem conexão.

### O que a interface exibe

- **Mapa do Recife** com os 94 bairros coloridos por nível de risco (baixo → verde, moderado → amarelo, alto → laranja, crítico → vermelho)
- **Painel lateral** ao clicar em um bairro: score de risco, precipitação atual, previsão para 24h, altura da maré, probabilidade de alagamento
- **Gráfico de histórico** com as últimas 24h de dados do bairro selecionado

---

## Motor de IA — Como Funciona

O sistema encadeia dois motores em sequência a cada execução do notebook 08:

### Etapa 1 — Regressão Linear
Recebe os acumulados de chuva atuais do bairro (1h, 6h, 12h, 24h) e prevê a precipitação das próximas 24h. Foi treinado com autocorrelação temporal: dias chuvosos tendem a ser seguidos de mais chuva (padrão real do inverno nordestino).

### Etapa 2 — Regressão Logística
Recebe os acumulados de chuva + altura da maré + altitude do bairro e prevê a probabilidade de alagamento (0 a 1). Treinada com a base fictícia de 180 dias, que emula o pico de alagamentos de Abril/Maio/Junho em Recife.

### Etapa 3 — Lógica Fuzzy
Recebe a precipitação prevista (da etapa 1) + maré atual + altitude e classifica o risco em 4 níveis usando funções de pertinência trapezoidais e regras do tipo "SE... ENTÃO...". A defuzzificação é feita pelo método do centroide.

| Nível | Score | Descrição |
|---|---|---|
| Baixo | 0.00 – 0.24 | Sem risco relevante |
| Moderado | 0.25 – 0.49 | Vigilância — monitorar |
| Alto | 0.50 – 0.74 | Risco real — atenção |
| Crítico | 0.75 – 1.00 | Evacuação recomendada |

---

## Observações e Pensamentos Futuros

### Limitações conhecidas do MVP

**Ingestão manual da APAC:** o Databricks Community Edition bloqueia chamadas HTTP de saída para domínios governamentais (IP `200.238.75.118`, porta 443 — bloqueio TCP confirmado). A solução definitiva seria migrar para um workspace Databricks em nuvem paga (AWS/Azure/GCP), onde as regras de egress são configuráveis, ou usar um servidor intermediário (ex: AWS Lambda) que chame a APAC e republique o dado em um endpoint acessível do cluster.

**Base de treino fictícia:** os modelos foram treinados com dados sintéticos gerados com padrões climáticos reais do Recife (sazonalidade, distribuição lognormal de chuva, susceptibilidade por RPA), mas não com dados históricos reais de alagamento. Isso limita a precisão do sistema para uso real.

**Maré uniforme por bairro:** todos os 94 bairros recebem o mesmo valor de maré. Na prática, bairros à beira-mar e bairros próximos aos rios Capibaribe e Beberibe têm exposição diferente à maré. Uma versão mais precisa usaria o coeficiente de proximidade ao corpo d'água mais relevante para cada bairro.

### Evoluções naturais

- **Integração com dados reais de alagamento da Defesa Civil do Recife:** substituiria a base fictícia pela série histórica real, aumentando significativamente a qualidade dos modelos.
- **Retreinamento automático:** configurar o notebook 07 para rodar semanalmente (Databricks Jobs) com os dados mais recentes, mantendo os modelos calibrados ao longo do tempo.
- **Alertas por push notification:** o backend já tem a estrutura para isso — bastaria adicionar um serviço de notificação (ex: Firebase Cloud Messaging) acionado quando o score de algum bairro ultrapassa um limiar.
- **Granularidade por rua:** o IDW atual opera por RPA (6 regiões). Uma versão futura poderia operar por bairro (94 pontos) ou por estação (se a APAC disponibilizar coordenadas detalhadas por estação), aumentando a precisão espacial.
- **Scheduler externo para ingestão:** usar GitHub Actions (gratuito) com cron agendado para rodar `apac_client.py` e fazer upload automático via Databricks Files API, eliminando a necessidade de intervenção manual.

---

## Divisão de Responsabilidades

| Integrante | Área | Notebooks/Arquivos |
|---|---|---|
| Gabriel de Freitas | Dados (Pessoa A) | 01, 04, 05, `apac_client.py` |
| Adenilson Gomes | Dados (Pessoa B) | 03, `apac_mare_client.py` |
| Pessoa 1 | IA — preparação dos dados | Blocos 2-3 do notebook 07 |
| Pessoa 2 | IA — treino e persistência | Blocos 4-6 do notebook 07 |
| Pessoa 3 | IA — funções de pertinência | Bloco 3 do notebook 08 |
| Pessoa 4 | IA — regras fuzzy | Bloco 4 do notebook 08 |
| Pessoa 5 | IA — integração e exportação | Blocos 2, 5-6 do notebook 08; backend; frontend |

---

*AlagarIA · Engenharia da Computação · 2026*
