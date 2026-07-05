import React, { useState } from 'react';
import { LABEL_POR_STATUS } from '../utils/riscoStatus';

const BADGE_CLASSES_POR_STATUS = {
    emergencia: 'bg-red-100 text-red-800 border-red-300',
    alerta: 'bg-orange-100 text-orange-800 border-orange-300',
    atencao: 'bg-yellow-100 text-yellow-800 border-yellow-300',
    normal: 'bg-green-100 text-green-800 border-green-300',
    'sem-dado': 'bg-slate-100 text-slate-500 border-slate-300',
};

function getBadgeColors(status) {
    return BADGE_CLASSES_POR_STATUS[status] || BADGE_CLASSES_POR_STATUS['sem-dado'];
}

/** Formata um número com segurança, devolvendo um placeholder se vier null/undefined. */
function formatarNumero(valor, casasDecimais = 2, sufixo = '') {
    if (valor === null || valor === undefined || Number.isNaN(valor)) return '—';
    return `${Number(valor).toFixed(casasDecimais)}${sufixo}`;
}

/** Faixa de status de conexão com o backend, mostrada apenas quando relevante. */
const StatusConexao = ({ carregando, origem, erro, atualizadoEm }) => {
    if (carregando) {
        return (
            <div className="bg-blue-50 text-blue-700 text-xs px-4 py-1.5 flex items-center gap-2 border-b border-blue-100">
                <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
                Carregando dados de risco do backend...
            </div>
        );
    }

    if (origem === 'fallback') {
        return (
            <div className="bg-amber-50 text-amber-800 text-xs px-4 py-1.5 flex items-center gap-2 border-b border-amber-200">
                <span className="w-2 h-2 rounded-full bg-amber-500" />
                Não foi possível conectar ao backend{erro ? ` (${erro})` : ''}. Exibindo última exportação
                conhecida do pipeline de IA (modo de contingência).
            </div>
        );
    }

    if (origem === 'api') {
        return (
            <div className="bg-emerald-50 text-emerald-700 text-xs px-4 py-1.5 flex items-center gap-2 border-b border-emerald-100">
                <span className="w-2 h-2 rounded-full bg-emerald-500" />
                Conectado ao backend
                {atualizadoEm && (
                    <span className="text-emerald-600">
                        · atualizado às {atualizadoEm.toLocaleTimeString('pt-BR')}
                    </span>
                )}
            </div>
        );
    }

    return null;
};

