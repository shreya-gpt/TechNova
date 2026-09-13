"""
Shared geospatial utility functions used across the pipeline stages.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np


@dataclass
class AOI:
    """A simple Area-Of-Interest bounding box in WGS84 (lat/lon)."""
    aoi_id: str
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float

    @property
    def centroid(self) -> Tuple[float, float]:
        return (
            (self.min_lat + self.max_lat) / 2.0,
            (self.min_lon + self.max_lon) / 2.0,
        )


def normalize_band(band: np.ndarray, clip_percentile: float = 2.0) -> np.ndarray:
    """
    Normalize a single raster band to [0, 1] using percentile clipping,
    which is robust to outlier/hot pixels common in raw satellite data.
    """
    lo = np.percentile(band, clip_percentile)
    hi = np.percentile(band, 100 - clip_percentile)
    if hi <= lo:
        return np.zeros_like(band, dtype=np.float32)
    out = (band.astype(np.float32) - lo) / (hi - lo)
    return np.clip(out, 0.0, 1.0)


def safe_divide(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    """Element-wise divide that avoids divide-by-zero warnings/NaNs."""
    with np.errstate(divide="ignore", invalid="ignore"):
        result = np.true_divide(numerator, denominator)
        result[~np.isfinite(result)] = 0.0
    return result


def pixels_to_area_m2(pixel_count: int, resolution_m: float = 10.0) -> float:
    """Convert a pixel count to ground area in square metres."""
    return pixel_count * (resolution_m ** 2)


def bbox_to_polygon_coords(aoi: AOI) -> list:
    """Return GeoJSON-style polygon ring coordinates for an AOI bounding box."""
    return [[
        [aoi.min_lon, aoi.min_lat],
        [aoi.max_lon, aoi.min_lat],
        [aoi.max_lon, aoi.max_lat],
        [aoi.min_lon, aoi.max_lat],
        [aoi.min_lon, aoi.min_lat],
    ]]
