// ============================================================================
// Configuracao central de integracao com o backend (AlagarIA API)
// ============================================================================
// URL base do backend. Pode ser sobrescrita por variavel de ambiente do Vite
// em .env ou .env.local, sem precisar alterar codigo-fonte.
//
// Exemplo de .env.local:
//   VITE_API_BASE_URL=http://localhost:8000
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// ----------------------------------------------------------------------------
// Endpoint com o score de risco por bairro. A API entrega o snapshot Gold mais
// recente em um envelope com metadados e a lista `neighborhoods`.
//
// Contrato:
//   GET {API_BASE_URL}/risk/bairros
//
// Para mudar o caminho publicado pela API, atualize apenas a constante abaixo.
export const ENDPOINTS = {
    riscoBairros: '/risk/bairros',
};

// Intervalo de atualizacao automatica do painel (em milissegundos). O motor de
// IA roda poucas vezes ao dia, entao 5 minutos bastam para refletir novas
// execucoes do pipeline sem sobrecarregar o backend.
export const POLLING_INTERVAL_MS = 5 * 60 * 1000;

// Tempo maximo de espera por uma resposta do backend antes de cair no modo de
// contingencia com o fallback local.
export const FETCH_TIMEOUT_MS = 8000;