const Layout = ({ children, bairroSelecionado, onClosePainel, statusIntegracao }) => {
    const [isLegendOpen, setIsLegendOpen] = useState(true);
    const { carregando, origem, erro, atualizadoEm } = statusIntegracao || {};

    return (
        <div className="flex flex-col h-screen bg-slate-50 text-slate-800 antialiased overflow-hidden">
            {/* Header */}
            <header className="bg-slate-900 text-white px-6 py-3 shadow-md z-10">
                <h1 className="text-xl font-bold tracking-tight text-blue-400">
                    AlagarIA <span className="text-white font-light">- alertas de alagamentos em Recife</span>
                </h1>
                <p className="text-xs text-slate-400 mt-0.5">Painel de Monitoramento</p>
            </header>

            {/* Faixa de status da integração com o backend */}
            <StatusConexao
                carregando={carregando}
                origem={origem}
                erro={erro}
                atualizadoEm={atualizadoEm}
            />

            {/* Corpo principal */}
            <main className="flex-1 flex overflow-hidden relative">

                {/* Área do Mapa */}
                <div className="flex-1 p-4 relative">
                    {children[0]} {/* Renderiza o mapa Leaflet */}

                    {/* Legenda Flutuante e Recolhível */}
                    <div className={`absolute bottom-8 left-8 z-[500] bg-white rounded-xl shadow-xl border border-slate-200/80 transition-all duration-300 ease-in-out ${isLegendOpen ? 'w-64 p-4' : 'w-auto p-2'}`}>

                        <div className="flex items-center justify-between gap-4">
                            {isLegendOpen && (
                                <h3 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                                    Legenda de Alerta
                                </h3>
                            )}

                            <button
                                onClick={() => setIsLegendOpen(!isLegendOpen)}
                                className="text-slate-400 hover:text-slate-600 hover:bg-slate-100 p-1 rounded-lg transition-all flex items-center gap-1.5"
                                title={isLegendOpen ? "Recolher legenda" : "Expandir legenda"}
                            >
                                {isLegendOpen ? (
                                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                                        <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                                    </svg>
                                ) : (
                                    <div className="flex items-center gap-2 px-1 text-slate-700 font-semibold text-xs">
                                        <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>
                                        <span>Ver Cores e Scores</span>
                                    </div>
                                )}
                            </button>
                        </div>

                        {isLegendOpen && (
                            <div className="space-y-2.5 mt-3 border-t border-slate-100 pt-3 animate-fadeIn">
                                <div className="flex items-center justify-between text-xs">
                                    <div className="flex items-center gap-2">
                                        <span className="w-3 h-3 rounded-full bg-[#22c55e] shadow-sm"></span>
                                        <span className="font-medium text-slate-700">Normal</span>
                                    </div>
                                    <span className="font-mono text-[11px] text-slate-500 bg-slate-50 px-1.5 py-0.5 rounded border border-slate-100">0.00 a 0.25</span>
                                </div>

                                <div className="flex items-center justify-between text-xs">
                                    <div className="flex items-center gap-2">
                                        <span className="w-3 h-3 rounded-full bg-[#eab308] shadow-sm"></span>
                                        <span className="font-medium text-slate-700">Atenção</span>
                                    </div>
                                    <span className="font-mono text-[11px] text-slate-500 bg-slate-50 px-1.5 py-0.5 rounded border border-slate-100">0.25 a 0.50</span>
                                </div>

                                <div className="flex items-center justify-between text-xs">
                                    <div className="flex items-center gap-2">
                                        <span className="w-3 h-3 rounded-full bg-[#f97316] shadow-sm"></span>
                                        <span className="font-medium text-slate-700">Alerta</span>
                                    </div>
                                    <span className="font-mono text-[11px] text-slate-500 bg-slate-50 px-1.5 py-0.5 rounded border border-slate-100">0.50 a 0.75</span>
                                </div>

                                <div className="flex items-center justify-between text-xs">
                                    <div className="flex items-center gap-2">
                                        <span className="w-3 h-3 rounded-full bg-[#ef4444] shadow-sm"></span>
                                        <span className="font-medium text-slate-700">Emergência</span>
                                    </div>
                                    <span className="font-mono text-[11px] text-slate-500 bg-slate-50 px-1.5 py-0.5 rounded border border-slate-100">0.75 a 1.00</span>
                                </div>

                                <div className="flex items-center justify-between text-xs">
                                    <div className="flex items-center gap-2">
                                        <span className="w-3 h-3 rounded-full bg-[#9ca3af] shadow-sm"></span>
                                        <span className="font-medium text-slate-700">Sem dado</span>
                                    </div>
                                    <span className="font-mono text-[11px] text-slate-500 bg-slate-50 px-1.5 py-0.5 rounded border border-slate-100">—</span>
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {/* Painel Lateral */}
                {bairroSelecionado && (
                    <aside className="w-80 bg-white shadow-[-4px_0_15px_rgba(0,0,0,0.05)] border-l border-slate-200 p-5 flex flex-col z-10 transition-all duration-300 relative overflow-y-auto">

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
                                {LABEL_POR_STATUS[bairroSelecionado.status] || bairroSelecionado.status}
                            </div>
                        </div>

                        {bairroSelecionado.status === 'sem-dado' ? (
                            <div className="bg-slate-50 p-3 rounded-lg border border-slate-100 mb-4 text-xs text-slate-500">
                                Este bairro ainda não possui dado de risco retornado pelo backend.
                            </div>
                        ) : (
                            <>
                                {/* Score Atual */}
                                <div className="bg-slate-50 p-3 rounded-lg border border-slate-100 mb-4">
                                    <span className="block text-[10px] text-slate-400 uppercase font-bold tracking-wider">Score de Risco (IA)</span>
                                    <span className="text-2xl font-black text-slate-700">{formatarNumero(bairroSelecionado.score, 2)}</span>
                                </div>

                                {/* Detalhes calculados pelo motor de IA */}
                                <div className="grid grid-cols-2 gap-2 mb-4">
                                    <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-100">
                                        <span className="block text-[9px] text-slate-400 uppercase font-bold tracking-wider">Chuva prevista 24h</span>
                                        <span className="text-sm font-bold text-slate-700">{formatarNumero(bairroSelecionado.precipitacaoPrevista24h, 1, ' mm')}</span>
                                    </div>
                                    <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-100">
                                        <span className="block text-[9px] text-slate-400 uppercase font-bold tracking-wider">Prob. alagamento</span>
                                        <span className="text-sm font-bold text-slate-700">
                                            {bairroSelecionado.probAlagamento === null || bairroSelecionado.probAlagamento === undefined
                                                ? '—'
                                                : `${(bairroSelecionado.probAlagamento * 100).toFixed(0)}%`}
                                        </span>
                                    </div>
                                    <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-100">
                                        <span className="block text-[9px] text-slate-400 uppercase font-bold tracking-wider">Maré</span>
                                        <span className="text-sm font-bold text-slate-700">
                                            {formatarNumero(bairroSelecionado.alturaMare, 2, ' m')}
                                            {bairroSelecionado.statusMare ? ` · ${bairroSelecionado.statusMare}` : ''}
                                        </span>
                                    </div>
                                    <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-100">
                                        <span className="block text-[9px] text-slate-400 uppercase font-bold tracking-wider">Alagamento previsto</span>
                                        <span className="text-sm font-bold text-slate-700">{bairroSelecionado.alagamentoPrevisto || '—'}</span>
                                    </div>
                                </div>

                                {bairroSelecionado.atualizadoEm && (
                                    <p className="text-[10px] text-slate-400 mb-2">
                                        Cálculo do motor de IA em: {bairroSelecionado.atualizadoEm}
                                    </p>
                                )}
                            </>
                        )}

                        {/* Gráfico do Histórico */}
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
