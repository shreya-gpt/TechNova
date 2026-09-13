"""
Feature Extraction stage — spectral indices.

Converts raw multi-band reflectance into normalized, physically-meaningful
numerical indicators. These are engineered features — the module never
hands the risk engine a raw pixel decision, only interpretable numbers.

Indices implemented:
  - NDVI  (vegetation health / loss)      -> used for vegetation_loss feature
  - NDWI  (surface water / moisture)      -> used for water_accumulation_score
  - NBR   (burn/bare-earth ratio, repurposed here as a bare-soil/scar proxy)
  - BSI   (Bare Soil Index, extra signal for exposed soil after a slide)
"""
from __future__ import annotations

import numpy as np

from src.utils.geo_utils import safe_divide


def ndvi(nir: np.ndarray, red: np.ndarray) -> np.ndarray:
    """Normalized Difference Vegetation Index. Range ~[-1, 1]; higher = healthier vegetation."""
    return safe_divide(nir - red, nir + red)


def ndwi(green: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """Normalized Difference Water Index (McFeeters). Higher = more surface water/moisture."""
    return safe_divide(green - nir, green + nir)


def nbr(nir: np.ndarray, swir2: np.ndarray) -> np.ndarray:
    """
    Normalized Burn Ratio. Originally for fire scars, repurposed here as a
    disturbance/bare-earth proxy: exposed soil and debris after a landslide
    lowers NIR reflectance and raises SWIR reflectance similarly to a burn
    scar, making NBR a useful secondary disturbance signal.
    """
    return safe_divide(nir - swir2, nir + swir2)


def bsi(blue: np.ndarray, red: np.ndarray, nir: np.ndarray, swir1: np.ndarray) -> np.ndarray:
    """
    Bare Soil Index. Landslide scars expose bare soil/rock; BSI rises sharply
    in the newly-disturbed footprint, complementing the NDVI drop.
    """
    numerator = (swir1 + red) - (nir + blue)
    denominator = (swir1 + red) + (nir + blue)
    return safe_divide(numerator, denominator)


def compute_index_delta(pre_index: np.ndarray, post_index: np.ndarray) -> np.ndarray:
    """Simple temporal delta of an index (post - pre); the core change signal."""
    return post_index.astype(np.float32) - pre_index.astype(np.float32)


def vegetation_loss_fraction(ndvi_pre: np.ndarray, ndvi_post: np.ndarray, drop_threshold: float = 0.15) -> float:
    """
    Fraction of AOI pixels showing a meaningful NDVI drop
    (proxy for `vegetation_loss` in the output schema, 0..1).
    """
    delta = compute_index_delta(ndvi_pre, ndvi_post)
    lost_mask = delta < -abs(drop_threshold)
    return float(np.mean(lost_mask)) if delta.size else 0.0


def water_accumulation_score(ndwi_pre: np.ndarray, ndwi_post: np.ndarray) -> float:
    """
    Mean positive increase in NDWI (proxy for new water pooling/blocked
    drainage that often precedes or follows a landslide), clipped to [0, 1].
    """
    delta = compute_index_delta(ndwi_pre, ndwi_post)
    positive_delta = np.clip(delta, 0, None)
    score = float(np.mean(positive_delta)) if delta.size else 0.0
    return float(np.clip(score * 4.0, 0.0, 1.0))  # scale small NDWI deltas into 0..1
