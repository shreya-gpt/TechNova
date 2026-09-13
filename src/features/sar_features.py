"""
Feature Extraction stage — SAR-derived features.

Sentinel-1 SAR is prioritized for the North Eastern Region because heavy
monsoon cloud cover routinely blocks Sentinel-2 optical acquisitions for
extended periods, while C-band SAR penetrates cloud and works day or night —
making it the only reliable near-real-time source during exactly the rainy
periods when landslide risk is highest.
"""
from __future__ import annotations

import numpy as np

from src.utils.geo_utils import safe_divide


def backscatter_change(vv_pre: np.ndarray, vv_post: np.ndarray) -> np.ndarray:
    """
    Log-ratio backscatter change between two SAR acquisitions (dB-like).
    Bare/disturbed ground (post-landslide) typically shows a sharp
    backscatter change relative to stable, vegetated terrain.
    """
    ratio = safe_divide(vv_post, vv_pre + 1e-6)
    return 10.0 * np.log10(np.clip(ratio, 1e-6, None))


def coherence_map(pre_complex: np.ndarray, post_complex: np.ndarray, window: int = 5) -> np.ndarray:
    """
    Simplified interferometric coherence estimate between two complex SAR
    acquisitions over a local window. Coherence drops sharply where the
    ground surface has physically changed (a landslide scar decorrelates the
    radar phase), making coherence loss a strong, independent change signal.
    """
    from scipy.ndimage import uniform_filter

    numerator = uniform_filter(
        (pre_complex * np.conj(post_complex)).real, size=window
    ) + 1j * uniform_filter((pre_complex * np.conj(post_complex)).imag, size=window)
    denom = np.sqrt(
        uniform_filter(np.abs(pre_complex) ** 2, size=window)
        * uniform_filter(np.abs(post_complex) ** 2, size=window)
    )
    coherence = np.abs(numerator) / (denom + 1e-9)
    return np.clip(coherence, 0.0, 1.0)


def coherence_loss_score(coherence: np.ndarray, threshold: float = 0.3) -> float:
    """Fraction of AOI pixels with coherence below threshold => likely disturbed ground."""
    return float(np.mean(coherence < threshold)) if coherence.size else 0.0
