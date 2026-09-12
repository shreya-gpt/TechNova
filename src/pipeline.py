"""
End-to-end pipeline orchestrator.

Wires together every stage:
  preprocessing -> features -> change_detection -> segmentation
  -> sar_insar -> risk_indicators

Used by:
  - scripts/demo.py       (synthetic, fully offline)
  - scripts/run_pipeline.py (CLI over real/cached rasters)
  - src/api/main.py       (FastAPI /analyze endpoint)

This is the single place that defines "how the stages connect", so all three
entry points stay in sync.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

import numpy as np
import torch

from src.change_detection.change_detector import (
    candidate_change_mask,
    change_vector_magnitude,
    extract_change_regions,
    overall_change_score,
)
from src.features.sar_features import coherence_loss_score, coherence_map
from src.features.spectral_indices import (
    compute_index_delta,
    ndvi,
    ndwi,
    vegetation_loss_fraction,
    water_accumulation_score,
)
from src.preprocessing.cloud_mask import simple_cloud_mask
from src.risk_indicators.indicator_builder import build_satellite_risk_indicators, SatelliteRiskIndicators
from src.sar_insar.deformation import deformation_features
from src.segmentation.model import UNet


@dataclass
class OpticalScenePair:
    """Stacked band arrays, each shape (H, W), for a pre/post scene pair."""
    blue_pre: np.ndarray
    green_pre: np.ndarray
    red_pre: np.ndarray
    nir_pre: np.ndarray
    swir1_pre: np.ndarray
    blue_post: np.ndarray
    green_post: np.ndarray
    red_post: np.ndarray
    nir_post: np.ndarray
    swir1_post: np.ndarray


@dataclass
class SarScenePair:
    """Complex SAR arrays (pre/post) for InSAR-style analysis, each shape (H, W)."""
    pre_complex: np.ndarray
    post_complex: np.ndarray


def run_satellite_pipeline(
    aoi_id: str,
    latitude: float,
    longitude: float,
    observation_date: date,
    optical: OpticalScenePair,
    sar: Optional[SarScenePair] = None,
    segmentation_model: Optional[UNet] = None,
    min_change_area_px: int = 25,
) -> SatelliteRiskIndicators:
    """
    Run the full satellite analysis pipeline for one AOI and return the
    standardized SatelliteRiskIndicators record.
    """
    # ---- 1. Cloud masking (optical) --------------------------------------
    cloud_mask = simple_cloud_mask(optical.blue_post, optical.nir_post)
    cloud_free_fraction = float(1.0 - np.mean(cloud_mask))

    # ---- 2. Spectral indices ---------------------------------------------
    ndvi_pre = ndvi(optical.nir_pre, optical.red_pre)
    ndvi_post = ndvi(optical.nir_post, optical.red_post)
    ndwi_pre = ndwi(optical.green_pre, optical.nir_pre)
    ndwi_post = ndwi(optical.green_post, optical.nir_post)

    veg_loss = vegetation_loss_fraction(ndvi_pre, ndvi_post)
    water_score = water_accumulation_score(ndwi_pre, ndwi_post)
    ndvi_delta_mean = float(np.mean(compute_index_delta(ndvi_pre, ndvi_post)))
    ndwi_delta_mean = float(np.mean(compute_index_delta(ndwi_pre, ndwi_post)))

    # ---- 3. Change detection (change-vector analysis) ---------------------
    deltas = [
        compute_index_delta(ndvi_pre, ndvi_post),
        compute_index_delta(ndwi_pre, ndwi_post),
    ]
    magnitude = change_vector_magnitude(deltas)
    mask = candidate_change_mask(magnitude)
    regions = extract_change_regions(mask, magnitude, min_area_px=min_change_area_px)
    change_score = overall_change_score(regions, image_area_px=magnitude.size)

    # ---- 4. Landslide segmentation (U-Net) --------------------------------
    landslide_cv_probability, cv_confidence = _run_segmentation(
        optical, ndvi_post, ndwi_post, segmentation_model
    )

    # ---- 5. SAR / InSAR deformation (optional) -----------------------------
    surface_displacement_mm = 0.0
    deformation_reliable_fraction = 0.0
    data_sources = ["sentinel-2"]
    road_disruption_score = _estimate_road_disruption(magnitude)

    if sar is not None:
        coherence = coherence_map(sar.pre_complex, sar.post_complex)
        deform = deformation_features(sar.pre_complex, sar.post_complex, coherence)
        surface_displacement_mm = deform.mean_displacement_mm
        deformation_reliable_fraction = deform.reliable_fraction
        data_sources.append("sentinel-1")
        # SAR coherence loss also reinforces the optical change score
        sar_change = coherence_loss_score(coherence)
        change_score = float(np.clip(0.7 * change_score + 0.3 * sar_change, 0.0, 1.0))

    # ---- 6. Fuse into the standardized output record -----------------------
    return build_satellite_risk_indicators(
        aoi_id=aoi_id,
        latitude=latitude,
        longitude=longitude,
        observation_date=observation_date,
        change_score=change_score,
        landslide_cv_probability=landslide_cv_probability,
        vegetation_loss=veg_loss,
        ndvi_delta=ndvi_delta_mean,
        ndwi_delta=ndwi_delta_mean,
        surface_displacement_mm=surface_displacement_mm,
        water_accumulation_score=water_score,
        road_disruption_score=road_disruption_score,
        cv_confidence=cv_confidence,
        deformation_reliable_fraction=deformation_reliable_fraction,
        cloud_free_fraction=cloud_free_fraction,
        data_sources=data_sources,
    )


def _run_segmentation(
    optical: OpticalScenePair,
    ndvi_post: np.ndarray,
    ndwi_post: np.ndarray,
    model: Optional[UNet],
) -> tuple[float, float]:
    """Stack bands+indices, run the U-Net, return (mean_probability, confidence)."""
    if model is None:
        return 0.0, 0.0

    stacked = np.stack(
        [optical.red_post, optical.green_post, optical.blue_post, optical.nir_post, ndvi_post, ndwi_post],
        axis=0,
    ).astype(np.float32)
    tensor = torch.from_numpy(stacked).unsqueeze(0)  # (1, C, H, W)

    with torch.no_grad():
        logits = model(tensor)
        probs = torch.sigmoid(logits)

    mean_prob = float(probs.mean().item())
    # Confidence proxy: how far the mean probability is from the uncertain
    # midpoint (0.5) — a model that is decisively low or high is more
    # trustworthy than one hovering at 0.5 everywhere.
    confidence = float(abs(mean_prob - 0.5) * 2.0)
    return mean_prob, confidence


def _estimate_road_disruption(change_magnitude: np.ndarray, linear_structure_bonus: float = 0.0) -> float:
    """
    Lightweight heuristic placeholder for road/debris disruption scoring:
    high localized change magnitude near known road vector layers (not
    modeled here) would indicate blockage. For the MVP this returns a
    conservative score derived from overall change intensity; the
    recommended upgrade path is intersecting `regions` with an OSM road
    vector layer to flag roads crossing a change polygon directly.
    """
    return float(np.clip(np.mean(change_magnitude > np.percentile(change_magnitude, 95)) * 3.0, 0.0, 1.0))
