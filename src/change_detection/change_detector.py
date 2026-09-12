"""
Change Detection stage.

Bi-temporal Change Vector Analysis (CVA): combines multiple index deltas
(NDVI, NDWI, NBR, BSI) into a single change-magnitude map, then thresholds
and connected-component-filters it into candidate disturbed regions. This
is the recommended hackathon MVP approach: it needs zero labeled data,
runs in milliseconds on CPU, and produces a directly-explainable score,
unlike a full Siamese deep network which needs paired labeled data the
team is unlikely to have in time.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np
from scipy import ndimage


@dataclass
class ChangeRegion:
    label_id: int
    pixel_count: int
    centroid_rc: tuple  # (row, col) in image coordinates
    mean_change_magnitude: float
    confidence: float


def change_vector_magnitude(index_deltas: List[np.ndarray]) -> np.ndarray:
    """
    Change Vector Analysis: stack several index-delta layers (NDVI delta,
    NDWI delta, NBR delta, ...) as a change vector at each pixel and take
    its Euclidean magnitude. Large-magnitude pixels = multi-index agreement
    that something physically changed, which is far more robust than
    thresholding a single index.
    """
    stacked = np.stack(index_deltas, axis=0)
    magnitude = np.sqrt(np.sum(stacked ** 2, axis=0))
    return magnitude


def candidate_change_mask(
    magnitude: np.ndarray,
    threshold: float | None = None,
    percentile: float = 90.0,
) -> np.ndarray:
    """
    Threshold the change magnitude map into a binary candidate mask.
    If `threshold` is not given, an adaptive percentile threshold is used so
    the method self-calibrates across different scenes/lighting conditions.
    """
    if threshold is None:
        threshold = float(np.percentile(magnitude, percentile))
    return magnitude >= threshold


def extract_change_regions(
    candidate_mask: np.ndarray,
    magnitude: np.ndarray,
    min_area_px: int = 25,
) -> List[ChangeRegion]:
    """
    Connected-component analysis on the candidate mask to produce discrete
    change regions, each with a size filter (removes salt-and-pepper noise)
    and a simple confidence score derived from mean change magnitude and
    region size (bigger + stronger change => higher confidence).
    """
    labeled, num_features = ndimage.label(candidate_mask)
    regions: List[ChangeRegion] = []

    if num_features == 0:
        return regions

    max_possible_magnitude = float(magnitude.max()) + 1e-6

    for label_id in range(1, num_features + 1):
        region_mask = labeled == label_id
        pixel_count = int(region_mask.sum())
        if pixel_count < min_area_px:
            continue

        centroid = ndimage.center_of_mass(region_mask)
        mean_mag = float(magnitude[region_mask].mean())

        size_factor = min(1.0, pixel_count / (min_area_px * 10))
        magnitude_factor = min(1.0, mean_mag / max_possible_magnitude)
        confidence = float(np.clip(0.5 * size_factor + 0.5 * magnitude_factor, 0.0, 1.0))

        regions.append(
            ChangeRegion(
                label_id=label_id,
                pixel_count=pixel_count,
                centroid_rc=centroid,
                mean_change_magnitude=mean_mag,
                confidence=confidence,
            )
        )

    return sorted(regions, key=lambda r: r.confidence, reverse=True)


def overall_change_score(regions: List[ChangeRegion], image_area_px: int) -> float:
    """
    Aggregate a single 0..1 `change_score` for the AOI from all detected
    regions, weighting by confidence and normalized area — this becomes the
    `change_score` field in the output schema sent to the central risk engine.
    """
    if not regions or image_area_px <= 0:
        return 0.0
    weighted = sum(r.confidence * r.pixel_count for r in regions)
    return float(np.clip(weighted / image_area_px * 5.0, 0.0, 1.0))
