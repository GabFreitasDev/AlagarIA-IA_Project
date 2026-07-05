// ============================================================================
// Correspondência entre os nomes de bairro do GeoJSON (mapa) e os nomes de
// bairro retornados pelo backend (pipeline de dados / IA).
// ============================================================================
//
// Os dois arquivos vêm de fontes diferentes e não usam exatamente a mesma
// grafia para todos os 94 bairros. Ex.:
//
//   GeoJSON (EBAIRRNOMEOF)        JSON de risco (Bairro)
//   ---------------------------   -----------------------
//   "Água Fria"                   "Agua Fria"          (sem acento)
//   "Sítio dos Pintos - São Brás" "Sitio Dos Pintos"   (nome abreviado)
//   "Cohab - Ibura de Cima"       "Cohab"              (nome abreviado)
//
// Por isso não podemos comparar strings diretamente. A estratégia é:
//   1. Normalizar (minúsculas, sem acento, sem espaços extras);
//   2. Tentar igualdade exata após normalização;
//   3. Se não achar, tentar correspondência por prefixo (um nome começa
//      com o outro) — cobre os casos de nomes abreviados;
//   4. Se ainda não achar, consultar a tabela de ALIASES abaixo (casos
//      residuais conhecidos, mantidos explícitos para não depender de
//      heurística silenciosa).
//
// Isso é resolvido uma única vez (no hook useRiscoBairros) e reaproveitado
// via Map para consulta O(1) no restante da aplicação.

/** Remove acentos, baixa a caixa e colapsa espaços. */
export function normalizarNomeBairro(nome) {
    if (!nome) return '';
    return nome
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '') // remove diacríticos
        .toLowerCase()
        .trim()
        .replace(/\s+/g, ' ');
}

// Correspondências conhecidas que não são resolvidas por normalização nem
// por prefixo. Chave: nome normalizado do JSON de risco (Bairro).
// Valor: nome normalizado equivalente no GeoJSON (EBAIRRNOMEOF).
const ALIASES_BAIRRO = {
    'cohab': 'cohab - ibura de cima',
    'sitio dos pintos': 'sitio dos pintos - sao bras',
};

/**
 * Constrói um Map(nomeNormalizadoDoGeoJSON -> registro de risco) a partir da
 * lista de registros retornada pelo backend, resolvendo aliases conhecidos.
 */
export function construirMapaDeRisco(registros) {
    const porNomeExato = new Map();
    for (const registro of registros) {
        const chave = normalizarNomeBairro(registro.Bairro);
        porNomeExato.set(chave, registro);
    }

    // Aplica aliases: garante que a chave usada pelo GeoJSON também aponte
    // para o registro correto, mesmo quando o nome de origem é diferente.
    for (const [chaveRisco, chaveGeo] of Object.entries(ALIASES_BAIRRO)) {
        if (porNomeExato.has(chaveRisco)) {
            porNomeExato.set(chaveGeo, porNomeExato.get(chaveRisco));
        }
    }

    return porNomeExato;
}

/**
 * Busca o registro de risco correspondente a um nome de bairro do GeoJSON.
 * Tenta: nome exato normalizado -> correspondência por prefixo -> null.
 */
export function buscarRiscoPorNomeGeo(mapaDeRisco, nomeGeo) {
    const chave = normalizarNomeBairro(nomeGeo);

    if (mapaDeRisco.has(chave)) {
        return mapaDeRisco.get(chave);
    }

    // Fallback por prefixo: cobre nomes compostos tipo "Bairro - Regiao"
    for (const [chaveRisco, registro] of mapaDeRisco.entries()) {
        if (chave.startsWith(chaveRisco) || chaveRisco.startsWith(chave)) {
            return registro;
        }
    }

    return null;
}
