"""
services/decision_service.py
=============================
Rule-based decision/recommendation engine.

IMPORTANT: this system supports human decision-makers — it does NOT
autonomously order evacuations, close roads, or take any binding action.
All recommended_actions are advisory, to be acted on by local authorities.
"""

from __future__ import annotations

from schemas import DecisionResult, ImpactResult, RiskLevel, RiskResult, UrgencyLevel

_ACTIONS_BY_LEVEL = {
    RiskLevel.LOW: [
        "Continue routine monitoring of rainfall and slope conditions.",
    ],
    RiskLevel.MODERATE: [
        "Increase monitoring frequency in the affected area.",
        "Verify environmental sensor readings with a manual/field check.",
        "Share advisory with local disaster management authority for awareness.",
    ],
    RiskLevel.HIGH: [
        "Dispatch a field team for on-ground inspection of slope conditions.",
        "Prepare and review evacuation routes for nearby settlements.",
        "Alert local authorities and district disaster management officials.",
    ],
    RiskLevel.CRITICAL: [
        "Conduct immediate field verification of slope stability.",
        "Activate evacuation preparedness for at-risk settlements.",
        "Assess and consider precautionary traffic restrictions on nearby roads.",
        "Initiate emergency coordination with district/state disaster response teams.",
    ],
}

_URGENCY_BY_LEVEL = {
    RiskLevel.LOW: UrgencyLevel.ROUTINE,
    RiskLevel.MODERATE: UrgencyLevel.ELEVATED,
    RiskLevel.HIGH: UrgencyLevel.URGENT,
    RiskLevel.CRITICAL: UrgencyLevel.IMMEDIATE,
}

_HIGH_UNCERTAINTY_THRESHOLD = 0.30
_UNCERTAINTY_NOTE = (
    "Data completeness is limited for this analysis — treat this output as "
    "an initial screening result and prioritize ground-truth verification "
    "before acting on it."
)


def recommend_actions(risk: RiskResult, impact: ImpactResult) -> DecisionResult:
    """Produce advisory recommendations. Human authorities remain the
    decision-makers; this engine only supports their judgement."""
    actions = list(_ACTIONS_BY_LEVEL[risk.risk_level])

    if risk.uncertainty > _HIGH_UNCERTAINTY_THRESHOLD:
        actions.append(_UNCERTAINTY_NOTE)

    urgency = _URGENCY_BY_LEVEL[risk.risk_level]

    rationale = (
        f"Risk level is {risk.risk_level.value} (score {risk.risk_score}/100, "
        f"confidence {risk.confidence}). Estimated impact level is "
        f"{impact.impact_level.value}, potentially affecting approximately "
        f"{impact.estimated_population} people, {impact.affected_settlements} "
        f"settlement(s), {impact.affected_roads} road segment(s), and "
        f"{impact.affected_bridges} bridge(s). {risk.explanation}"
    )

    return DecisionResult(
        recommended_actions=actions,
        urgency=urgency,
        rationale=rationale,
    )
