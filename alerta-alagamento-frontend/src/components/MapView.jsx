import React from 'react';
import { MapContainer, TileLayer, GeoJSON } from 'react-leaflet';
import bairrosRecife from '../data/bairros-do-recife.json';

const MapView = ({ onBairroClick }) => { // <-- Recebe a função como prop
    const positionRecife = [-8.05428, -34.92842];

    // Lógica determinística da Sprint 1 para gerar a cor e o status
    const getMockData = (code) => {
        if (code % 7 === 0) return { status: 'emergencia', score: 0.92 };
        if (code % 5 === 0) return { status: 'alerta', score: 0.78 };
        if (code % 3 === 0) return { status: 'atencao', score: 0.55 };
        return { status: 'normal', score: 0.15 };
    };

    const getColorByStatus = (status) => {
        switch (status) {
            case 'normal': return '#22c55e';
            case 'atencao': return '#eab308';
            case 'alerta': return '#f97316';
            case 'emergencia': return '#ef4444';
            default: return '#9ca3af';
        }
    };

    const styleFeature = (feature) => {
        const bairroCode = feature.properties.CBAIRRCODI;
        const { status } = getMockData(bairroCode);

        return {
            fillColor: getColorByStatus(status),
            weight: 1.5,
            opacity: 1,
            color: '#ffffff',
            fillOpacity: 0.65,
        };
    };

    const onEachFeature = (feature, layer) => {
        const nomeBairro = feature.properties.EBAIRRNOMEOF;
        const bairroCode = feature.properties.CBAIRRCODI;
        const { status, score } = getMockData(bairroCode);

        // Adiciona interatividade de clique para abrir o painel lateral
        layer.on({
            click: () => {
                // Envia os dados do bairro clicado para o componente Pai (App.jsx)
                onBairroClick({
                    id: bairroCode,
                    nome: nomeBairro,
                    status: status,
                    score: score
                });
            },
            mouseover: (e) => { e.target.setStyle({ fillOpacity: 0.85, weight: 2.5 }); },
            mouseout: (e) => { e.target.setStyle({ fillOpacity: 0.65, weight: 1.5 }); }
        });
    };

    return (
        <div className="h-full w-full rounded-xl overflow-hidden shadow-xl border border-slate-200 bg-slate-100">
            <MapContainer
                center={positionRecife}
                zoom={12}
                style={{ height: '100%', width: '100%' }}
            >
                <TileLayer
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    attribution='&copy; OpenStreetMap contributors'
                />
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