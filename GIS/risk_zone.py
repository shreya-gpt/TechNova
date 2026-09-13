import geopandas as gpd
from shapely.geometry import Point
from dataclasses import dataclass


@dataclass
class RiskZone:
    """Prototype risk-zone polygon around a predicted landslide point.
    NOTE: buffer radius is a placeholder, not a scientifically validated
    runout model. Must be agreed with risk/impact teammate before treating
    as more than a prototype visual."""
    geometry: object          # shapely Polygon
    center_lat: float
    center_lon: float
    radius_km: float
    risk_level: str


def create_risk_zone(
    latitude: float,
    longitude: float,
    risk_level: str = "HIGH",
    radius_km: float = 1.0
) -> RiskZone:
    """
    Creates a simple circular buffer polygon around a predicted landslide
    point, standing in for a proper runout/susceptibility zone.

    radius_km should scale with risk_level in a real system (e.g. CRITICAL
    zones larger than LOW), but for the prototype a fixed default is used
    unless overridden.
    """
    center = Point(longitude, latitude)
    radius_deg = radius_km / 111.0  # same rough km->degree conversion as Step 11

    zone_polygon = center.buffer(radius_deg)

    return RiskZone(
        geometry=zone_polygon,
        center_lat=latitude,
        center_lon=longitude,
        radius_km=radius_km,
        risk_level=risk_level
    )


def save_risk_zone(zone: RiskZone, output_path: str):
    gdf = gpd.GeoDataFrame(
        [{
            "risk_level": zone.risk_level,
            "radius_km": zone.radius_km,
            "center_lat": zone.center_lat,
            "center_lon": zone.center_lon,
            "note": "PROTOTYPE risk zone - simple buffer, not a validated runout model"
        }],
        geometry=[zone.geometry],
        crs="EPSG:4326"
    )
    gdf.to_file(output_path, driver="GeoJSON")


if __name__ == "__main__":
    test_lat, test_lon = 27.30, 92.40

    zone = create_risk_zone(test_lat, test_lon, risk_level="HIGH", radius_km=1.0)
    save_risk_zone(zone, "data/infrastructure/risk_zone_example.geojson")

    print(f"Risk zone created: {zone.risk_level}, radius {zone.radius_km} km")
    print(f"Center: ({zone.center_lat}, {zone.center_lon})")
    print("Saved: data/infrastructure/risk_zone_example.geojson")