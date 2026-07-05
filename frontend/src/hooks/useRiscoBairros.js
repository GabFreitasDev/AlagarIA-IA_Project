import { useEffect, useRef, useState, useCallback } from 'react';
import { buscarRiscoBairros } from '../services/riscoService';
import { construirMapaDeRisco } from '../utils/bairroMatcher';
import { POLLING_INTERVAL_MS } from '../config/api';

/**
 * Hook responsável por toda a integração do mapa com o backend:
 * - Busca os dados de risco por bairro (score + nível calculados pela IA);
 * - Constrói o Map(nomeNormalizado -> registro) usado pelo MapView;
 * - Atualiza os dados automaticamente a cada POLLING_INTERVAL_MS;
 * - Expõe estados de loading / erro / origem dos dados (api ou fallback)
 *   para a UI poder avisar o usuário quando estiver em modo de contingência.
 */
export function useRiscoBairros() {
    const [mapaDeRisco, setMapaDeRisco] = useState(new Map());
    const [registros, setRegistros] = useState([]);
    const [carregando, setCarregando] = useState(true);
    const [origem, setOrigem] = useState(null); // 'api' | 'fallback'
    const [erro, setErro] = useState(null);
    const [atualizadoEm, setAtualizadoEm] = useState(null);

    // Evita "setState" após desmontagem do componente (ex.: troca de página)
    const montadoRef = useRef(true);

    const carregarDados = useCallback(async ({ mostrarLoading = false } = {}) => {
        if (mostrarLoading) setCarregando(true);

        const { dados, origem: origemDados, erro: erroDados } = await buscarRiscoBairros();

        if (!montadoRef.current) return;

        setRegistros(dados);
        setMapaDeRisco(construirMapaDeRisco(dados));
        setOrigem(origemDados);
        setErro(erroDados);
        setAtualizadoEm(new Date());
        setCarregando(false);
    }, []);

    useEffect(() => {
        montadoRef.current = true;
        carregarDados({ mostrarLoading: true });

        const intervalId = setInterval(() => {
            carregarDados({ mostrarLoading: false });
        }, POLLING_INTERVAL_MS);

        return () => {
            montadoRef.current = false;
            clearInterval(intervalId);
        };
    }, [carregarDados]);

    return {
        mapaDeRisco,
        registros,
        carregando,
        origem,
        erro,
        atualizadoEm,
        recarregar: () => carregarDados({ mostrarLoading: false }),
    };
}
