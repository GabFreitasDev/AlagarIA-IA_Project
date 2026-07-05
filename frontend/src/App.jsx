import React, { useState } from 'react';
import Layout from './components/Layout';
import MapView from './components/MapView';
import HistoricoChart from './components/HistoricoChart';
import { gerarHistorico24h } from './data/mockHistorico';
import { useRiscoBairros } from './hooks/useRiscoBairros';

function App() {
    // Dados reais de risco por bairro (API do backend, com fallback local
    // em caso de indisponibilidade). Ver src/hooks/useRiscoBairros.js
    const { mapaDeRisco, carregando, origem, erro, atualizadoEm } = useRiscoBairros();

    // Estado para armazenar qual bairro o usuário clicou
    const [bairroSelecionado, setBairroSelecionado] = useState(null);

    // Estado para armazenar os dados de 24h do gráfico daquele bairro
    const [dadosGrafico, setDadosGrafico] = useState([]);

    // Função disparada quando um bairro é clicado no MapView
    const handleBairroClick = (bairro) => {
        setBairroSelecionado(bairro);

        // NOTA: o backend ainda não expõe uma série histórica de 24h por
        // bairro (o pipeline de IA gera apenas o snapshot atual, 3x/dia).
        // Enquanto esse endpoint não existir, mantemos a simulação do
        // histórico ancorada no score REAL retornado pela IA, para que o
        // gráfico ao menos termine no valor correto. Quando o backend
        // expuser algo como GET /risco/bairros/{bairro}/historico, basta
        // trocar esta chamada por um fetch real.
        if (bairro.score !== null && bairro.score !== undefined) {
            setDadosGrafico(gerarHistorico24h(bairro.score));
        } else {
            setDadosGrafico([]);
        }
    };

    return (
        <Layout
            bairroSelecionado={bairroSelecionado}
            onClosePainel={() => setBairroSelecionado(null)}
            statusIntegracao={{ carregando, origem, erro, atualizadoEm }}
        >
            {/* Componente 1: O Mapa (children[0] no Layout) */}
            <MapView mapaDeRisco={mapaDeRisco} onBairroClick={handleBairroClick} />

            {/* Componente 2: O Gráfico (children[1] no Layout) */}
            <HistoricoChart dados={dadosGrafico} />
        </Layout>
    );
}

export default App;
