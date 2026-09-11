import rasterio
import numpy as np
from dataclasses import dataclass
from typing import Optional
import matplotlib.pyplot as plt


@dataclass
class TerrainData:
    """Matches the TerrainData contract in schemas.py"""
    slope: float                                   # degrees, 0-90, required
    elevation: Optional[float] = None               # meters
    geology: Optional[str] = None                    # not derivable from DEM alone — left for teammate/other source
    historical_landslide_density: Optional[float] = None  # not derivable from DEM alone


def _read_dem(dem_path: str):
    with rasterio.open(dem_path) as src:
        elevation_grid = src.read(1).astype(np.float64)
        transform = src.transform
        crs = src.crs
    return elevation_grid, transform, crs


def _calculate_slope_grid(elevation_grid: np.ndarray, transform, latitude: float) -> np.ndarray:
    # Pixel size in degrees (from the DEM's transform)
    pixel_size_x_deg = transform[0]
    pixel_size_y_deg = -transform[4]

    # Convert degrees to meters
    # 1 degree latitude ≈ 111,320 meters (roughly constant everywhere)
    # 1 degree longitude ≈ 111,320 * cos(latitude) meters (shrinks toward poles)
    meters_per_deg_lat = 111320
    meters_per_deg_lon = 111320 * np.cos(np.radians(latitude))

    pixel_size_x_m = pixel_size_x_deg * meters_per_deg_lon
    pixel_size_y_m = pixel_size_y_deg * meters_per_deg_lat

    dz_dy, dz_dx = np.gradient(elevation_grid, pixel_size_y_m, pixel_size_x_m)
    slope_rad = np.arctan(np.sqrt(dz_dx**2 + dz_dy**2))
    slope_deg = np.degrees(slope_rad)
    return slope_deg


def get_terrain_data(dem_path: str, latitude: float, longitude: float) -> TerrainData:
    elevation_grid, transform, crs = _read_dem(dem_path)
    slope_grid = _calculate_slope_grid(elevation_grid, transform, latitude)  # pass latitude
    ...

    # Convert lat/lon to row/col pixel index
    row, col = rasterio.transform.rowcol(transform, longitude, latitude)

    # Guard against a point falling outside the DEM's bounding box
    rows, cols = elevation_grid.shape
    if not (0 <= row < rows and 0 <= col < cols):
        raise ValueError(
            f"Location ({latitude}, {longitude}) is outside the DEM coverage area."
        )

    elevation_value = float(elevation_grid[row, col])
    slope_value = float(slope_grid[row, col])

    return TerrainData(
        slope=slope_value,
        elevation=elevation_value,
        geology=None,                       # no source for this yet
        historical_landslide_density=None   # no source for this yet
    )


def _save_raster(data: np.ndarray, reference_path: str, output_path: str):
    """Save a numpy array as a GeoTIFF, copying georeferencing from the reference DEM."""
    with rasterio.open(reference_path) as src:
        profile = src.profile

    profile.update(dtype=rasterio.float32, count=1)

    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(data.astype(rasterio.float32), 1)


if __name__ == "__main__":
    dem_path = "data/terrain/dem.tif"
    test_lat, test_lon = 27.30, 92.40

    elevation_grid, transform, crs = _read_dem(dem_path)
    slope_grid = _calculate_slope_grid(elevation_grid, transform, test_lat)

    # Save full-grid outputs as proper georeferenced GeoTIFFs
    _save_raster(elevation_grid, dem_path, "data/terrain/elevation.tif")
    _save_raster(slope_grid, dem_path, "data/terrain/slope.tif")
    print("Saved elevation.tif and slope.tif")

    # Save slope preview image (visual, for slides)
    plt.figure(figsize=(8, 8))
    plt.imshow(slope_grid, cmap="Reds")
    plt.colorbar(label="Slope (degrees)")
    plt.title("Slope Map - Bomdila-Dirang Corridor")
    plt.savefig("slope_preview.png", dpi=150)
    plt.close()
    print("Saved slope_preview.png")

    # Test single-point extraction (matches TerrainData contract)
    terrain = get_terrain_data(dem_path, test_lat, test_lon)
    print(f"Elevation: {terrain.elevation:.1f} m")
    print(f"Slope: {terrain.slope:.1f}°")