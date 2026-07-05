import { API_BASE_URL, ENDPOINTS, FETCH_TIMEOUT_MS } from '../config/api';
import riscoFallback from '../data/riscoBairrosFallback.json';

/**
 * Faz um fetch com timeout, para não deixar a tela "carregando" para sempre
 * caso o backend esteja fora do ar ou muito lento.
 */
async function fetchComTimeout(url, timeoutMs) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    try {
        const resposta = await fetch(url, { signal: controller.signal });
        return resposta;
    } finally {
        clearTimeout(timeoutId);
    }
}

/**
 * Valida minimamente se o payload recebido tem a forma esperada
 * (lista de registros por bairro). Evita quebrar a aplicação silenciosamente
 * se o backend mudar o contrato sem avisar.
 */
function validarPayload(dados) {
    if (!Array.isArray(dados)) {
        throw new Error('Formato inesperado: resposta do backend não é uma lista de bairros.');
    }
    if (dados.length > 0) {
        const registro = dados[0];
        const camposEsperados = ['Bairro', 'score_risco', 'nivel_risco'];
        const faltando = camposEsperados.filter((campo) => !(campo in registro));
        if (faltando.length > 0) {
            throw new Error(
                `Formato inesperado: campo(s) ausente(s) no registro de bairro: ${faltando.join(', ')}.`
            );
        }
    }
    return dados;
}

/**
 * Busca os dados de risco por bairro no backend.
 *
 * @returns {Promise<{ dados: Array, origem: 'api' | 'fallback', erro: string | null }>}
 *
 * Nunca lança exceção: em caso de qualquer falha (rede, timeout, formato
 * inválido), retorna os dados de contingência (`fallback`) para que o mapa
 * nunca fique vazio, sinalizando a origem e o erro para a camada de UI
 * decidir como avisar o usuário.
 */
export async function buscarRiscoBairros() {
    const url = `${API_BASE_URL}${ENDPOINTS.riscoBairros}`;

    try {
        const resposta = await fetchComTimeout(url, FETCH_TIMEOUT_MS);

        if (!resposta.ok) {
            throw new Error(`Backend retornou status ${resposta.status} ao buscar ${url}`);
        }

        const dados = validarPayload(await resposta.json());
        return { dados, origem: 'api', erro: null };
    } catch (erroOriginal) {
        const mensagem =
            erroOriginal.name === 'AbortError'
                ? `Tempo limite excedido ao contatar o backend em ${url}.`
                : erroOriginal.message;

        console.warn(
            `[AlagarIA] Não foi possível carregar dados reais do backend (${mensagem}). ` +
            'Exibindo dados de contingência (última exportação conhecida do pipeline).'
        );

        return { dados: riscoFallback, origem: 'fallback', erro: mensagem };
    }
}
