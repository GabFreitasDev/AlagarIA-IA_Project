import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';

const HistoricoChart = ({ dados }) => {
    return (
        <div className="h-64 w-full bg-white rounded-lg p-2 border border-slate-200 shadow-sm mt-4">
            <h3 className="text-sm font-semibold text-slate-700 mb-2 px-2">Histórico de Risco (Últimas 24h)</h3>
            <ResponsiveContainer width="100%" height="100%">
                <LineChart data={dados} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                    <XAxis dataKey="hora" tick={{fontSize: 10}} stroke="#94a3b8" />
                    <YAxis domain={[0, 1]} tick={{fontSize: 10}} stroke="#94a3b8" />
                    <Tooltip
                        contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                        formatter={(value) => [`Score: ${value}`, 'Risco']}
                    />
                    {/* Linha vermelha indicando o limiar de emergência */}
                    <ReferenceLine y={0.8} stroke="#ef4444" strokeDasharray="3 3" opacity={0.5} />
                    <Line
                        type="monotone"
                        dataKey="score"
                        stroke="#3b82f6"
                        strokeWidth={3}
                        dot={false}
                        activeDot={{ r: 6 }}
                    />
                </LineChart>
            </ResponsiveContainer>
        </div>
    );
};

export default HistoricoChart;