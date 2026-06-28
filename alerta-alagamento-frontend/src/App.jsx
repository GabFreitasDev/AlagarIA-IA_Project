import React, { useState } from 'react';
import Layout from './components/Layout';
import MapView from './components/MapView';
import HistoricoChart from './components/HistoricoChart';
import { gerarHistorico24h } from './data/mockHistorico';

function App() {
    // Estado para armazenar qual bairro o usuário clicou
    const [bairroSelecionado, setBairroSelecionado] = useState(null);

    // Estado para armazenar os dados de 24h do gráfico daquele bairro
    const [dadosGrafico, setDadosGrafico] = useState([]);


    // Função disparada quando um bairro é clicado no MapView
    const handleBairroClick = (bairro) => {
        setBairroSelecionado(bairro);

        // Agora passamos o score real do bairro para a função de mock
        setDadosGrafico(gerarHistorico24h(bairro.score));
    };

    return (
        <Layout
            bairroSelecionado={bairroSelecionado}
            onClosePainel={() => setBairroSelecionado(null)} // <-- Nova prop adicionada aqui!
        >
            {/* Componente 1: O Mapa (children[0] no Layout) */}
            <MapView onBairroClick={handleBairroClick} />

            {/* Componente 2: O Gráfico (children[1] no Layout) */}
            <HistoricoChart dados={dadosGrafico} />
        </Layout>
    );
}

export default App;