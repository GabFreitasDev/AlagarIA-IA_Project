// Recebe o score atual do bairro para "ancorar" o final do gráfico
export const gerarHistorico24h = (scoreAtual) => {
    const historico = [];

    // Começamos o cálculo a partir do score exato do bairro selecionado
    let riscoSimulado = scoreAtual;

    // i = 0 representa o momento atual, i = 24 representa 24 horas atrás
    for (let i = 0; i <= 24; i++) {
        const hora = new Date();
        hora.setHours(hora.getHours() - i);

        historico.push({
            hora: `${hora.getHours().toString().padStart(2, '0')}:00`,
            score: Number(riscoSimulado.toFixed(2))
        });

        // Calcula como estava o risco na hora *anterior* adicionando uma variação aleatória
        riscoSimulado = Math.max(0, Math.min(1, riscoSimulado + (Math.random() * 0.3 - 0.15)));
    }

    // Como o array foi preenchido do presente para o passado,
    // nós o invertemos (reverse) para o gráfico desenhar da esquerda para a direita corretamente
    return historico.reverse();
};