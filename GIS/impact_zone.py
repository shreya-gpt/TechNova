import geopandas as gpd
from dataclasses import dataclass
from GIS.risk_zone import RiskZone  # reuse the RiskZone dataclass from Step 12


@dataclass
class ImpactResult:
    """Matches the ImpactResult contract in schemas.py"""
    affected_roads: int = 0
    affected_bridges: int = 0
    affected_settlements: int = 0
    estimated_population: int = 0
    impact_level: str = "NEGLIGIBLE"


def _load_layers(infra_dir: str):
    roads = gpd.read_file(f"{infra_dir}/roads.geojson")
    bridges = gpd.read_file(f"{infra_dir}/bridges.geojson")
    settlements = gpd.read_file(f"{infra_dir}/settlements.geojson")
    return roads, bridges, settlements


def _classify_impact_level(roads: int, bridges: int, settlements: int) -> str:
    """
    Simple placeholder classification based on how many assets intersect
    the risk zone. Thresholds are a prototype guess — refine with the
    risk/impact teammate.
    """
    total_score = roads + (bridges * 3) + (settlements * 5)  # bridges/settlements weighted higher

    if total_score == 0:
        return "NEGLIGIBLE"
    elif total_score <= 5:
        return "LOW"
    elif total_score <= 15:
        return "MODERATE"
    else:
        return "SEVERE"


def compute_impact(risk_zone: RiskZone, infra_dir: str) -> ImpactResult:
    roads, bridges, settlements = _load_layers(infra_dir)

    affected_roads = roads[roads.intersects(risk_zone.geometry)]
    affected_bridges = bridges[bridges.intersects(risk_zone.geometry)]
    affected_settlements = settlements[settlements.intersects(risk_zone.geometry)]

    # Population: same limitation as Step 11 — OSM rarely has population tags
    estimated_population = 0
    if "population" in affected_settlements.columns:
        pop_values = gpd.pd.to_numeric(affected_settlements["population"], errors="coerce")
        estimated_population = int(pop_values.fillna(0).sum())

    impact_level = _classify_impact_level(
        len(affected_roads), len(affected_bridges), len(affected_settlements)
    )

    return ImpactResult(
        affected_roads=len(affected_roads),
        affected_bridges=len(affected_bridges),
        affected_settlements=len(affected_settlements),
        estimated_population=estimated_population,
        impact_level=impact_level
    )


if __name__ == "__main__":
    from GIS.risk_zone import create_risk_zone

    test_points = [
        (27.35, 92.50, "Remote area"),
        (27.30, 92.40, "Moderate area (your current test)"),
        (27.26, 92.42, "Near Dirang town center"),  # adjust to wherever the actual town center is
    ]

    for lat, lon, label in test_points:
        zone = create_risk_zone(lat, lon, risk_level="HIGH", radius_km=1.0)
        impact = compute_impact(zone, "data/infrastructure")
        print(f"{label}: {impact}")