"""
SAR/InSAR Deformation Analysis stage.

Pipeline:
    SAR image (pre, post)
      -> co-registration            (src.preprocessing.registration)
      -> interferogram              (complex conjugate product)
      -> phase difference           (wrapped phase, radians)
      -> displacement estimation    (phase -> line-of-sight displacement, mm)
      -> deformation indicator      (AOI-level summary score)

IMPORTANT — honesty about scope: production InSAR requires precise orbital
data, atmospheric correction, phase unwrapping (e.g. SNAPHU) and typically
ESA SNAP or GAMMA. That full chain is out of scope for a hackathon timeline.
This module implements a clearly-labeled SIMPLIFIED proxy that:
  - demonstrates the correct end-to-end signal flow and output contract
  - can be point-in-place-upgraded to a real SNAP backend later without any
    change to `deformation_features()`'s output schema

Limitations (surfaced explicitly in the output so the risk engine and any
human reviewer can weight this signal appropriately):
  - Decorrelation: dense vegetation and steep, rapidly-changing terrain
    (both common in NER) decorrelate the radar phase quickly, especially
    over 6/12-day+ revisit gaps — coherence must be checked before trusting
    a displacement estimate.
  - Atmospheric effects: water vapor differences between the two passes
    introduce phase delay unrelated to ground motion; not corrected in this
    simplified version.
  - Terrain geometry: layover/foreshortening on steep NER slopes can distort
    or invalidate phase measurements in the affected pixels.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class DeformationResult:
    mean_displacement_mm: float
    max_displacement_mm: float
    coherence_mean: float
    reliable_fraction: float  # fraction of pixels above coherence threshold
    limitations: list


def wrapped_phase_difference(pre_complex: np.ndarray, post_complex: np.ndarray) -> np.ndarray:
    """Interferometric phase difference (wrapped, radians in [-pi, pi])."""
    interferogram = pre_complex * np.conj(post_complex)
    return np.angle(interferogram)


def unwrap_phase_simple(wrapped_phase: np.ndarray) -> np.ndarray:
    """
    Simplified 2D phase unwrapping via numpy's 1D unwrap applied row-then-
    column-wise. This is a lightweight stand-in for a true minimum-cost-flow
    unwrapper (e.g. SNAPHU) — adequate for smooth, low-gradient hackathon
    demo scenes, but should be replaced with SNAPHU for production accuracy
    on complex, layover-affected NER terrain.
    """
    unwrapped = np.unwrap(wrapped_phase, axis=0)
    unwrapped = np.unwrap(unwrapped, axis=1)
    return unwrapped


def phase_to_displacement_mm(unwrapped_phase: np.ndarray, wavelength_mm: float = 55.6) -> np.ndarray:
    """
    Convert unwrapped phase to line-of-sight displacement in millimetres.
    displacement = (wavelength / 4*pi) * phase   [standard InSAR relation]
    Sentinel-1 C-band wavelength ≈ 55.6 mm.
    """
    return (wavelength_mm / (4.0 * np.pi)) * unwrapped_phase


def deformation_features(
    pre_complex: np.ndarray,
    post_complex: np.ndarray,
    coherence: np.ndarray,
    coherence_threshold: float = 0.3,
    wavelength_mm: float = 55.6,
) -> DeformationResult:
    """
    Full simplified InSAR chain producing AOI-level deformation summary
    features for the central AI Risk Engine (`surface_displacement_mm`).
    """
    wrapped = wrapped_phase_difference(pre_complex, post_complex)
    unwrapped = unwrap_phase_simple(wrapped)
    displacement_mm = phase_to_displacement_mm(unwrapped, wavelength_mm)

    reliable_mask = coherence >= coherence_threshold
    reliable_fraction = float(np.mean(reliable_mask)) if coherence.size else 0.0

    if reliable_fraction > 0:
        reliable_disp = displacement_mm[reliable_mask]
        mean_disp = float(np.mean(np.abs(reliable_disp)))
        max_disp = float(np.max(np.abs(reliable_disp)))
    else:
        mean_disp, max_disp = 0.0, 0.0

    limitations = []
    if reliable_fraction < 0.5:
        limitations.append(
            f"Low coherence over {100 * (1 - reliable_fraction):.0f}% of AOI — "
            "likely vegetation/terrain decorrelation; displacement estimate is low-confidence."
        )
    limitations.append("Atmospheric phase delay not corrected in this simplified pipeline.")
    limitations.append("Steep-slope layover/foreshortening may distort phase in affected pixels.")

    return DeformationResult(
        mean_displacement_mm=mean_disp,
        max_displacement_mm=max_disp,
        coherence_mean=float(np.mean(coherence)) if coherence.size else 0.0,
        reliable_fraction=reliable_fraction,
        limitations=limitations,
    )
