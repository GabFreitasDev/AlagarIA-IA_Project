// ============================================================================
// Configuração central de integração com o backend (AlagarIA API)
// ============================================================================
// URL base do backend. Pode ser sobrescrita por variável de ambiente do Vite
// (arquivo .env / .env.local), sem precisar alterar código-fonte.
//
// Exemplo de .env.local:
//   VITE_API_BASE_URL=http://localhost:8000
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// ----------------------------------------------------------------------------
// Endpoint com o score de risco por bairro (saída do motor de IA: regressão
// linear + lógica fuzzy — ver notebooks 07_regressao_linear e 08_logica_fuzzy).
//
// CONTRATO ESPERADO DO BACKEND (a combinar com o time de back-end):
//   GET {API_BASE_URL}/risco/bairros
//   200 OK
//   [
//     {
//       "data": "2026-07-04 03:34:22",
//       "municipio": "Recife",
//       "RPA": 3,
//       "Bairro": "Aflitos",
//       "elevacao_metros": 6.0,
//       "precipitacao_atual": 0.0,
//       "1_hora": 0.0,
//       "6_horas": 0.017,
//       "12_horas": 0.017,
//       "24_horas": 0.017,
//       "altura_mare": 2.14,
//       "status_mare": "Alta",
//       "precipitacao_prevista_24h": 32.25,
//       "prob_alagamento": 0.1077,
//       "alagamento_previsto": "Não",
//       "score_risco": 0.4251,
//       "nivel_risco": "moderado"   // "baixo" | "moderado" | "alto" | "critico"
//     },
//     ...
//   ]
//
// Este é exatamente o formato do arquivo risco_bairros_atual.json exportado
// pelo pipeline (Bloco 6 do notebook 08_logica_fuzzy.py). Caso o backend
// exponha esses dados em outro caminho, basta atualizar a constante abaixo.
export const ENDPOINTS = {
    riscoBairros: '/risco/bairros',
};

// Intervalo de atualização automática do painel (em milissegundos).
// O motor de IA roda 3x/dia (03h, 11h, 19h), então não há necessidade de
// polling agressivo — 5 minutos é suficiente para refletir novas execuções
// do pipeline sem sobrecarregar o backend.
export const POLLING_INTERVAL_MS = 5 * 60 * 1000;

// Tempo máximo de espera por uma resposta do backend antes de desistir
// e cair no modo de contingência (fallback).
export const FETCH_TIMEOUT_MS = 8000;
