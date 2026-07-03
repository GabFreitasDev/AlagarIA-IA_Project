from app.schemas import FloodRiskResponse, RainSummary


RISK_THRESHOLDS = {
    "low": 0.40,
    "high": 0.70,
}


def _add_rule_score(
    value: float,
    threshold: float,
    points: int,
    explanation: list[str],
    interval_label: str,
) -> int:
    if value >= threshold:
        explanation.append(
            f"Chuva acumulada em {interval_label} atingiu {value:.1f} mm, acima do limiar de {threshold:.0f} mm."
        )
        return points
    return 0


def predict_flood_risk(city: str, summaries: dict[str, RainSummary]) -> FloodRiskResponse:
    rain = {
        interval: summary.max_rainfall_mm
        for interval, summary in summaries.items()
    }

    explanation: list[str] = []
    score = 0

    score += _add_rule_score(rain.get("1h", 0), 20, 15, explanation, "1h")
    score += _add_rule_score(rain.get("3h", 0), 30, 25, explanation, "3h")
    score += _add_rule_score(rain.get("6h", 0), 50, 20, explanation, "6h")
    score += _add_rule_score(rain.get("12h", 0), 70, 20, explanation, "12h")
    score += _add_rule_score(rain.get("24h", 0), 100, 20, explanation, "24h")

    score = min(score, 100)
    probability = round(score / 100, 2)

    if probability >= RISK_THRESHOLDS["high"]:
        risk_level = "alto"
    elif probability >= RISK_THRESHOLDS["low"]:
        risk_level = "moderado"
    else:
        risk_level = "baixo"

    if not explanation:
        explanation.append("Nenhum limiar crítico de chuva acumulada foi atingido nos intervalos analisados.")

    return FloodRiskResponse(
        city=city,
        flood_probability=probability,
        risk_level=risk_level,
        risk_score=score,
        rain=rain,
        explanation=explanation,
    )
