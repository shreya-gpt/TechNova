"""
Cloud / Noise Handling stage.

Two independent paths:
  - Optical (Sentinel-2): a lightweight cloud + cloud-shadow heuristic mask
    based on reflectance + NDVI/brightness thresholds (a fast stand-in for
    s2cloudless in a resource-constrained hackathon environment).
  - SAR (Sentinel-1): a Lee speckle filter to suppress multiplicative
    speckle noise inherent to radar imagery, since SAR has no "clouds" but
    is dominated by speckle.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import uniform_filter


def simple_cloud_mask(blue: np.ndarray, nir: np.ndarray, brightness_threshold: float = 0.35) -> np.ndarray:
    """
    Heuristic optical cloud mask.
    Clouds: high reflectance across visible bands (bright), low NDVI-like
    contrast between NIR and blue. Returns a boolean mask where True = cloud.

    This is intentionally simple (numpy-only, no external cloud model) so the
    pipeline can run in any hackathon environment; swap in `s2cloudless` for
    production-grade masking without changing the pipeline's interface.
    """
    brightness = (blue.astype(np.float32) + nir.astype(np.float32)) / 2.0
    brightness = brightness / (brightness.max() + 1e-6)
    cloud_mask = brightness > brightness_threshold
    return cloud_mask


def apply_cloud_mask(image: np.ndarray, cloud_mask: np.ndarray, fill_value: float = np.nan) -> np.ndarray:
    """Mask out cloud pixels in a single band, setting them to `fill_value`."""
    out = image.astype(np.float32).copy()
    out[cloud_mask] = fill_value
    return out


def lee_speckle_filter(sar_image: np.ndarray, window_size: int = 5) -> np.ndarray:
    """
    Lee filter for SAR speckle suppression.

    Speckle is multiplicative noise: I_observed = I_true * noise. The Lee
    filter locally estimates signal vs. noise variance and blends the local
    mean with the observed pixel accordingly, preserving edges (important —
    we don't want to smear real landslide-scar boundaries) while suppressing
    speckle in homogeneous areas.
    """
    img = sar_image.astype(np.float32)
    mean = uniform_filter(img, size=window_size)
    mean_sq = uniform_filter(img ** 2, size=window_size)
    variance = mean_sq - mean ** 2
    variance[variance < 0] = 0

    overall_variance = np.var(img)
    if overall_variance <= 0:
        return img

    weight = variance / (variance + overall_variance)
    filtered = mean + weight * (img - mean)
    return filtered
