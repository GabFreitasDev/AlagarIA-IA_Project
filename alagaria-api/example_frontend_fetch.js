async function loadFloodRisk() {
  const response = await fetch("http://localhost:8000/predict/recife");

  if (!response.ok) {
    throw new Error("Erro ao buscar risco de enchente");
  }

  const data = await response.json();

  document.querySelector("#risk-level").textContent = data.risk_level;
  document.querySelector("#probability").textContent = `${Math.round(data.flood_probability * 100)}%`;
  document.querySelector("#rain-24h").textContent = `${data.rain["24h"]} mm`;
}

loadFloodRisk().catch(console.error);
