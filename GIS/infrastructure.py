import geopandas as gpd
from dataclasses import dataclass
from shapely.geometry import Point


@dataclass
class Infrastructure:
    """Matches the Infrastructure contract in schemas.py"""
    roads: int = 0
    bridges: int = 0
    settlements: int = 0
    hospitals: int = 0
    schools: int = 0
    estimated_population: int = 0


def _load_layers(infra_dir: str):
    roads = gpd.read_file(f"{infra_dir}/roads.geojson")
    bridges = gpd.read_file(f"{infra_dir}/bridges.geojson")
    settlements = gpd.read_file(f"{infra_dir}/settlements.geojson")
    return roads, bridges, settlements


def get_infrastructure_data(
    infra_dir: str,
    latitude: float,
    longitude: float,
    radius_km: float = 5.0
) -> Infrastructure:
    """
    Counts infrastructure assets within `radius_km` of the given point.
    """
    roads, bridges, settlements = _load_layers(infra_dir)

    center = Point(longitude, latitude)

    # Convert radius from km to degrees (rough approximation, fine for a small prototype area)
    radius_deg = radius_km / 111.0

    buffer_zone = center.buffer(radius_deg)

    roads_nearby = roads[roads.intersects(buffer_zone)]
    bridges_nearby = bridges[bridges.intersects(buffer_zone)]
    settlements_nearby = settlements[settlements.intersects(buffer_zone)]

    # Population isn't in your OSM data by default — settlements often lack a
    # population tag. We'll try to read it if present, else leave as 0.
    estimated_population = 0
    if "population" in settlements_nearby.columns:
        pop_values = gpd.pd.to_numeric(settlements_nearby["population"], errors="coerce")
        estimated_population = int(pop_values.fillna(0).sum())

    return Infrastructure(
        roads=len(roads_nearby),
        bridges=len(bridges_nearby),
        settlements=len(settlements_nearby),
        hospitals=0,   # not fetched yet — optional per roadmap
        schools=0,     # not fetched yet — optional per roadmap
        estimated_population=estimated_population
    )


if __name__ == "__main__":
    test_lat, test_lon = 27.30, 92.40

    infra = get_infrastructure_data("data/infrastructure", test_lat, test_lon, radius_km=5)
    print(infra)