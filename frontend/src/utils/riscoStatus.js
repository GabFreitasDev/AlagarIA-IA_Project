// ============================================================================
// Mapeamento entre a saída do motor de IA (nivel_risco) e o vocabulário
// visual do frontend (status).
// ============================================================================
//
// O motor de lógica fuzzy (notebook 08) classifica cada bairro em 4 níveis
// linguísticos: "baixo", "moderado", "alto", "critico".
//
// O frontend (mapa, legenda, badges) já usa 4 status equivalentes, com os
// nomes usados no domínio de Defesa Civil / APAC:
//
//   baixo    -> normal      (verde)
//   moderado -> atencao     (amarelo)
//   alto     -> alerta      (laranja)
//   critico  -> emergencia  (vermelho)
//
// Caso um bairro não tenha dado (ex.: nome não encontrado ou API fora do ar),
// usamos o status "sem-dado" (cinza), para deixar isso visualmente explícito
// em vez de fingir que é "normal".

export const NIVEL_PARA_STATUS = {
    baixo: 'normal',
    moderado: 'atencao',
    alto: 'alerta',
    critico: 'emergencia',
};

export const STATUS_PARA_NIVEL = Object.fromEntries(
    Object.entries(NIVEL_PARA_STATUS).map(([nivel, status]) => [status, nivel])
);

/** Converte o nivel_risco vindo do backend para o status usado na UI. */
export function nivelParaStatus(nivelRisco) {
    if (!nivelRisco) return 'sem-dado';
    const chave = String(nivelRisco).trim().toLowerCase();
    return NIVEL_PARA_STATUS[chave] || 'sem-dado';
}

export const CORES_POR_STATUS = {
    normal: '#22c55e',
    atencao: '#eab308',
    alerta: '#f97316',
    emergencia: '#ef4444',
    'sem-dado': '#9ca3af',
};

export const LABEL_POR_STATUS = {
    normal: 'Normal',
    atencao: 'Atenção',
    alerta: 'Alerta',
    emergencia: 'Emergência',
    'sem-dado': 'Sem dado',
};

export function corPorStatus(status) {
    return CORES_POR_STATUS[status] || CORES_POR_STATUS['sem-dado'];
}
