import rasterio
import matplotlib.pyplot as plt

fig, axes = plt.subplots(1, 3, figsize=(18, 6))

with rasterio.open("data/terrain/dem.tif") as src:
    axes[0].imshow(src.read(1), cmap="terrain")
    axes[0].set_title("DEM")

with rasterio.open("data/terrain/elevation.tif") as src:
    axes[1].imshow(src.read(1), cmap="terrain")
    axes[1].set_title("Elevation")

with rasterio.open("data/terrain/slope.tif") as src:
    axes[2].imshow(src.read(1), cmap="Reds")
    axes[2].set_title("Slope")

plt.tight_layout()
plt.show()