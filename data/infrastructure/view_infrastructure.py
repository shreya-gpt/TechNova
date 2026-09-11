import geopandas as gpd
import matplotlib.pyplot as plt

roads = gpd.read_file("data/infrastructure/roads.geojson")
settlements = gpd.read_file("data/infrastructure/settlements.geojson")
bridges = gpd.read_file("data/infrastructure/bridges.geojson")

fig, ax = plt.subplots(figsize=(10, 10))

roads.plot(ax=ax, color="gray", linewidth=0.8, label="Roads")
settlements.plot(ax=ax, color="blue", markersize=20, label="Settlements")
bridges.plot(ax=ax, color="red", markersize=40, marker="^", label="Bridges")

ax.set_title("Infrastructure - Bomdila-Dirang Corridor")
ax.legend()
plt.savefig("infrastructure_preview.png", dpi=150)
plt.show()

print("Saved infrastructure_preview.png")

