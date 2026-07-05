import React from 'react';
import { MapContainer, TileLayer, GeoJSON } from 'react-leaflet';
import bairrosRecife from '../data/bairros-do-recife.json';
import { buscarRiscoPorNomeGeo } from '../utils/bairroMatcher';
import { nivelParaStatus, corPorStatus } from '../utils/riscoStatus';

/**
 * MapView agora é "burro" em relação aos dados: toda a lógica de onde vem
 * o risco (API real ou fallback) fica no hook useRiscoBairros (App.jsx).
 * Aqui só recebemos o mapa já pronto e desenhamos o GeoJSON com as cores
 * correspondentes.
 *
 * @param {Map} mapaDeRisco - Map(nomeNormalizado -> registro de risco)
 * @param {(bairro) => void} onBairroClick - callback ao clicar em um bairro
 */
const MapView = ({ mapaDeRisco, onBairroClick }) => {
    const positionRecife = [-8.05428, -34.92842];

    // Une o feature do GeoJSON com o registro de risco correspondente,
    // devolvendo sempre um objeto com o mesmo formato — mesmo quando não
    // há dado (status "sem-dado"), para o restante da UI não precisar
    // tratar "undefined" em vários lugares.
    const obterRiscoDoFeature = (feature) => {
        const nomeBairro = feature.properties.EBAIRRNOMEOF;
        const registro = buscarRiscoPorNomeGeo(mapaDeRisco, nomeBairro);

        if (!registro) {
            return { status: 'sem-dado', score: null, registro: null };
        }

        return {
            status: nivelParaStatus(registro.nivel_risco),
            score: registro.score_risco,
            registro,
        };
    };

    const styleFeature = (feature) => {
        const { status } = obterRiscoDoFeature(feature);

        return {
            fillColor: corPorStatus(status),
            weight: 1.5,
            opacity: 1,
            color: '#ffffff',
            fillOpacity: status === 'sem-dado' ? 0.35 : 0.65,
        };
    };

    const onEachFeature = (feature, layer) => {
        const nomeBairro = feature.properties.EBAIRRNOMEOF;
        const bairroCode = feature.properties.CBAIRRCODI;

        layer.on({
            click: () => {
                // Relê o risco no momento do clique (não no momento da
                // renderização do layer), para refletir atualizações vindas
                // do polling sem precisar recriar o GeoJSON inteiro.
                const { status, score, registro } = obterRiscoDoFeature(feature);

                onBairroClick({
                    id: bairroCode,
                    nome: nomeBairro,
                    status,
                    score,
                    // Campos adicionais vindos do motor de IA (podem ser
                    // undefined quando o bairro está em "sem-dado").
                    precipitacaoPrevista24h: registro?.precipitacao_prevista_24h ?? null,
                    probAlagamento: registro?.prob_alagamento ?? null,
                    alagamentoPrevisto: registro?.alagamento_previsto ?? null,
                    alturaMare: registro?.altura_mare ?? null,
                    statusMare: registro?.status_mare ?? null,
                    atualizadoEm: registro?.data ?? null,
                });
            },
            mouseover: (e) => { e.target.setStyle({ fillOpacity: 0.85, weight: 2.5 }); },
            mouseout: (e) => {
                const { status } = obterRiscoDoFeature(feature);
                e.target.setStyle({ fillOpacity: status === 'sem-dado' ? 0.35 : 0.65, weight: 1.5 });
            }
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
                    // key força o React a redesenhar as cores quando o
                    // mapaDeRisco muda (ex.: após o polling trazer dados novos)
                    key={mapaDeRisco.size}
                    data={bairrosRecife}
                    style={styleFeature}
                    onEachFeature={onEachFeature}
                />
            </MapContainer>
        </div>
    );
};

export default MapView;
