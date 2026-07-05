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

function normalizarRegistroApi(registro) {
    return {
        data: registro.data,
        municipio: registro.municipio ?? 'Recife',
        RPA: registro.rpa ?? registro.RPA,
        Bairro: registro.bairro ?? registro.Bairro,
        elevacao_metros: registro.elevacao_metros,
        precipitacao_atual: registro.precipitacao_atual,
        '1_hora': registro.chuva_1h ?? registro['1_hora'],
        '6_horas': registro.chuva_6h ?? registro['6_horas'],
        '12_horas': registro.chuva_12h ?? registro['12_horas'],
        '24_horas': registro.chuva_24h ?? registro['24_horas'],
        altura_mare: registro.altura_mare,
        status_mare: registro.status_mare,
        precipitacao_prevista_24h: registro.precipitacao_prevista_24h,
        prob_alagamento: registro.prob_alagamento,
        alagamento_previsto: registro.alagamento_previsto,
        score_risco: registro.score_risco,
        nivel_risco: registro.nivel_risco,
    };
}

function extrairRegistros(payload) {
    if (Array.isArray(payload)) {
        return payload.map(normalizarRegistroApi);
    }

    if (payload && Array.isArray(payload.neighborhoods)) {
        return payload.neighborhoods.map(normalizarRegistroApi);
    }

    throw new Error('Formato inesperado: resposta do backend nao contem lista de bairros.');
}

/**
 * Valida minimamente se o payload recebido tem a forma esperada
 * (lista de registros por bairro). Evita quebrar a aplicação silenciosamente
 * se o backend mudar o contrato sem avisar.
 */
function validarPayload(dados) {
    const registros = extrairRegistros(dados);

    if (registros.length > 0) {
        const registro = registros[0];
        const camposEsperados = ['Bairro', 'score_risco', 'nivel_risco'];
        const faltando = camposEsperados.filter((campo) => !(campo in registro));
        if (faltando.length > 0) {
            throw new Error(
                `Formato inesperado: campo(s) ausente(s) no registro de bairro: ${faltando.join(', ')}.`
            );
        }
    }

    return registros;
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

function registrosParaHistorico(registros) {
    return registros
        .filter((registro) => registro.data && registro.score_risco !== null && registro.score_risco !== undefined)
        .sort((a, b) => new Date(a.data) - new Date(b.data))
        .map((registro) => ({
            hora: new Date(registro.data).toLocaleTimeString('pt-BR', {
                hour: '2-digit',
                minute: '2-digit',
            }),
            score: Number(Number(registro.score_risco).toFixed(2)),
        }));
}

export async function buscarHistoricoBairro(nomeBairro) {
    const url = `${API_BASE_URL}/risk/bairros/${encodeURIComponent(nomeBairro)}/historico`;

    try {
        const resposta = await fetchComTimeout(url, FETCH_TIMEOUT_MS);

        if (!resposta.ok) {
            throw new Error(`Backend retornou status ${resposta.status} ao buscar ${url}`);
        }

        return registrosParaHistorico(validarPayload(await resposta.json()));
    } catch (erroOriginal) {
        console.warn(`[AlagarIA] Historico real indisponivel para ${nomeBairro}: ${erroOriginal.message}`);
        return null;
    }
}
