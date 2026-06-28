import React, { useState } from 'react'; // Importamos o useState para controlar a legenda

const Layout = ({ children, bairroSelecionado, onClosePainel }) => {
    // Estado para controlar se a legenda flutuante está aberta ou recolhida (Padrão: true)
    const [isLegendOpen, setIsLegendOpen] = useState(true);

    // Configuração visual do badge de nível de alerta
    const getBadgeColors = (status) => {
        switch (status) {
            case 'emergencia': return 'bg-red-100 text-red-800 border-red-300';
            case 'alerta': return 'bg-orange-100 text-orange-800 border-orange-300';
            case 'atencao': return 'bg-yellow-100 text-yellow-800 border-yellow-300';
            case 'normal': return 'bg-green-100 text-green-800 border-green-300';
            default: return 'bg-slate-100 text-slate-800 border-slate-300';
        }
    };

    return (
        <div className="flex flex-col h-screen bg-slate-50 text-slate-800 antialiased overflow-hidden">
            {/* Header */}
            <header className="bg-slate-900 text-white px-6 py-3 shadow-md z-10">
                <h1 className="text-xl font-bold tracking-tight text-blue-400">
                    AlegarIA <span className="text-white font-light">- alertas de alagamentos em Recife</span>
                </h1>
                <p className="text-xs text-slate-400 mt-0.5">Painel de Monitoramento</p>
            </header>

            {/* Corpo principal */}
            <main className="flex-1 flex overflow-hidden relative">

                {/* Área do Mapa (Adicionamos 'relative' para ancorar a legenda absoluta aqui dentro) */}
                <div className="flex-1 p-4 relative">
                    {children[0]} {/* Renderiza o mapa Leaflet */}

                    {/* ========================================================== */}
                    {/* NOVA ABA: Legenda Flutuante e Recolhível (z-[500] fica sobre o mapa) */}
                    {/* ========================================================== */}
                    <div className={`absolute bottom-8 left-8 z-[500] bg-white rounded-xl shadow-xl border border-slate-200/80 transition-all duration-300 ease-in-out ${isLegendOpen ? 'w-64 p-4' : 'w-auto p-2'}`}>

                        {/* Cabeçalho da Legenda / Botão de Recolher */}
                        <div className="flex items-center justify-between gap-4">
                            {isLegendOpen && (
                                <h3 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                                    Legenda de Alerta (APAC)
                                </h3>
                            )}

                            <button
                                onClick={() => setIsLegendOpen(!isLegendOpen)}
                                className="text-slate-400 hover:text-slate-600 hover:bg-slate-100 p-1 rounded-lg transition-all flex items-center gap-1.5"
                                title={isLegendOpen ? "Recolher legenda" : "Expandir legenda"}
                            >
                                {isLegendOpen ? (
                                    // Ícone de seta para recolher (Minimizar)
                                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                                        <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                                    </svg>
                                ) : (
                                    // Layout compacto quando recolhida
                                    <div className="flex items-center gap-2 px-1 text-slate-700 font-semibold text-xs">
                                        <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>
                                        <span>Ver Cores e Scores</span>
                                    </div>
                                )}
                            </button>
                        </div>

                        {/* Conteúdo das Cores (Só renderiza se estiver aberto) */}
                        {isLegendOpen && (
                            <div className="space-y-2.5 mt-3 border-t border-slate-100 pt-3 animate-fadeIn">
                                {/* Verde - Normal */}
                                <div className="flex items-center justify-between text-xs">
                                    <div className="flex items-center gap-2">
                                        <span className="w-3 h-3 rounded-full bg-[#22c55e] shadow-sm"></span>
                                        <span className="font-medium text-slate-700">Normal</span>
                                    </div>
                                    <span className="font-mono text-[11px] text-slate-500 bg-slate-50 px-1.5 py-0.5 rounded border border-slate-100">0.00 a 0.50</span>
                                </div>

                                {/* Amarelo - Atenção */}
                                <div className="flex items-center justify-between text-xs">
                                    <div className="flex items-center gap-2">
                                        <span className="w-3 h-3 rounded-full bg-[#eab308] shadow-sm"></span>
                                        <span className="font-medium text-slate-700">Atenção</span>
                                    </div>
                                    <span className="font-mono text-[11px] text-slate-500 bg-slate-50 px-1.5 py-0.5 rounded border border-slate-100">0.51 a 0.75</span>
                                </div>

                                {/* Laranja - Alerta */}
                                <div className="flex items-center justify-between text-xs">
                                    <div className="flex items-center gap-2">
                                        <span className="w-3 h-3 rounded-full bg-[#f97316] shadow-sm"></span>
                                        <span className="font-medium text-slate-700">Alerta</span>
                                    </div>
                                    <span className="font-mono text-[11px] text-slate-500 bg-slate-50 px-1.5 py-0.5 rounded border border-slate-100">0.76 a 0.90</span>
                                </div>

                                {/* Vermelho - Emergência */}
                                <div className="flex items-center justify-between text-xs">
                                    <div className="flex items-center gap-2">
                                        <span className="w-3 h-3 rounded-full bg-[#ef4444] shadow-sm"></span>
                                        <span className="font-medium text-slate-700">Emergência</span>
                                    </div>
                                    <span className="font-mono text-[11px] text-slate-500 bg-slate-50 px-1.5 py-0.5 rounded border border-slate-100">0.91 a 1.00</span>
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {/* Painel Lateral Simplificado (Sem as legendas poluindo o espaço) */}
                {bairroSelecionado && (
                    <aside className="w-80 bg-white shadow-[-4px_0_15px_rgba(0,0,0,0.05)] border-l border-slate-200 p-5 flex flex-col z-10 transition-all duration-300 relative overflow-y-auto">

                        {/* Botão de Fechar Lateral (X) */}
                        <button
                            onClick={onClosePainel}
                            className="absolute top-4 right-4 text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-all p-1.5 rounded-lg"
                            title="Fechar painel"
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                            </svg>
                        </button>

                        {/* Cabeçalho do Bairro */}
                        <div className="mb-4 pr-6">
                            <h2 className="text-lg font-bold text-slate-800 mb-1">
                                {bairroSelecionado.nome}
                            </h2>

                            <div className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold border uppercase tracking-wide mt-2 ${getBadgeColors(bairroSelecionado.status)}`}>
                                <span className="w-2 h-2 rounded-full bg-current mr-2 animate-pulse"></span>
                                {bairroSelecionado.status}
                            </div>
                        </div>

                        {/* Score Atual */}
                        <div className="bg-slate-50 p-3 rounded-lg border border-slate-100 mb-4">
                            <span className="block text-[10px] text-slate-400 uppercase font-bold tracking-wider">Score de Risco Coletado</span>
                            <span className="text-2xl font-black text-slate-700">{bairroSelecionado.score}</span>
                        </div>

                        {/* Gráfico do Histórico (Renderiza diretamente abaixo do score) */}
                        <div className="mt-2">
                            {children[1]}
                        </div>
                    </aside>
                )}
            </main>
        </div>
    );
};

export default Layout;