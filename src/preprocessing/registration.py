"""
Image Registration stage.

Aligns a "post" image to a "pre" image so that per-pixel change detection is
valid. Uses phase-correlation (FFT-based) sub-pixel shift estimation, which
is fast, dependency-light (numpy/scipy only) and robust for the near-nadir,
already-orthorectified Sentinel-2/Sentinel-1 products used here.

Input:  two single-band numpy arrays of the same nominal footprint
Output: the post image shifted to align with the pre image + the (dy, dx) shift
"""
from __future__ import annotations

from typing import Tuple

import numpy as np
from scipy.fft import fft2, ifft2
from scipy.ndimage import shift as nd_shift


def phase_correlation_shift(reference: np.ndarray, target: np.ndarray) -> Tuple[float, float]:
    """
    Estimate the (dy, dx) pixel shift that best aligns `target` onto
    `reference` using FFT-based phase correlation.
    """
    f_ref = fft2(reference)
    f_tgt = fft2(target)
    cross_power = (f_ref * f_tgt.conj()) / (np.abs(f_ref * f_tgt.conj()) + 1e-12)
    correlation = np.abs(ifft2(cross_power))
    peak = np.unravel_index(np.argmax(correlation), correlation.shape)

    dy, dx = peak
    # Wrap shifts > half the image size to represent negative offsets
    if dy > reference.shape[0] // 2:
        dy -= reference.shape[0]
    if dx > reference.shape[1] // 2:
        dx -= reference.shape[1]
    return float(dy), float(dx)


def register_image(reference: np.ndarray, target: np.ndarray) -> Tuple[np.ndarray, Tuple[float, float]]:
    """
    Co-register `target` onto `reference`. Returns the aligned image and the
    shift that was applied, so the same shift can be re-used across all bands
    of a multi-band scene (apply once on a luminance/band-8 proxy, reuse
    everywhere else for speed).
    """
    dy, dx = phase_correlation_shift(reference, target)
    aligned = nd_shift(target, shift=(dy, dx), order=1, mode="nearest")
    return aligned, (dy, dx)


def register_stack(reference: np.ndarray, target_bands: list[np.ndarray]) -> list[np.ndarray]:
    """
    Register a list of target bands to a single reference band, computing the
    shift once (on the first band) and applying it to all bands for consistency
    and speed.
    """
    if not target_bands:
        return []
    _, shift_vec = register_image(reference, target_bands[0])
    return [nd_shift(band, shift=shift_vec, order=1, mode="nearest") for band in target_bands]
