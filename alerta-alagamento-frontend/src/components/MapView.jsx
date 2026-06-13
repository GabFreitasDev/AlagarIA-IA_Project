import React from 'react';
import { MapContainer, TileLayer, GeoJSON } from 'react-leaflet';
import bairrosRecife from '../data/bairros-do-recife.json'; // Seu arquivo oficial adaptado

const MapView = () => {
    // Centro geográfico aproximado para focar Recife na tela
    const positionRecife = [-8.05428, -34.92842];

    // 1. Simulador de Risco para a Sprint 1
    // Como o GeoJSON oficial não tem dados de alagamento, usamos o ID do bairro
    // de forma determinística para espalhar as cores do MVP pela cidade.
    const getMockStatus = (code) => {
        if (code % 7 === 0) return 'emergencia'; // Vermelho
        if (code % 5 === 0) return 'alerta';     // Laranja
        if (code % 3 === 0) return 'atencao';    // Amarelo
        return 'normal';                         // Verde
    };

    // 2. Tradutor de Status para as Cores Hexadecimais Acessíveis (WCAG AA)
    const getColorByStatus = (status) => {
        switch (status) {
            case 'normal': return '#22c55e';     // Verde
            case 'atencao': return '#eab308';    // Amarelo
            case 'alerta': return '#f97316';     // Laranja
            case 'emergencia': return '#ef4444'; // Vermelho
            default: return '#9ca3af';           // Cinza padrão
        }
    };

    // 3. Estilização aplicada a cada polígono de bairro
    const styleFeature = (feature) => {
        const bairroCode = feature.properties.CBAIRRCODI;
        const status = getMockStatus(bairroCode);

        return {
            fillColor: getColorByStatus(status),
            weight: 1.5,
            opacity: 1,
            color: '#ffffff', // Linhas divisórias brancas e limpas
            fillOpacity: 0.65, // Transparência ideal para visualizar o mapa base abaixo
        };
    };

    // 4. Interatividade: Popups informativos ao clicar em um bairro
    const onEachFeature = (feature, layer) => {
        const nomeBairro = feature.properties.EBAIRRNOMEOF;
        const bairroCode = feature.properties.CBAIRRCODI;
        const status = getMockStatus(bairroCode).toUpperCase();

        // Vincula um popup nativo do Leaflet com estilização básica
        layer.bindPopup(`
      <div style="font-family: sans-serif; min-width: 140px;">
        <h3 style="margin: 0 0 4px 0; font-size: 14px; font-weight: bold; color: #1e3a8a;">
          ${nomeBairro}
        </h3>
        <p style="margin: 0; font-size: 12px; color: #4b5563;">
          Status: <strong style="color: ${getColorByStatus(getMockStatus(bairroCode))}">${status}</strong>
        </p>
      </div>
    `);

        // Efeito visual sutil de hover para dar sensação de app profissional
        layer.on({
            mouseover: (e) => {
                const l = e.target;
                l.setStyle({ fillOpacity: 0.85, weight: 2.5 });
            },
            mouseout: (e) => {
                const l = e.target;
                l.setStyle({ fillOpacity: 0.65, weight: 1.5 });
            }
        });
    };

    return (
        <div className="h-full w-full rounded-xl overflow-hidden shadow-xl border border-gray-200">
            <MapContainer
                center={positionRecife}
                zoom={12}
                style={{ height: '100%', width: '100%' }}
                scrollWheelZoom={true}
            >
                {/* Camada do OpenStreetMap com visual clean */}
                <TileLayer
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                />

                {/* Renderização da sua malha geográfica oficial */}
                <GeoJSON
                    data={bairrosRecife}
                    style={styleFeature}
                    onEachFeature={onEachFeature}
                />
            </MapContainer>
        </div>
    );
};

export default MapView;