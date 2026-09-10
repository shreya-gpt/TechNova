"""
services/impact_service.py
===========================
PROTOTYPE impact assessment.

Real implementation (future): take the risk zone geometry (e.g. a buffer or
modeled runout polygon around the location, produced by the GIS teammate's
module) and perform an actual spatial intersection against a roads/bridges/
settlements/population layer to find exactly which assets fall inside it.

For now, since we don't have real geometries yet, we use a simple rule-based
"exposure fraction" driven by risk level: the higher the risk, the larger the
fraction of nearby infrastructure we assume could plausibly be affected. This
keeps the pipeline runnable and the output shape correct, while making it
obvious this must be replaced with real spatial logic later.
"""

from __future__ import annotations

import math

from config import IMPACT_EXPOSURE_FRACTION
from schemas import ImpactLevel, ImpactResult, Infrastructure, RiskResult


def assess_impact(risk: RiskResult, infrastructure: Infrastructure) -> ImpactResult:
    """
    PLACEHOLDER for real GIS spatial-intersection logic.

    TODO (future teammate integration): replace `fraction` below with an
    actual polygon/buffer intersection against real asset locations.
    """
    fraction = IMPACT_EXPOSURE_FRACTION[risk.risk_level.value]

    affected_roads = math.ceil(infrastructure.roads * fraction)
    affected_bridges = math.ceil(infrastructure.bridges * fraction)
    affected_settlements = math.ceil(infrastructure.settlements * fraction)
    affected_population = math.ceil(infrastructure.estimated_population * fraction)

    impact_level = _impact_level_from_population(affected_population, fraction)

    return ImpactResult(
        affected_roads=affected_roads,
        affected_bridges=affected_bridges,
        affected_settlements=affected_settlements,
        estimated_population=affected_population,
        impact_level=impact_level,
    )


def _impact_level_from_population(affected_population: int, fraction: float) -> ImpactLevel:
    """Simple prototype mapping from exposure fraction/affected population to
    an impact category. Kept independent of risk_level so that impact can
    later diverge from raw risk once real population/asset density is used."""
    if fraction == 0.0 or affected_population == 0:
        return ImpactLevel.NEGLIGIBLE
    if fraction < 0.20:
        return ImpactLevel.LOW
    if fraction < 0.50:
        return ImpactLevel.MODERATE
    return ImpactLevel.SEVERE
