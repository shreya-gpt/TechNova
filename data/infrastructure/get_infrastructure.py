import osmnx as ox
import geopandas as gpd
import os

# Same bounding box as your DEM (Bomdila-Dirang corridor)
north, south = 27.45, 27.20
east, west = 92.55, 92.30
bbox = (west, south, east, north)

output_dir = "data/infrastructure"
os.makedirs(output_dir, exist_ok=True)

# 1. ROADS
print("Fetching roads...")
roads = ox.features_from_bbox(bbox=bbox, tags={"highway": True})
roads = roads[roads.geom_type.isin(["LineString", "MultiLineString"])]
roads.to_file(os.path.join(output_dir, "roads.geojson"), driver="GeoJSON")
print(f"Saved {len(roads)} road segments")

# 2. SETTLEMENTS (villages, towns, cities)
print("Fetching settlements...")
settlements = ox.features_from_bbox(
    bbox=bbox,
    tags={"place": ["city", "town", "village", "hamlet"]}
)
settlements.to_file(os.path.join(output_dir, "settlements.geojson"), driver="GeoJSON")
print(f"Saved {len(settlements)} settlements")

# 3. BRIDGES
print("Fetching bridges...")
bridges = ox.features_from_bbox(bbox=bbox, tags={"bridge": True})
bridges.to_file(os.path.join(output_dir, "bridges.geojson"), driver="GeoJSON")
print(f"Saved {len(bridges)} bridges")

print("Done. Files saved in", output_dir)