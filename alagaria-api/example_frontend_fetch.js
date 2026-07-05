async function loadFloodRisk() {
  const response = await fetch("http://localhost:8000/risk/bairros");

  if (!response.ok) {
    throw new Error("Erro ao buscar risco de alagamento por bairro");
  }

  const data = await response.json();
  const neighborhoods = data.neighborhoods ?? [];
  const highestRisk = neighborhoods.reduce((currentHighest, neighborhood) => {
    if (!currentHighest || neighborhood.score_risco > currentHighest.score_risco) {
      return neighborhood;
    }

    return currentHighest;
  }, null);

  document.querySelector("#updated-at").textContent = data.generated_at ?? "-";
  document.querySelector("#neighborhoods-count").textContent = data.neighborhoods_count;

  if (highestRisk) {
    document.querySelector("#neighborhood").textContent = highestRisk.bairro;
    document.querySelector("#risk-level").textContent = highestRisk.nivel_risco;
    document.querySelector("#risk-score").textContent = `${Math.round(highestRisk.score_risco * 100)}%`;
    document.querySelector("#rain-24h").textContent = `${highestRisk.chuva_24h ?? 0} mm`;
  }
}

loadFloodRisk().catch(console.error);
