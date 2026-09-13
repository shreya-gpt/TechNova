import geopandas as gpd
import matplotlib.pyplot as plt

roads = gpd.read_file("data/infrastructure/roads.geojson")
settlements = gpd.read_file("data/infrastructure/settlements.geojson")
risk_zone = gpd.read_file("data/infrastructure/risk_zone_example.geojson")

fig, ax = plt.subplots(figsize=(8, 8))

roads.plot(ax=ax, color="gray", linewidth=0.6, label="Roads")
settlements.plot(ax=ax, color="blue", markersize=15, label="Settlements")
risk_zone.plot(ax=ax, color="red", alpha=0.4, edgecolor="darkred", linewidth=2, label="Risk Zone")

ax.set_title("Prototype Risk Zone - Bomdila-Dirang Corridor")
ax.legend()
plt.savefig("risk_zone_preview.png", dpi=150)
plt.show()

print("Saved risk_zone_preview.png")