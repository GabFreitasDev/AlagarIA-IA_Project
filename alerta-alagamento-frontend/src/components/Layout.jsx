import React from 'react';

const Layout = ({ children }) => {
    return (
        <div className="flex flex-col h-screen bg-gray-50">
            <header className="bg-blue-900 text-white p-4 shadow-md">
                <h1 className="text-xl font-bold tracking-wide">
                    Alerta de Alagamento - Recife
                </h1>
                <p className="text-sm text-blue-200">Visão Geral de Risco (Sprint 1)</p>
            </header>

            <main className="flex-1 p-4">
                {/* O container interno renderiza o mapa ou outros componentes */}
                {children}
            </main>
        </div>
    );
};

export default Layout;